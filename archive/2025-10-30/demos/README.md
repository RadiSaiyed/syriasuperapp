AI Gateway UI Demo

Start
- Öffne `demos/ai_gateway_ui/index.html` im Browser.
- Setze ggf. `Gateway URL` (Standard: `http://localhost:8099`).
- Optional: Trage `User JWT` und `User ID` ein, um Tools auszuführen.

Funktionen
- Assistant: schickt `/v1/chat`, zeigt Antwort und vorgeschlagene `tool_calls` an.
- Bestätigung & Ausführung: Button bei Vorschlägen löst `/v1/chat` mit `confirm`+`selected_tool` aus.
- SuperSearch: ruft `/v1/store/search` auf.
- OCR: ruft `/v1/ocr` (MVP: `text_hint`) auf.

Hinweis
- In DEV erlaubt der Gateway CORS (`*`), so dass Aufrufe vom `file://`‑Kontext funktionieren sollten.
- Für PROD `ALLOWED_ORIGINS` auf konkrete Domains setzen.
