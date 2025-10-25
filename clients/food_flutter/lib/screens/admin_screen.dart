import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:intl/intl.dart';

import '../api.dart';

class AdminScreen extends StatefulWidget {
  final ApiClient api;
  const AdminScreen({super.key, required this.api});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  String? _selectedRestaurantId;
  Future<List<Map<String, dynamic>>>? _ordersFuture;
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
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          FutureBuilder<List<Map<String, dynamic>>>(
            future: widget.api.listRestaurants(),
            builder: (context, snap) {
              final restaurants = snap.data ?? const [];
              return DropdownButton<String>(
                value: _selectedRestaurantId,
                hint: const Text('Select restaurant'),
                items: restaurants.map((r) => DropdownMenuItem(value: r['id'] as String, child: Text(r['name'] as String))).toList(),
                onChanged: (v) => setState(() => _selectedRestaurantId = v),
              );
            },
          ),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: _selectedRestaurantId == null ? null : () async {
              try { await widget.api.adminBecomeOwner(_selectedRestaurantId!); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Linked as owner'))); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()))); }
            },
            child: const Text('Become Owner (dev)'),
          ),
          const Spacer(),
          FilledButton(
            onPressed: () => setState(() => _ordersFuture = widget.api.adminListOrders()),
            child: const Text('Refresh Orders'),
          )
        ]),
      ),
      const Divider(height: 1),
      Expanded(
        child: _ordersFuture == null
            ? const Center(child: Text('No orders yet'))
            : FutureBuilder<List<Map<String, dynamic>>>(
                future: _ordersFuture,
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
                        onTap: () async { await _showStatusDialog(o); },
                        trailing: reqId != null ? IconButton(onPressed: () async { final uri = Uri.parse('payments://request/$reqId'); try { await launchUrl(uri); } catch (_) {} }, icon: const Icon(Icons.open_in_new)) : null,
                      );
                    },
                  );
                },
              ),
      ),
    ]);
  }

  Future<void> _showStatusDialog(Map<String, dynamic> order) async {
    final statuses = <String>[];
    switch (order['status']) {
      case 'created': statuses.addAll(['accepted','canceled']); break;
      case 'accepted': statuses.addAll(['preparing','canceled']); break;
      case 'preparing': statuses.addAll(['out_for_delivery','canceled']); break;
      case 'out_for_delivery': statuses.addAll(['delivered','canceled']); break;
      default: break;
    }
    if (statuses.isEmpty) return;
    final sel = await showDialog<String>(context: context, builder: (_) => SimpleDialog(title: const Text('Update status'), children: [for (final s in statuses) SimpleDialogOption(onPressed: () => Navigator.pop(context, s), child: Text(s))]));
    if (sel == null) return;
    try {
      await widget.api.adminUpdateOrderStatus(orderId: order['id'] as String, statusValue: sel);
      setState(() => _ordersFuture = widget.api.adminListOrders());
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }
}
