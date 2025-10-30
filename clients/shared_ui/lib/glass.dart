library shared_ui_glass;

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
  const Glass(
      {super.key,
      this.child,
      this.blur = 24,
      this.opacity = 0.14,
      this.borderRadius = const BorderRadius.all(Radius.circular(16)),
      this.padding = const EdgeInsets.all(12),
      this.margin = EdgeInsets.zero});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final base = isDark ? Colors.black : Colors.white;
    final effectiveOpacity = isDark
        ? (opacity < 0.34 ? 0.34 : opacity)
        : (opacity < 0.26 ? 0.26 : opacity);
    return Container(
      margin: margin,
      decoration: BoxDecoration(borderRadius: borderRadius),
      child: ClipRRect(
        borderRadius: borderRadius,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: Stack(children: [
            DecoratedBox(
              decoration: BoxDecoration(
                color: base.withValues(alpha: effectiveOpacity),
                borderRadius: borderRadius,
                border: Border.all(
                    color: Colors.white.withValues(alpha: isDark ? 0.28 : 0.35),
                    width: 1.15),
                boxShadow: [
                  BoxShadow(
                      color:
                          Colors.black.withValues(alpha: isDark ? 0.62 : 0.18),
                      blurRadius: 54,
                      offset: const Offset(0, 14)),
                ],
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Colors.white.withValues(
                        alpha: isDark
                            ? (effectiveOpacity * 1.00)
                            : (effectiveOpacity + 0.08)),
                    Colors.white.withValues(
                        alpha: isDark
                            ? (effectiveOpacity * 0.85)
                            : (effectiveOpacity + 0.04)),
                  ],
                ),
              ),
            ),
            const FrostNoise(opacity: 0.06, scale: 6),
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: borderRadius,
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.center,
                    stops: const [0.0, 0.25, 1.0],
                    colors: [
                      Colors.white.withValues(alpha: isDark ? 0.18 : 0.12),
                      Colors.white.withValues(alpha: 0.06),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: borderRadius,
                  gradient: LinearGradient(
                    begin: Alignment.bottomRight,
                    end: Alignment.center,
                    stops: const [0.0, 0.35, 1.0],
                    colors: [
                      Colors.black.withValues(alpha: isDark ? 0.24 : 0.10),
                      Colors.black.withValues(alpha: 0.04),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            Padding(padding: padding, child: child),
          ]),
        ),
      ),
    );
  }
}

class LiquidBackground extends StatefulWidget {
  const LiquidBackground({super.key});
  @override
  State<LiquidBackground> createState() => _LiquidBackgroundState();
}

class _LiquidBackgroundState extends State<LiquidBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl =
      AnimationController(vsync: this, duration: const Duration(seconds: 16))
        ..repeat(reverse: true);
  late final Animation<double> _t =
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut);
  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    const c1 = Color(0xFF0A84FF); // blue
    const c2 = Color(0xFF30D158); // green
    const c3 = Color(0xFFFF9F0A); // orange
    const c4 = Color(0xFF64D2FF); // light‑cyan
    final base = isDark ? const Color(0xFF07080A) : Colors.white;
    return AnimatedBuilder(
      animation: _t,
      builder: (_, __) {
        final p = _t.value;
        return RepaintBoundary(
            child: Stack(children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: isDark
                      ? [base, c1.withValues(alpha: 0.035), base]
                      : [Colors.white, Colors.white, Colors.white],
                ),
              ),
            ),
          ),
          Positioned(
            top: -80 + math.sin(p * math.pi * 2) * 10,
            left: -40 + math.cos(p * math.pi * 2) * 8,
            child: _blob(size: 220, colors: [
              c1.withValues(alpha: isDark ? 0.22 : 0.06),
              c3.withValues(alpha: isDark ? 0.18 : 0.05)
            ]),
          ),
          Positioned(
            bottom: -60 + math.cos(p * math.pi * 2) * 10,
            right: -20 + math.sin(p * math.pi * 2) * 8,
            child: _blob(size: 260, colors: [
              c2.withValues(alpha: isDark ? 0.20 : 0.05),
              c4.withValues(alpha: isDark ? 0.20 : 0.05)
            ]),
          ),
        ]));
      },
    );
  }

  Widget _blob({required double size, required List<Color> colors}) => ClipOval(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 40, sigmaY: 40),
          child: Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                    colors: colors,
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight)),
          ),
        ),
      );
}

class LiquidGlassOverlay extends StatelessWidget {
  final double blur;
  final double opacity;
  const LiquidGlassOverlay({super.key, this.blur = 56, this.opacity = 0.28});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: true,
      child: Stack(children: [
        Positioned.fill(
          child: Glass(
            blur: blur,
            opacity: opacity,
            borderRadius: BorderRadius.zero,
            padding: EdgeInsets.zero,
            child: const SizedBox.expand(),
          ),
        ),
        Positioned.fill(
          child: IgnorePointer(
            ignoring: true,
            child: DecoratedBox(
              decoration:
                  BoxDecoration(color: Colors.black.withValues(alpha: 0.06)),
            ),
          ),
        ),
        const FrostNoise(opacity: 0.045, scale: 5),
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                stops: const [0.0, 0.30, 0.62, 1.0],
                colors: [
                  Colors.white.withValues(alpha: 0.14),
                  Colors.white.withValues(alpha: 0.05),
                  Colors.white.withValues(alpha: 0.10),
                  Colors.transparent,
                ],
              ),
            ),
          ),
        ),
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.bottomCenter,
                end: Alignment.topCenter,
                stops: const [0.0, 0.2, 1.0],
                colors: [
                  Colors.black.withValues(alpha: 0.10),
                  Colors.black.withValues(alpha: 0.02),
                  Colors.transparent,
                ],
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets margin;
  const GlassCard({super.key, required this.child, this.margin = const EdgeInsets.symmetric(horizontal: 12, vertical: 8)});
  @override
  Widget build(BuildContext context) {
    return Glass(margin: margin, child: child);
  }
}

class FrostNoise extends StatelessWidget {
  final double opacity;
  final double scale;
  final int seed;
  const FrostNoise(
      {super.key, this.opacity = 0.04, this.scale = 6, this.seed = 1337});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: true,
      child: CustomPaint(
        painter: _FrostNoisePainter(opacity: opacity, scale: scale, seed: seed),
      ),
    );
  }
}

class _FrostNoisePainter extends CustomPainter {
  final double opacity;
  final double scale;
  final int seed;
  _FrostNoisePainter(
      {required this.opacity, required this.scale, required this.seed});

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final rnd = math.Random(seed ^ size.width.toInt() ^ size.height.toInt());
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: opacity.clamp(0, 1))
      ..strokeWidth = (scale * 0.16).clamp(0.6, 1.2)
      ..strokeCap = StrokeCap.round
      ..isAntiAlias = true;

    final List<Offset> pts = [];
    final step = scale.clamp(3, 12);
    for (double y = 0; y < size.height; y += step) {
      for (double x = 0; x < size.width; x += step) {
        if (rnd.nextDouble() < 0.14) {
          final dx = (rnd.nextDouble() - 0.5) * step * 0.6;
          final dy = (rnd.nextDouble() - 0.5) * step * 0.6;
          pts.add(Offset(x + dx, y + dy));
        }
      }
    }
    if (pts.isNotEmpty) {
      canvas.drawPoints(PointMode.points, pts, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _FrostNoisePainter oldDelegate) {
    return oldDelegate.opacity != opacity ||
        oldDelegate.scale != scale ||
        oldDelegate.seed != seed;
  }
}
