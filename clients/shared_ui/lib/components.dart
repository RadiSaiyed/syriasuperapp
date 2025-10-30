import 'package:flutter/material.dart';

class SectionHeader extends StatelessWidget {
  final String title;
  final Widget? trailing;
  final EdgeInsets padding;
  const SectionHeader({super.key, required this.title, this.trailing, this.padding = const EdgeInsets.only(top: 8, bottom: 8)});

  @override
  Widget build(BuildContext context) {
    final text = Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold));
    return Padding(
      padding: padding,
      child: Row(children: [Expanded(child: text), if (trailing != null) trailing!]),
    );
  }
}

class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;
  const EmptyState({super.key, required this.icon, required this.title, this.subtitle, this.action});

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[
      Icon(icon, size: 64, color: Theme.of(context).colorScheme.outline),
      const SizedBox(height: 12),
      Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
    ];
    if (subtitle != null && subtitle!.isNotEmpty) {
      children.add(const SizedBox(height: 6));
      children.add(Text(subtitle!, textAlign: TextAlign.center));
    }
    if (action != null) {
      children.add(const SizedBox(height: 12));
      children.add(action!);
    }
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Column(mainAxisSize: MainAxisSize.min, children: children),
        ),
      ),
    );
  }
}

Future<bool> showConfirmDialog(
  BuildContext context, {
  String title = 'Confirm',
  String content = 'Are you sure?',
  String confirmText = 'Confirm',
  String cancelText = 'Cancel',
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (_) => AlertDialog(
      title: Text(title),
      content: Text(content),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(cancelText)),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(confirmText)),
      ],
    ),
  );
  return result == true;
}

