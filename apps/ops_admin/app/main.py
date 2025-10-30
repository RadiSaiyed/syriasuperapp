from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
import os
import httpx
from typing import List, Dict, Any
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import hmac
import hashlib
import time
from urllib.parse import parse_qs


class SummaryOut(BaseModel):
    by_service_rps: dict[str, float]
    error_rate_percent: float
    payments: dict[str, float]


def _prom() -> str:
    return os.getenv("PROMETHEUS_BASE_URL", "http://localhost:9090")


def _bff() -> str:
    return os.getenv("BFF_BASE_URL", "http://localhost:8070")


async def prom_query(expr: str) -> float | dict:
    url = f"{_prom()}/api/v1/query"
    async with httpx.AsyncClient(timeout=3.0) as client:
        r = await client.get(url, params={"query": expr})
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            raise RuntimeError("prom query failed")
        res = data["data"]["result"]
        if not res:
            return 0.0
        # If vector with labels (e.g., by job), return dict
        if isinstance(res, list) and "metric" in res[0] and "value" in res[0]:
            if "job" in res[0]["metric"]:
                out: dict[str, float] = {}
                for it in res:
                    job = it["metric"].get("job", "")
                    try:
                        out[job] = float(it["value"][1])
                    except Exception:
                        out[job] = 0.0
                return out
        try:
            return float(res[0]["value"][1])
        except Exception:
            return 0.0


app = FastAPI(title="Ops Admin", version="0.1.0")
security = HTTPBasic()


