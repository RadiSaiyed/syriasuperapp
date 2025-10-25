import 'dart:convert';
import 'package:flutter/material.dart';
import '../ui/glass.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'profile_screen.dart';
import 'package:intl/intl.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'restaurant_admin_screen.dart';

class FoodScreen extends StatefulWidget {
  const FoodScreen({super.key});
  @override
  State<FoodScreen> createState() => _FoodScreenState();
}

class _FoodScreenState extends State<FoodScreen> {
  final _tokens = MultiTokenStore();
  List<dynamic> _orders = [];
  List<dynamic> _restaurants = [];
  List<dynamic> _menu = [];
  List<dynamic> _images = [];
  List<dynamic> _favorites = [];
  List<dynamic> _reviews = [];
  List<dynamic> _adminOrders = [];
  List<dynamic> _courierAvailable = [];
  List<dynamic> _courierOrders = [];
  Map<String, dynamic>? _cart;
  String? _selectedRestaurantId;
  bool _loading = false;
  bool _favoritesFetched = false;
  bool _restaurantsFetched = false;
  bool _ordersFetched = false;
  bool _adminFetched = false;
  // KPIs (owner summary)
  int _kpiTodayTotalCents = 0;
  int _kpiTodayOrders = 0;
  bool _mineFilter = false;
  // Owner tools controllers
  final _miNameCtrl = TextEditingController();
  final _miPriceCtrl = TextEditingController(text: '10000');
  final _miDescCtrl = TextEditingController();
  final _imageUrlCtrl = TextEditingController();
  final NumberFormat _currencyFmt = NumberFormat.currency(locale: 'de_DE', symbol: 'SYP', decimalDigits: 2);
  Future<Map<String, String>> _foodHeaders() =>
      authHeaders('food', store: _tokens);

  Uri _foodUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('food', path, query: query);

  Future<http.Response> _foodRequest(
    String method,
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) async {
    final reqHeaders = headers ?? await _foodHeaders();
    final uri = _foodUri(path, query: query);
    switch (method) {
      case 'GET':
        return http.get(uri, headers: reqHeaders);
      case 'POST':
        return http.post(uri, headers: reqHeaders, body: body);
      case 'PUT':
        return http.put(uri, headers: reqHeaders, body: body);
      case 'PATCH':
        return http.patch(uri, headers: reqHeaders, body: body);
      case 'DELETE':
        return http.delete(uri, headers: reqHeaders, body: body);
      default:
        throw ArgumentError('Unsupported method $method');
    }
  }

