from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
import os
import httpx
from typing import List, Dict, Any
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets


class SummaryOut(BaseModel):
    by_service_rps: dict[str, float]
    error_rate_percent: float
    payments: dict[str, float]


def _prom() -> str:
    return os.getenv("PROMETHEUS_BASE_URL", "http://localhost:9090")


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
    html = """
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
    <script>
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

