import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api.dart';
import '../security/auth_gate.dart';

class TransferScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback? onDone;
  final String? initialPhone;
  const TransferScreen({super.key, required this.api, this.onDone, this.initialPhone});

  @override
  State<TransferScreen> createState() => _TransferScreenState();
}

class _TransferScreenState extends State<TransferScreen> {
  final _phoneCtrl = TextEditingController();
  final _amountCtrl = TextEditingController(text: '1000');
  final _memoCtrl = TextEditingController();
  bool _loading = false;
  bool _cancelRequested = false;
  int? _perTxnMax;
  static const int _feesBps = int.fromEnvironment('FEES_PCT_BPS', defaultValue: 100); // 1% default
  static const int _feesFixed = int.fromEnvironment('FEES_FIXED_CENTS', defaultValue: 0);
  final _uuid = const Uuid();

  @override
  void initState() {
    super.initState();
    if (widget.initialPhone != null) _phoneCtrl.text = widget.initialPhone!;
    // Load limits
    widget.api.limitsSummary().then((m) { if (mounted) setState(() => _perTxnMax = (m?['per_txn_max_cents'] as int?) ); });
  }

  Future<void> _send() async {
    final phone = _phoneCtrl.text.trim();
    final amount = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    if (phone.isEmpty || amount <= 0) return;
    if (_perTxnMax != null && amount > _perTxnMax!) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Amount exceeds per‑transaction limit ($_perTxnMax)')));
      return;
    }
    final ok = await AuthGate.verifyForAction(context, reason: 'Send transfer');
    if (!ok) return;
    setState(() { _loading = true; _cancelRequested = false; });
    try {
      final res = await widget.api.transfer(
        toPhone: phone,
        amountCents: amount,
        idempotencyKey: 'p2p-${_uuid.v4()}',
        memo: _memoCtrl.text.trim().isEmpty ? null : _memoCtrl.text.trim(),
      );
      if (mounted && !_cancelRequested) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Sent ${res['amount_cents']}')));
        widget.onDone?.call();
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted && !_cancelRequested) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Send transfer')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          TextField(controller: _phoneCtrl, decoration: const InputDecoration(labelText: 'To phone (+963...)')),
          const SizedBox(height: 12),
          TextField(
              controller: _amountCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Amount (cents)')),
          const SizedBox(height: 8),
          TextField(controller: _memoCtrl, decoration: const InputDecoration(labelText: 'Memo (optional)')),
          const SizedBox(height: 8),
          Builder(builder: (context) {
            final amt = int.tryParse(_amountCtrl.text.trim()) ?? 0;
            final fee = (amt * _feesBps ~/ 10000) + _feesFixed;
            final total = amt + fee;
            return Align(alignment: Alignment.centerLeft, child: Text('Fees: $fee  •  Total debited: $total'));
          }),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: FilledButton(onPressed: _loading ? null : _send, child: const Text('Send'))),
            if (_loading) ...[
              const SizedBox(width: 12),
              OutlinedButton(onPressed: () { setState(() => _cancelRequested = true); }, child: const Text('Cancel')),
            ]
          ]),
          if (_loading) const Padding(padding: EdgeInsets.only(top: 16), child: LinearProgressIndicator()),
        ]),
      ),
    );
  }
}
