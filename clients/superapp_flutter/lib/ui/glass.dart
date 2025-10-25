import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';

const Color _glassDarkTop = Color(0xFF0A0C11);
const Color _glassDarkBottom = Color(0xFF111827);
const Color _glassGreenAccent = Color(0xFF30D158);

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
    final effectiveOpacity =
        isDark ? math.max(opacity, 0.36) : math.max(opacity, 0.28);
    final accent = isDark ? const Color(0xFF64D2FF) : const Color(0xFF32ADE6);
    return Container(
      margin: margin,
      decoration: BoxDecoration(borderRadius: borderRadius),
      child: ClipRRect(
        borderRadius: borderRadius,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: Stack(children: [
            // Base frosted layer with subtle curvature gradient
            DecoratedBox(
              decoration: BoxDecoration(
                color: base.withValues(alpha: effectiveOpacity),
                borderRadius: borderRadius,
                border: Border.all(
                    color: Colors.white.withValues(alpha: isDark ? 0.32 : 0.38),
                    width: 1.25),
                boxShadow: [
                  BoxShadow(
                      color:
                          Colors.black.withValues(alpha: isDark ? 0.66 : 0.22),
                      blurRadius: 60,
                      offset: const Offset(0, 18)),
                  BoxShadow(
                      color: accent.withValues(alpha: isDark ? 0.26 : 0.16),
                      blurRadius: 22,
                      offset: const Offset(-6, -8)),
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
            // Sub-surface glow to emulate liquid translucency
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: borderRadius,
                  gradient: RadialGradient(
                    center: const Alignment(-0.65, -0.9),
                    radius: 1.25,
                    colors: [
                      accent.withValues(alpha: isDark ? 0.22 : 0.14),
                      Colors.white.withValues(alpha: isDark ? 0.16 : 0.12),
                      Colors.transparent,
                    ],
                    stops: const [0.0, 0.35, 1.0],
                  ),
                ),
              ),
            ),
            // Inner outline to mimic laminated iOS glass edge
            Positioned.fill(
              child: IgnorePointer(
                ignoring: true,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: borderRadius,
                    border: Border.all(
                        color: Colors.white
                            .withValues(alpha: isDark ? 0.22 : 0.18),
                        width: 0.7),
                  ),
                ),
              ),
            ),
            // Subtle frost noise texture (very light)
            const FrostNoise(opacity: 0.06, scale: 6),
            // Edge highlight (rim light) for 3D bevel at top-left
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: borderRadius,
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.center,
                    stops: const [0.0, 0.25, 1.0],
                    colors: [
                      Colors.white.withValues(alpha: isDark ? 0.24 : 0.16),
                      Colors.white.withValues(alpha: 0.08),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            // Edge shadow at bottom-right to enhance depth
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: borderRadius,
                  gradient: LinearGradient(
                    begin: Alignment.bottomRight,
                    end: Alignment.center,
                    stops: const [0.0, 0.35, 1.0],
                    colors: [
                      Colors.black.withValues(alpha: isDark ? 0.30 : 0.12),
                      Colors.black.withValues(alpha: 0.06),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            // Content
            Padding(padding: padding, child: child),
          ]),
        ),
      ),
    );
  }
}

class GlassCard extends StatelessWidget {
  final Widget child;
  const GlassCard({super.key, required this.child});
  @override
  Widget build(BuildContext context) => Glass(
      margin: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      child: child);
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
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final Color accent = theme.colorScheme.primary;
    final Color warm = theme.colorScheme.secondary;
    final Color cool = accent.withValues(alpha: isDark ? 0.28 : 0.10);
    final Color cyan = accent.withValues(alpha: isDark ? 0.22 : 0.08);
    final Color ember = warm.withValues(alpha: isDark ? 0.18 : 0.07);
    final Color baseTop = isDark ? _glassDarkTop : Colors.white;
    final Color baseBottom = isDark ? _glassDarkBottom : Colors.white;
    return AnimatedBuilder(
      animation: _t,
      builder: (_, __) {
        final p = _t.value;
        return Stack(children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: isDark
                      ? [baseTop, accent.withValues(alpha: 0.06), baseBottom]
                      : [Colors.white, Colors.white, Colors.white],
                ),
              ),
            ),
          ),
          Positioned(
            top: -80 + math.sin(p * math.pi * 2) * 10,
            left: -40 + math.cos(p * math.pi * 2) * 8,
            child: _blob(
              size: 220,
              colors: [cool, ember],
            ),
          ),
          Positioned(
            bottom: -60 + math.cos(p * math.pi * 2) * 10,
            right: -20 + math.sin(p * math.pi * 2) * 8,
            child: _blob(
              size: 260,
              colors: [
                _glassGreenAccent.withValues(alpha: isDark ? 0.22 : 0.08),
                cyan
              ],
            ),
          ),
        ]);
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

