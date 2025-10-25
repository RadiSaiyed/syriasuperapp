Dark Mode Color Palette (Super‑App)

Base
- Background: #0A0A0A (deep black)
- Surface: #1A1A1A (subtle dark gray)
- Surface Variant: #121212 (inputs, chips)
- Outline: #2E2E2E (dividers, borders)

Typography
- Primary Text: #FFFFFF
- Secondary Text: #B3B3B3

Accents
- Primary (Neon Lime): #A4FF00 — primary CTAs, active icons, highlights
- Orange: #FF7A00 — commerce, utilities, real estate
- Electric Blue: #00BFFF — rides, travel, jobs, doctors
- Hot Pink: #FF3CAC — social, food, stays
- Bright Red: #FF4040 — errors, destructive actions

Design Intent
- Futuristic, vibrant, high‑contrast, slightly playful
- Use accent colors sparingly; keep large surfaces dark to preserve contrast
- Prefer Filled buttons (primary accent), Outlined buttons (accent border), and tonal variations for less prominent actions

Flutter Implementation
- Super‑App: `clients/superapp_flutter/lib/ui/palette.dart` → `buildSuperDarkTheme()`
- Freight: `clients/freight_flutter/lib/ui/palette.dart` → `buildFreightDarkTheme()`
- Suggested usage in other apps: add a `ui/palette.dart` with the same tokens and set `themeMode: ThemeMode.dark`, `darkTheme: build...DarkTheme()` in `MaterialApp`.

Category Mapping (suggested)
- Payments, Freight: Primary (#A4FF00)
- Commerce, Utilities, Real Estate, Car Market: Orange (#FF7A00)
- Taxi, Flights, Jobs, Doctors: Electric Blue (#00BFFF)
- Food, Stays, Chat: Hot Pink (#FF3CAC)

Accessibility Tips
- Maintain text contrast ratio ≥ 4.5:1 on surfaces (#1A1A1A) when not using pure white
- For disabled states, lower opacity to ~40% on text/icon colors
- Use focus outlines with the primary accent at 2 px for keyboard navigation

