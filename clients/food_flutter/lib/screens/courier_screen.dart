import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api.dart';

class CourierScreen extends StatefulWidget {
  final ApiClient api;
  const CourierScreen({super.key, required this.api});

  @override
  State<CourierScreen> createState() => _CourierScreenState();
}

class _CourierScreenState extends State<CourierScreen> {
  late Future<List<Map<String, dynamic>>> _availFuture = widget.api.courierAvailable();
  late Future<List<Map<String, dynamic>>> _mineFuture = widget.api.courierMyOrders();
  bool _simRunning = false;
  final NumberFormat _fmt = NumberFormat.currency(locale: 'de_DE', symbol: 'SYP', decimalDigits: 2);

  Future<void> _refresh() async {
    setState(() {
      _availFuture = widget.api.courierAvailable();
      _mineFuture = widget.api.courierMyOrders();
    });
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Column(children: [
        Row(children: [
          const SizedBox(width: 8),
          FilledButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
        ]),
        const TabBar(tabs: [Tab(text: 'Available'), Tab(text: 'My Orders')]),
        Expanded(child: TabBarView(children: [ _buildAvailable(), _buildMine() ])),
      ]),
    );
  }

  Widget _buildAvailable() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _availFuture,
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final orders = snap.data!;
        if (orders.isEmpty) return const Center(child: Text('No available orders'));
        return ListView.separated(
          itemCount: orders.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final o = orders[i];
            final total = _fmt.format(((o['total_cents'] ?? 0) as int) / 100.0);
            return ListTile(
              title: Text('Order #${(o['id'] ?? '').toString().substring(0,8)} — $total'),
              subtitle: Text(o['status'] ?? 'preparing'),
              trailing: FilledButton(
                onPressed: () async {
                  try { await widget.api.courierAccept(o['id'] as String); await _refresh(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()))); }
                },
                child: const Text('Accept'),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildMine() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _mineFuture,
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
            return ListTile(
              title: Text('Order #${(o['id'] ?? '').toString().substring(0,8)} — $total'),
              subtitle: Text(o['status'] ?? ''),
              trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                if (o['status'] == 'accepted' || o['status'] == 'preparing') FilledButton(onPressed: () async { await widget.api.courierPickedUp(o['id'] as String); await _refresh(); }, child: const Text('Picked up')),
                if (o['status'] == 'out_for_delivery') FilledButton(onPressed: () async { await widget.api.courierDelivered(o['id'] as String); await _refresh(); }, child: const Text('Delivered')),
                if (o['status'] == 'out_for_delivery') const SizedBox(width: 8),
                if (o['status'] == 'out_for_delivery') FilledButton(
                  onPressed: _simRunning ? null : () async {
                    setState(() { _simRunning = true; });
                    // Simple path simulation near Damascus
                    final oid = o['id'] as String;
                    double lat = 33.5138, lon = 36.2765;
                    for (int i = 0; i < 10; i++) {
                      await widget.api.courierUpdateLocation(orderId: oid, lat: lat, lon: lon);
                      await Future.delayed(const Duration(seconds: 1));
                      lat += 0.001; lon += 0.001;
                    }
                    if (mounted) setState(() { _simRunning = false; });
                  }, child: const Text('Simulate')),
              ]),
            );
          },
        );
      },
    );
  }
}
