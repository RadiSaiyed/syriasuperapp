import 'package:flutter/material.dart';
import '../api.dart';

class WishlistScreen extends StatefulWidget {
  final ApiClient api;
  const WishlistScreen({super.key, required this.api});
  @override
  State<WishlistScreen> createState() => _WishlistScreenState();
}

class _WishlistScreenState extends State<WishlistScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.wishlistList();
      setState(() => _items = rows);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _delete(String id) async {
    setState(() => _loading = true);
    try {
      await widget.api.wishlistDelete(id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addToCart(String productId) async {
    setState(() => _loading = true);
    try {
      await widget.api.addCartItem(productId: productId, qty: 1);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Added to cart')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: _items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final it = _items[i];
              final favId = it['id'] as String?;
              final productId = it['product_id'] as String?;
              return ListTile(
                title: Text((it['product_name'] as String?) ?? (productId ?? '')),
                subtitle: Text('Price: ${it['price_cents'] ?? 0} • Stock: ${it['stock_qty'] ?? 0}'),
                trailing: Wrap(spacing: 8, children: [
                  IconButton(onPressed: _loading ? null : () => _addToCart(productId!), icon: const Icon(Icons.add_shopping_cart)),
                  IconButton(onPressed: _loading ? null : () => _delete(favId!), icon: const Icon(Icons.delete_outline)),
                ]),
              );
            },
          ),
        ),
      )
    ]);
  }
}
