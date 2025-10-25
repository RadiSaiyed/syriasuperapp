Release Build Hardening (Android/iOS)

Android
- R8/Proguard: aktiviert (minify + shrinkResources) in android/app/build.gradle.kts
- Proguard-Regeln: android/app/proguard-rules.pro
- Empfohlener Build:
  flutter build appbundle --release \
    --obfuscate --split-debug-info=build/symbols/payments \
    --dart-define=ENFORCE_TLS=true \
    --dart-define=AUDIT_ENABLED=true

iOS
- Bitcode nicht nötig.
- Empfohlener Build: Xcode Release + "Strip Swift Symbols" aktiviert.
- Dart Obfuscation ebenfalls möglich (wirkt nur auf Dart):
  flutter build ipa --release \
    --obfuscate --split-debug-info=build/symbols/payments \
    --dart-define=ENFORCE_TLS=true \
    --dart-define=AUDIT_ENABLED=true

Symbols
- Die Debug‑Infos aus --split-debug-info sichern (nicht ins Repo einchecken), für Crash‑Symbolication.

