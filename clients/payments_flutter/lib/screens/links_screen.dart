import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../api.dart';

class LinksScreen extends StatefulWidget {
  final ApiClient api;
  const LinksScreen({super.key, required this.api});

  @override
  State<LinksScreen> createState() => _LinksScreenState();
}

class _LinksScreenState extends State<LinksScreen> {
  final _amountCtrl = TextEditingController();
  final _expiresCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  final _payAmountCtrl = TextEditingController();
  final _uuid = const Uuid();
  bool _loading = false;
  String? _createdCode;
  String? _msg;

  Future<void> _create() async {
    final amount = _amountCtrl.text.trim().isEmpty ? null : int.tryParse(_amountCtrl.text.trim());
    final expires = _expiresCtrl.text.trim().isEmpty ? null : int.tryParse(_expiresCtrl.text.trim());
    setState(() { _loading = true; _msg = null; });
    try {
      final res = await widget.api.createLink(amountCents: amount, expiresInMinutes: expires);
      setState(() { _createdCode = res['code'] as String?; _msg = 'Link created'; });
    } catch (e) { if (mounted) setState(() { _msg = '$e'; }); }
    finally { if (mounted) setState(() { _loading = false; }); }
  }

  Future<void> _pay() async {
    final code = _codeCtrl.text.trim();
    if (code.isEmpty) return;
    final amount = _payAmountCtrl.text.trim().isEmpty ? null : int.tryParse(_payAmountCtrl.text.trim());
    setState(() { _loading = true; _msg = null; });
    try {
      final res = await widget.api.payLink(code: code, idempotencyKey: 'link-${_uuid.v4()}', amountCents: amount);
      setState(() { _msg = 'Paid ${res['status']}'; });
    } catch (e) { if (mounted) setState(() { _msg = '$e'; }); }
    finally { if (mounted) setState(() { _loading = false; }); }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment Links')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Create Link', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          TextField(controller: _amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (cents, leave empty for static)')),
          const SizedBox(height: 8),
          TextField(controller: _expiresCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Expires in minutes (optional)')),
          const SizedBox(height: 8),
          FilledButton(onPressed: _loading ? null : _create, child: const Text('Create')),
          if (_createdCode != null) ...[
            const SizedBox(height: 8),
            SelectableText('Code: $_createdCode')
          ],
          const SizedBox(height: 24),
          const Text('Pay Link', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          TextField(controller: _codeCtrl, decoration: const InputDecoration(labelText: 'LINK:v1;code=...')),
          const SizedBox(height: 8),
          TextField(controller: _payAmountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (required for static)')),
          const SizedBox(height: 8),
          FilledButton(onPressed: _loading ? null : _pay, child: const Text('Pay')),
          if (_msg != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_msg!)),
          if (_loading) const Padding(padding: EdgeInsets.only(top: 8), child: LinearProgressIndicator()),
        ]),
      ),
    );
  }
}

