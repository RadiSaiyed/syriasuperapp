#!/usr/bin/env python3
import os
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLIENTS_DIR = ROOT / "clients"

APPS = {
    "carmarket": {"dir": CLIENTS_DIR / "carmarket_flutter", "port": 9001},
    "bus":        {"dir": CLIENTS_DIR / "bus_flutter",        "port": 9002},
    "chat":       {"dir": CLIENTS_DIR / "chat_flutter",       "port": 9003},
    "commerce":   {"dir": CLIENTS_DIR / "commerce_flutter",   "port": 9004},
    "doctors":    {"dir": CLIENTS_DIR / "doctors_flutter",    "port": 9005},
    "food":       {"dir": CLIENTS_DIR / "food_flutter",       "port": 9006},
    "freight":    {"dir": CLIENTS_DIR / "freight_flutter",    "port": 9007},
    "jobs":       {"dir": CLIENTS_DIR / "jobs_flutter",       "port": 9008},
    "patient":    {"dir": CLIENTS_DIR / "patient_flutter",    "port": 9009},
    "payments":   {"dir": CLIENTS_DIR / "payments_flutter",   "port": 9010},
    "stays":      {"dir": CLIENTS_DIR / "stays_flutter",      "port": 9011},
    "taxi":       {"dir": CLIENTS_DIR / "taxi_flutter",       "port": 9012},
    "utilities":  {"dir": CLIENTS_DIR / "utilities_flutter",  "port": 9013},
}

PROCS = {}  # app -> subprocess.Popen
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def is_running(app: str) -> bool:
    p = PROCS.get(app)
    return p is not None and (p.poll() is None)


def start_app(app: str) -> str:
    if app not in APPS:
        return f"unknown app: {app}"
    if is_running(app):
        return "already running"
    info = APPS[app]
    app_dir = info["dir"]
    port = info["port"]
    if not app_dir.exists():
        return f"missing dir: {app_dir}"
    # Ensure deps
    try:
        subprocess.run(["flutter", "pub", "get"], cwd=str(app_dir), check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return f"flutter pub get failed: {e.stdout.decode(errors='ignore')[-400:]}"
    # Launch flutter run -d chrome
    log_path = LOG_DIR / f"{app}.log"
    log_f = open(log_path, "ab", buffering=0)
    env = os.environ.copy()
    # Hint Chrome if installed via Homebrew cask
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome_path):
        env.setdefault("CHROME_EXECUTABLE", chrome_path)
    cmd = [
        "flutter", "run", "-d", "chrome",
        "--web-port", str(port),
        "--web-hostname", "localhost",
    ]
    # Spawn in its own process group so we can terminate cleanly
    p = subprocess.Popen(cmd, cwd=str(app_dir), stdout=log_f, stderr=subprocess.STDOUT, preexec_fn=os.setsid, env=env)
    PROCS[app] = p
    return "started"


def stop_app(app: str) -> str:
    p = PROCS.get(app)
    if not p:
        return "not running"
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass
    PROCS.pop(app, None)
    return "stopped"


def home_page() -> bytes:
    has_flutter = shutil_which("flutter") is not None
    rows = []
    for app, info in APPS.items():
        running = is_running(app)
        port = info["port"]
        dir_rel = str(info["dir"].relative_to(ROOT))
        open_link = f"http://localhost:{port}"
        btns = []
        if running:
            btns.append(f"<a class=btn href='{open_link}' target=_blank>Open</a>")
            btns.append(f"<a class=btn data-act href='/stop?app={app}'>Stop</a>")
        else:
            btns.append(f"<a class=btn data-act href='/start?app={app}'>Start</a>")
        rows.append(f"""
        <tr>
          <td>{html_escape(app)}</td>
          <td><code>{html_escape(dir_rel)}</code></td>
          <td>{port}</td>
          <td>{'Running' if running else 'Stopped'}</td>
          <td>{' '.join(btns)}</td>
        </tr>
        """)
    rows_html = "\n".join(rows)
    warn = "" if has_flutter else "<p class=warn>Flutter not found in PATH. Install via: brew install --cask flutter</p>"
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Superapp UI Launcher</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1200px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; }}
    th {{ background: #f7f7f7; text-align: left; }}
    .btn {{ display: inline-block; padding: 6px 10px; background: #1e88e5; color: white; text-decoration: none; border-radius: 4px; margin-right: 6px; }}
    .btn[data-act] {{ background: #455a64; }}
    .warn {{ color: #c62828; }}
    code {{ background: #f1f1f1; padding: 2px 4px; border-radius: 3px; }}
  </style>
  <script>
  document.addEventListener('click', async (e) => {{
    const a = e.target.closest('a[data-act]');
    if (!a) return;
    e.preventDefault();
    try {{ await fetch(a.href, {{ method: 'POST' }}); }} catch (err) {{ console.error(err); }}
    setTimeout(() => location.reload(), 600);
  }});
  </script>
</head>
<body>
  <h1>Superapp UI Launcher</h1>
  {warn}
  <table>
    <tr><th>App</th><th>Path</th><th>Web Port</th><th>Status</th><th>Actions</th></tr>
    {rows_html}
  </table>
  <p>Logs: <code>{html_escape(str(LOG_DIR))}</code></p>
</body>
</html>
"""
    return html.encode("utf-8")


def shutil_which(cmd: str):
    from shutil import which
    return which(cmd)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # type: ignore
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = home_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        elif parsed.path == "/start":
            qs = parse_qs(parsed.query)
            app = (qs.get("app") or [""])[0]
            msg = start_app(app)
            self._redirect_with_msg(msg)
            return
        elif parsed.path == "/stop":
            qs = parse_qs(parsed.query)
            app = (qs.get("app") or [""])[0]
            msg = stop_app(app)
            self._redirect_with_msg(msg)
            return
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):  # type: ignore
        # Allow JS to POST to /start and /stop
        parsed = urlparse(self.path)
        if parsed.path in ("/start", "/stop"):
            # rewrite to GET handler for simplicity
            return self.do_GET()
        self.send_error(405, "Method Not Allowed")

    def log_message(self, fmt, *args):  # silence server logs
        pass

    def _redirect_with_msg(self, msg: str):
        # simple redirect back to home
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("X-Result", msg)
        self.end_headers()


def main():
    host = os.environ.get("PORTAL_HOST", "127.0.0.1")
    port = int(os.environ.get("PORTAL_PORT", "5050"))
    httpd = HTTPServer((host, port), Handler)
    print(f"[portal] UI launcher at http://{host}:{port}")
    print("[portal] Tip: open in browser and click Start next to an app.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
