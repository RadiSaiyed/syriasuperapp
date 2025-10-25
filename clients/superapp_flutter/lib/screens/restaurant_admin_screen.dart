import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../ui/glass.dart';
import '../services.dart';
import 'package:http/http.dart' as http;
import 'dart:io';
import 'package:flutter/services.dart';

class RestaurantAdminScreen extends StatefulWidget {
  final String restaurantId;
  final String? restaurantName;
  const RestaurantAdminScreen({super.key, required this.restaurantId, this.restaurantName});

  @override
  State<RestaurantAdminScreen> createState() => _RestaurantAdminScreenState();
}

class _RestaurantAdminScreenState extends State<RestaurantAdminScreen> {
  final _tokens = MultiTokenStore();
  bool _loading = false;

  // Restaurant fields
  final _nameCtrl = TextEditingController();
  final _cityCtrl = TextEditingController();
  final _addrCtrl = TextEditingController();
  final _descCtrl = TextEditingController();

  // Menu create
  final _miNameCtrl = TextEditingController();
  final _miPriceCtrl = TextEditingController(text: '10000');
  final _miDescCtrl = TextEditingController();

  // Image add
  final _imgUrlCtrl = TextEditingController();
  final _imgSortCtrl = TextEditingController(text: '0');

  List<dynamic> _menu = [];
  List<dynamic> _images = [];
  List<dynamic> _adminOrders = [];
  Map<String, dynamic>? _stats;
  String _statsRange = 'day'; // day|week|month
  // removed unused _lastCsvPath field

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

  String _fmtMoney(int? cents) {
    final v = (cents ?? 0) / 100.0;
    return '${v.toStringAsFixed(2)} SYP';
  }

  void _toast(String m) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  @override
  void initState() {
    super.initState();
    if (widget.restaurantName != null) {
      _nameCtrl.text = widget.restaurantName!;
    }
    _refreshAll();
  }

