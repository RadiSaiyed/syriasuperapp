import 'package:flutter/services.dart';
import 'package:flutter/material.dart';

Future<void> playTapFeedback() async {
  try {
    HapticFeedback.lightImpact();
  } catch (_) {}
  try {
    SystemSound.play(SystemSoundType.click);
  } catch (_) {}
}

class HapticActionButton extends StatefulWidget {
  final Widget label;
  final IconData? icon;
  final VoidCallback onPressed;
  final bool tonal;
  const HapticActionButton({super.key, required this.label, required this.onPressed, this.icon, this.tonal = false});

  @override
  State<HapticActionButton> createState() => _HapticActionButtonState();
}

class _HapticActionButtonState extends State<HapticActionButton> {
  bool _pressed = false;
  @override
  Widget build(BuildContext context) {
    final child = widget.tonal
        ? FilledButton.tonalIcon(onPressed: _handlePressed, icon: Icon(widget.icon), label: widget.label)
        : FilledButton.icon(onPressed: _handlePressed, icon: Icon(widget.icon), label: widget.label);
    return AnimatedScale(
      duration: const Duration(milliseconds: 120),
      curve: Curves.easeOut,
      scale: _pressed ? 0.97 : 1.0,
      child: Listener(
        onPointerDown: (_) => setState(() => _pressed = true),
        onPointerUp: (_) => setState(() => _pressed = false),
        onPointerCancel: (_) => setState(() => _pressed = false),
        child: child,
      ),
    );
  }

  Future<void> _handlePressed() async {
    await playTapFeedback();
    if (!mounted) return;
    widget.onPressed();
  }
}
