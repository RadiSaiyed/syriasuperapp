import 'package:flutter/material.dart';
import 'package:shared_core/shared_core.dart';
import '../services.dart';

class OutboxScreen extends StatefulWidget {
  const OutboxScreen({super.key});
  @override
  State<OutboxScreen> createState() => _OutboxScreenState();
}

class _OutboxScreenState extends State<OutboxScreen> {
  final Map<String, List<OfflineQueuedRequest>> _items = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final map = <String, List<OfflineQueuedRequest>>{};
    for (final svc in ServiceConfig.services) {
      final q = OfflineRequestQueue(svc);
      final items = await q.load();
      if (items.isNotEmpty) {
        map[svc] = items;
      }
    }
    if (!mounted) return;
    setState(() { _items
      ..clear()
      ..addAll(map); _loading = false; });
  }

  Future<void> _flushService(String service) async {
    final client = SharedHttpClient(
      service: service,
      baseUrl: ServiceConfig.baseUrl(service),
      tokenProvider: (svc) => MultiTokenStore().get(svc),
      connectivity: ConnectivityService(),
    );
    await flushOfflineQueue(client);
    client.close();
    await _load();
  }

  Future<void> _flushAll() async {
    for (final svc in List<String>.from(_items.keys)) {
      await _flushService(svc);
    }
  }

  Future<void> _sendOne(String service, int index) async {
    final queue = OfflineRequestQueue(service);
    final items = await queue.load();
    if (index < 0 || index >= items.length) return;
    final it = items[index];
    final client = SharedHttpClient(
      service: service,
      baseUrl: ServiceConfig.baseUrl(service),
      tokenProvider: (svc) => MultiTokenStore().get(svc),
      connectivity: ConnectivityService(),
    );
    try {
      await client.send(CoreHttpRequest(
        method: it.method,
        path: it.path,
        body: it.bodyText,
        options: RequestOptions(
          queryParameters: it.query,
          idempotent: true,
          idempotencyKey: it.idempotencyKey,
          attachAuthHeader: true,
          expectValidationErrors: it.expectValidationErrors,
          headers: it.contentType == null ? null : {'Content-Type': it.contentType!},
        ),
      ));
      await queue.removeAt(index);
      await OfflineQueueHistoryStore().appendFromQueued(service, it, 'sent');
    } on CoreError catch (e) {
      // On non-retriable errors, drop; on retriable keep
      if (!e.isRetriable) {
        await queue.removeAt(index);
        await OfflineQueueHistoryStore().appendFromQueued(service, it, 'removed');
      }
    } finally {
      client.close();
      await _load();
    }
  }

  Future<void> _deleteOne(String service, int index) async {
    final queue = OfflineRequestQueue(service);
    final items = await queue.load();
    if (index >= 0 && index < items.length) {
      await OfflineQueueHistoryStore().appendFromQueued(service, items[index], 'removed');
      await queue.removeAt(index);
    }
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ausstehende Vorgänge'),
        actions: [
          IconButton(onPressed: _loading ? null : _load, icon: const Icon(Icons.refresh)),
          TextButton(onPressed: _loading || _items.isEmpty ? null : _flushAll, child: const Text('Alle senden')),
          TextButton(onPressed: _showHistory, child: const Text('Historie')),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? const Center(child: Text('Keine ausstehenden Vorgänge'))
              : ListView(
                  padding: const EdgeInsets.all(12),
                  children: _items.entries.map((e) {
                    final service = e.key;
                    final items = e.value;
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Row(children: [
                              _serviceAvatar(service),
                              const SizedBox(width: 8),
                              Expanded(child: Text('$service • ${items.length} Vorgänge', style: const TextStyle(fontWeight: FontWeight.w600))),
                              TextButton(onPressed: () => _flushService(service), child: const Text('Alle senden')),
                            ]),
                            const SizedBox(height: 6),
                            for (var idx = 0; idx < items.length; idx++)
                              ListTile(
                                dense: true,
                                leading: _serviceAvatar(service),
                                title: Text('${items[idx].method.toUpperCase()} ${items[idx].path}${_fmtQuery(items[idx].query)}'),
                                subtitle: Text(_fmtMeta(items[idx])),
                                trailing: Wrap(spacing: 8, children: [
                                  IconButton(
                                    tooltip: 'Senden',
                                    icon: const Icon(Icons.send_outlined),
                                    onPressed: () => _sendOne(service, idx),
                                  ),
                                  IconButton(
                                    tooltip: 'Entfernen',
                                    icon: const Icon(Icons.delete_outline),
                                    onPressed: () => _deleteOne(service, idx),
                                  ),
                                ]),
                              ),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                ),
    );
  }

  String _fmtQuery(Map<String, String>? q) {
    if (q == null || q.isEmpty) return '';
    final parts = q.entries
        .map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    return '?$parts';
  }

  String _fmtMeta(OfflineQueuedRequest it) {
    final ts = it.createdAt;
    String when = '';
    if (ts != null) {
      try {
        final dt = DateTime.parse(ts).toLocal();
        when = ' • ${dt.toIso8601String()}';
      } catch (_) {}
    }
    String body = '';
    if (it.bodyText != null && it.bodyText!.isNotEmpty) {
      final snippet = it.bodyText!.length > 140 ? it.bodyText!.substring(0, 140) + '…' : it.bodyText!;
      body = ' • body: $snippet';
    }
    final key = it.idempotencyKey != null && it.idempotencyKey!.isNotEmpty ? ' • key: ${it.idempotencyKey}' : '';
    return 'queued$when$key$body';
  }

  Future<void> _showHistory() async {
    final store = OfflineQueueHistoryStore();
    final entries = await store.load();
    if (!mounted) return;
    if (!mounted) return;
    String? svcFilter;
    String actionFilter = 'all';
    showDialog(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setDlg) {
        final allServices = <String>{...entries.map((e) => e.service)}.toList()..sort();
        final filtered = entries.where((e) {
          final svcOk = svcFilter == null || e.service == svcFilter;
          final actOk = actionFilter == 'all' || e.action == actionFilter;
          return svcOk && actOk;
        }).toList();
        return AlertDialog(
          title: const Text('Outbox‑Historie'),
          content: SizedBox(
            width: 520,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(children: [
                  const Text('Service:'),
                  const SizedBox(width: 8),
                  DropdownButton<String?>(
                    value: svcFilter,
                    items: [
                      const DropdownMenuItem(value: null, child: Text('Alle')),
                      ...allServices.map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    ],
                    onChanged: (v) => setDlg(() => svcFilter = v),
                  ),
                  const SizedBox(width: 16),
                  const Text('Aktion:'),
                  const SizedBox(width: 8),
                  DropdownButton<String>(
                    value: actionFilter,
                    items: const [
                      DropdownMenuItem(value: 'all', child: Text('Alle')),
                      DropdownMenuItem(value: 'sent', child: Text('Gesendet')),
                      DropdownMenuItem(value: 'removed', child: Text('Entfernt')),
                    ],
                    onChanged: (v) => setDlg(() => actionFilter = v ?? 'all'),
                  ),
                ]),
                const SizedBox(height: 8),
                if (filtered.isEmpty) const Text('Keine Historie') else SizedBox(
                  height: 360,
                  child: ListView.builder(
                    itemCount: filtered.length,
                    itemBuilder: (_, i) {
                      final e = filtered[i];
                      final ts = e.at ?? '';
                      final q = e.query == null || e.query!.isEmpty ? '' : ' ${e.query}';
                      return ListTile(
                        dense: true,
                        leading: _serviceAvatar(e.service),
                        title: Text('${e.method.toUpperCase()} ${e.path}$q'),
                        subtitle: Text(_fmtHistoryMeta(ts, e.idempotencyKey, e.bodyPreview)),
                        trailing: _actionBadge(e.action),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () async { await store.clear(); if (context.mounted) Navigator.pop(context); },
              child: const Text('Leeren'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Schließen'),
            ),
          ],
        );
      }),
    );
  }

  String _fmtHistoryMeta(String ts, String? key, String? preview) {
    final b = StringBuffer();
    if (ts.isNotEmpty) b.write(ts);
    if (key != null && key.isNotEmpty) b.write(b.isEmpty ? 'key: $key' : ' • key: $key');
    if (preview != null && preview.isNotEmpty) b.write(b.isEmpty ? 'body: $preview' : ' • body: $preview');
    return b.isEmpty ? '' : b.toString();
  }

  Widget _actionBadge(String action) {
    final sent = action == 'sent';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: sent ? Colors.green.withValues(alpha: 0.2) : Colors.red.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: sent ? Colors.green : Colors.red, width: 0.6),
      ),
      child: Text(sent ? 'Gesendet' : 'Entfernt', style: TextStyle(color: sent ? Colors.green : Colors.red, fontSize: 11)),
    );
  }

  Widget _serviceAvatar(String service) {
    final icon = _serviceIcon(service);
    final color = _serviceColor(service);
    return CircleAvatar(
      radius: 14,
      backgroundColor: color.withValues(alpha: 0.15),
      child: Icon(icon, color: color, size: 16),
    );
  }

  IconData _serviceIcon(String s) {
    switch (s) {
      case 'payments': return Icons.account_balance_wallet_outlined;
      case 'taxi': return Icons.local_taxi;
      case 'food': return Icons.fastfood_outlined;
      case 'commerce': return Icons.storefront_outlined;
      case 'utilities': return Icons.bolt_outlined;
      case 'doctors': return Icons.medical_services_outlined;
      case 'bus': return Icons.directions_bus_filled_outlined;
      case 'stays': return Icons.hotel_outlined;
      case 'jobs': return Icons.work_outline;
      case 'chat': return Icons.chat_bubble_outline;
      case 'freight': return Icons.local_shipping_outlined;
      case 'carmarket': return Icons.directions_car_filled_outlined;
      default: return Icons.apps;
    }
  }

  Color _serviceColor(String s) {
    switch (s) {
      case 'payments': return const Color(0xFF64D2FF);
      case 'taxi': return const Color(0xFFFFC107);
      case 'food': return const Color(0xFFE91E63);
      case 'commerce': return const Color(0xFF9C27B0);
      case 'utilities': return const Color(0xFF00BCD4);
      case 'doctors': return const Color(0xFF4CAF50);
      case 'bus': return const Color(0xFF3F51B5);
      case 'stays': return const Color(0xFF795548);
      case 'jobs': return const Color(0xFFFF9800);
      case 'chat': return const Color(0xFF03A9F4);
      case 'freight': return const Color(0xFF607D8B);
      case 'carmarket': return const Color(0xFF8BC34A);
      default: return const Color(0xFF90A4AE);
    }
  }
}
