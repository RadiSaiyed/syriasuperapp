import 'dart:async';
import 'package:flutter/material.dart';

void showToast(BuildContext context, String message, {Duration duration = const Duration(seconds: 2)}) {
  final overlay = Overlay.of(context);
  if (overlay == null) return;
  final theme = Theme.of(context);
  final entry = OverlayEntry(
    builder: (_) => Positioned(
      left: 16,
      right: 16,
      bottom: 48,
      child: IgnorePointer(
        child: Material(
          color: Colors.transparent,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: theme.colorScheme.inverseSurface.withOpacity(0.9),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.check_circle_outline, color: Colors.white70, size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text(message, style: const TextStyle(color: Colors.white), maxLines: 2, overflow: TextOverflow.ellipsis)),
              ],
            ),
          ),
        ),
      ),
    ),
  );
  overlay.insert(entry);
  Timer(duration, () => entry.remove());
}