  Future<void> _refreshAll() async {
    setState(() => _loading = true);
    try {
      await Future.wait([
        _loadMenu(),
        _loadImages(),
        _loadAdminOrders(),
      ]);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<Map<String, String>> _auth() async => await _foodHeaders();

  Future<void> _saveRestaurant() async {
    final headers = await _auth();
    setState(() => _loading = true);
    try {
      final query = {
        if (_nameCtrl.text.trim().isNotEmpty) 'name': _nameCtrl.text.trim(),
        if (_cityCtrl.text.trim().isNotEmpty) 'city': _cityCtrl.text.trim(),
        if (_descCtrl.text.trim().isNotEmpty) 'description': _descCtrl.text.trim(),
        if (_addrCtrl.text.trim().isNotEmpty) 'address': _addrCtrl.text.trim(),
      };
      final res = await _foodPatch(
        '/admin/restaurants/${widget.restaurantId}',
        query: query,
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Saved');
    } catch (e) {
      _toast('Save failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadMenu() async {
    try {
      final res = await _foodGet(
        '/admin/restaurants/${widget.restaurantId}/menu_all',
        headers: await _auth(),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      setState(() => _menu = (jsonDecode(res.body) as List?) ?? []);
    } catch (e) {
      _toast('Menu failed: $e');
    }
  }

  Future<void> _loadImages() async {
    try {
      final res = await _foodGet(
        '/admin/restaurants/${widget.restaurantId}/images',
        headers: await _auth(),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      setState(() => _images = (jsonDecode(res.body) as List?) ?? []);
    } catch (e) {
      _toast('Images failed: $e');
    }
  }

  Future<void> _addMenuItem() async {
    final name = _miNameCtrl.text.trim();
    final syp = int.tryParse(_miPriceCtrl.text.trim());
    final desc = _miDescCtrl.text.trim();
    if (name.isEmpty || syp == null || syp <= 0) {
      _toast('Please provide name and price');
      return;
    }
    final headers = await _auth();
    setState(() => _loading = true);
    try {
      final query = {
        'name': name,
        'price_cents': '${syp * 100}',
        if (desc.isNotEmpty) 'description': desc,
      };
      final res = await _foodPost(
        '/admin/restaurants/${widget.restaurantId}/menu',
        query: query,
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      _miNameCtrl.clear(); _miDescCtrl.clear();
      await _loadMenu();
    } catch (e) {
      _toast('Add item failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _setPrice(String itemId) async {
    final ctrl = TextEditingController();
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
      if (syp == null || syp <= 0) { _toast('Invalid price'); return; }
      setState(() => _loading = true);
      try {
        final res = await _foodPatch(
          '/admin/menu/$itemId',
          query: {'price_cents': '${syp * 100}'},
          headers: await _auth(),
        );
        if (res.statusCode >= 400) throw Exception(res.body);
        await _loadMenu();
      } catch (e) {
        _toast('Update failed: $e');
      } finally { if (mounted) setState(() => _loading = false); }
    }
  }

  Future<void> _setAvailability(String itemId, bool available) async {
    final headers = await _auth();
    setState(() => _loading = true);
    try {
      final res = await _foodPatch(
        '/admin/menu/$itemId',
        query: {'available': available ? 'true' : 'false'},
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _loadMenu();
    } catch (e) {
      _toast('Availability failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _deleteMenuItem(String itemId) async {
    final headers = await _auth();
    setState(() => _loading = true);
    try {
      final res = await _foodDelete('/admin/menu/$itemId', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      await _loadMenu();
    } catch (e) {
      _toast('Delete failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _addImage() async {
    final url = _imgUrlCtrl.text.trim();
    final sort = int.tryParse(_imgSortCtrl.text.trim()) ?? 0;
    if (url.isEmpty) { _toast('Bild‑URL angeben'); return; }
    final headers = await _auth();
    setState(() => _loading = true);
    try {
      final body = jsonEncode([{ 'url': url, 'sort_order': sort }]);
      final res = await _foodPost(
        '/admin/restaurants/${widget.restaurantId}/images',
        headers: headers,
        body: body,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      _imgUrlCtrl.clear();
      await _loadImages();
    } catch (e) {
      _toast('Add image failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _deleteImage(String imageId) async {
    final headers = await _auth();
    setState(() => _loading = true);
    try {
      final res = await _foodDelete('/admin/images/$imageId', headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      await _loadImages();
    } catch (e) {
      _toast('Delete image failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _loadAdminOrders() async {
    try {
      final res = await _foodGet('/admin/orders', headers: await _auth());
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final all = (js['orders'] as List?) ?? [];
      setState(() => _adminOrders = all.where((o) => o['restaurant_id'] == widget.restaurantId).toList());
    } catch (e) {
      _toast('Admin orders failed: $e');
    }
  }

  Future<void> _loadStats() async {
    try {
      final res = await _foodGet(
        '/admin/restaurants/${widget.restaurantId}/stats',
        query: {'range': _statsRange},
        headers: await _auth(),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      setState(() => _stats = jsonDecode(res.body) as Map<String, dynamic>);
    } catch (e) {
      _toast('Stats failed: $e');
    }
  }

  Future<void> _exportCsv() async {
    final headers = await _auth();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _foodGet(
        '/admin/restaurants/${widget.restaurantId}/orders_export',
        query: {'range': _statsRange},
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final csv = res.body;
      // Save
      final ts = DateTime.now().toIso8601String().replaceAll(':', '-');
      final path = '${Directory.systemTemp.path}/orders_${widget.restaurantId}_$ts.csv';
      await File(path).writeAsString(csv);
      // Saved to temp path; path available in log/notification if needed
      if (!mounted) return;
      await showDialog(context: context, builder: (_) => AlertDialog(
        title: const Text('CSV export'),
        content: SizedBox(width: 500, height: 320, child: SingleChildScrollView(child: SelectableText(csv))),
        actions: [
          TextButton(onPressed: () { Clipboard.setData(ClipboardData(text: csv)); Navigator.pop(context); }, child: const Text('Copy')),
          FilledButton(onPressed: ()=>Navigator.pop(context), child: const Text('Close')),
        ],
      ));
      _toast('CSV gespeichert: $path');
    } catch (e) {
      _toast('CSV export failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  String _nextStatus(String s) {
    switch (s) {
      case 'created': return 'accepted';
      case 'accepted': return 'preparing';
      case 'preparing': return 'out_for_delivery';
      case 'out_for_delivery': return 'delivered';
      default: return 'delivered';
    }
  }

  Future<void> _updateOrderStatus(String orderId, String statusValue) async {
    final headers = await _auth();
    setState(() => _loading = true);
    try {
      final res = await _foodPost(
        '/admin/orders/$orderId/status',
        query: {'status_value': statusValue},
        headers: headers,
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      await _loadAdminOrders();
    } catch (e) {
      _toast('Update status failed: $e');
    } finally { if (mounted) setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.restaurantName == null ? 'Manage Restaurant' : 'Manage: ${widget.restaurantName}';
    return Scaffold(
      appBar: AppBar(title: Text(title), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero), actions: [
        IconButton(onPressed: _refreshAll, icon: const Icon(Icons.refresh))
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (_loading) const LinearProgressIndicator(),

        // Restaurant meta
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Restaurant', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _cityCtrl, decoration: const InputDecoration(labelText: 'City'))),
                const SizedBox(width: 8),
                Expanded(child: TextField(controller: _addrCtrl, decoration: const InputDecoration(labelText: 'Address'))),
              ]),
              const SizedBox(height: 8),
              TextField(controller: _descCtrl, decoration: const InputDecoration(labelText: 'Description')),
              const SizedBox(height: 8),
              FilledButton(onPressed: _loading ? null : _saveRestaurant, child: const Text('Save')),
            ]),
          ),
        ),

        const SizedBox(height: 16),
        // KPIs
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                const Expanded(child: Text('KPIs', style: TextStyle(fontWeight: FontWeight.w600))),
                DropdownButton<String>(
                  value: _statsRange,
                  items: const [
                    DropdownMenuItem(value: 'day', child: Text('Heute')),
                    DropdownMenuItem(value: 'week', child: Text('Woche')),
                    DropdownMenuItem(value: 'month', child: Text('Monat')),
                  ],
                  onChanged: (v) => setState(() => _statsRange = v ?? 'day'),
                ),
                const SizedBox(width: 8),
                FilledButton.tonal(onPressed: _loading ? null : _loadStats, child: const Text('Load')),
                const SizedBox(width: 8),
                FilledButton(onPressed: _loading ? null : _exportCsv, child: const Text('Export CSV')),
              ]),
              const SizedBox(height: 8),
              if (_stats != null) Wrap(spacing: 12, runSpacing: 8, children: [
                Chip(label: Text('Orders: ${_stats!['total_orders'] ?? 0}')),
                Chip(label: Text('Total: ${_stats!['total_cents'] ?? 0} SYP')),
                if ((_stats!['by_status'] as Map?) != null) ...[
                  for (final e in (_stats!['by_status'] as Map).entries)
                    Chip(label: Text('${e.key}: ${e.value}')),
                ],
              ]) else const Text('Noch nicht geladen.'),
            ]),
          ),
        ),

        const SizedBox(height: 16),
        // Menu
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Menu', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _miNameCtrl, decoration: const InputDecoration(labelText: 'Item name'))),
                const SizedBox(width: 8),
                SizedBox(width: 140, child: TextField(controller: _miPriceCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Price (SYP)'))),
              ]),
              const SizedBox(height: 8),
              TextField(controller: _miDescCtrl, decoration: const InputDecoration(labelText: 'Description (optional)')),
              const SizedBox(height: 8),
              FilledButton(onPressed: _loading ? null : _addMenuItem, child: const Text('Add Item')),
              const SizedBox(height: 8),
              if (_menu.isEmpty) const Text('No menu loaded.'),
              for (final m in _menu)
                ListTile(
                  title: Text(m['name'] ?? ''),
                  subtitle: Text('Price: ${_fmtMoney(m['price_cents'])}'),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(tooltip: 'Set price…', onPressed: _loading ? null : () => _setPrice(m['id'] as String), icon: const Icon(Icons.edit_outlined)),
                    IconButton(tooltip: 'Unavailable', onPressed: _loading ? null : () => _setAvailability(m['id'] as String, false), icon: const Icon(Icons.visibility_off_outlined)),
                    IconButton(tooltip: 'Available', onPressed: _loading ? null : () => _setAvailability(m['id'] as String, true), icon: const Icon(Icons.visibility_outlined)),
                    IconButton(tooltip: 'Delete', onPressed: _loading ? null : () => _deleteMenuItem(m['id'] as String), icon: const Icon(Icons.delete_outline)),
                  ]),
                ),
            ]),
          ),
        ),

        const SizedBox(height: 16),
        // Images
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Images', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _imgUrlCtrl, decoration: const InputDecoration(labelText: 'Image URL'))),
                const SizedBox(width: 8),
                SizedBox(width: 100, child: TextField(controller: _imgSortCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Sort'))),
                const SizedBox(width: 8),
                FilledButton.tonal(onPressed: _loading ? null : _addImage, child: const Text('Add')),
              ]),
              const SizedBox(height: 8),
              if (_images.isEmpty) const Text('No images.'),
              SizedBox(
                height: 120,
                child: ListView(scrollDirection: Axis.horizontal, children: [
                  const SizedBox(width: 8),
                  for (final im in _images)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: Stack(children: [
                        ClipRRect(
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
                        Positioned(
                          right: 4,
                          top: 4,
                          child: IconButton(
                            icon: const Icon(Icons.close, color: Colors.white),
                            onPressed: _loading ? null : () => _deleteImage(im['id'] as String),
                          ),
                        ),
                      ]),
                    ),
                ]),
              ),
            ]),
          ),
        ),

        const SizedBox(height: 16),
        // Orders for this restaurant
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                const Expanded(child: Text('Orders', style: TextStyle(fontWeight: FontWeight.w600))),
                FilledButton.tonal(onPressed: _loading ? null : _loadAdminOrders, child: const Text('Reload')),
              ]),
              const SizedBox(height: 8),
              if (_adminOrders.isEmpty) const Text('Keine Bestellungen.'),
              for (final o in _adminOrders)
                ListTile(
                  title: Text('Order ${o['id']}'),
                  subtitle: Text('Status: ${o['status']} • Total: ${_fmtMoney(o['total_cents'])}'),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(tooltip: 'Next', onPressed: _loading ? null : () => _updateOrderStatus(o['id'] as String, _nextStatus((o['status'] as String?) ?? 'created')), icon: const Icon(Icons.skip_next_outlined)),
                    IconButton(tooltip: 'Cancel', onPressed: _loading ? null : () => _updateOrderStatus(o['id'] as String, 'canceled'), icon: const Icon(Icons.cancel_outlined)),
                  ]),
                ),
            ]),
          ),
        ),
      ]),
    );
  }
}
