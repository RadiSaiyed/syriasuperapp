import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';

class CartScreen extends StatefulWidget {
  final ApiClient api;
  const CartScreen({super.key, required this.api});
  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  bool _loading = false;
  Map<String, dynamic>? _cart;
  final _promoCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _addrCtrl = TextEditingController();

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final c = await widget.api.getCart();
      setState(() => _cart = c);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _update(String itemId, int qty) async {
    setState(() => _loading = true);
    try {
      final c = await widget.api.updateCartItem(itemId: itemId, qty: qty);
      setState(() => _cart = c);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _clear() async {
    setState(() => _loading = true);
    try {
      await widget.api.clearCart();
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _checkout() async {
    setState(() => _loading = true);
    try {
      final order = await widget.api.checkout(
        promoCode: _promoCtrl.text.trim().isEmpty ? null : _promoCtrl.text.trim(),
        shipName: _nameCtrl.text.trim().isEmpty ? null : _nameCtrl.text.trim(),
        shipPhone: _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        shipAddr: _addrCtrl.text.trim().isEmpty ? null : _addrCtrl.text.trim(),
      );
      if (!mounted) return;
      final id = order['id'];
      final paymentId = order['payment_request_id'] as String?;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Order $id created')));
      if (paymentId != null) {
        await _showPaymentCta(paymentId);
      }
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        await Clipboard.setData(ClipboardData(text: requestId));
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed. Copied request ID.')));
      }
    }
  }

  Future<void> _showPaymentCta(String requestId) async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: false,
      showDragHandle: true,
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: const [
                Icon(Icons.account_balance_wallet_outlined, size: 28),
                SizedBox(width: 8),
                Text('Complete your payment', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ]),
              const SizedBox(height: 8),
              const Text('Open the Payments app to review and authorize this order.'),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () { Navigator.pop(ctx); _openPayment(requestId); },
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('Open in Payments'),
                  ),
                ),
              ]),
              const SizedBox(height: 8),
              TextButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: requestId));
                  if (!mounted) return; 
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied payment request ID')));
                },
                icon: const Icon(Icons.copy_outlined),
                label: const Text('Copy request ID'),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final items = ((_cart?['items'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
    final total = _cart?['total_cents'] as int? ?? 0;
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final it = items[i];
              final qty = it['qty'] as int? ?? 1;
              return ListTile(
                title: Text(it['product_name'] as String? ?? ''),
                subtitle: Text('${it['price_cents']} SYP × $qty = ${it['subtotal_cents']}'),
                trailing: Wrap(spacing: 8, children: [
                  IconButton(onPressed: _loading ? null : () => _update(it['id'] as String, qty - 1), icon: const Icon(Icons.remove_circle_outline)),
                  IconButton(onPressed: _loading ? null : () => _update(it['id'] as String, qty + 1), icon: const Icon(Icons.add_circle_outline)),
                ]),
              );
            },
          ),
        ),
      ),
      Container(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Total: $total SYP', style: const TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('Optional: Promo & Shipping'),
          Row(children: [
            Expanded(child: TextField(controller: _promoCtrl, decoration: const InputDecoration(hintText: 'PROMO'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _nameCtrl, decoration: const InputDecoration(hintText: 'Full name'))),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _phoneCtrl, decoration: const InputDecoration(hintText: 'Phone'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _addrCtrl, decoration: const InputDecoration(hintText: 'Address'))),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            OutlinedButton(onPressed: items.isEmpty || _loading ? null : _clear, child: const Text('Clear')),
            const Spacer(),
            FilledButton(onPressed: items.isEmpty || _loading ? null : _checkout, child: const Text('Checkout')),
          ]),
        ]),
      )
    ]);
  }
}
