# shared_core

Shared core utilities for Syria Super-App Flutter clients. Provides:

- Resilient HTTP client with auth header injection, exponential backoff with jitter, request idempotency keys, and offline detection.
- Unified error taxonomy (`CoreError`) plus `CoreErrorPresenter` for consistent MessageHost banner/toast mapping.
- Secure token storage via `SecureTokenStore` (uses platform keychain/keystore, shared_preferences fallback on web).
- App configuration primitives: dart-define environment parsing, remote JSON config loader, lightweight feature flag accessor.
- Observability helpers: Sentry bootstrap (`CrashReporter`/`runWithCrashReporting`) and global error handler wiring.
- Connectivity service abstraction for offline/online awareness.

## Usage

Add the path dependency to your client app `pubspec.yaml`:

```yaml
dependencies:
  shared_core:
    path: ../shared_core
```

Typical bootstrap in `main.dart`:

```dart
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final reporter = CrashReporter(
    dsn: const String.fromEnvironment('SENTRY_DSN', defaultValue: ''),
    environment: const String.fromEnvironment('APP_ENV', defaultValue: 'dev'),
    release: const String.fromEnvironment('APP_RELEASE', defaultValue: ''),
  );
  final errorHandler = GlobalErrorHandler(crashReporter: reporter);
  await runWithCrashReporting(
    reporter: reporter,
    appRunner: () async {
      errorHandler.install();
      runApp(const MyApp());
    },
  );
}
```

Instantiate the HTTP client from your feature API layer:

```dart
final client = SharedHttpClient(
  service: 'taxi',
  baseUrl: baseUrl,
  tokenProvider: (_) => tokenStore.getToken(),
  connectivity: ConnectivityService(),
);
final quote = await client.postJson('/rides/quote', body: {...});
```

Use `CoreErrorPresenter` in UI catch blocks:

```dart
try {
  await api.requestRide(...);
} catch (e) {
  presentError(context, e); // wraps CoreErrorPresenter
}
```

## Configuration & dart-defines

| Define | Description | Example |
| --- | --- | --- |
| `APP_ENV` | `dev`/`staging`/`prod` environment flag. | `--dart-define=APP_ENV=staging` |
| `APP_RELEASE` | Release identifier propagated to Sentry. | `--dart-define=APP_RELEASE=taxi_flutter@0.2.0+7` |
| `SENTRY_DSN` | Optional Sentry DSN. Leave empty to disable crash reporting. | `--dart-define=SENTRY_DSN=https://...` |
| `APP_CONFIG_URL` | Optional remote JSON config endpoint consumed by `AppConfigLoader`. | `--dart-define=APP_CONFIG_URL=https://config.dev/app.json` |

`SecureTokenStore` prefixes keys with `sc_jwt_`. On web, tokens are stored via `SharedPreferences`; native platforms use secure storage backends.

## Feature flags & remote config

```dart
final config = AppConfig.fromEnvironment();
final loader = AppConfigLoader(baseConfig: config);
await loader.ensureLoaded();
final flags = FeatureFlagProvider(loader: loader).current;
if (flags.isEnabled('new_checkout')) {
  // toggle UI
}
```

## Migration notes

- Replace legacy per-app HTTP helpers with `SharedHttpClient`. See `clients/taxi_flutter/lib/api.dart` for a reference implementation.
- Use `CrashReporter`/`GlobalErrorHandler` to replace ad hoc `runZonedGuarded` wiring.
- Replace direct `SharedPreferences` token usage with `SecureTokenStore` for OAuth/JWT persistence.
- Subscribe to `ConnectivityService` in view models if you need online/offline banners or retry orchestration.

## Pending follow-ups

- Expand `SecureTokenStore` with optional obfuscation for additional secrecy on rooted devices.
- Add offline queue primitives for POST operations.
- Provide SharedMessages entries in additional locales.
