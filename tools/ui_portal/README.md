Superapp UI Launcher
====================

Local web UI to start/stop individual Flutter clients (web, Chrome) so you don’t have to run them all at once.

Usage
- Ensure Flutter + Chrome are installed (`brew install --cask flutter google-chrome`).
- Start the portal:
  - `python3 tools/ui_portal/portal.py`
  - It prints: `UI launcher at http://127.0.0.1:5050`
- Open the URL and click “Start” next to an app. Click “Open” to view it.
- Use “Stop” to stop a running app. Logs are in `tools/ui_portal/logs/`.

Ports
- Each client uses a fixed web port: 9001..9013 by default.
- You can change mappings in `tools/ui_portal/portal.py`.

Notes
- The portal runs `flutter pub get` for the app before launching.
- If Chrome was installed via Homebrew or is in `/Applications`, it is auto-detected; otherwise set `CHROME_EXECUTABLE` in your shell.