  Future<http.Response> _foodGet(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
  }) =>
      _foodRequest('GET', path, query: query, headers: headers);

  Future<http.Response> _foodPost(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) =>
      _foodRequest('POST', path, query: query, headers: headers, body: body);

  Future<http.Response> _foodPut(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) =>
      _foodRequest('PUT', path, query: query, headers: headers, body: body);

  Future<http.Response> _foodPatch(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) =>
      _foodRequest('PATCH', path, query: query, headers: headers, body: body);

  Future<http.Response> _foodDelete(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) =>
      _foodRequest('DELETE', path,
          query: query, headers: headers, body: body);
  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Food'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: RefreshIndicator(
        onRefresh: _refreshAll,
        child: ListView(padding: const EdgeInsets.all(16), children: [
        if (_loading) const LinearProgressIndicator(),
        const Text('Use single‑login via Profile/Payments.'),
        if (_kpiTodayOrders > 0 || _kpiTodayTotalCents > 0)
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 8),
            child: Glass(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(children: [
                  const Icon(Icons.bar_chart_outlined),
                  const SizedBox(width: 8),
                  Expanded(child: Text('Heute: ${_fmtMoney(_kpiTodayTotalCents)} • Orders: $_kpiTodayOrders')),
                  IconButton(onPressed: _loading ? null : _loadOwnerKpisToday, icon: const Icon(Icons.refresh)),
                ]),
              ),
            ),
          ),
        TextButton(
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const ProfileScreen())),
            child: const Text('Zum Profil (Login)')),
        const Divider(height: 16),
        Glass(child: Wrap(spacing: 8, children: [
          FilledButton(onPressed: _loading ? null : _listOrders, child: const Text('List Orders')),
          FilledButton.tonal(onPressed: _loading ? null : () async { setState(()=>_mineFilter=false); await _listRestaurants(); }, child: const Text('Restaurants')),
          FilledButton.tonal(onPressed: _loading ? null : () async { setState(()=>_mineFilter=true); await _listMyRestaurants(); }, child: const Text('Meine Restaurants')),
          OutlinedButton(onPressed: _loading ? null : _listFavorites, child: const Text('Favorites')),
          OutlinedButton(onPressed: _loading ? null : _loadCart, child: const Text('Cart')),
          FilledButton(onPressed: (_loading || (_cart == null || (_cart!['items'] as List?)?.isEmpty != false)) ? null : _checkout, child: const Text('Checkout')),
          // Courier quick actions
          TextButton(onPressed: _loading ? null : _courierListAvailable, child: const Text('Courier: Available')),
          TextButton(onPressed: _loading ? null : _courierMyOrders, child: const Text('Courier: My Orders')),
          // Owner/Admin quick action
          TextButton(onPressed: _loading ? null : _adminListOrders, child: const Text('Owner/Admin Orders')),
        ])),
        const SizedBox(height: 8),
        if (_favorites.isNotEmpty || _favoritesFetched) const Text('Favorites:'),
        if (_favoritesFetched && _favorites.isEmpty)
          const Padding(padding: EdgeInsets.symmetric(vertical: 4), child: Text('Keine Favoriten.')),
        for (final r in _favorites)
          GlassCard(
            child: ListTile(
              title: Text(r['name'] ?? ''),
              subtitle: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                if ((r['city'] as String?)?.isNotEmpty == true) Chip(label: Text(r['city'])),
                _ratingChip(r['rating_avg'], r['rating_count']),
                Text('id: ${r['id']}', style: Theme.of(context).textTheme.bodySmall),
              ]),
              trailing: TextButton(onPressed: () => _loadMenu(r['id'] as String), child: const Text('Menu anzeigen')),
            ),
          ),
        if (_favorites.isNotEmpty) const Divider(height: 16),
        if (_restaurants.isNotEmpty || _restaurantsFetched) Text(_mineFilter ? 'Meine Restaurants:' : 'Restaurants:'),
        if (_restaurantsFetched && _restaurants.isEmpty)
          const Padding(padding: EdgeInsets.symmetric(vertical: 4), child: Text('No restaurants found. Consider running the demo seed.')),
        for (final r in _restaurants)
          GlassCard(
            child: ListTile(
              title: Text(r['name'] ?? ''),
              subtitle: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                if ((r['city'] as String?)?.isNotEmpty == true) Chip(label: Text(r['city'])),
                _ratingChip(r['rating_avg'], r['rating_count']),
                Text('id: ${r['id']}', style: Theme.of(context).textTheme.bodySmall),
              ]),
              trailing: Wrap(spacing: 8, children: [
                IconButton(tooltip: 'Menu', onPressed: () => _loadMenu(r['id'] as String), icon: const Icon(Icons.restaurant_menu)),
                IconButton(tooltip: 'Images', onPressed: () => _listImages(r['id'] as String), icon: const Icon(Icons.photo_library_outlined)),
                IconButton(tooltip: 'Reviews', onPressed: () => _listReviews(r['id'] as String), icon: const Icon(Icons.reviews_outlined)),
                IconButton(tooltip: 'Favorite', onPressed: () => _favoriteRestaurant(r['id'] as String), icon: const Icon(Icons.favorite_border)),
                IconButton(tooltip: 'Unfavorite', onPressed: () => _unfavoriteRestaurant(r['id'] as String), icon: const Icon(Icons.favorite_outline)),
                IconButton(tooltip: 'Dev: Become owner', onPressed: () => _devBecomeOwner(r['id'] as String), icon: const Icon(Icons.verified_user_outlined)),
                if (_mineFilter)
                  IconButton(
                    tooltip: 'Manage',
                    onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => RestaurantAdminScreen(restaurantId: r['id'] as String, restaurantName: r['name'] as String?))),
                    icon: const Icon(Icons.settings_applications_outlined),
                  ),
              ]),
            ),
          ),
        if (_selectedRestaurantId != null && _menu.isNotEmpty) ...[
          const Divider(),
          Text('Menu (${_menu.length}) — Restaurant $_selectedRestaurantId'),
          const SizedBox(height: 4),
          for (final m in _menu)
            GlassCard(
              child: ListTile(
                title: Text(m['name'] ?? ''),
                subtitle: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                  Text('Price: ${_fmtMoney(m['price_cents'])}'),
                  if ((m['available'] as bool?) == false) const Chip(label: Text('Unavailable')),
                ]),
                trailing: FilledButton.tonalIcon(
                  onPressed: (_loading || (m['available'] == false)) ? null : () => _addToCart(m['id'] as String),
                  icon: const Icon(Icons.add_shopping_cart_outlined),
                  label: const Text('Add to cart'),
                ),
              ),
            ),
          // Owner tools for current restaurant
          const SizedBox(height: 8),
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('Owner Tools', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: TextField(controller: _miNameCtrl, decoration: const InputDecoration(labelText: 'Item name'))),
                  const SizedBox(width: 8),
                  SizedBox(width: 140, child: TextField(controller: _miPriceCtrl, decoration: const InputDecoration(labelText: 'Price (SYP)'), keyboardType: TextInputType.number)),
                ]),
                const SizedBox(height: 8),
                TextField(controller: _miDescCtrl, decoration: const InputDecoration(labelText: 'Description (optional)')),
                const SizedBox(height: 8),
                FilledButton(onPressed: _loading ? null : _adminAddMenuItemForSelected, child: const Text('Add Menu Item')),
                const Divider(height: 16),
                Row(children: [
                  Expanded(child: TextField(controller: _imageUrlCtrl, decoration: const InputDecoration(labelText: 'Image URL'))),
                  const SizedBox(width: 8),
                  FilledButton.tonal(onPressed: _loading ? null : _adminAddImageForSelected, child: const Text('Add Image')),
                ]),
                const SizedBox(height: 8),
                const Text('Quick edit current items:'),
                const SizedBox(height: 4),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final m in _menu)
                    GlassCard(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                        child: Row(children: [
                          Expanded(child: Text(m['name'] ?? '')),
                          Text(_fmtMoney(m['price_cents'])),
                          const SizedBox(width: 8),
                          IconButton(tooltip: 'Set price…', onPressed: _loading ? null : () => _promptEditPrice(m), icon: const Icon(Icons.edit_outlined)),
                          IconButton(tooltip: 'Price +1000', onPressed: _loading ? null : () => _adminUpdateMenuPrice(m['id'] as String, (m['price_cents'] as int) + 100000), icon: const Icon(Icons.add_circle_outline)),
                          IconButton(tooltip: 'Set unavailable', onPressed: _loading ? null : () => _adminSetMenuAvailability(m['id'] as String, false), icon: const Icon(Icons.visibility_off_outlined)),
                          IconButton(tooltip: 'Set available', onPressed: _loading ? null : () => _adminSetMenuAvailability(m['id'] as String, true), icon: const Icon(Icons.visibility_outlined)),
                          IconButton(tooltip: 'Delete', onPressed: _loading ? null : () => _adminDeleteMenuItem(m['id'] as String), icon: const Icon(Icons.delete_outline)),
                        ]),
                      ),
                    ),
                ]),
              ]),
            ),
          ),
        ],
        if (_selectedRestaurantId != null && _images.isNotEmpty) ...[
          const Divider(),
          Text('Images (${_images.length}) — Restaurant $_selectedRestaurantId'),
          const SizedBox(height: 4),
          SizedBox(
            height: 120,
            child: ListView(scrollDirection: Axis.horizontal, children: [
              const SizedBox(width: 8),
              for (final im in _images)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: CachedNetworkImage(
                      imageUrl: im['url'] ?? '',
                      height: 120,
                      width: 180,
                      fit: BoxFit.cover,
                      placeholder: (ctx, _) => Container(color: Colors.black12, width: 180, height: 120),
                      errorWidget: (ctx, _, __) => Container(color: Colors.black26, width: 180, height: 120, child: const Icon(Icons.broken_image_outlined)),
                    ),
                  ),
                ),
              const SizedBox(width: 8),
            ]),
          ),
        ],
        if (_selectedRestaurantId != null && _reviews.isNotEmpty) ...[
          const Divider(),
          Text('Reviews (${_reviews.length}) — Restaurant $_selectedRestaurantId'),
          const SizedBox(height: 4),
          for (final rv in _reviews)
            GlassCard(
              child: ListTile(
                title: Text('Rating: ${rv['rating']} ★'),
                subtitle: Text(rv['comment'] ?? ''),
              ),
            ),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.tonal(onPressed: _loading ? null : _addReviewDialog, child: const Text('Review hinzufügen')),
          )
        ],
        if (_cart != null) ...[
          const Divider(),
          const Text('Cart'),
          const SizedBox(height: 4),
          for (final it in ((_cart!['items'] as List?) ?? []))
            GlassCard(
              child: ListTile(
                title: Text(it['name'] ?? ''),
                subtitle: Text('x${it['qty']}  —  ${_fmtMoney(it['subtotal_cents'])}'),
                trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                  IconButton(onPressed: _loading ? null : () => _updateCartItem(it['id'] as String, (it['qty'] as int) - 1), icon: const Icon(Icons.remove_circle_outline)),
                  IconButton(onPressed: _loading ? null : () => _updateCartItem(it['id'] as String, (it['qty'] as int) + 1), icon: const Icon(Icons.add_circle_outline)),
                ]),
              ),
            ),
          Align(
            alignment: Alignment.centerRight,
            child: Text('Total: ${_fmtMoney(_cart!['total_cents'] ?? 0)}', style: Theme.of(context).textTheme.titleMedium),
          ),
        ],
        if (_orders.isNotEmpty || _ordersFetched) const Divider(),
        if (_orders.isNotEmpty || _ordersFetched) const Text('My Orders:'),
        if (_ordersFetched && _orders.isEmpty)
          const Padding(padding: EdgeInsets.symmetric(vertical: 4), child: Text('No orders.')),
        for (final o in _orders)
          GlassCard(
            child: ListTile(
              title: Text('Order ${o['id']}'),
              subtitle: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                _statusChip((o['status'] as String?) ?? 'created'),
                Text('Total: ${_fmtMoney(o['total_cents'])}'),
              ]),
            ),
          ),
        const Divider(height: 16),
        const Text('Owner/Admin Orders:'),
        if (_adminFetched && _adminOrders.isEmpty)
          const Padding(padding: EdgeInsets.symmetric(vertical: 4), child: Text('No admin orders (become owner via Restaurants → "Dev: Become owner").')),
        for (final o in _adminOrders)
          GlassCard(
            child: ListTile(
              title: Text('Order ${o['id']}'),
              subtitle: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                _statusChip((o['status'] as String?) ?? 'created'),
                Text('Total: ${_fmtMoney(o['total_cents'])}'),
              ]),
              trailing: Wrap(spacing: 8, children: [
                IconButton(tooltip: 'Next Status', onPressed: _loading ? null : () => _adminUpdateNextStatus(o), icon: const Icon(Icons.skip_next_outlined)),
                IconButton(tooltip: 'Cancel Order', onPressed: _loading ? null : () => _adminUpdateStatus(o, 'canceled'), icon: const Icon(Icons.cancel_outlined)),
              ]),
            ),
          ),
        if (_courierAvailable.isNotEmpty) const Divider(),
        if (_courierAvailable.isNotEmpty) const Text('Courier: Available Orders'),
        for (final o in _courierAvailable)
          GlassCard(
            child: ListTile(
              title: Text('Order ${o['id']}'),
              subtitle: Text('Total: ${_fmtMoney(o['total_cents'])}'),
              trailing: FilledButton.tonalIcon(onPressed: _loading ? null : () => _courierAccept(o['id'] as String), icon: const Icon(Icons.hail_outlined), label: const Text('Accept')),
            ),
          ),
        if (_courierOrders.isNotEmpty) const Divider(),
        if (_courierOrders.isNotEmpty) const Text('Courier: My Orders'),
        for (final o in _courierOrders)
          GlassCard(
            child: ListTile(
              title: Text('Order ${o['id']}'),
              subtitle: _statusChip((o['status'] as String?) ?? 'created'),
              trailing: Wrap(spacing: 8, children: [
                IconButton(tooltip: 'Picked up', onPressed: _loading ? null : () => _courierPickedUp(o['id'] as String), icon: const Icon(Icons.shopping_bag_outlined)),
                IconButton(tooltip: 'Delivered', onPressed: _loading ? null : () => _courierDelivered(o['id'] as String), icon: const Icon(Icons.check_circle_outline)),
                IconButton(tooltip: 'Update location', onPressed: _loading ? null : () => _courierUpdateLocation(o['id'] as String, 33.5138, 36.2765), icon: const Icon(Icons.my_location_outlined)),
              ]),
            ),
          ),
      ]),
      ),
    );
  }

  Future<void> _listRestaurants() async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodGet(
        '/restaurants',
        query: _mineFilter ? {'mine': 'true'} : null,
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as List<dynamic>;
      setState(() {_restaurants = js; _menu = []; _images = []; _reviews = []; _selectedRestaurantId = null; _restaurantsFetched = true;});
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Restaurants failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _listImages(String rid) async {
    final headers = await _foodHeaders();
    setState(() { _loading = true; _selectedRestaurantId = rid; _images = []; });
    try {
      final res = await _foodGet(
        '/restaurants/$rid/images',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as List<dynamic>;
      setState(() => _images = js);
    } catch (e) {
      _toast('Images failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  // UI helpers
  String _fmtMoney(dynamic cents) {
    final n = (cents is int) ? cents : int.tryParse('$cents') ?? 0;
    return _currencyFmt.format(n / 100.0);
  }

  Widget _ratingChip(dynamic avg, dynamic count) {
    final a = (avg is num) ? avg.toDouble() : null;
    final c = (count is num) ? count.toInt() : 0;
    return Chip(avatar: const Icon(Icons.star, size: 16), label: Text(a != null ? '${a.toStringAsFixed(1)} ($c)' : '- ($c)'));
  }

  Widget _statusChip(String status) {
    Color color;
    switch (status) {
      case 'accepted':
        color = Colors.blueAccent;
        break;
      case 'preparing':
        color = Colors.orange;
        break;
      case 'out_for_delivery':
        color = Colors.purple;
        break;
      case 'delivered':
        color = Colors.green;
        break;
      case 'canceled':
        color = Colors.redAccent;
        break;
      default:
        color = Colors.grey;
    }
    return Chip(backgroundColor: color.withValues(alpha: 0.2), label: Text(status));
  }

  Future<void> _loadMenu(String rid) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() {
      _loading = true;
      _selectedRestaurantId = rid;
      _menu = [];
    });
    try {
      final res = await _foodGet(
        '/restaurants/$rid/menu',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as List<dynamic>;
      setState(() => _menu = js);
    } catch (e) {
      _toast('Menu failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _listOrders() async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodGet('/orders', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {_orders = js['orders'] as List? ?? []; _ordersFetched = true;});
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Orders failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _listReviews(String rid) async {
    final headers = await _foodHeaders();
    setState(() { _loading = true; _reviews = []; _selectedRestaurantId = rid; });
    try {
      final res = await _foodGet(
        '/restaurants/$rid/reviews',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = (jsonDecode(res.body) as Map<String, dynamic>);
      setState(() => _reviews = ((js['reviews'] as List?) ?? []));
    } catch (e) {
      _toast('Reviews failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addReviewDialog() async {
    final rid = _selectedRestaurantId;
    if (rid == null) return;
    final ratingCtrl = TextEditingController(text: '5');
    final commentCtrl = TextEditingController();
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Add review'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: ratingCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Rating (1-5)')),
          TextField(controller: commentCtrl, decoration: const InputDecoration(labelText: 'Kommentar')), 
        ]),
        actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save'))],
      )
    );
    if (result == true) {
      final rating = int.tryParse(ratingCtrl.text.trim()) ?? 5;
      await _addReview(rid, rating: rating, comment: commentCtrl.text.trim());
    }
  }

  Future<void> _addReview(String rid, {required int rating, String? comment}) async {
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/restaurants/$rid/reviews',
        headers: headers,
        body: jsonEncode({'rating': rating, 'comment': comment}),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _listReviews(rid);
    } catch (e) {
      _toast('Add review failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  // Owner tools: Admin API helpers
  Future<void> _adminAddMenuItemForSelected() async {
    final rid = _selectedRestaurantId;
    if (rid == null) { _toast('Select a restaurant'); return; }
    final name = _miNameCtrl.text.trim();
    final priceSyp = int.tryParse(_miPriceCtrl.text.trim());
    final desc = _miDescCtrl.text.trim();
    if (name.isEmpty || priceSyp == null || priceSyp <= 0) { _toast('Please provide name and price'); return; }
    await _adminAddMenuItem(rid, name: name, priceCents: priceSyp * 100, description: desc.isEmpty ? null : desc);
  }

  Future<void> _adminAddMenuItem(String rid, {required String name, required int priceCents, String? description}) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final query = {
        'name': name,
        'price_cents': '$priceCents',
        if (description != null) 'description': description,
      };
      final res = await _foodPost(
        '/admin/restaurants/$rid/menu',
        query: query,
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      _miNameCtrl.clear();
      _miDescCtrl.clear();
      await _loadMenu(rid);
    } catch (e) {
      _toast('Add menu item failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _adminUpdateMenuPrice(String itemId, int newPriceCents) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodPatch(
        '/admin/menu/$itemId',
        query: {'price_cents': '$newPriceCents'},
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      if (_selectedRestaurantId != null) await _loadMenu(_selectedRestaurantId!);
    } catch (e) {
      _toast('Update price failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _adminSetMenuAvailability(String itemId, bool available) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodPatch(
        '/admin/menu/$itemId',
        query: {'available': available ? 'true' : 'false'},
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      if (_selectedRestaurantId != null) await _loadMenu(_selectedRestaurantId!);
    } catch (e) {
      _toast('Set availability failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _adminDeleteMenuItem(String itemId) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodDelete('/admin/menu/$itemId', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      if (_selectedRestaurantId != null) await _loadMenu(_selectedRestaurantId!);
    } catch (e) {
      _toast('Delete item failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _promptEditPrice(Map<String, dynamic> m) async {
    final ctrl = TextEditingController(text: (((m['price_cents'] as int?) ?? 0) ~/ 100).toString());
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Set price (SYP)'),
        content: TextField(controller: ctrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Price SYP')),
        actions: [
          TextButton(onPressed: ()=>Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: ()=>Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    if (ok == true) {
      final syp = int.tryParse(ctrl.text.trim());
      if (syp != null && syp > 0) {
        await _adminUpdateMenuPrice(m['id'] as String, syp * 100);
      } else {
        _toast('Invalid price');
      }
    }
  }

  Future<void> _adminAddImageForSelected() async {
    final rid = _selectedRestaurantId;
    if (rid == null) { _toast('Restaurant auswählen'); return; }
    final url = _imageUrlCtrl.text.trim();
    if (url.isEmpty) { _toast('Bild‑URL angeben'); return; }
    await _adminAddImages(rid, [ {'url': url, 'sort_order': 0} ]);
  }

  Future<void> _adminAddImages(String rid, List<Map<String, dynamic>> images) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/admin/restaurants/$rid/images',
        headers: headers,
        body: jsonEncode(images),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      _imageUrlCtrl.clear();
      await _listImages(rid);
    } catch (e) {
      _toast('Add image failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _addToCart(String menuItemId) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/cart/items',
        headers: headers,
        body: jsonEncode({'menu_item_id': menuItemId, 'qty': 1}),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _loadCart();
    } catch (e) {
      _toast('Add failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _updateCartItem(String itemId, int qty) async {
    if (qty <= 0) {
      qty = 0; // backend may remove on zero or reject; try update first
    }
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodPut(
        '/cart/items/$itemId',
        headers: headers,
        body: jsonEncode(
            {'menu_item_id': _cartItemMenuId(itemId), 'qty': qty}),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _loadCart();
    } catch (e) {
      _toast('Update failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  String? _cartItemMenuId(String itemId) {
    final items = (_cart?['items'] as List?) ?? [];
    for (final it in items) {
      if (it['id'] == itemId) return it['menu_item_id'] as String?;
    }
    return null;
  }

  Future<void> _loadCart() async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await _foodGet('/cart', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _cart = js);
    } catch (e) {
      _toast('Cart failed: $e');
    }
  }

  Future<void> _checkout() async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodPost('/orders/checkout', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      _toast('Bestellung erstellt: ${js['id']}');
      await _listOrders();
    } catch (e) {
      _toast('Checkout failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  // Favorites
  Future<void> _listFavorites() async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodGet(
        '/restaurants/favorites',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as List<dynamic>;
      setState(() {_favorites = js; _favoritesFetched = true;});
    } catch (e) {
      _toast('Favorites failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _listMyRestaurants() async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodGet(
        '/admin/restaurants/mine',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as List<dynamic>;
      setState(() {_restaurants = js; _menu = []; _images = []; _reviews = []; _selectedRestaurantId = null; _restaurantsFetched = true;});
    } catch (e) {
      _toast('Meine Restaurants failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _refreshAll() async {
    // best-effort refresh multiple sections
    await Future.wait([
      _listRestaurants(),
      _listOrders(),
      _loadCart(),
      _listFavorites(),
      _loadOwnerKpisToday(),
    ].map((f) async {
      try {
        await f;
      } catch (_) {}
    }));
  }

  Future<void> _favoriteRestaurant(String rid) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await _foodPost('/restaurants/$rid/favorite', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      await _listFavorites();
    } catch (e) {
      _toast('Fav failed: $e');
    }
  }

  Future<void> _loadOwnerKpisToday() async {
    final headers = await _foodHeaders();
    try {
      // fetch my restaurants, then sum stats day
      final rs = await _foodGet('/admin/restaurants/mine', headers: headers);
      if (rs.statusCode >= 400) return;
      final items = (jsonDecode(rs.body) as List?) ?? [];
      int total = 0; int count = 0;
      for (final r in items) {
        final id = r['id'] as String?; if (id == null) continue;
        final st = await _foodGet(
          '/admin/restaurants/$id/stats',
          query: {'range': 'day'},
          headers: headers,
        );
        if (st.statusCode >= 400) continue;
        final js = jsonDecode(st.body) as Map<String, dynamic>;
        total += (js['total_cents'] as int?) ?? 0;
        count += (js['total_orders'] as int?) ?? 0;
      }
      if (mounted) setState(() { _kpiTodayTotalCents = total; _kpiTodayOrders = count; });
    } catch (_) {}
  }

  Future<void> _unfavoriteRestaurant(String rid) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await _foodDelete('/restaurants/$rid/favorite', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      await _listFavorites();
    } catch (e) {
      _toast('Unfav failed: $e');
    }
  }

  // Admin (owner)
  Future<void> _devBecomeOwner(String rid) async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/admin/dev/become_owner',
        query: {'restaurant_id': rid},
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _adminListOrders();
      _toast('You are now the owner (dev).');
    } catch (e) {
      _toast('Become owner failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _adminListOrders() async {
    final headers = await _foodHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodGet('/admin/orders', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() { _adminOrders = (js['orders'] as List?) ?? []; _adminFetched = true; });
    } catch (e) {
      _toast('Admin orders failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  String _nextStatusFor(Map<String, dynamic> o) {
    final s = (o['status'] as String?) ?? 'created';
    switch (s) {
      case 'created':
        return 'accepted';
      case 'accepted':
        return 'preparing';
      case 'preparing':
        return 'out_for_delivery';
      case 'out_for_delivery':
        return 'delivered';
      default:
        return 'delivered';
    }
  }

  Future<void> _adminUpdateNextStatus(Map<String, dynamic> o) async {
    await _adminUpdateStatus(o, _nextStatusFor(o));
  }

  Future<void> _adminUpdateStatus(Map<String, dynamic> o, String statusValue) async {
    final id = o['id'] as String;
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/admin/orders/$id/status',
        query: {'status_value': statusValue},
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _adminListOrders();
    } catch (e) {
      _toast('Update status failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  // Courier
  Future<void> _courierListAvailable() async {
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodGet('/courier/available', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _courierAvailable = (js['orders'] as List?) ?? []);
    } catch (e) {
      _toast('Courier available failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _courierMyOrders() async {
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodGet('/courier/orders', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _courierOrders = (js['orders'] as List?) ?? []);
    } catch (e) {
      _toast('Courier orders failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _courierAccept(String orderId) async {
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/courier/orders/$orderId/accept',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _courierMyOrders();
    } catch (e) {
      _toast('Courier accept failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _courierPickedUp(String orderId) async {
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/courier/orders/$orderId/picked_up',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _courierMyOrders();
    } catch (e) {
      _toast('Courier picked up failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _courierDelivered(String orderId) async {
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/courier/orders/$orderId/delivered',
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _courierMyOrders();
    } catch (e) {
      _toast('Courier deliver failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _courierUpdateLocation(String orderId, double lat, double lon) async {
    final headers = await _foodHeaders();
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/courier/orders/$orderId/location',
        headers: headers,
        body: jsonEncode({'lat': lat, 'lon': lon}),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
    } catch (e) {
      _toast('Courier update location failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }
}
