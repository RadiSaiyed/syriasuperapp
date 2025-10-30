import 'package:flutter/material.dart';

class ErrorBanner extends StatelessWidget {
  final String message;
  final IconData icon;
  final EdgeInsets padding;
  final EdgeInsets margin;
  final VoidCallback? onClose;
  final bool dense;
  const ErrorBanner({super.key, required this.message, this.icon = Icons.error_outline, this.padding = const EdgeInsets.all(12), this.margin = const EdgeInsets.symmetric(vertical: 8), this.onClose, this.dense = false});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final pad = dense ? const EdgeInsets.symmetric(horizontal: 12, vertical: 8) : padding;
    return Container(
      margin: margin,
      padding: pad,
      decoration: BoxDecoration(
        color: cs.error.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: cs.error.withOpacity(0.45)),
      ),
      child: Row(children: [
        Icon(icon, color: cs.error, size: dense ? 18 : 24),
        const SizedBox(width: 8),
        Expanded(child: Text(message, style: TextStyle(color: cs.onSurface))),
        if (onClose != null) ...[
          const SizedBox(width: 8),
          IconButton(onPressed: onClose, icon: const Icon(Icons.close), color: cs.onSurface, iconSize: dense ? 18 : 24, padding: EdgeInsets.zero, visualDensity: VisualDensity.compact),
        ]
      ]),
    );
  }
}

class InfoBanner extends StatelessWidget {
  final String message;
  final IconData icon;
  final EdgeInsets padding;
  final EdgeInsets margin;
  final VoidCallback? onClose;
  final bool dense;
  const InfoBanner({super.key, required this.message, this.icon = Icons.info_outline, this.padding = const EdgeInsets.all(12), this.margin = const EdgeInsets.symmetric(vertical: 8), this.onClose, this.dense = false});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final pad = dense ? const EdgeInsets.symmetric(horizontal: 12, vertical: 8) : padding;
    return Container(
      margin: margin,
      padding: pad,
      decoration: BoxDecoration(
        color: cs.primary.withOpacity(0.10),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: cs.primary.withOpacity(0.40)),
      ),
      child: Row(children: [
        Icon(icon, color: cs.primary, size: dense ? 18 : 24),
        const SizedBox(width: 8),
        Expanded(child: Text(message, style: TextStyle(color: cs.onSurface))),
        if (onClose != null) ...[
          const SizedBox(width: 8),
          IconButton(onPressed: onClose, icon: const Icon(Icons.close), color: cs.onSurface, iconSize: dense ? 18 : 24, padding: EdgeInsets.zero, visualDensity: VisualDensity.compact),
        ]
      ]),
    );
  }
}
