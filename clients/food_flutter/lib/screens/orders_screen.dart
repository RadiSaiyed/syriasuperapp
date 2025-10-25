import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:intl/intl.dart';

import '../api.dart';

class OrdersScreen extends StatefulWidget {
  final ApiClient api;
  const OrdersScreen({super.key, required this.api});

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  late Future<List<Map<String, dynamic>>> _future = widget.api.listOrders();
  final NumberFormat _fmt = NumberFormat.currency(locale: 'de_DE', symbol: 'SYP', decimalDigits: 2);
  Widget _statusChip(String status) {
    Color color;
    switch (status) {
      case 'accepted': color = Colors.blueAccent; break;
      case 'preparing': color = Colors.orange; break;
      case 'out_for_delivery': color = Colors.purple; break;
      case 'delivered': color = Colors.green; break;
      case 'canceled': color = Colors.redAccent; break;
      default: color = Colors.grey;
    }
    return Chip(backgroundColor: color.withOpacity(0.2), label: Text(status));
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => setState(() => _future = widget.api.listOrders()),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final orders = snap.data!;
          if (orders.isEmpty) return const Center(child: Text('No orders'));
          return ListView.separated(
            itemCount: orders.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final o = orders[i];
              final total = _fmt.format(((o['total_cents'] ?? 0) as int) / 100.0);
              final reqId = o['payment_request_id'] as String?;
              final s = (o['status'] as String?) ?? 'created';
              return ListTile(
                title: Text('Order #${(o['id'] ?? '').toString().substring(0,8)} — $total'),
                subtitle: _statusChip(s),
                trailing: Wrap(spacing: 8, children: [
                  if (reqId != null) FilledButton.icon(onPressed: () async { final uri = Uri.parse('payments://request/$reqId'); try { await launchUrl(uri); } catch (_) {} }, icon: const Icon(Icons.open_in_new), label: const Text('Open Payment')),
                  if (o['status'] == 'out_for_delivery') FilledButton(onPressed: () async {
                    try {
                      final t = await widget.api.getOrderTracking(o['id'] as String);
                      if (!mounted) return;
                      await showDialog(context: context, builder: (_) => AlertDialog(title: const Text('Tracking'), content: Text('Lat: ${t['lat']}, Lon: ${t['lon']},\nUpdated: ${t['updated_at'] ?? '-'}'), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))]));
                    } catch (e) {
                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                    }
                  }, child: const Text('Track')),
                ]),
              );
            },
          );
        },
      ),
    );
  }
}
