import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../api.dart';
import '../security/auth_gate.dart';
import '../ui/connectivity_banner.dart';
import '../ui/errors.dart';

class RequestsInboxScreen extends StatefulWidget {
  final ApiClient api;
  final String? focusRequestId;
  const RequestsInboxScreen({super.key, required this.api, this.focusRequestId});

  @override
  State<RequestsInboxScreen> createState() => _RequestsInboxScreenState();
}

class _RequestsInboxScreenState extends State<RequestsInboxScreen> {
  bool _loading = true;
  List<dynamic> _incoming = [];
  List<dynamic> _outgoing = [];
  String? _focus;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _focus = widget.focusRequestId;
    _load();
    _poll = Timer.periodic(const Duration(seconds: 10), (_) => _load());
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final res = await widget.api.listRequests();
      setState(() {
        _incoming = (res['incoming'] as List?) ?? [];
        _outgoing = (res['outgoing'] as List?) ?? [];
      });
    } catch (e) {
      if (mounted) showRetrySnack(context, '$e', _load);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Requests'), actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                const Padding(
                  padding: EdgeInsets.all(12.0),
                  child: ConnectivityBanner(),
                ),
                const ListTile(title: Text('Incoming', style: TextStyle(fontWeight: FontWeight.bold))),
                ..._incoming.map((r) => _RequestTile(api: widget.api, data: r, incoming: true, onChanged: _load, focusRequestId: widget.focusRequestId)),
                const Divider(height: 24),
                const ListTile(title: Text('Outgoing', style: TextStyle(fontWeight: FontWeight.bold))),
                ..._outgoing.map((r) => _RequestTile(api: widget.api, data: r, incoming: false, onChanged: _load, focusRequestId: widget.focusRequestId)),
                const SizedBox(height: 24),
              ],
            ),
    );
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }
}

class _RequestTile extends StatelessWidget {
  final ApiClient api;
  final Map<String, dynamic> data;
  final bool incoming;
  final VoidCallback onChanged;
  final String? focusRequestId;
  const _RequestTile({required this.api, required this.data, required this.incoming, required this.onChanged, this.focusRequestId});

  @override
  Widget build(BuildContext context) {
    final numFmt = NumberFormat.decimalPattern();
    final id = data['id'] as String? ?? '';
    final amount = data['amount_cents'] ?? 0;
    final status = data['status'] as String? ?? 'pending';
    final other = incoming ? data['requester_phone'] : data['target_phone'];
    final focused = (focusRequestId != null) && (data['id'] == focusRequestId);
    return ListTile(
      title: Text('${incoming ? 'From' : 'To'} $other'),
      subtitle: Text('Amount: ${numFmt.format((amount as int) / 100)} — $status${focused ? '  (link)' : ''}'),
      tileColor: focused ? Colors.yellow.shade100 : null,
      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
        if (status == 'pending' && incoming)
          IconButton(
            icon: const Icon(Icons.check_circle, color: Colors.green),
            tooltip: 'Accept',
            onPressed: () async {
              try {
                final ok = await AuthGate.verifyForAction(context, reason: 'Accept payment request');
                if (!ok) return;
                await api.acceptRequest(id);
                unawaited(api.audit('request_accept', {'id': id}));
                onChanged();
              } catch (e) {
                showRetrySnack(context, '$e', () async { await api.acceptRequest(id); onChanged(); });
              }
            },
          ),
        if (status == 'pending' && incoming)
          IconButton(
            icon: const Icon(Icons.cancel, color: Colors.red),
            tooltip: 'Reject',
            onPressed: () async {
              try {
                await api.rejectRequest(id);
                unawaited(api.audit('request_reject', {'id': id}));
                onChanged();
              } catch (e) {
                showRetrySnack(context, '$e', () async { await api.rejectRequest(id); onChanged(); });
              }
            },
          ),
        if (status == 'pending' && !incoming)
          IconButton(
            icon: const Icon(Icons.close),
            tooltip: 'Cancel',
            onPressed: () async {
              try {
                await api.cancelRequest(id);
                unawaited(api.audit('request_cancel', {'id': id}));
                onChanged();
              } catch (e) {
                showRetrySnack(context, '$e', () async { await api.cancelRequest(id); onChanged(); });
              }
            },
          ),
      ]),
    );
  }
}
