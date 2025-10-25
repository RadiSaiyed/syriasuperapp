import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class QrScanScreen extends StatefulWidget {
  const QrScanScreen({super.key});

  @override
  State<QrScanScreen> createState() => _QrScanScreenState();
}

class _QrScanScreenState extends State<QrScanScreen> {
  final TextEditingController _manualCtrl = TextEditingController();
  MobileScannerController? _controller;
  bool _handled = false;
  bool _permissionDenied = false;

  bool get _cameraSupported {
    if (kIsWeb) return false;
    return defaultTargetPlatform == TargetPlatform.iOS ||
        defaultTargetPlatform == TargetPlatform.android;
  }

  @override
  void initState() {
    super.initState();
    if (_cameraSupported) {
      _controller = MobileScannerController(
        detectionSpeed: DetectionSpeed.noDuplicates,
        facing: CameraFacing.back,
        torchEnabled: false,
        returnImage: false,
      );
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    _manualCtrl.dispose();
    super.dispose();
  }

  Future<void> _handleDetection(BarcodeCapture capture) async {
    if (_handled) return;
    final code = capture.barcodes
        .map((barcode) => barcode.rawValue)
        .firstWhere((value) => value != null && value.trim().isNotEmpty,
            orElse: () => null);
    if (code == null) return;
    _handled = true;
    await _controller?.stop();
    if (!mounted) return;
    Navigator.of(context).pop(code.trim());
  }

  void _onPermissionSet(MobileScannerController controller, bool granted) {
    if (!granted && mounted) {
      setState(() => _permissionDenied = true);
    }
  }

  Widget _buildManualControls({String? message}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (message != null) ...[
          Text(message, style: const TextStyle(fontWeight: FontWeight.w500)),
          const SizedBox(height: 12),
        ],
        TextField(
          controller: _manualCtrl,
          decoration: const InputDecoration(labelText: 'Enter code manually'),
    ),
        const SizedBox(height: 8),
        FilledButton(
          onPressed: () {
            final value = _manualCtrl.text.trim();
            Navigator.of(context).pop(value.isEmpty ? null : value);
          },
          child: const Text('Apply'),
        ),
        const SizedBox(height: 8),
        OutlinedButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
      ],
    );
  }

  Widget _buildScannerView() {
    if (_controller == null) {
      return _buildManualControls(
        message:
            'Camera scanning is not available on this platform. Please enter the code manually.',
      );
    }
    if (_permissionDenied) {
      return _buildManualControls(
        message:
            'Camera access was denied. Enable access in settings or enter the code manually.',
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Stack(
              fit: StackFit.expand,
              children: [
                MobileScanner(
                  controller: _controller!,
                  fit: BoxFit.cover,
                  onDetect: _handleDetection,
                  onPermissionSet: _onPermissionSet,
                  errorBuilder: (context, error, child) {
                    return _buildErrorOverlay(
                      'Scanner error: ${error.errorCode.name}',
                      error.errorDetails,
                    );
                  },
                ),
                _ScannerOverlay(),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        _buildManualControls(
          message:
              'If the QR code is not detected, you can enter it manually instead.',
        ),
      ],
    );
  }

  Widget _buildErrorOverlay(String title, String? details) {
    return Container(
      color: Colors.black.withOpacity(0.6),
      alignment: Alignment.center,
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, color: Colors.white, size: 40),
          const SizedBox(height: 12),
          Text(
            title,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          if (details != null && details.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(details,
                style: const TextStyle(color: Colors.white70),
                textAlign: TextAlign.center),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan QR'),
        actions: [
          if (_controller != null && !_permissionDenied)
            ValueListenableBuilder<TorchState>(
              valueListenable: _controller!.torchState,
              builder: (context, state, _) {
                final enabled = state == TorchState.on;
                return IconButton(
                  icon: Icon(enabled ? Icons.flash_on : Icons.flash_off),
                  tooltip: enabled ? 'Turn off flash' : 'Turn on flash',
                  onPressed: () => _controller?.toggleTorch(),
                );
              },
            ),
          if (_controller != null && !_permissionDenied)
            IconButton(
              icon: const Icon(Icons.cameraswitch),
              tooltip: 'Switch camera',
              onPressed: () => _controller?.switchCamera(),
            ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: _buildScannerView(),
      ),
    );
  }
}

class _ScannerOverlay extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = constraints.biggest;
        final edge = size.shortestSide * 0.7;
        final rectSize = Size(edge, edge);
        return Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(
                painter: _ScannerOverlayPainter(rectSize: rectSize),
              ),
            ),
            Align(
              alignment: Alignment.bottomCenter,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 24),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
                  decoration: BoxDecoration(
                    color: Colors.black.withOpacity(0.5),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text(
                    'Position the code within the frame',
                    style: TextStyle(color: Colors.white),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ScannerOverlayPainter extends CustomPainter {
  _ScannerOverlayPainter({required this.rectSize});

  final Size rectSize;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.black.withOpacity(0.55)
      ..style = PaintingStyle.fill;
    final center = size.center(Offset.zero);
    final rect = Rect.fromCenter(center: center, width: rectSize.width, height: rectSize.height);
    final overlayPath = Path()..addRect(Rect.fromLTWH(0, 0, size.width, size.height));
    overlayPath.addRRect(RRect.fromRectXY(rect, 20, 20));
    canvas.drawPath(
      Path.combine(PathOperation.difference, overlayPath,
          Path()..addRRect(RRect.fromRectXY(rect, 20, 20))),
      paint,
    );

    final borderPaint = Paint()
      ..color = Colors.white70
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawRRect(RRect.fromRectXY(rect, 20, 20), borderPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
