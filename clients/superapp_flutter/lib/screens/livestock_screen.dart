import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';

class LivestockScreen extends StatefulWidget {
  const LivestockScreen({super.key});
  @override
  State<LivestockScreen> createState() => _LivestockScreenState();
}

class _LivestockScreenState extends State<LivestockScreen>
    with SingleTickerProviderStateMixin {
  final _tokens = MultiTokenStore();
  String _health = '?';
  // Per-app login removed: rely on central login
  late TabController _tab;

  List<dynamic> _animals = [];
  List<dynamic> _products = [];
  List<dynamic> _orders = [];
  List<dynamic> _auctions = [];
  List<dynamic> _myAnimals = [];
  List<dynamic> _myProducts = [];
  List<dynamic> _myAuctions = [];
  List<dynamic> _sellerOrders = [];
  List<dynamic> _favAnimals = [];
  List<dynamic> _favProducts = [];

  // Filters
  Map<String, String> _animalFilters = {};
  Map<String, String> _productFilters = {};

  // Static options + helpers
  final List<String> _speciesOptions = const ['cow', 'sheep', 'goat', 'chicken', 'camel', 'buffalo'];
  final List<String> _unitOptions = const ['kg', 'liter', 'dozen'];
  final List<String> _productTypeOptions = const ['milk', 'eggs', 'cheese', 'meat'];
  final List<String> _sexOptions = const ['M', 'F'];

  Future<Map<String, String>> _livestockHeaders() =>
      authHeaders('livestock', store: _tokens);

  Uri _livestockUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('livestock', path, query: query);

  Future<http.Response> _livestockRequest(
    String method,
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) async {
    final reqHeaders = headers ?? await _livestockHeaders();
    final uri = _livestockUri(path, query: query);
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

  Future<http.Response> _livestockGet(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
  }) =>
      _livestockRequest('GET', path, query: query, headers: headers);

  Future<http.Response> _livestockPost(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) =>
      _livestockRequest('POST', path, query: query, headers: headers, body: body);

  Future<http.Response> _livestockPatch(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) =>
      _livestockRequest('PATCH', path, query: query, headers: headers, body: body);

  Future<http.Response> _livestockDelete(
    String path, {
    Map<String, String>? query,
    Map<String, String>? headers,
    Object? body,
  }) =>
      _livestockRequest('DELETE', path,
          query: query, headers: headers, body: body);

  String _fmtCents(dynamic cents) {
    final n = (cents is num) ? cents.toInt() : int.tryParse('$cents') ?? 0;
    return (n / 100).toStringAsFixed(2);
  }

  String _fmtDate(dynamic iso) {
    try {
      final dt = DateTime.tryParse('$iso');
      if (dt == null) return '$iso';
      return '${dt.year.toString().padLeft(4, '0')}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return '$iso';
    }
  }

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 5, vsync: this);
    _healthCheck();
    _loadAnimals();
    _loadProducts();
    _loadAuctions();
  }

  Future<void> _healthCheck() async {
    try {
      final r = await _livestockGet('/health');
      final js = jsonDecode(r.body);
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (_) {
      setState(() => _health = 'error');
    }
  }

  Future<void> _loadAnimals() async {
    try {
      final query =
          _animalFilters.isEmpty ? null : Map<String, String>.from(_animalFilters);
      final r = await _livestockGet('/market/animals', query: query);
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _animals = js['animals'] as List<dynamic>);
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _loadProducts() async {
    try {
      final query = _productFilters.isEmpty
          ? null
          : Map<String, String>.from(_productFilters);
      final r = await _livestockGet('/market/products', query: query);
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _products = js['products'] as List<dynamic>);
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _loadOrders() async {
    final h = await _livestockHeaders();
    try {
      final r = await _livestockGet('/market/orders', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _orders = js['orders'] as List<dynamic>);
    } catch (e) {
      _toast('$e');
    }
  }
  Future<void> _loadFavorites() async {
    final h = await _livestockHeaders();
    try {
      final ra =
          await _livestockGet('/market/animals/favorites', headers: h);
      final rp =
          await _livestockGet('/market/products/favorites', headers: h);
      if (ra.statusCode < 400) {
        setState(() => _favAnimals = (jsonDecode(ra.body) as Map<String, dynamic>)['animals'] as List<dynamic>);
      }
      if (rp.statusCode < 400) {
        setState(() => _favProducts = (jsonDecode(rp.body) as Map<String, dynamic>)['products'] as List<dynamic>);
      }
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadAuctions() async {
    try {
      final r = await _livestockGet('/market/auctions');
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _auctions = js['auctions'] as List<dynamic>);
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _orderProduct(Map<String, dynamic> p) async {
    final qtyCtrl = TextEditingController(text: '1');
    final qty = await showDialog<int>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Menge bestellen'),
        content: TextField(controller: qtyCtrl, keyboardType: TextInputType.number),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, int.tryParse(qtyCtrl.text.trim())),
              child: const Text('OK')),
        ],
      ),
    );
    if (qty == null || qty <= 0) return;
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Please log in first');
      return;
    }
    try {
      final id = p['id'];
      final r = await _livestockPost(
        '/market/products/$id/order',
        headers: h,
        body: jsonEncode({'qty': qty}),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Bestellung erstellt');
      _loadProducts();
      _loadOrders();
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _orderAnimal(Map<String, dynamic> a) async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Please log in first');
      return;
    }
    try {
      final id = a['id'];
      final r = await _livestockPost('/market/animals/$id/order', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Bestellung erstellt');
      _loadAnimals();
      _loadOrders();
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _seed() async {
    try {
      final r = await _livestockPost('/admin/seed');
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Seed ok');
      _loadAnimals();
      _loadProducts();
    } catch (e) {
      _toast('Seed fehlgeschlagen: $e');
    }
  }

  // Per-app OTP login removed: use central login

  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Livestock'),
        bottom: TabBar(
          controller: _tab,
          tabs: const [
            Tab(text: 'Products'),
            Tab(text: 'Animals'),
            Tab(text: 'Favorites'),
            Tab(text: 'My Orders'),
            Tab(text: 'Auctions'),
            Tab(text: 'Seller'),
          ],
        ),
        actions: [
          Center(child: Text(_health, style: const TextStyle(fontSize: 12))),
          const SizedBox(width: 12),
          TextButton(onPressed: _seed, child: const Text('Seed')),
          const SizedBox(width: 8),
        ],
      ),
      body: TabBarView(
        controller: _tab,
        children: [
          _buildProducts(),
          _buildAnimals(),
          _buildFavorites(),
          _buildOrders(),
          _buildAuctions(),
          _buildSeller(),
        ],
      ),
    );
  }

  Widget _buildProducts() {
    return RefreshIndicator(
      onRefresh: () async {
        await _loadProducts();
        await _loadOrders();
      },
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              icon: const Icon(Icons.filter_list),
              label: const Text('Filter'),
              onPressed: _openProductFilters,
            ),
          ),
          ..._products.map((p) => Card(
                child: ListTile(
                  title: Text('${p['product_type']} (${p['unit']})'),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Qty ${p['quantity']} • Price ${_fmtCents(p['price_per_unit_cents'])}'),
                      const SizedBox(height: 4),
                      Wrap(spacing: 6, runSpacing: 2, children: [
                        Chip(label: Text('${p['status']}')),
                        Chip(label: Text('Typ: ${p['product_type']}')),
                        Chip(label: Text('Einheit: ${p['unit']}')),
                      ]),
                    ],
                  ),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: () => _favProduct(p), icon: const Icon(Icons.favorite_border)),
                    ElevatedButton(onPressed: () => _orderProduct(p), child: const Text('Order')),
                  ]),
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildAnimals() {
    return RefreshIndicator(
      onRefresh: () async {
        await _loadAnimals();
        await _loadOrders();
      },
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              icon: const Icon(Icons.filter_list),
              label: const Text('Filter'),
              onPressed: _openAnimalFilters,
            ),
          ),
          ..._animals.map((a) => Card(
                child: ListTile(
                  title: Text('${a['species']} • ${a['breed'] ?? ''}'),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${a['sex'] ?? ''} • ${a['weight_kg'] ?? '-'} kg • Price ${_fmtCents(a['price_cents'])}'),
                      const SizedBox(height: 4),
                      Wrap(spacing: 6, runSpacing: 2, children: [
                        Chip(label: Text('${a['status']}')),
                        if (a['sex'] != null) Chip(label: Text('Sex: ${a['sex']}')),
                        if (a['age_months'] != null) Chip(label: Text('Alter: ${a['age_months']}m')),
                      ]),
                    ],
                  ),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: () => _favAnimal(a), icon: const Icon(Icons.favorite_border)),
                    ElevatedButton(onPressed: () => _orderAnimal(a), child: const Text('Order')),
                  ]),
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildFavorites() {
    return RefreshIndicator(
      onRefresh: _loadFavorites,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          ElevatedButton(onPressed: _loadFavorites, child: const Text('Refresh')),
          const SizedBox(height: 8),
          if (_favProducts.isNotEmpty) const Text('Products', style: TextStyle(fontWeight: FontWeight.bold)),
          ..._favProducts.map((p) => Card(
                child: ListTile(
                  title: Text('${p['product_type']} (${p['unit']})'),
                  subtitle: Text('Qty ${p['quantity']} • Price ${_fmtCents(p['price_per_unit_cents'])}'),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: () => _unfavProduct(p), icon: const Icon(Icons.delete_outline)),
                    ElevatedButton(onPressed: () => _orderProduct(p), child: const Text('Order')),
                  ]),
                ),
              )),
          if (_favAnimals.isNotEmpty) const SizedBox(height: 8),
          if (_favAnimals.isNotEmpty) const Text('Animals', style: TextStyle(fontWeight: FontWeight.bold)),
          ..._favAnimals.map((a) => Card(
                child: ListTile(
                  title: Text('${a['species']} • ${a['breed'] ?? ''}'),
                  subtitle: Text('${a['sex'] ?? ''} • ${_fmtCents(a['price_cents'])}'),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: () => _unfavAnimal(a), icon: const Icon(Icons.delete_outline)),
                    ElevatedButton(onPressed: () => _orderAnimal(a), child: const Text('Order')),
                  ]),
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildAuctions() {
    return RefreshIndicator(
      onRefresh: _loadAuctions,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          ElevatedButton(onPressed: _loadAuctions, child: const Text('Refresh')),
          const SizedBox(height: 8),
          ..._auctions.map((a) => Card(
                child: ListTile(
                  title: Text('Auction ${a['id'].toString().substring(0, 6)}'),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Current ${_fmtCents(a['current_price_cents'])} • Ends ${_fmtDate(a['ends_at'])}'),
                      const SizedBox(height: 4),
                      Wrap(spacing: 6, children: [
                        Chip(label: Text('${a['status']}')),
                      ]),
                    ],
                  ),
                  trailing: ElevatedButton(onPressed: () => _bidAuction(a), child: const Text('Bieten')),
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildSeller() {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        const Text('Seller actions', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          ElevatedButton(onPressed: _createRanch, child: const Text('Create ranch')),
          ElevatedButton(onPressed: _createAnimal, child: const Text('Add animal')),
          ElevatedButton(onPressed: _createProduct, child: const Text('Add product')),
          ElevatedButton(onPressed: _loadMyAnimals, child: const Text('My animals')),
          ElevatedButton(onPressed: _loadMyProducts, child: const Text('My products')),
          ElevatedButton(onPressed: _loadSellerOrders, child: const Text('Seller orders')),
          ElevatedButton(onPressed: _createAuction, child: const Text('Create auction (ID)')),
          ElevatedButton(onPressed: _createAuctionFromPicker, child: const Text('Create auction from animal')),
          ElevatedButton(onPressed: _loadMyAuctions, child: const Text('My auctions')),
        ]),
        const Divider(),
        if (_myAnimals.isNotEmpty) const Text('My animals'),
        ..._myAnimals.map((a) => ListTile(
              title: Text('${a['species']} • ${a['breed'] ?? ''}'),
              subtitle: Text('${a['sex'] ?? ''} • ${a['status']} • Price ${(a['price_cents'] / 100).toStringAsFixed(2)}'),
              trailing: Wrap(spacing: 8, children: [
                IconButton(onPressed: () => _editAnimal(a), icon: const Icon(Icons.edit)),
                IconButton(onPressed: () => _deleteAnimal(a), icon: const Icon(Icons.delete_outline)),
              ]),
            )),
        if (_myProducts.isNotEmpty) const Divider(),
        if (_myProducts.isNotEmpty) const Text('My products'),
        ..._myProducts.map((p) => ListTile(
              title: Text('${p['product_type']} (${p['unit']})'),
              subtitle: Text('Qty ${p['quantity']} • Price ${(p['price_per_unit_cents'] / 100).toStringAsFixed(2)} • ${p['status']}'),
              trailing: Wrap(spacing: 8, children: [
                IconButton(onPressed: () => _editProduct(p), icon: const Icon(Icons.edit)),
                IconButton(onPressed: () => _deleteProduct(p), icon: const Icon(Icons.delete_outline)),
              ]),
            )),
        if (_sellerOrders.isNotEmpty) const Divider(),
        if (_sellerOrders.isNotEmpty) const Text('Seller‑Bestellungen'),
        ..._sellerOrders.map((o) => ListTile(
              title: Text('Order ${o['id']} • ${o['type']}'),
              subtitle: Text('Qty ${o['qty']} • Total ${(o['total_cents'] / 100).toStringAsFixed(2)} • ${o['status']}'),
            )),
        if (_myAuctions.isNotEmpty) const Divider(),
        if (_myAuctions.isNotEmpty) const Text('Meine Auktionen'),
        ..._myAuctions.map((a) => ListTile(
              title: Text('Auktion ${a['id'].toString().substring(0,6)}'),
              subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Aktuell ${_fmtCents(a['current_price_cents'])} • Ende ${_fmtDate(a['ends_at'])}'),
                const SizedBox(height: 4),
                Wrap(spacing: 6, children: [Chip(label: Text('${a['status']}'))]),
              ]),
              trailing: a['status'] == 'open'
                  ? ElevatedButton(onPressed: () => _closeAuction(a), child: const Text('Close auction'))
                  : null,
            )),
      ],
    );
  }

  Future<void> _createRanch() async {
    final nameCtrl = TextEditingController();
    final locCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final data = await showDialog<Map<String, String>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Ranch anlegen'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
          TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Location')),
          TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Beschreibung')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'name': nameCtrl.text,
            'location': locCtrl.text,
            'description': descCtrl.text,
          }), child: const Text('Anlegen')),
        ],
      ),
    );
    if (data == null) return;
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockPost(
        '/seller/ranch',
        headers: h,
        body: jsonEncode(data),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Ranch erstellt');
    } catch (e) { _toast('$e'); }
  }

  Future<void> _createAnimal() async {
    String speciesVal = _speciesOptions.first;
    final breedCtrl = TextEditingController();
    String sexVal = _sexOptions.first;
    final ageCtrl = TextEditingController(text: '0');
    final weightCtrl = TextEditingController(text: '0');
    final priceCtrl = TextEditingController(text: '0');
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setSt) {
        return AlertDialog(
          title: const Text('Add animal'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            DropdownButtonFormField<String>(
              initialValue: speciesVal,
              items: _speciesOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => speciesVal = v ?? speciesVal),
              decoration: const InputDecoration(labelText: 'Species'),
            ),
            TextField(controller: breedCtrl, decoration: const InputDecoration(labelText: 'Breed')),
            DropdownButtonFormField<String>(
              initialValue: sexVal,
              items: _sexOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => sexVal = v ?? sexVal),
              decoration: const InputDecoration(labelText: 'Sex'),
            ),
            TextField(controller: ageCtrl, decoration: const InputDecoration(labelText: 'Alter (Monate)'), keyboardType: TextInputType.number),
            TextField(controller: weightCtrl, decoration: const InputDecoration(labelText: 'Gewicht (kg)'), keyboardType: TextInputType.number),
            TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price (cents)'), keyboardType: TextInputType.number),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, {
              'species': speciesVal,
              'breed': breedCtrl.text,
              'sex': sexVal,
              'age_months': int.tryParse(ageCtrl.text) ?? 0,
              'weight_kg': int.tryParse(weightCtrl.text) ?? 0,
              'price_cents': int.tryParse(priceCtrl.text) ?? 0,
            }), child: const Text('Create')),
          ],
        );
      }),
    );
    if (data == null) return;
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockPost(
        '/seller/animals',
        headers: h,
        body: jsonEncode(data),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Tier erstellt');
    } catch (e) { _toast('$e'); }
  }

  Future<void> _createProduct() async {
    String typeVal = _productTypeOptions.first;
    String unitVal = _unitOptions.first;
    final qtyCtrl = TextEditingController(text: '1');
    final priceCtrl = TextEditingController(text: '0');
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setSt) {
        return AlertDialog(
          title: const Text('Add product'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            DropdownButtonFormField<String>(
              initialValue: typeVal,
              items: _productTypeOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => typeVal = v ?? typeVal),
              decoration: const InputDecoration(labelText: 'Type'),
            ),
            DropdownButtonFormField<String>(
              initialValue: unitVal,
              items: _unitOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => unitVal = v ?? unitVal),
              decoration: const InputDecoration(labelText: 'Unit'),
            ),
            TextField(controller: qtyCtrl, decoration: const InputDecoration(labelText: 'Quantity'), keyboardType: TextInputType.number),
            TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price/unit (cents)'), keyboardType: TextInputType.number),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, {
              'product_type': typeVal,
              'unit': unitVal,
              'quantity': int.tryParse(qtyCtrl.text) ?? 0,
              'price_per_unit_cents': int.tryParse(priceCtrl.text) ?? 0,
            }), child: const Text('Create')),
          ],
        );
      }),
    );
    if (data == null) return;
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockPost(
        '/seller/products',
        headers: h,
        body: jsonEncode(data),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Produkt erstellt');
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadMyAnimals() async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockGet('/seller/animals', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      setState(() => _myAnimals = jsonDecode(r.body) as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadMyProducts() async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockGet('/seller/products', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      setState(() => _myProducts = jsonDecode(r.body) as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadSellerOrders() async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockGet('/seller/orders', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      setState(() => _sellerOrders = (jsonDecode(r.body) as Map<String, dynamic>)['orders'] as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _createAuction() async {
    final animalIdCtrl = TextEditingController();
    final startCtrl = TextEditingController(text: '0');
    final endsCtrl = TextEditingController();
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Create auction'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: animalIdCtrl, decoration: const InputDecoration(labelText: 'Animal ID')),
          TextField(controller: startCtrl, decoration: const InputDecoration(labelText: 'Startpreis (Cent)'), keyboardType: TextInputType.number),
          TextField(controller: endsCtrl, decoration: const InputDecoration(labelText: 'Ends (ISO e.g. 2025-01-01T12:00:00Z)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'animal_id': animalIdCtrl.text,
            'starting_price_cents': int.tryParse(startCtrl.text) ?? 0,
            'ends_at_iso': endsCtrl.text,
          }), child: const Text('Create')),
        ],
      ),
    );
    if (data == null) return;
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockPost(
        '/seller/auctions',
        headers: h,
        body: jsonEncode(data),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Auction created');
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadMyAuctions() async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await _livestockGet('/seller/auctions', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      setState(() => _myAuctions = jsonDecode(r.body) as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _closeAuction(Map<String, dynamic> a) async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final id = a['id'];
      final r = await _livestockPost(
        '/seller/auctions/$id/close',
        headers: h,
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Auction closed');
      _loadMyAuctions();
    } catch (e) { _toast('$e'); }
  }
  Future<void> _bidAuction(Map<String, dynamic> a) async {
    final amtCtrl = TextEditingController(text: ((a['current_price_cents'] ?? a['starting_price_cents']) + 100).toString());
    final amt = await showDialog<int>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Gebot (Cent)'),
        content: TextField(controller: amtCtrl, keyboardType: TextInputType.number),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, int.tryParse(amtCtrl.text)), child: const Text('Bieten')),
        ],
      ),
    );
    if (amt == null || amt <= 0) return;
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Please log in first');
      return;
    }
    try {
      final id = a['id'];
      final r = await _livestockPost(
        '/market/auctions/$id/bid',
        headers: h,
        body: jsonEncode({'amount_cents': amt}),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Gebot platziert');
      _loadAuctions();
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _favProduct(Map<String, dynamic> p) async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Please log in first');
      return;
    }
    try {
      final id = p['id'];
      final r = await _livestockPost(
        '/market/products/$id/favorite',
        headers: h,
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Favorit gespeichert');
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _favAnimal(Map<String, dynamic> a) async {
    final h = await _livestockHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Please log in first');
      return;
    }
    try {
      final id = a['id'];
      final r = await _livestockPost(
        '/market/animals/$id/favorite',
        headers: h,
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Favorit gespeichert');
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _unfavProduct(Map<String, dynamic> p) async {
    final h = await _livestockHeaders();
    try {
      final id = p['id'];
      final r = await _livestockDelete('/market/products/$id/favorite', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _loadFavorites();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _unfavAnimal(Map<String, dynamic> a) async {
    final h = await _livestockHeaders();
    try {
      final id = a['id'];
      final r = await _livestockDelete('/market/animals/$id/favorite', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _loadFavorites();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _openProductFilters() async {
    String typeVal = _productFilters['type'] ?? (_productTypeOptions.isNotEmpty ? _productTypeOptions.first : '');
    String unitVal = _productFilters['unit'] ?? (_unitOptions.isNotEmpty ? _unitOptions.first : '');
    final locCtrl = TextEditingController(text: _productFilters['location'] ?? '');
    final minCtrl = TextEditingController(text: _productFilters['min_price'] ?? '');
    final maxCtrl = TextEditingController(text: _productFilters['max_price'] ?? '');
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setSt) {
        return AlertDialog(
          title: const Text('Filter (Products)'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            DropdownButtonFormField<String>(
              initialValue: typeVal,
              items: _productTypeOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => typeVal = v ?? typeVal),
              decoration: const InputDecoration(labelText: 'Type'),
            ),
            DropdownButtonFormField<String>(
              initialValue: unitVal,
              items: _unitOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => unitVal = v ?? unitVal),
              decoration: const InputDecoration(labelText: 'Unit'),
            ),
            TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Location')),
            TextField(controller: minCtrl, decoration: const InputDecoration(labelText: 'Min price (cents)'), keyboardType: TextInputType.number),
            TextField(controller: maxCtrl, decoration: const InputDecoration(labelText: 'Max price (cents)'), keyboardType: TextInputType.number),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Reset')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Anwenden')),
          ],
        );
      }),
    );
    setState(() {
      if (ok == true) {
        _productFilters = {
          if (typeVal.isNotEmpty) 'type': typeVal,
          if (unitVal.isNotEmpty) 'unit': unitVal,
          if (locCtrl.text.isNotEmpty) 'location': locCtrl.text,
          if (minCtrl.text.isNotEmpty) 'min_price': minCtrl.text,
          if (maxCtrl.text.isNotEmpty) 'max_price': maxCtrl.text,
        };
      } else {
        _productFilters = {};
      }
    });
    _loadProducts();
  }

  Future<void> _openAnimalFilters() async {
    String speciesVal = _animalFilters['species'] ?? (_speciesOptions.isNotEmpty ? _speciesOptions.first : '');
    final breedCtrl = TextEditingController(text: _animalFilters['breed'] ?? '');
    String sexVal = _animalFilters['sex'] ?? (_sexOptions.isNotEmpty ? _sexOptions.first : '');
    final locCtrl = TextEditingController(text: _animalFilters['location'] ?? '');
    final minCtrl = TextEditingController(text: _animalFilters['min_price'] ?? '');
    final maxCtrl = TextEditingController(text: _animalFilters['max_price'] ?? '');
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setSt) {
        return AlertDialog(
          title: const Text('Filter (Animals)'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            DropdownButtonFormField<String>(
              initialValue: speciesVal,
              items: _speciesOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => speciesVal = v ?? speciesVal),
              decoration: const InputDecoration(labelText: 'Species'),
            ),
            TextField(controller: breedCtrl, decoration: const InputDecoration(labelText: 'Breed')),
            DropdownButtonFormField<String>(
              initialValue: sexVal,
              items: _sexOptions.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => setSt(() => sexVal = v ?? sexVal),
              decoration: const InputDecoration(labelText: 'Sex'),
            ),
            TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Location')),
            TextField(controller: minCtrl, decoration: const InputDecoration(labelText: 'Min price (cents)'), keyboardType: TextInputType.number),
            TextField(controller: maxCtrl, decoration: const InputDecoration(labelText: 'Max price (cents)'), keyboardType: TextInputType.number),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Reset')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Anwenden')),
          ],
        );
      }),
    );
    setState(() {
      if (ok == true) {
        _animalFilters = {
          if (speciesVal.isNotEmpty) 'species': speciesVal,
          if (breedCtrl.text.isNotEmpty) 'breed': breedCtrl.text,
          if (sexVal.isNotEmpty) 'sex': sexVal,
          if (locCtrl.text.isNotEmpty) 'location': locCtrl.text,
          if (minCtrl.text.isNotEmpty) 'min_price': minCtrl.text,
          if (maxCtrl.text.isNotEmpty) 'max_price': maxCtrl.text,
        };
      } else {
        _animalFilters = {};
      }
    });
    _loadAnimals();
  }

  Future<void> _createAuctionFromPicker() async {
    await _loadMyAnimals();
    final choices = _myAnimals.where((e) => (e['status'] == 'available')).toList();
    if (choices.isEmpty) {
      _toast('No available animals');
      return;
    }
    final selected = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => SimpleDialog(
        title: const Text('Select animal'),
        children: choices
            .map((a) => SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, a),
                  child: Text('${a['id'].toString().substring(0,6)} • ${a['species']} ${a['breed'] ?? ''}'),
                ))
            .toList(),
      ),
    );
    if (selected == null) return;
    final startCtrl = TextEditingController(text: '0');
    final endsCtrl = TextEditingController();
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Create auction'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('Tier: ${selected['id']}'),
          TextField(controller: startCtrl, decoration: const InputDecoration(labelText: 'Startpreis (Cent)'), keyboardType: TextInputType.number),
          TextField(controller: endsCtrl, decoration: const InputDecoration(labelText: 'Ends (ISO e.g. 2025-01-01T12:00:00Z)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'animal_id': selected['id'],
            'starting_price_cents': int.tryParse(startCtrl.text) ?? 0,
            'ends_at_iso': endsCtrl.text,
          }), child: const Text('Create')),
        ],
      ),
    );
    if (data == null) return;
    final h = await _livestockHeaders();
    try {
      final r = await _livestockPost(
        '/seller/auctions',
        headers: h,
        body: jsonEncode(data),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Auction created');
      _loadMyAuctions();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _editAnimal(Map<String, dynamic> a) async {
    final priceCtrl = TextEditingController(text: a['price_cents']?.toString() ?? '0');
    final statusCtrl = TextEditingController(text: a['status'] ?? 'available');
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Edit animal'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price (cents)'), keyboardType: TextInputType.number),
          TextField(controller: statusCtrl, decoration: const InputDecoration(labelText: 'Status (available/sold/auction)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'price_cents': int.tryParse(priceCtrl.text),
            'status': statusCtrl.text,
          }), child: const Text('Save')),
        ],
      ),
    );
    if (data == null) return;
    final h = await _livestockHeaders();
    try {
      final id = a['id'];
      final r = await _livestockPatch(
        '/seller/animals/$id',
        headers: h,
        body: jsonEncode(data),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Gespeichert');
      _loadMyAnimals();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _deleteAnimal(Map<String, dynamic> a) async {
    final h = await _livestockHeaders();
    try {
      final id = a['id'];
      final r = await _livestockDelete('/seller/animals/$id', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Deleted');
      _loadMyAnimals();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _editProduct(Map<String, dynamic> p) async {
    final qtyCtrl = TextEditingController(text: p['quantity']?.toString() ?? '0');
    final priceCtrl = TextEditingController(text: p['price_per_unit_cents']?.toString() ?? '0');
    final statusCtrl = TextEditingController(text: p['status'] ?? 'active');
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Edit product'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: qtyCtrl, decoration: const InputDecoration(labelText: 'Quantity'), keyboardType: TextInputType.number),
          TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price/unit (cents)'), keyboardType: TextInputType.number),
          TextField(controller: statusCtrl, decoration: const InputDecoration(labelText: 'Status (active/sold_out)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'quantity': int.tryParse(qtyCtrl.text),
            'price_per_unit_cents': int.tryParse(priceCtrl.text),
            'status': statusCtrl.text,
          }), child: const Text('Save')),
        ],
      ),
    );
    if (data == null) return;
    final h = await _livestockHeaders();
    try {
      final id = p['id'];
      final r = await _livestockPatch(
        '/seller/products/$id',
        headers: h,
        body: jsonEncode(data),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Gespeichert');
      _loadMyProducts();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _deleteProduct(Map<String, dynamic> p) async {
    final h = await _livestockHeaders();
    try {
      final id = p['id'];
      final r = await _livestockDelete('/seller/products/$id', headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Deleted');
      _loadMyProducts();
    } catch (e) { _toast('$e'); }
  }

  Widget _buildOrders() {
    return RefreshIndicator(
      onRefresh: _loadOrders,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          ElevatedButton(onPressed: _loadOrders, child: const Text('Refresh')),
          const SizedBox(height: 8),
          ..._orders.map((o) => ListTile(
                title: Text('Order ${o['id']} • ${o['type']}'),
                subtitle: Row(children: [
                  Text('Qty ${o['qty']} • Total ${_fmtCents(o['total_cents'])}  '),
                  Chip(label: Text('${o['status']}')),
                ]),
              )),
        ],
      ),
    );
  }
}
// ignore_for_file: use_build_context_synchronously
