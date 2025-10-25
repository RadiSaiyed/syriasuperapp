import 'package:flutter/material.dart';

import '../api.dart';

class CashInboxScreen extends StatefulWidget {
  final ApiClient api;
  const CashInboxScreen({super.key, required this.api});

  @override
  State<CashInboxScreen> createState() => _CashInboxScreenState();
}

class _CashInboxScreenState extends State<CashInboxScreen> {
  bool _loading = true;
  List<dynamic> _my = [];
  List<dynamic> _incoming = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final res = await widget.api.listCashRequests();
      setState(() {
        _my = (res['my'] as List?) ?? [];
        _incoming = (res['incoming'] as List?) ?? [];
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cash Requests'), actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                const ListTile(title: Text('Incoming (Agent)', style: TextStyle(fontWeight: FontWeight.bold))),
                ..._incoming.map((r) => _Tile(api: widget.api, data: r, isIncoming: true, onChanged: _load)),
                const Divider(height: 24),
                const ListTile(title: Text('My Requests', style: TextStyle(fontWeight: FontWeight.bold))),
                ..._my.map((r) => _Tile(api: widget.api, data: r, isIncoming: false, onChanged: _load)),
                const SizedBox(height: 24),
              ],
            ),
    );
  }
}

class _Tile extends StatelessWidget {
  final ApiClient api;
  final Map<String, dynamic> data;
  final bool isIncoming;
  final VoidCallback onChanged;
  const _Tile({required this.api, required this.data, required this.isIncoming, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final id = data['id'] as String? ?? '';
    final type = data['type'] as String? ?? '';
    final amt = data['amount_cents'] as int? ?? 0;
    final status = data['status'] as String? ?? '';
    final other = isIncoming ? data['user_phone'] : (data['agent_phone'] ?? '-');
    return ListTile(
      title: Text('${type.toUpperCase()} — ${isIncoming ? 'User' : 'Agent'}: $other'),
      subtitle: Text('Amount: $amt — $status'),
      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
        if (isIncoming && status == 'pending')
          IconButton(
            icon: const Icon(Icons.check_circle, color: Colors.green),
            onPressed: () async {
              try {
                await api.acceptCashRequest(id);
                onChanged();
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
              }
            },
          ),
        if (isIncoming && status == 'pending')
          IconButton(
            icon: const Icon(Icons.cancel, color: Colors.red),
            onPressed: () async {
              try {
                await api.rejectCashRequest(id);
                onChanged();
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
              }
            },
          ),
        if (!isIncoming && status == 'pending')
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: () async {
              try {
                await api.cancelCashRequest(id);
                onChanged();
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
              }
            },
          ),
      ]),
    );
  }
}

