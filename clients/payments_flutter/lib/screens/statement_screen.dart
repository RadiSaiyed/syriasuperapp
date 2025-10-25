import 'package:flutter/material.dart';
import '../api.dart';

class StatementScreen extends StatefulWidget {
  final ApiClient api;
  const StatementScreen({super.key, required this.api});
  @override
  State<StatementScreen> createState() => _StatementScreenState();
}

class _StatementScreenState extends State<StatementScreen> {
  final _fromCtrl = TextEditingController();
  final _toCtrl = TextEditingController();
  bool _loading = false;
  Map<String, dynamic>? _data;
  String? _err;

  Future<void> _load() async {
    setState(() { _loading = true; _err = null; });
    try {
      final d = await widget.api.merchantStatement(fromIso: _fromCtrl.text.isEmpty ? null : _fromCtrl.text.trim(), toIso: _toCtrl.text.isEmpty ? null : _toCtrl.text.trim());
      setState(() { _data = d; });
    } catch (e) { setState(() { _err = '$e'; }); }
    finally { setState(() { _loading = false; }); }
  }

  @override
  void initState() { super.initState(); _load(); }

  @override
  Widget build(BuildContext context) {
    final rows = (_data?['rows'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('Merchant Statement')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: TextField(controller: _fromCtrl, decoration: const InputDecoration(labelText: 'From ISO (optional)'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _toCtrl, decoration: const InputDecoration(labelText: 'To ISO (optional)'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading ? null : _load, child: const Text('Refresh')),
          ]),
          if (_err != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_err!, style: const TextStyle(color: Colors.red))),
          const SizedBox(height: 12),
          if (_data != null) Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Gross: ${_data!['gross_cents']}'),
              Text('Fees: ${_data!['fees_cents']}'),
              Text('Net: ${_data!['net_cents']}'),
            ],
          ),
          const SizedBox(height: 12),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: rows.length,
            separatorBuilder: (_, __) => const Divider(height:1),
            itemBuilder: (context, i) {
              final r = rows[i] as Map<String, dynamic>;
              return ListTile(
                dense: true,
                title: Text('${r['direction']} ${r['amount_cents']} ${r['currency_code']}'),
                subtitle: Text(r['created_at'] ?? ''),
                trailing: Text(r['transfer_id'] ?? ''),
              );
            },
          ),
          if (_loading) const Padding(padding: EdgeInsets.only(top: 8), child: LinearProgressIndicator()),
        ]),
      ),
    );
  }
}

