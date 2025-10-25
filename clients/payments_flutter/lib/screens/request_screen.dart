import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../api.dart';

class RequestScreen extends StatefulWidget {
  final ApiClient api;
  final String? initialPhone;
  const RequestScreen({super.key, required this.api, this.initialPhone});

  @override
  State<RequestScreen> createState() => _RequestScreenState();
}

class _RequestScreenState extends State<RequestScreen> {
  final _phoneCtrl = TextEditingController();
  final _amountCtrl = TextEditingController(text: '1000');
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialPhone != null) _phoneCtrl.text = widget.initialPhone!;
  }

  Future<void> _create() async {
    final phone = _phoneCtrl.text.trim();
    final amount = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    if (phone.isEmpty || amount <= 0) return;
    setState(() => _loading = true);
    try {
      await widget.api.createRequest(toPhone: phone, amountCents: amount);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Request sent')));
        Navigator.pop(context);
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
      appBar: AppBar(title: const Text('Request Payment')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          TextField(controller: _phoneCtrl, decoration: const InputDecoration(labelText: 'From phone (+963...)')),
          const SizedBox(height: 12),
          TextField(
            controller: _amountCtrl,
            decoration: const InputDecoration(labelText: 'Amount (cents)'),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _loading ? null : _create, child: const Text('Send Request')),
          if (_loading) const Padding(padding: EdgeInsets.only(top: 16), child: LinearProgressIndicator()),
        ]),
      ),
    );
  }
}

