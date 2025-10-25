import os
import threading
import time
import webview
import requests


def _start_server():
    import uvicorn
    from apps.ops_admin.app.main import app  # ensure importable
    config = uvicorn.Config(app, host="127.0.0.1", port=8099, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def main():
    # Set defaults for desktop run
    os.environ.setdefault("PROMETHEUS_BASE_URL", "http://localhost:9090")
    os.environ.setdefault("OPS_ADMIN_BASIC_USER", "admin")
    os.environ.setdefault("OPS_ADMIN_BASIC_PASS", "admin")

    # Start API server in background thread
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()

    # Wait for health
    url = "http://127.0.0.1:8099/health"
    for _ in range(60):
        try:
            r = requests.get(url, timeout=0.5)
            if r.ok:
                break
        except Exception:
            pass
        time.sleep(0.2)

    # Launch desktop window
    # Note: Basic auth is enabled; the webview may prompt for credentials (admin/admin).
    webview.create_window("Ops Admin", "http://127.0.0.1:8099", width=1100, height=800)
    webview.start()


if __name__ == "__main__":
    main()

