import 'package:flutter/material.dart';

class StethoscopeIcon extends StatelessWidget {
  final double size;
  final Color color;
  final double? strokeWidth;
  const StethoscopeIcon({super.key, this.size = 44, this.color = Colors.white, this.strokeWidth});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _StethoscopePainter(color: color, strokeWidth: strokeWidth ?? (size * 0.08)),
      ),
    );
  }
}

class _StethoscopePainter extends CustomPainter {
  final Color color;
  final double strokeWidth;
  _StethoscopePainter({required this.color, required this.strokeWidth});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..isAntiAlias = true;

    final s = size.shortestSide;
    // Ear tips
    final earR = s * 0.06;
    final earLPos = Offset(s * 0.26, s * 0.22);
    final earRPos = Offset(s * 0.74, s * 0.22);
    canvas.drawCircle(earLPos, earR, paint);
    canvas.drawCircle(earRPos, earR, paint);

    // Tubing (U shape)
    final path = Path()
      ..moveTo(earLPos.dx, earLPos.dy)
      ..quadraticBezierTo(s * 0.26, s * 0.48, s * 0.40, s * 0.60)
      ..quadraticBezierTo(s * 0.50, s * 0.68, s * 0.60, s * 0.60)
      ..quadraticBezierTo(s * 0.74, s * 0.48, earRPos.dx, earRPos.dy);
    canvas.drawPath(path, paint);

    // Tube from bottom toward chest piece
    final tubeStart = Offset(s * 0.50, s * 0.64);
    final tubeKnee = Offset(s * 0.66, s * 0.74);
    canvas.drawLine(tubeStart, tubeKnee, paint);

    // Chest piece (double ring)
    final chestCenter = Offset(s * 0.80, s * 0.82);
    final chestOuter = s * 0.12;
    final chestInner = s * 0.075;
    canvas.drawCircle(chestCenter, chestOuter, paint);
    canvas.drawCircle(chestCenter, chestInner, paint);
  }

  @override
  bool shouldRepaint(covariant _StethoscopePainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.strokeWidth != strokeWidth;
  }
}

