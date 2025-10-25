import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

class ReceiveQrScreen extends StatefulWidget {
  final String phone;
  const ReceiveQrScreen({super.key, required this.phone});

  @override
  State<ReceiveQrScreen> createState() => _ReceiveQrScreenState();
}

class _ReceiveQrScreenState extends State<ReceiveQrScreen> {
  final _amountCtrl = TextEditingController();

  String _buildQrText() {
    final amtText = _amountCtrl.text.trim();
    final parts = <String>['P2P:v1', 'to=${widget.phone}'];
    if (amtText.isNotEmpty) {
      final amt = int.tryParse(amtText) ?? 0;
      if (amt > 0) parts.add('amount_cents=$amt');
    }
    return parts.join(';');
  }

  Future<void> _copy() async {
    await Clipboard.setData(ClipboardData(text: _buildQrText()));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('QR copied')));
  }

  Future<void> _share() async {
    await Share.share(_buildQrText(), subject: 'P2P Receive QR');
  }

  @override
  Widget build(BuildContext context) {
    final qrText = _buildQrText();
    return Scaffold(
      appBar: AppBar(title: const Text('Receive (P2P)')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('Show this QR to receive a P2P payment.'),
          const SizedBox(height: 12),
          TextField(
            controller: _amountCtrl,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Amount (cents, optional)'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 16),
          Center(child: QrImageView(data: qrText, size: 240)),
          const SizedBox(height: 8),
          SelectableText(qrText),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: OutlinedButton.icon(onPressed: _copy, icon: const Icon(Icons.copy), label: const Text('Copy'))),
            const SizedBox(width: 8),
            Expanded(child: OutlinedButton.icon(onPressed: _share, icon: const Icon(Icons.share), label: const Text('Share'))),
          ])
        ]),
      ),
    );
  }
}

