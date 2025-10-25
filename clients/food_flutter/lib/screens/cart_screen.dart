import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:intl/intl.dart';

import '../api.dart';

class CartScreen extends StatefulWidget {
  final ApiClient api;
  const CartScreen({super.key, required this.api});

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  late Future<Map<String, dynamic>> _future = widget.api.getCart();
  final NumberFormat _fmt = NumberFormat.currency(locale: 'de_DE', symbol: 'SYP', decimalDigits: 2);

  Future<void> _reload() async => setState(() => _future = widget.api.getCart());

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final cart = snap.data!;
        final items = (cart['items'] as List? ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
        final total = (cart['total_cents'] ?? 0) as int;
        return Column(children: [
          Expanded(
            child: items.isEmpty
                ? const Center(child: Text('Cart is empty'))
                : ListView.separated(
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, i) {
                      final it = items[i];
                      final price = _fmt.format(((it['price_cents'] ?? 0) as int) / 100.0);
                      final subtotal = _fmt.format(((it['subtotal_cents'] ?? 0) as int) / 100.0);
                      return ListTile(
                        title: Text(it['name'] ?? ''),
                        subtitle: Text('$price • qty ${it['qty']} • subtotal $subtotal'),
                        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                          IconButton(onPressed: () async { await widget.api.updateCartItem(itemId: it['id'] as String, qty: (it['qty'] as int) + 1); await _reload(); }, icon: const Icon(Icons.add)),
                          IconButton(onPressed: () async { final q = (it['qty'] as int) - 1; if (q >= 1) { await widget.api.updateCartItem(itemId: it['id'] as String, qty: q); await _reload(); } }, icon: const Icon(Icons.remove)),
                          IconButton(onPressed: () async { await widget.api.deleteCartItem(itemId: it['id'] as String); await _reload(); }, icon: const Icon(Icons.delete)),
                        ]),
                      );
                    },
                  ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(children: [
              Text('Total: ${_fmt.format(total / 100.0)}'),
              const Spacer(),
              FilledButton(onPressed: items.isEmpty ? null : _checkout, child: const Text('Checkout')),
            ]),
          )
        ]);
      },
    );
  }

  Future<void> _checkout() async {
    try {
      final order = await widget.api.checkout();
      if (!mounted) return;
      final reqId = order['payment_request_id'] as String?;
      showModalBottomSheet(context: context, builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Order created', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (reqId != null) Text('Payment request: $reqId'),
            const SizedBox(height: 12),
            Row(children: [
              if (reqId != null) FilledButton.icon(onPressed: () async { final uri = Uri.parse('payments://request/$reqId'); try { await launchUrl(uri); } catch (_) {} }, icon: const Icon(Icons.open_in_new), label: const Text('Open in Payments')),
              const SizedBox(width: 8),
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
            ])
          ]),
        );
      });
      await _reload();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }
}
