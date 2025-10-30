import 'dart:async';

import 'package:flutter/widgets.dart';

import '../errors/core_error.dart';
import '../errors/error_presenter.dart';
import 'crash_reporter.dart';

/// Installs a global error boundary that forwards uncaught errors to Sentry and
/// shows a user-facing banner via [CoreErrorPresenter].
class GlobalErrorHandler {
  GlobalErrorHandler({
    CrashReporter? crashReporter,
    CoreErrorPresenter? presenter,
  })  : _crashReporter = crashReporter,
        _presenter = presenter ?? const CoreErrorPresenter();

  final CrashReporter? _crashReporter;
  final CoreErrorPresenter _presenter;

  void install() {
    final previous = FlutterError.onError;
    FlutterError.onError = (details) {
      previous?.call(details);
      _handle(details.exception, details.stack);
    };
    WidgetsBinding.instance.platformDispatcher.onError = (error, stack) {
      _handle(error, stack);
      return false;
    };
  }

  void handle(Object error, [StackTrace? stackTrace]) => _handle(error, stackTrace);

  void _handle(Object error, StackTrace? stackTrace) {
    final coreError = error is CoreError
        ? error
        : CoreError(kind: CoreErrorKind.unknown, message: '$error', cause: error, stackTrace: stackTrace);
    _presenter.show(coreError);
    final reporter = _crashReporter;
    if (reporter != null) {
      unawaited(reporter.captureException(error, stackTrace: stackTrace));
    }
  }
}
