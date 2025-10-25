import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../api.dart';
import 'qr_scan_screen.dart';

class VouchersScreen extends StatefulWidget {
  final ApiClient api;
  const VouchersScreen({super.key, required this.api});
  @override
  State<VouchersScreen> createState() => _VouchersScreenState();
}

class _VouchersScreenState extends State<VouchersScreen> {
  final _amountCtrl = TextEditingController(text: '100');
  final _codeCtrl = TextEditingController();
  bool _loading = false;
  String? _lastCode;
  String? _lastQrText;
  List<Map<String, dynamic>> _items = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.listVouchers();
      setState(() => _items = rows);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final amt = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    if (amt <= 0) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Invalid amount')));
      return;
    }
    setState(() => _loading = true);
    try {
      final v = await widget.api.createVoucher(amountSyp: amt);
      setState(() { _lastCode = v['code'] as String?; _lastQrText = v['qr_text'] as String?; });
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _redeem([String? code]) async {
    final c = (code ?? _codeCtrl.text).trim();
    if (c.isEmpty) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter voucher code')));
      return;
    }
    setState(() => _loading = true);
    try {
      await widget.api.redeemVoucher(code: c);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Redeemed')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _scanVoucher() async {
    final code = await Navigator.of(context).push<String>(MaterialPageRoute(builder: (_) => const QrScanScreen()));
    if (code == null || code.isEmpty) return;
    // Expect format VCHR|<code>
    final parts = code.split('|');
    final parsed = parts.length == 2 && parts[0] == 'VCHR' ? parts[1] : code;
    _codeCtrl.text = parsed;
    await _redeem(parsed);
  }

  @override
  void initState() { super.initState(); _load(); }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Expanded(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text('Top-up via Voucher', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Create Voucher (for Cash Top-up)'),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(child: TextField(controller: _amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (SYP)'))),
                    const SizedBox(width: 8),
                    FilledButton(onPressed: _create, child: const Text('Create')),
                  ]),
                  if (_lastQrText != null) ...[
                    const SizedBox(height: 12),
                    Center(child: QrImageView(data: _lastQrText!, size: 200)),
                    const SizedBox(height: 8),
                    SelectableText(_lastQrText!),
                    if (_lastCode != null) SelectableText('Code: ${_lastCode!}'),
                  ]
                ]),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Redeem Voucher'),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(child: TextField(controller: _codeCtrl, decoration: const InputDecoration(labelText: 'Voucher code'))),
                    const SizedBox(width: 8),
                    OutlinedButton.icon(onPressed: _scanVoucher, icon: const Icon(Icons.qr_code_scanner), label: const Text('Scan')),
                    const SizedBox(width: 8),
                    FilledButton(onPressed: () => _redeem(), child: const Text('Redeem')),
                  ]),
                ]),
              ),
            ),
            const SizedBox(height: 12),
            const Text('My Vouchers', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            ..._items.map((v) => ListTile(
              title: Text('${v['amount_syp'] ?? ((v['amount_cents'] ?? 0) / 100).round()} ${v['currency_code']}'),
              subtitle: Text('Code: ${v['code']}\nStatus: ${v['status']}\nCreated: ${v['created_at'] ?? ''}'),
              trailing: v['status'] == 'active' && v['qr_text'] != null
                  ? IconButton(icon: const Icon(Icons.qr_code), onPressed: () => _showQr(v['qr_text'] as String))
                  : null,
            )),
          ],
        ),
      )
    ]);
  }

  Future<void> _showQr(String qrText) async {
    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Voucher QR'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          QrImageView(data: qrText, size: 200),
          const SizedBox(height: 8),
          SelectableText(qrText),
        ]),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
      ),
    );
  }
}
