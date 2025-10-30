import 'package:flutter/widgets.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/messages.dart';

import 'core_error.dart';

enum ErrorPresentationSeverity { info, warning, error }

typedef ErrorActionCallback = void Function();

class ErrorPresentation {
  const ErrorPresentation({
    required this.message,
    required this.severity,
    this.duration,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final ErrorPresentationSeverity severity;
  final Duration? duration;
  final String? actionLabel;
  final ErrorActionCallback? onAction;
}

/// Centralized helper to map [CoreError]s to localized banners using
/// [MessageHost].
class CoreErrorPresenter {
  const CoreErrorPresenter();

  void show(CoreError error, {BuildContext? context, ErrorPresentation? overridePresentation}) {
    final ctx = context ?? MessageHost.messengerKey.currentContext;
    if (ctx == null) return;
    final presentation = overridePresentation ?? buildPresentation(ctx, error);
    switch (presentation.severity) {
      case ErrorPresentationSeverity.info:
      case ErrorPresentationSeverity.warning:
        MessageHost.showInfoBanner(
          ctx,
          presentation.message,
          duration: presentation.duration ?? const Duration(seconds: 4),
          actionLabel: presentation.actionLabel,
          onAction: presentation.onAction,
        );
        break;
      case ErrorPresentationSeverity.error:
        MessageHost.showErrorBanner(
          ctx,
          presentation.message,
          duration: presentation.duration ?? const Duration(seconds: 6),
          actionLabel: presentation.actionLabel,
          onAction: presentation.onAction,
        );
        break;
    }
  }

  ErrorPresentation buildPresentation(BuildContext context, CoreError error) {
    switch (error.kind) {
      case CoreErrorKind.network:
        final queued = error.details != null && error.details!['queued'] == true;
        return ErrorPresentation(
          message: queued ? SharedMessages.offlineQueued(context) : SharedMessages.networkOffline(context),
          severity: ErrorPresentationSeverity.warning,
          duration: const Duration(seconds: 5),
        );
      case CoreErrorKind.timeout:
        return ErrorPresentation(
          message: SharedMessages.requestTimedOut(context),
          severity: ErrorPresentationSeverity.warning,
        );
      case CoreErrorKind.unauthorized:
        return ErrorPresentation(
          message: SharedMessages.sessionExpired(context),
          severity: ErrorPresentationSeverity.error,
          actionLabel: SharedMessages.relogin(context),
          onAction: () => MessageHost.clearBanners(context),
        );
      case CoreErrorKind.forbidden:
        return ErrorPresentation(
          message: SharedMessages.accessDenied(context),
          severity: ErrorPresentationSeverity.error,
        );
      case CoreErrorKind.notFound:
        return ErrorPresentation(
          message: SharedMessages.resourceMissing(context),
          severity: ErrorPresentationSeverity.info,
        );
      case CoreErrorKind.validation:
        final detail = error.message;
        final base = SharedMessages.validationError(context);
        return ErrorPresentation(
          message: detail == null || detail.isEmpty ? base : '$base: $detail',
          severity: ErrorPresentationSeverity.warning,
        );
      case CoreErrorKind.conflict:
        return ErrorPresentation(
          message: SharedMessages.conflictError(context),
          severity: ErrorPresentationSeverity.warning,
        );
      case CoreErrorKind.rateLimited:
        return ErrorPresentation(
          message: SharedMessages.rateLimited(context),
          severity: ErrorPresentationSeverity.warning,
        );
      case CoreErrorKind.server:
        return ErrorPresentation(
          message: SharedMessages.serverError(context),
          severity: ErrorPresentationSeverity.error,
        );
      case CoreErrorKind.cancelled:
        return ErrorPresentation(
          message: SharedMessages.requestCancelled(context),
          severity: ErrorPresentationSeverity.info,
          duration: const Duration(seconds: 3),
        );
      case CoreErrorKind.unknown:
        final msg = error.message;
        return ErrorPresentation(
          message: msg == null || msg.isEmpty ? SharedMessages.unexpectedError(context) : msg,
          severity: ErrorPresentationSeverity.error,
        );
    }
  }
}
