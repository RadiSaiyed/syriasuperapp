import 'dart:math' as math;
import 'package:flutter/material.dart';

class SteeringWheelIcon extends StatelessWidget {
  final double size;
  final Color color;
  final double strokeWidth;
  const SteeringWheelIcon({super.key, this.size = 22, this.color = Colors.white, this.strokeWidth = 2.2});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _SteeringWheelPainter(color: color, strokeWidth: strokeWidth),
      ),
    );
  }
}

class _SteeringWheelPainter extends CustomPainter {
  final Color color;
  final double strokeWidth;
  const _SteeringWheelPainter({required this.color, required this.strokeWidth});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..isAntiAlias = true;

    final cx = size.width / 2;
    final cy = size.height / 2;
    final r = (size.shortestSide / 2) - strokeWidth * 0.6;
    final center = Offset(cx, cy);

    // Outer rim
    canvas.drawCircle(center, r, paint);

    // Hub
    canvas.drawCircle(center, r * 0.22, paint);

    // Spokes at 0°, 120°, 240°
    void spoke(double deg) {
      final rad = deg * 3.1415926535 / 180.0;
      final inner = Offset(
        cx + (r * 0.35) * math.cos(rad),
        cy + (r * 0.35) * math.sin(rad),
      );
      final outer = Offset(
        cx + (r - strokeWidth * 1.2) * math.cos(rad),
        cy + (r - strokeWidth * 1.2) * math.sin(rad),
      );
      canvas.drawLine(inner, outer, paint);
    }

    spoke(0);
    spoke(120);
    spoke(240);
  }

  @override
  bool shouldRepaint(covariant _SteeringWheelPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.strokeWidth != strokeWidth;
  }
}
