import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import '../services.dart';
import 'profile_screen.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';
import 'package:shared_core/shared_core.dart';

import '../ui/errors.dart';
import 'commerce_order_screen.dart';
import '../animations.dart';

class _SkeletonTile extends StatelessWidget {
  const _SkeletonTile();
  @override
  Widget build(BuildContext context) {
    return GlassCard(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Container(width: 36, height: 36, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8))),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(height: 12, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(4))),
            const SizedBox(height: 6),
            Container(height: 10, width: 120, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(4))),
          ])),
        ]),
      ),
    );
  }
}

class CommerceScreen extends StatefulWidget {
  final String? initialShopId;
  final String? initialProductId;
  final String? initialAction; // 'checkout' | 'checkout_auto'
  final String? initialOrderId;
  const CommerceScreen({super.key, this.initialShopId, this.initialProductId, this.initialAction, this.initialOrderId});
  @override
  State<CommerceScreen> createState() => _CommerceScreenState();
}

class _CommerceScreenState extends State<CommerceScreen> {
  List<dynamic> _orders = [];
  List<dynamic> _shops = [];
  List<dynamic> _products = [];
  Map<String, dynamic>? _cart;
  String? _selectedShopId;
  bool _loading = false;
  bool _bootstrapped = false;

  void _toast(String m) {
    if (!mounted) return;
    showToast(context, m);
  }

  @override
  void initState() {
    super.initState();
    // Bootstrap via deep-link parameters if provided
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (_bootstrapped) return;
      _bootstrapped = true;
      if (widget.initialShopId != null && widget.initialShopId!.isNotEmpty) {
        await _listShops();
        if (!mounted) return;
        await _loadProducts(widget.initialShopId!);
        if (!mounted) return;
        if (widget.initialProductId != null && widget.initialProductId!.isNotEmpty) {
          await _addToCart(widget.initialProductId!);
          _toast('Produkt in den Warenkorb');
        }
      }
      if ((widget.initialAction ?? '').isNotEmpty) {
        if (widget.initialAction == 'checkout' || widget.initialAction == 'checkout_auto') {
          await _viewCart();
          if (widget.initialAction == 'checkout_auto') {
            if ((_cart?['items'] as List?)?.isNotEmpty == true) {
              await _checkout();
            } else {
              _toast('Warenkorb leer');
            }
          }
        }
      }
      if ((widget.initialOrderId ?? '').isNotEmpty) {
        await _listOrders();
        _toast('Bestellung ${widget.initialOrderId} geladen');
      }
    });
  }

  Future<void> _listOrders() async {
    if (!await hasTokenFor('commerce')) {
      if (!mounted) return;
      MessageHost.showInfoBanner(context, 'Login first');
      return;
    }
    if (!mounted) return;
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson(
        'commerce',
        '/orders',
        options: const RequestOptions(cacheTtl: Duration(minutes: 1), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _orders = js['orders'] as List? ?? []);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Orders failed');
    } finally {
      if (mounted) setState(() => _loading = false);
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
        AnimatedSwitcher(
          duration: AppAnimations.switcherDuration,
          child: _loading && _shops.isEmpty
              ? Column(key: const ValueKey('skel1'), children: List.generate(3, (i) => const _SkeletonTile()))
              : Column(key: const ValueKey('shops'), children: [
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
                ]),
        ),
        if (_selectedShopId != null) ...[
          const Divider(),
          Text('Products — Shop $_selectedShopId'),
          const SizedBox(height: 4),
          AnimatedSwitcher(
            duration: AppAnimations.switcherDuration,
            child: _loading && _products.isEmpty
                ? Column(key: const ValueKey('skel2'), children: List.generate(4, (i) => const _SkeletonTile()))
                : Column(key: const ValueKey('prods'), children: [
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
                  ]),
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
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          child: _loading && _orders.isEmpty
              ? Column(key: const ValueKey('orders_skel'), children: List.generate(3, (i) => const _SkeletonTile()))
              : Column(key: const ValueKey('orders_list'), children: [
                  for (final o in _orders)
                    GlassCard(child: ListTile(
                      title: Text('Order ${o['id']}'),
                      subtitle: Text('Status: ${o['status']} Total: ${o['total_cents']}'),
                      onTap: () {
                        final id = (o['id'] ?? '').toString();
                        if (id.isNotEmpty) {
                          Navigator.push(context, MaterialPageRoute(builder: (_) => CommerceOrderScreen(orderId: id)));
                        }
                      },
                    )),
                ]),
        ),
      ]),
    );
  }

  Future<void> _listShops() async {
    if (!await hasTokenFor('commerce')) {
      if (!mounted) return;
      MessageHost.showInfoBanner(context, 'Login first');
      return;
    }
    if (!mounted) return;
    setState(() => _loading = true);
    try {
      final js = await serviceGetJsonList(
        'superapp',
        '/v1/commerce/shops',
        options: const RequestOptions(cacheTtl: Duration(minutes: 5), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() {_shops = js; _products = []; _selectedShopId = null;});
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Shops failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadProducts(String shopId) async {
    if (!await hasTokenFor('commerce')) {
      if (!mounted) return;
      MessageHost.showInfoBanner(context, 'Login first');
      return;
    }
    if (!mounted) return;
    setState(() {_selectedShopId = shopId; _loading = true; _products = [];});
    try {
      final js = await serviceGetJsonList(
        'superapp',
        '/v1/commerce/shops/$shopId/products',
        options: const RequestOptions(cacheTtl: Duration(minutes: 5), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _products = js);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Products failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addToCart(String productId) async {
    if (!await hasTokenFor('commerce')) {
      if (!mounted) return;
      MessageHost.showInfoBanner(context, 'Login first');
      return;
    }
    if (!mounted) return;
    setState(() => _loading = true);
    try {
      await servicePost(
        'commerce',
        '/cart/items',
        body: {'product_id': productId, 'qty': 1},
        options: const RequestOptions(expectValidationErrors: true, idempotent: true, queueIfOffline: true),
      );
      await _viewCart();
    } catch (e) {
      if (!mounted) return;
      if (e is CoreError && e.kind == CoreErrorKind.network && (e.details?['queued'] == true)) {
        MessageHost.showInfoBanner(context, 'Offline – Vorgang wird gesendet, sobald Verbindung besteht.');
        return;
      }
      presentError(context, e, message: 'Add failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _viewCart() async {
    try {
      final js = await serviceGetJson('commerce', '/cart');
      if (!mounted) return;
      setState(() => _cart = js);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Cart failed');
    }
  }

  Future<void> _checkout() async {
    if (!await hasTokenFor('commerce')) {
      if (!mounted) return;
      MessageHost.showInfoBanner(context, 'Login first');
      return;
    }
    if (!mounted) return;
    setState(() => _loading = true);
    try {
      final js = await servicePostJson('commerce', '/orders/checkout');
      _toast('Order created: ${js['id']}');
      await _listOrders();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Checkout failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }
}
