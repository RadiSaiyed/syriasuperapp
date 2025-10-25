import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';

class Glass extends StatelessWidget {
  final Widget? child;
  final double blur;
  final double opacity;
  final BorderRadius borderRadius;
  final EdgeInsets padding;
  final EdgeInsets margin;
  const Glass({super.key, this.child, this.blur = 24, this.opacity = 0.14, this.borderRadius = const BorderRadius.all(Radius.circular(16)), this.padding = const EdgeInsets.all(12), this.margin = EdgeInsets.zero});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? Colors.black : Colors.white;
    final effectiveOpacity = isDark ? (opacity < 0.22 ? 0.22 : opacity) : (opacity < 0.20 ? 0.20 : opacity);
    return Container(
      margin: margin,
      decoration: BoxDecoration(borderRadius: borderRadius),
      child: ClipRRect(
        borderRadius: borderRadius,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: bg.withOpacity(effectiveOpacity),
              borderRadius: borderRadius,
              border: Border.all(color: (isDark ? Colors.white : Colors.white).withOpacity(isDark ? 0.10 : 0.22), width: 1),
              boxShadow: [
                BoxShadow(color: (isDark ? Colors.black : Colors.black).withOpacity(isDark ? 0.40 : 0.08), blurRadius: 24, offset: const Offset(0, 8)),
              ],
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  (isDark ? Colors.white : Colors.white).withOpacity(isDark ? (effectiveOpacity * 0.6) : (effectiveOpacity + 0.04)),
                  (isDark ? Colors.white : Colors.white).withOpacity(isDark ? (effectiveOpacity * 0.45) : (effectiveOpacity - 0.02)),
                ],
              ),
            ),
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
  }
}

class GlassCard extends StatelessWidget {
  final Widget child;
  const GlassCard({super.key, required this.child});
  @override
  Widget build(BuildContext context) {
    return Glass(margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8), child: child);
  }
}

class LiquidBackground extends StatefulWidget {
  const LiquidBackground({super.key});

  @override
  State<LiquidBackground> createState() => _LiquidBackgroundState();
}

class _LiquidBackgroundState extends State<LiquidBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _t;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(seconds: 16))..repeat(reverse: true);
    _t = CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    if (!isDark) {
      return const ColoredBox(color: Colors.white);
    }
    final c1 = const Color(0xFF0A84FF); // iOS accent blue
    final c2 = const Color(0xFF30D158); // iOS green
    final c3 = const Color(0xFFFF9F0A); // iOS orange
    final c4 = const Color(0xFFAF52DE); // iOS purple
    final base = const Color(0xFF0A0A0C);
    return AnimatedBuilder(
      animation: _t,
      builder: (context, _) {
        final p = _t.value;
        return Stack(children: [
          // Base gradient
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: isDark
                      ? [base, c4.withOpacity(0.08), base]
                      : [c1.withOpacity(0.08), c4.withOpacity(0.06), base],
                ),
              ),
            ),
          ),
          // Blobs with gentle motion
          Positioned(
            top: -80 + math.sin(p * math.pi * 2) * 10,
            left: -40 + math.cos(p * math.pi * 2) * 8,
            child: _blob(size: 220, colors: [c1.withOpacity(isDark ? 0.22 : 0.35), c3.withOpacity(isDark ? 0.18 : 0.25)]),
          ),
          Positioned(
            bottom: -60 + math.cos(p * math.pi * 2) * 10,
            right: -20 + math.sin(p * math.pi * 2) * 8,
            child: _blob(size: 260, colors: [c2.withOpacity(isDark ? 0.20 : 0.30), c4.withOpacity(isDark ? 0.20 : 0.28)]),
          ),
        ]);
      },
    );
  }

  Widget _blob({required double size, required List<Color> colors}) {
    return ClipOval(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 40, sigmaY: 40),
        child: Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(colors: colors, begin: Alignment.topLeft, end: Alignment.bottomRight),
          ),
        ),
      ),
    );
  }
}
