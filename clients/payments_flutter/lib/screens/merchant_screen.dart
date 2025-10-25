import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api.dart';
import 'qr_scan_screen.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import '../security/auth_gate.dart';

class MerchantScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback? onChanged;
  const MerchantScreen({super.key, required this.api, this.onChanged});

  @override
  State<MerchantScreen> createState() => _MerchantScreenState();
}

class _MerchantScreenState extends State<MerchantScreen> {
  bool _loading = false;
  final _uuid = const Uuid();
  final _amountCtrl = TextEditingController(text: '10000');
  String? _qrCodeText;
  String? _qrExpiry;
  final _payCodeCtrl = TextEditingController();
  bool _isMerchant = false;
  String _merchantStatus = 'none';
  int _kycLevel = 0;
  String _kycStatus = 'none';

  @override
  void initState() {
    super.initState();
    _loadStatus();
    _loadKyc();
  }

  Future<void> _loadStatus() async {
    try {
      final s = await widget.api.merchantStatus();
      if (mounted) {
        setState(() {
          _isMerchant = (s['is_merchant'] as bool?) ?? false;
          _merchantStatus = (s['merchant_status'] as String?) ?? 'none';
        });
      }
    } catch (_) {}
  }

  Future<void> _loadKyc() async {
    try {
      final r = await widget.api.getKyc();
      if (mounted) setState(() {
        _kycLevel = (r['kyc_level'] as int?) ?? 0;
        _kycStatus = (r['kyc_status'] as String?) ?? 'none';
      });
    } catch (_) {}
  }

  Future<void> _becomeMerchant() async {
    setState(() => _loading = true);
    try {
      await widget.api.devBecomeMerchant();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Merchant enabled')));
      widget.onChanged?.call();
      await _loadStatus();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _applyMerchant() async {
    setState(() => _loading = true);
    try {
      await widget.api.applyMerchant();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Application submitted')));
      await _loadStatus();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _createQr() async {
    final amount = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    if (amount <= 0) return;
    setState(() => _loading = true);
    try {
      final res = await widget.api.createQr(amountCents: amount);
      setState(() {
        _qrCodeText = res['code'] as String?;
        _qrExpiry = res['expires_at'] as String?;
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _copyQr() async {
    if (_qrCodeText == null || _qrCodeText!.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: _qrCodeText!));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('QR copied to clipboard')));
    }
  }

  Future<void> _shareQr() async {
    if (_qrCodeText == null || _qrCodeText!.isEmpty) return;
    await Share.share(_qrCodeText!, subject: 'Payment QR');
  }

  Future<void> _payQr() async {
    final code = _payCodeCtrl.text.trim();
    if (code.isEmpty) return;
    final ok = await AuthGate.verifyForAction(context, reason: 'Pay merchant');
    if (!ok) return;
    setState(() => _loading = true);
    try {
      final res = await widget.api.payQr(code: code, idempotencyKey: 'qr-${_uuid.v4()}');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Paid ${res['amount_cents']}')));
        widget.onChanged?.call();
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Merchant / QR')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Merchant status', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: Text('Status: ${_isMerchant ? 'approved' : _merchantStatus}')),
            if (!_isMerchant && _merchantStatus != 'applied')
              FilledButton(onPressed: _loading ? null : _applyMerchant, child: const Text('Apply')),
          ]),
          const SizedBox(height: 4),
          TextButton(onPressed: _loading ? null : _becomeMerchant, child: const Text('Dev: enable immediately')),
          const SizedBox(height: 8),
          Text('KYC: level $_kycLevel — $_kycStatus (Level 1 required for merchant QR)'),
          const SizedBox(height: 24),
          const Text('Create QR', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _amountCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Amount (cents)'),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading || _kycLevel < 1 ? null : _createQr, child: const Text('Generate')),
          ]),
          if (_qrCodeText != null) ...[
            const SizedBox(height: 8),
            Center(
              child: QrImageView(
                data: _qrCodeText!,
                size: 220,
                gapless: true,
              ),
            ),
            const SizedBox(height: 8),
            SelectableText('QR text: $_qrCodeText'),
            if (_qrExpiry != null) Text('Expires: $_qrExpiry'),
            const SizedBox(height: 8),
            Row(
              children: [
                OutlinedButton.icon(onPressed: _copyQr, icon: const Icon(Icons.copy), label: const Text('Copy')),
                const SizedBox(width: 8),
                OutlinedButton.icon(onPressed: _shareQr, icon: const Icon(Icons.share), label: const Text('Share')),
              ],
            ),
          ],
          const SizedBox(height: 24),
          const Text('Pay QR (manual input)', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _payCodeCtrl,
                decoration: const InputDecoration(hintText: 'PAY:v1;code=...'),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              onPressed: _loading
                  ? null
                  : () async {
                      final scanned = await Navigator.of(context).push<String>(
                        MaterialPageRoute(builder: (_) => const QrScanScreen()),
                      );
                      if (scanned != null && scanned.isNotEmpty) {
                        setState(() => _payCodeCtrl.text = scanned);
                      }
                    },
              icon: const Icon(Icons.qr_code_scanner),
              tooltip: 'Scan',
            ),
            FilledButton(onPressed: _loading ? null : _payQr, child: const Text('Pay')),
          ]),
          if (_loading) const Padding(padding: EdgeInsets.only(top: 16), child: LinearProgressIndicator()),
        ]),
      ),
    );
  }
}
