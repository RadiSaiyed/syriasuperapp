import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:sentry_flutter/sentry_flutter.dart';

/// Wrapper around Sentry to enforce consistent configuration (PII safe logging,
/// release metadata, breadcrumbs).
class CrashReporter {
  CrashReporter({
    this.dsn,
    required this.environment,
    this.release,
    this.tracesSampleRate = 0.1,
  });

  final String? dsn;
  final String environment;
  final String? release;
  final double tracesSampleRate;

  bool _initialized = false;

  bool get isEnabled => _initialized;

  Future<void> init({FutureOr<void> Function()? appRunner}) async {
    if (dsn == null || dsn!.isEmpty) {
      if (appRunner != null) {
        await appRunner();
      }
      return;
    }
    await SentryFlutter.init(
      (options) {
        options.dsn = dsn;
        options.environment = environment;
        if (release != null && release!.isNotEmpty) {
          options.release = release;
        }
        options.tracesSampleRate = tracesSampleRate.clamp(0, 1);
        options.sendDefaultPii = false;
        options.enableAutoSessionTracking = true;
        options.reportPackages = false;
      },
      appRunner: () async {
        _initialized = true;
        if (appRunner != null) {
          await appRunner();
        }
      },
    );
  }

  Future<void> captureException(Object error, {StackTrace? stackTrace, Map<String, dynamic>? extras}) async {
    if (!_initialized) return;
    await Sentry.captureException(error, stackTrace: stackTrace, withScope: (scope) {
      extras?.forEach((key, value) {
        scope.setTag('extra_$key', '$value');
      });
    });
  }

  Future<void> captureMessage(String message, {SentryLevel level = SentryLevel.info}) async {
    if (!_initialized) return;
    await Sentry.captureMessage(message, level: level);
  }

  Future<void> setUserContext({String? id, String? username, String? segment}) async {
    if (!_initialized) return;
    await Sentry.configureScope((scope) {
      scope.setUser(id == null ? null : SentryUser(id: id, username: username, segment: segment));
    });
  }

  Future<void> clearUser() async {
    if (!_initialized) return;
    await Sentry.configureScope((scope) {
      scope.setUser(null);
    });
  }

  Future<void> setTag(String key, String value) async {
    if (!_initialized) return;
    await Sentry.configureScope((scope) {
      scope.setTag(key, value);
    });
  }

  Future<void> addBreadcrumb(String message, {String? category, SentryLevel level = SentryLevel.info}) async {
    if (!_initialized) return;
    await Sentry.addBreadcrumb(
      Breadcrumb(
        message: message,
        category: category,
        level: level,
      ),
    );
  }

  Future<void> close() async {
    if (!_initialized) return;
    await Sentry.close();
    _initialized = false;
  }
}

/// Convenience bootstrapper to run guarded zones with crash reporting +
/// Flutter error wiring.
Future<void> runWithCrashReporting({
  required FutureOr<void> Function() appRunner,
  required CrashReporter reporter,
}) async {
  // Initialize Sentry and run the app entirely within a single zone where
  // Flutter bindings are first created, to avoid zone mismatch warnings.
  await reporter.init(appRunner: () async {
    await runZonedGuarded(() async {
      // Ensure bindings and error hooks are set within the same zone as runApp.
      WidgetsFlutterBinding.ensureInitialized();
      FlutterError.onError = (details) {
        FlutterError.presentError(details);
        unawaited(reporter.captureException(details.exception, stackTrace: details.stack));
      };
      WidgetsBinding.instance.platformDispatcher.onError = (error, stack) {
        unawaited(reporter.captureException(error, stackTrace: stack));
        return false;
      };
      await appRunner();
    }, (error, stackTrace) {
      unawaited(reporter.captureException(error, stackTrace: stackTrace));
    });
  });
}
