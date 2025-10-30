import 'package:flutter/material.dart';
import 'package:shared_core/shared_core.dart';

const CoreErrorPresenter _coreErrorPresenter = CoreErrorPresenter();

void presentError(
  BuildContext context,
  Object error, {
  String? message,
  ErrorPresentationSeverity severity = ErrorPresentationSeverity.error,
}) {
  if (error is CoreError) {
    _coreErrorPresenter.show(
      error,
      context: context,
      overridePresentation: message == null
          ? null
          : ErrorPresentation(message: message, severity: severity),
    );
    return;
  }
  final fallback = message ?? error.toString();
  _coreErrorPresenter.show(
    CoreError(
      kind: CoreErrorKind.unknown,
      message: fallback,
      cause: error,
    ),
    context: context,
    overridePresentation: ErrorPresentation(message: fallback, severity: severity),
  );
}
