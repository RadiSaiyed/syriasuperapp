import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_core/shared_core.dart';
import '../services.dart';

class CommerceOrderScreen extends StatefulWidget {
  final String orderId;
  const CommerceOrderScreen({super.key, required this.orderId});
  @override
  State<CommerceOrderScreen> createState() => _CommerceOrderScreenState();
}

class _CommerceOrderScreenState extends State<CommerceOrderScreen> {
  bool _loading = false;
  Map<String, dynamic>? _order;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson('superapp', '/v1/commerce/orders/${widget.orderId}', options: const RequestOptions(cacheTtl: Duration(seconds: 10)));
      if (!mounted) return;
      setState(() => _order = js);
    } catch (_) {} finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final o = _order ?? const <String, dynamic>{};
    final items = (o['items'] as List?) ?? const [];
    return Scaffold(
      appBar: AppBar(title: Text('Order ${widget.orderId}'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: _loading ? const Center(child: CircularProgressIndicator()) : ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('Status: ${o['status'] ?? '-'}  •  Total: ${o['total_cents'] ?? '-'}c'))),
          const SizedBox(height: 8),
          const Text('Items'),
          const SizedBox(height: 4),
          for (final it in items) GlassCard(child: ListTile(title: Text(it['name']?.toString() ?? ''), subtitle: Text('x${it['qty'] ?? 1}  •  ${it['subtotal_cents'] ?? 0}c'))),
        ],
      ),
    );
  }
}

