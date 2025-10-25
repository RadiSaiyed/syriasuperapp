import 'package:flutter/material.dart';
import '../api.dart';

class SubscriptionsScreen extends StatefulWidget {
  final ApiClient api;
  const SubscriptionsScreen({super.key, required this.api});

  @override
  State<SubscriptionsScreen> createState() => _SubscriptionsScreenState();
}

class _SubscriptionsScreenState extends State<SubscriptionsScreen> {
  final _merchantPhoneCtrl = TextEditingController();
  final _amountCtrl = TextEditingController(text: '2000');
  final _intervalCtrl = TextEditingController(text: '30');
  bool _loading = true;
  List<dynamic> _rows = [];
  String? _msg;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() { _loading = true; });
    try { final r = await widget.api.listSubscriptions(); setState(() { _rows = r; }); }
    catch (e) { if (mounted) setState(() { _msg = '$e'; }); }
    finally { if (mounted) setState(() { _loading = false; }); }
  }

  Future<void> _create() async {
    final phone = _merchantPhoneCtrl.text.trim();
    final amount = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    final days = int.tryParse(_intervalCtrl.text.trim()) ?? 30;
    if (phone.isEmpty || amount <= 0) return;
    setState(() { _loading = true; _msg = null; });
    try { await widget.api.createSubscription(merchantPhone: phone, amountCents: amount, intervalDays: days); await _load(); _msg = 'Created'; }
    catch (e) { if (mounted) setState(() { _msg = '$e'; }); }
    finally { if (mounted) setState(() { _loading = false; }); }
  }

  Future<void> _cancel(String id) async { setState(() { _loading = true; }); try { await widget.api.cancelSubscription(id); await _load(); } finally { if (mounted) setState(() { _loading = false; }); } }
  Future<void> _devCharge(String id) async { setState(() { _loading = true; }); try { await widget.api.devForceDue(id); await widget.api.processDue(); await _load(); } finally { if (mounted) setState(() { _loading = false; }); } }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Subscriptions')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Create', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          TextField(controller: _merchantPhoneCtrl, decoration: const InputDecoration(labelText: 'Merchant phone +963...')),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (cents)'))),
            const SizedBox(width: 8),
            SizedBox(width: 120, child: TextField(controller: _intervalCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Days'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading ? null : _create, child: const Text('Create')),
          ]),
          if (_msg != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_msg!)),
          const SizedBox(height: 16),
          const Text('Your Subscriptions', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          if (_loading) const LinearProgressIndicator(),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _rows.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final s = _rows[i] as Map<String, dynamic>;
              return ListTile(
                title: Text('${s['amount_cents']} — every ${s['interval_days']} days'),
                subtitle: Text('Status: ${s['status']}  Next: ${s['next_charge_at']}'),
                trailing: Wrap(spacing: 8, children: [
                  OutlinedButton(onPressed: () => _devCharge(s['id'] as String), child: const Text('Dev charge')),
                  FilledButton(onPressed: s['status'] == 'active' ? () => _cancel(s['id'] as String) : null, child: const Text('Cancel')),
                ]),
              );
            },
          ),
        ]),
      ),
    );
  }
}

