import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

/// QR scanning placeholder for Simulator and builds without camera scanning.
/// Provides manual input to keep flows working.
class QrScanScreen extends StatefulWidget {
  const QrScanScreen({super.key});

  @override
  State<QrScanScreen> createState() => _QrScanScreenState();
}

class _QrScanScreenState extends State<QrScanScreen> {
  final TextEditingController _manualCtrl = TextEditingController();
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.normal,
    formats: [BarcodeFormat.qrCode],
    torchEnabled: false,
  );
  bool _useManual = false;
  String? _cameraError;

  @override
  void dispose() {
    _controller.dispose();
    _manualCtrl.dispose();
    super.dispose();
  }

  void _submit() {
    final value = _manualCtrl.text.trim();
    Navigator.of(context).pop(value.isEmpty ? null : value);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan QR'),
        actions: [
          if (!_useManual && _cameraError == null)
            IconButton(
              tooltip: 'Toggle Flash',
              icon: const Icon(Icons.flash_on),
              onPressed: () => _controller.toggleTorch(),
            ),
          IconButton(
            tooltip: _useManual ? 'Use Camera' : 'Manual Input',
            icon: Icon(_useManual ? Icons.photo_camera : Icons.keyboard),
            onPressed: () => setState(() => _useManual = !_useManual),
          ),
        ],
      ),
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 200),
        child: (_useManual || _cameraError != null)
            ? _buildManual()
            : _buildScanner(),
      ),
    );
  }

  Widget _buildScanner() {
    return Stack(
      fit: StackFit.expand,
      children: [
        MobileScanner(
          controller: _controller,
          onDetect: (capture) {
            for (final b in capture.barcodes) {
              final v = b.rawValue;
              if (v != null && v.isNotEmpty) {
                Navigator.of(context).pop(v);
                break;
              }
            }
          },
          errorBuilder: (context, error) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) setState(() => _cameraError = error.toString());
            });
            return _buildManual(hint:
                'Camera not available. You can still enter the code manually.');
          },
        ),
        // Simple center guide
        IgnorePointer(
          child: Center(
            child: Container(
              width: 240,
              height: 240,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white70, width: 2),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildManual({String? hint}) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.qr_code_rounded, size: 80, color: Colors.grey),
          const SizedBox(height: 16),
          Text(
            hint ?? 'Enter the QR code manually if scanning is unavailable.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _manualCtrl,
            decoration: const InputDecoration(labelText: 'Enter code manually'),
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _submit(),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _submit, child: const Text('Apply')),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }
}