/// Full‑screen, touch‑transparent glass overlay. Place above backgrounds
/// (e.g. [LiquidBackground]) and below page content to give everything a
/// subtle liquid‑glass appearance without blocking interactions.
class LiquidGlassOverlay extends StatefulWidget {
  final double blur;
  final double opacity;
  const LiquidGlassOverlay({super.key, this.blur = 60, this.opacity = 0.30});

  @override
  State<LiquidGlassOverlay> createState() => _LiquidGlassOverlayState();
}

class _LiquidGlassOverlayState extends State<LiquidGlassOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl =
      AnimationController(vsync: this, duration: const Duration(seconds: 18))
        ..repeat();
  late final Animation<double> _anim =
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOutSine);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: true,
      child: AnimatedBuilder(
        animation: _anim,
        builder: (context, _) {
          final t = _anim.value;
          final theme = Theme.of(context);
          final colorScheme = theme.colorScheme;
          final accent = colorScheme.primary;
          final warm = colorScheme.secondary;
          final bool isDark = theme.brightness == Brightness.dark;
          return Stack(children: [
            Positioned.fill(
              child: Glass(
                blur: widget.blur,
                opacity: widget.opacity,
                borderRadius: BorderRadius.zero,
                padding: EdgeInsets.zero,
                child: const SizedBox.expand(),
              ),
            ),
            _liquidCaustics(t, accent, warm, isDark),
            _animatedSpecular(t, accent, warm, isDark),
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    stops: const [0.0, 0.45, 1.0],
                    colors: [
                      accent.withValues(alpha: isDark ? 0.14 : 0.08),
                      Colors.white.withValues(alpha: 0.03),
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
                    stops: const [0.0, 0.18, 1.0],
                    colors: [
                      Colors.black.withValues(alpha: isDark ? 0.22 : 0.14),
                      Colors.black.withValues(alpha: 0.05),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            const FrostNoise(opacity: 0.05, scale: 5),
          ]);
        },
      ),
    );
  }

  Widget _animatedSpecular(double t, Color accent, Color warm, bool isDark) {
    final sweep = (t * 1.6) % 1.0;
    final startX = lerpDouble(-1.35, 0.95, sweep)!;
    final endX = startX + 0.65;
    final wobbleY = math.sin(t * math.pi * 2) * 0.08;
    return Positioned.fill(
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment(startX, -1.0 + wobbleY),
            end: Alignment(endX, 1.0 - wobbleY),
            stops: const [0.0, 0.18, 0.50, 1.0],
            colors: [
              Colors.transparent,
              accent.withValues(alpha: isDark ? 0.40 : 0.24),
              warm.withValues(alpha: isDark ? 0.22 : 0.14),
              Colors.transparent,
            ],
          ),
        ),
      ),
    );
  }

  Widget _liquidCaustics(double t, Color accent, Color warm, bool isDark) {
    final wave = math.sin(t * math.pi * 2);
    final wave2 = math.cos(t * math.pi * 2 * 0.75);
    final wave3 = math.sin((t + 0.28) * math.pi * 2);
    return Positioned.fill(
      child: IgnorePointer(
        ignoring: true,
        child: Stack(children: [
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(wave * 0.35, wave2 * 0.28 - 0.15),
                radius: 1.05,
                colors: [
                  accent.withValues(alpha: isDark ? 0.24 : 0.12),
                  Colors.transparent,
                ],
                stops: const [0.0, 1.0],
              ),
            ),
          ),
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(wave3 * 0.45 - 0.2, 0.55),
                radius: 1.25,
                colors: [
                  warm.withValues(alpha: isDark ? 0.20 : 0.10),
                  Colors.transparent,
                ],
                stops: const [0.0, 1.0],
              ),
            ),
          ),
        ]),
      ),
    );
  }
}

/// Very subtle procedural frost noise (white dots) to give glass micro‑texture.
class FrostNoise extends StatelessWidget {
  final double opacity; // 0..1, typical 0.02..0.06
  final double scale; // pixel grid spacing; lower = more dense
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
        // sparsity ~10-20%
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
