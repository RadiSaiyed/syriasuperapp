import 'package:flutter/material.dart';

import '../api.dart';
import '../security/auth_gate.dart';

class CashScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback onChanged;
  const CashScreen({super.key, required this.api, required this.onChanged});

  @override
  State<CashScreen> createState() => _CashScreenState();
}

class _CashScreenState extends State<CashScreen> {
  final _inCtrl = TextEditingController(text: '10000');
  final _outCtrl = TextEditingController(text: '10000');
  bool _loading = false;

  Future<void> _reqIn() async {
    final amt = int.tryParse(_inCtrl.text.trim()) ?? 0;
    if (amt <= 0) return;
    setState(() => _loading = true);
    try {
      await widget.api.createCashIn(amountCents: amt);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cash-in requested')));
      widget.onChanged();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _reqOut() async {
    final amt = int.tryParse(_outCtrl.text.trim()) ?? 0;
    if (amt <= 0) return;
    final ok = await AuthGate.verifyForAction(context, reason: 'Request cash-out');
    if (!ok) return;
    setState(() => _loading = true);
    try {
      await widget.api.createCashOut(amountCents: amt);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cash-out requested')));
      widget.onChanged();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cash In / Out')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Cash-In', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _inCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (cents)'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading ? null : _reqIn, child: const Text('Request')),
          ]),
          const SizedBox(height: 24),
          const Text('Cash-Out', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _outCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (cents)'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading ? null : _reqOut, child: const Text('Request')),
          ]),
          if (_loading) const Padding(padding: EdgeInsets.only(top: 16), child: LinearProgressIndicator()),
        ]),
      ),
    );
  }
}
