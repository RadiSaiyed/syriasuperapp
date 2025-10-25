import 'dart:io' show Platform;
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class QrScanScreen extends StatefulWidget {
  final String? title;
  final String? hint;
  const QrScanScreen({super.key, this.title, this.hint});
  @override
  State<QrScanScreen> createState() => _QrScanScreenState();
}

class _QrScanScreenState extends State<QrScanScreen> {
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
    facing: CameraFacing.back,
    torchEnabled: false,
  );
  bool _busy = false;
  final _manualCtrl = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    _manualCtrl.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) async {
    if (_busy) return;
    final codes = capture.barcodes.map((b) => b.rawValue).whereType<String>().toList();
    if (codes.isEmpty) return;
    setState(() => _busy = true);
    final code = codes.first;
    if (!mounted) return;
    Navigator.pop(context, code);
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.title ?? 'Scan QR';
    final hint = widget.hint ?? 'Enter the QR code manually if scanning is unavailable.';
    final onSim = !Platform.isIOS && !Platform.isAndroid;
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(children: [
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: onSim
                  ? _buildManual()
                  : MobileScanner(controller: _controller, onDetect: _onDetect),
            ),
          ),
          const SizedBox(height: 12),
          if (!onSim)
            Text(hint, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70)),
          const SizedBox(height: 8),
          _buildManual(),
        ]),
      ),
    );
  }

  Widget _buildManual() {
    return Row(children: [
      Expanded(child: TextField(controller: _manualCtrl, decoration: const InputDecoration(labelText: 'QR content (manual)'))),
      const SizedBox(width: 8),
      FilledButton(onPressed: _busy ? null : () => Navigator.pop(context, _manualCtrl.text.trim()), child: const Text('Use')),
    ]);
  }
}

