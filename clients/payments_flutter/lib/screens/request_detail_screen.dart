import 'package:flutter/material.dart';
import '../api.dart';

class RequestDetailScreen extends StatefulWidget {
  final ApiClient api;
  final String requestId;
  const RequestDetailScreen({super.key, required this.api, required this.requestId});

  @override
  State<RequestDetailScreen> createState() => _RequestDetailScreenState();
}

class _RequestDetailScreenState extends State<RequestDetailScreen> {
  bool _loading = true;
  Map<String, dynamic>? _req;
  String? _myPhone;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final r = await widget.api.getRequest(widget.requestId);
      final w = await widget.api.getWallet();
      setState(() { _req = r; _myPhone = (w['user'] as Map<String,dynamic>)['phone'] as String?; });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  bool get _iAmTarget => _req != null && _myPhone != null && _req!['target_phone'] == _myPhone;
  bool get _iAmRequester => _req != null && _myPhone != null && _req!['requester_phone'] == _myPhone;

  Future<void> _accept() async { await widget.api.acceptRequest(widget.requestId); await _load(); }
  Future<void> _reject() async { await widget.api.rejectRequest(widget.requestId); await _load(); }
  Future<void> _cancel() async { await widget.api.cancelRequest(widget.requestId); await _load(); }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    final r = _req;
    if (r == null) return const Center(child: Text('Request not found'));
    return Scaffold(
      appBar: AppBar(title: const Text('Payment Request')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('ID: ${widget.requestId}'),
          const SizedBox(height: 8),
          Text('From: ${r['requester_phone']}'),
          Text('To:   ${r['target_phone']}'),
          const SizedBox(height: 8),
          Text('Amount: ${r['amount_cents']} cents'),
          Text('Status: ${r['status']}'),
          const SizedBox(height: 16),
          Wrap(spacing: 8, children: [
            if (_iAmTarget && r['status'] == 'pending')
              FilledButton(onPressed: _accept, child: const Text('Accept')),
            if (_iAmTarget && r['status'] == 'pending')
              OutlinedButton(onPressed: _reject, child: const Text('Reject')),
            if (_iAmRequester && r['status'] == 'pending')
              OutlinedButton(onPressed: _cancel, child: const Text('Cancel')),
          ]),
          const Spacer(),
          FilledButton(onPressed: _load, child: const Text('Refresh')),
        ]),
      ),
    );
  }
}

