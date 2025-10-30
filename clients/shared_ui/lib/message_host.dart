import 'dart:async';
import 'package:flutter/material.dart';
import 'toast.dart';

/// Centralized message host for showing app-wide banners and toasts.
///
/// Usage:
/// - Wire into your MaterialApp via `scaffoldMessengerKey: MessageHost.messengerKey`.
/// - Call `MessageHost.showInfoBanner(context, '...')` or `MessageHost.showErrorBanner(...)`.
/// - For success notifications, prefer `showToast(context, '...')` from toast.dart.
class MessageHost extends InheritedWidget {
  const MessageHost({super.key, required super.child});

  @override
  bool updateShouldNotify(covariant InheritedWidget oldWidget) => false;

  /// Global messenger key to allow showing banners outside of a local context.
  static final GlobalKey<ScaffoldMessengerState> messengerKey = GlobalKey<ScaffoldMessengerState>();

  /// Show a Material banner with info/neutral styling.
  static void showInfoBanner(BuildContext context, String message, {Duration duration = const Duration(seconds: 4), String? actionLabel, VoidCallback? onAction}) {
    _showBanner(context, message,
        duration: duration,
        icon: Icons.info_outline,
        backgroundColor: Theme.of(context).colorScheme.surface,
        foregroundColor: Theme.of(context).colorScheme.onSurface,
        actionLabel: actionLabel,
        onAction: onAction);
  }

  /// Show a Material banner with error styling.
  static void showErrorBanner(BuildContext context, String message, {Duration duration = const Duration(seconds: 5), String? actionLabel, VoidCallback? onAction}) {
    final theme = Theme.of(context);
    _showBanner(context, message,
        duration: duration,
        icon: Icons.error_outline,
        backgroundColor: theme.colorScheme.errorContainer,
        foregroundColor: theme.colorScheme.onErrorContainer,
        actionLabel: actionLabel,
        onAction: onAction);
  }

  /// Remove any currently displayed banners.
  static void clearBanners([BuildContext? context]) {
    final messenger = context != null
        ? ScaffoldMessenger.of(context)
        : messengerKey.currentState;
    messenger?.clearMaterialBanners();
  }

  static void _showBanner(
    BuildContext context,
    String message, {
    required Duration duration,
    required IconData icon,
    required Color backgroundColor,
    required Color foregroundColor,
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearMaterialBanners();
    final banner = MaterialBanner(
      backgroundColor: backgroundColor,
      dividerColor: Colors.transparent,
      elevation: 0,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      content: Row(
        children: [
          Icon(icon, color: foregroundColor),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: foregroundColor),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
      actions: [
        if (actionLabel != null && onAction != null)
          TextButton(
            onPressed: onAction,
            child: Text(actionLabel, style: TextStyle(color: foregroundColor)),
          ),
        IconButton(
          onPressed: () => messenger.clearMaterialBanners(),
          icon: Icon(Icons.close, color: foregroundColor),
        ),
      ],
    );
    messenger.showMaterialBanner(banner);
    // Auto dismiss after [duration]
    Timer(duration, () => messenger.clearMaterialBanners());
  }

  /// Convenience passthrough for success toasts.
  static void showSuccessToast(BuildContext context, String message, {Duration duration = const Duration(seconds: 2)}) {
    showToast(context, message, duration: duration);
  }
}