def require_basic(credentials: HTTPBasicCredentials = Depends(security)):
    user = os.getenv("OPS_ADMIN_BASIC_USER", "")
    pwd = os.getenv("OPS_ADMIN_BASIC_PASS", "")
    if not user and not pwd:
        return True
    if secrets.compare_digest(credentials.username or "", user) and secrets.compare_digest(credentials.password or "", pwd):
        return True
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/summary", response_model=SummaryOut)
async def summary(_: bool = Depends(require_basic)):
    try:
        by_job = await prom_query('sum(rate(http_requests_total[5m])) by (job)')
        err = await prom_query('100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))')
        qr = await prom_query('sum(rate(payments_qr_total[5m]))')
        tr_p2p = await prom_query('sum(rate(payments_transfers_total{kind="p2p"}[5m]))')
        tr_topup = await prom_query('sum(rate(payments_transfers_total{kind="topup"}[5m]))')
        fees_1h = await prom_query('sum(increase(payments_merchant_fees_cents[1h]))')
        return SummaryOut(
            by_service_rps=by_job if isinstance(by_job, dict) else {},
            error_rate_percent=float(err) if isinstance(err, (float, int)) else 0.0,
            payments={
                "qr_rate": float(qr) if isinstance(qr, (float, int)) else 0.0,
                "p2p_rate": float(tr_p2p) if isinstance(tr_p2p, (float, int)) else 0.0,
                "topup_rate": float(tr_topup) if isinstance(tr_topup, (float, int)) else 0.0,
                "fees_1h_cents": float(fees_1h) if isinstance(fees_1h, (float, int)) else 0.0,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Prometheus error: {e}")


@app.get("/")
async def index(_: bool = Depends(require_basic)):
    # Simple HTML dashboard
    html = f"""
    <!DOCTYPE html>
    <html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>Ops Admin</title>
    <style>body{font-family:system-ui,Arial;margin:16px} .row{display:flex;gap:12px;flex-wrap:wrap}
    .card{border:1px solid #ddd;border-radius:8px;padding:12px;min-width:240px} h3{margin:.2rem 0}
    table{border-collapse:collapse} td,th{padding:4px 8px;border-bottom:1px solid #eee}
    .ok{color:#0a0} .warn{color:#c90} .crit{color:#c00}
    </style></head><body>
    <h2>Ops Admin</h2>
    <div class='row'>
      <div class='card'><h3>Error Rate (5m)</h3><div id='err'>…</div></div>
      <div class='card'><h3>Payments (rate)</h3><div id='pays'>…</div></div>
    </div>
    <div class='card' style='margin-top:12px'>
      <h3>RPS by Service (5m)</h3>
      <table id='rps'><thead><tr><th>Service</th><th>RPS</th></tr></thead><tbody></tbody></table>
    </div>
    <div class='card' style='margin-top:12px'>
      <h3>Recent Alerts</h3>
      <table id='alerts'><thead><tr><th>Severity</th><th>Alert</th><th>Job</th><th>Since</th></tr></thead><tbody></tbody></table>
    </div>
    <div class='card' style='margin-top:12px'>
      <h3>Push Broadcast (Dev)</h3>
      <div style='display:flex;gap:8px;flex-wrap:wrap'>
        <input id='bff' placeholder='BFF Base' style='min-width:260px'>
        <input id='tok' placeholder='Bearer Token' style='min-width:320px'>
        <button onclick='saveAuth()'>Save</button>
      </div>
      <div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:8px'>
        <input id='title' placeholder='Title'>
        <input id='body' placeholder='Body' style='min-width:240px'>
        <input id='deeplink' placeholder='superapp://... ' style='min-width:260px'>
      </div>
      <div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:8px'>
        <input id='topic' placeholder='Topic (e.g., offers)'>
        <button onclick='sendToMe()'>Send to me</button>
        <button onclick='broadcastTopic()'>Broadcast topic</button>
        <button onclick='listTopics()'>My topics</button>
        <button onclick='subscribe()'>Subscribe</button>
        <button onclick='unsubscribe()'>Unsubscribe</button>
      </div>
      <pre id='pushlog' style='white-space:pre-wrap;margin-top:8px'></pre>
    </div>
    <script>
    const BFF = '{_bff()}';
    function _headers(){ const t=localStorage.getItem('bff_token')||''; return { 'Authorization': 'Bearer '+t, 'Content-Type':'application/json' }; }
    function saveAuth(){ localStorage.setItem('bff_token', document.getElementById('tok').value.trim()); localStorage.setItem('bff_base', document.getElementById('bff').value.trim()); log('Saved auth'); }
    function base(){ return (document.getElementById('bff').value||localStorage.getItem('bff_base')||BFF).trim(); }
    function log(msg){ const el=document.getElementById('pushlog'); el.textContent = (new Date()).toISOString()+"\n"+msg; }
    async function sendToMe(){ try{ const res = await fetch(base()+'/v1/push/dev/send', {method:'POST', headers:_headers(), body: JSON.stringify({title: val('title'), body: val('body'), deeplink: val('deeplink')})}); log(await res.text()); } catch(e){ log(e); } }
    async function broadcastTopic(){ try{ const res = await fetch(base()+'/v1/push/dev/broadcast_topic', {method:'POST', headers:_headers(), body: JSON.stringify({topic: val('topic'), title: val('title'), body: val('body'), deeplink: val('deeplink')})}); log(await res.text()); } catch(e){ log(e); } }
    async function subscribe(){ try{ const res = await fetch(base()+'/v1/push/topic/subscribe', {method:'POST', headers:_headers(), body: JSON.stringify({topic: val('topic')})}); log(await res.text()); } catch(e){ log(e); } }
    async function unsubscribe(){ try{ const res = await fetch(base()+'/v1/push/topic/unsubscribe', {method:'POST', headers:_headers(), body: JSON.stringify({topic: val('topic')})}); log(await res.text()); } catch(e){ log(e); } }
    async function listTopics(){ try{ const res = await fetch(base()+'/v1/push/topic/list', {headers:_headers()}); log(await res.text()); } catch(e){ log(e); } }
    function val(id){ return document.getElementById(id).value.trim(); }
    async function load(){
      const s = await fetch('/summary').then(r=>r.json());
      const err = document.getElementById('err'); err.textContent = s.error_rate_percent.toFixed(3) + '%';
      err.className = s.error_rate_percent > 1 ? 'crit' : (s.error_rate_percent>0.3?'warn':'ok');
      const p = s.payments; document.getElementById('pays').textContent = `QR ${p.qr_rate.toFixed(2)}/s  P2P ${p.p2p_rate.toFixed(2)}/s  Topup ${p.topup_rate.toFixed(2)}/s`;
      const rps = document.querySelector('#rps tbody'); rps.innerHTML='';
      Object.entries(s.by_service_rps).sort().forEach(([k,v])=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${k}</td><td>${(+v).toFixed(2)}</td>`; rps.appendChild(tr); });
      const a = await fetch('/alerts').then(r=>r.json()); const tb = document.querySelector('#alerts tbody'); tb.innerHTML='';
      a.slice(0,20).forEach(x=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${x.labels.severity||''}</td><td>${x.labels.alertname||''}</td><td>${x.labels.job||''}</td><td>${x.startsAt||''}</td>`; tb.appendChild(tr); });
    }
    load(); setInterval(load, 5000);
      // Init auth fields
      document.getElementById('bff').value = localStorage.getItem('bff_base') || BFF;
      document.getElementById('tok').value = localStorage.getItem('bff_token') || '';
    }
    </script>
    </body></html>
    """
    return HTMLResponse(html)

# --- Alert intake (from Alertmanager) ---
_alerts: List[Dict[str, Any]] = []

@app.post("/alert")
async def alert_hook(request: Request):
    try:
        payload = await request.json()
        alerts = payload.get("alerts", [])
        for a in alerts:
            _alerts.append(a)
        # keep last 200
        del _alerts[:-200]
        return {"status": "ok", "received": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/alerts")
def list_alerts(_: bool = Depends(require_basic)):
    return list(reversed(_alerts))

# --- Slack ChatOps (Slash Commands) ---

def _slack_signing_secret() -> str:
    return os.getenv("SLACK_SIGNING_SECRET", "")


def _verify_slack(req: Request, body: bytes) -> bool:
    secret = _slack_signing_secret().encode()
    if not secret:
        return False
    ts = req.headers.get("X-Slack-Request-Timestamp", "")
    sig = req.headers.get("X-Slack-Signature", "")
    try:
        ts_int = int(ts)
    except Exception:
        return False
    if abs(time.time() - ts_int) > 60 * 5:
        return False
    base = f"v0:{ts}:{body.decode('utf-8', errors='ignore')}".encode()
    mac = hmac.new(secret, base, hashlib.sha256).hexdigest()
    expected = f"v0={mac}"
    return hmac.compare_digest(expected, sig or "")


async def _gh_dispatch_chatops(payload: Dict[str, Any]) -> None:
    token = os.getenv("CHATOPS_GH_TOKEN", "")
    repo = os.getenv("CHATOPS_GH_REPO", "")  # e.g. owner/repo
    if not token or not repo:
        return  # soft-fail: still reply to Slack locally
    url = f"https://api.github.com/repos/{repo}/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = {"event_type": "chatops", "client_payload": payload}
    async with httpx.AsyncClient(timeout=6.0) as client:
        r = await client.post(url, json=data, headers=headers)
        r.raise_for_status()


def _chatops_help() -> str:
    return (
        "• status — show error rate and RPS by service\n"
        "• alerts — last 5 alerts\n"
        "• restart <app> — restart service via GH ChatOps (requires self‑hosted runner)\n"
        "  apps: payments, taxi, food, freight, bus, commerce, doctors, automarket, utilities, stays, chat, jobs\n"
        "• restart stack <name> — restart preset group (core, food, commerce, taxi, doctors, bus, freight, utilities, automarket, chat, stays, jobs)\n"
    )


@app.post("/slack/command")
async def slack_command(request: Request):
    body = await request.body()
    if not _verify_slack(request, body):
        raise HTTPException(status_code=401, detail="invalid signature")
    form = parse_qs(body.decode("utf-8", errors="ignore"))
    text = (form.get("text") or [""])[0].strip()
    user = (form.get("user_name") or [""])[0]
    user_id = (form.get("user_id") or [""])[0]
    channel_id = (form.get("channel_id") or [""])[0]
    response_url = (form.get("response_url") or [""])[0]

    # Allowlist filters (optional)
    users_env = os.getenv("CHATOPS_ALLOWED_USERS", "").strip()
    chans_env = os.getenv("CHATOPS_ALLOWED_CHANNELS", "").strip()
    if users_env:
        allowed_users = {u.strip() for u in users_env.replace(";", ",").split(",") if u.strip()}
        if user not in allowed_users and user_id not in allowed_users:
            return {"response_type": "ephemeral", "text": "Not allowed for this user."}
    if chans_env:
        allowed_chans = {c.strip() for c in chans_env.replace(";", ",").split(",") if c.strip()}
        if channel_id not in allowed_chans:
            return {"response_type": "ephemeral", "text": "Not allowed in this channel."}

    if not text or text.lower() in {"help", "?"}:
        return {"response_type": "ephemeral", "text": f"Commands:\n{_chatops_help()}"}

    parts = text.split()
    cmd = parts[0].lower()

    if cmd == "status":
        try:
            by_job = await prom_query('sum(rate(http_requests_total[5m])) by (job)')
            err = await prom_query('100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))')
            lines = [f"Error rate: {float(err):.3f}%"]
            if isinstance(by_job, dict):
                for k, v in sorted(by_job.items()):
                    lines.append(f"{k}: {float(v):.2f} rps")
            return {"response_type": "ephemeral", "text": "\n".join(lines)}
        except Exception as e:
            return {"response_type": "ephemeral", "text": f"status failed: {e}"}

    if cmd == "alerts":
        items = list(reversed(_alerts))[:5]
        if not items:
            return {"response_type": "ephemeral", "text": "No recent alerts."}
        lines = ["Recent alerts:"]
        for a in items:
            lbl = a.get("labels", {})
            lines.append(f"- {lbl.get('severity','')}: {lbl.get('alertname','')} ({lbl.get('job','')})")
        return {"response_type": "ephemeral", "text": "\n".join(lines)}

    if cmd == "restart" and len(parts) >= 2:
        # Supports: restart <app>   or   restart stack <name>
        if parts[1].lower() == "stack" and len(parts) >= 3:
            app = f"stack:{parts[2].lower()}"
        else:
            app = parts[1].lower()
        payload = {"action": "deploy-restart", "app": app, "actor": user, "channel_id": channel_id, "response_url": response_url}
        try:
            await _gh_dispatch_chatops(payload)
            return {"response_type": "ephemeral", "text": f"Restart requested for {app}. I will update here when done."}
        except Exception as e:
            return {"response_type": "ephemeral", "text": f"Failed to submit restart for {app}: {e}"}

    return {"response_type": "ephemeral", "text": f"Unknown command.\n{_chatops_help()}"}
