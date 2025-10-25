import 'dart:convert';
import 'package:flutter/material.dart';
import '../ui/glass.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'profile_screen.dart';

class CommerceScreen extends StatefulWidget {
  const CommerceScreen({super.key});
  @override
  State<CommerceScreen> createState() => _CommerceScreenState();
}

class _CommerceScreenState extends State<CommerceScreen> {
  final _tokens = MultiTokenStore();
  List<dynamic> _orders = [];
  List<dynamic> _shops = [];
  List<dynamic> _products = [];
  Map<String, dynamic>? _cart;
  String? _selectedShopId;
  bool _loading = false;

  Future<Map<String, String>> _commerceHeaders() =>
      authHeaders('commerce', store: _tokens);

  Uri _commerceUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('commerce', path, query: query);

  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _listOrders() async {
    final headers = await _commerceHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.get(_commerceUri('/orders'),
          headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _orders = js['orders'] as List? ?? []);
    } catch (e) {
      _toast('Orders failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Commerce'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Use single‑login via Profile/Payments.'),
        TextButton(
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const ProfileScreen())),
            child: const Text('Zum Profil (Login)')),
        const Divider(height: 16),
        Glass(child: Wrap(spacing: 8, children: [
          FilledButton(onPressed: _loading ? null : _listOrders, child: const Text('List Orders')),
          FilledButton.tonal(onPressed: _loading ? null : _listShops, child: const Text('Shops')),
          OutlinedButton(onPressed: _loading ? null : _viewCart, child: const Text('Cart')),
          FilledButton(onPressed: (_loading || (_cart == null || (_cart!['items'] as List?)?.isEmpty != false)) ? null : _checkout, child: const Text('Checkout')),
        ])),
        const SizedBox(height: 8),
        if (_shops.isNotEmpty) const Text('Shops:'),
        for (final s in _shops)
          GlassCard(
            child: ListTile(
              title: Text(s['name'] ?? ''),
              subtitle: Text('id: ${s['id']}  city: ${s['city'] ?? '-'}'),
              trailing: TextButton(
                onPressed: () => _loadProducts(s['id'] as String),
                child: const Text('Products'),
              ),
            ),
          ),
        if (_selectedShopId != null && _products.isNotEmpty) ...[
          const Divider(),
          Text('Products — Shop $_selectedShopId'),
          const SizedBox(height: 4),
          for (final p in _products)
            GlassCard(
              child: ListTile(
                title: Text(p['name'] ?? ''),
                subtitle: Text('Price: ${p['price_cents']}c'),
                trailing: FilledButton.tonal(
                  onPressed: _loading ? null : () => _addToCart(p['id'] as String),
                  child: const Text('Add to cart'),
                ),
              ),
            ),
        ],
        if (_cart != null) ...[
          const Divider(),
          const Text('Cart'),
          const SizedBox(height: 4),
          for (final it in ((_cart!['items'] as List?) ?? []))
            GlassCard(child: ListTile(title: Text(it['name'] ?? ''), subtitle: Text('x${it['qty']}  —  ${it['subtotal_cents']}c'))),
          Align(
              alignment: Alignment.centerRight,
              child: Text('Total: ${_cart!['total_cents'] ?? 0}c')),
        ],
        for (final o in _orders)
          GlassCard(child: ListTile(title: Text('Order ${o['id']}'), subtitle: Text('Status: ${o['status']} Total: ${o['total_cents']}'))),
      ]),
    );
  }

  Future<void> _listShops() async {
    final headers = await _commerceHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.get(_commerceUri('/shops'),
          headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as List<dynamic>;
      setState(() {_shops = js; _products = []; _selectedShopId = null;});
    } catch (e) {
      _toast('Shops failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _loadProducts(String shopId) async {
    final headers = await _commerceHeaders();
    setState(() {_selectedShopId = shopId; _loading = true; _products = [];});
    try {
      final res = await http.get(_commerceUri('/shops/$shopId/products'),
          headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as List<dynamic>;
      setState(() => _products = js);
    } catch (e) {
      _toast('Products failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _addToCart(String productId) async {
    final headers = await _commerceHeaders();
    setState(() => _loading = true);
    try {
      final res = await http.post(_commerceUri('/cart/items'),
          headers: headers,
          body: jsonEncode({'product_id': productId, 'qty': 1}));
      if (res.statusCode >= 400) throw Exception(res.body);
      await _viewCart();
    } catch (e) {
      _toast('Add failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _viewCart() async {
    final headers = await _commerceHeaders();
    try {
      final res = await http.get(_commerceUri('/cart'),
          headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _cart = js);
    } catch (e) {
      _toast('Cart failed: $e');
    }
  }

  Future<void> _checkout() async {
    final headers = await _commerceHeaders();
    setState(() => _loading = true);
    try {
      final res = await http.post(_commerceUri('/orders/checkout'),
          headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      _toast('Order created: ${js['id']}');
      await _listOrders();
    } catch (e) {
      _toast('Checkout failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }
}
