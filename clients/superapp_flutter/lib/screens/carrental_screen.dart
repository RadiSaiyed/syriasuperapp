import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
// url_launcher no longer used for maps; keep imports lean
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../map_tiles.dart';
import '../services.dart';

class CarRentalScreen extends StatefulWidget {
  const CarRentalScreen({super.key});
  @override
  State<CarRentalScreen> createState() => _CarRentalScreenState();
}

class _CarRentalScreenState extends State<CarRentalScreen>
    with SingleTickerProviderStateMixin {
  String _health = '?';
  // removed unused _loading field
  late TabController _tab;

  List<dynamic> _vehicles = [];
  List<dynamic> _bookings = [];
  List<dynamic> _favorites = [];
  // Seller
  List<dynamic> _myVehicles = [];
  List<dynamic> _sellerOrders = [];
  Map<String, String> _filters = {};
  int _offset = 0;
  final int _limit = 20;
  int _total = 0;

  Future<Map<String, String>> _carRentalHeaders() =>
      authHeaders('carrental');

  Uri _carRentalUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('carrental', path, query: query);

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 4, vsync: this);
    _healthCheck();
    _loadVehicles();
  }

  String _fmtCents(dynamic cents) {
    final n = (cents is num) ? cents.toInt() : int.tryParse('$cents') ?? 0;
    return (n / 100).toStringAsFixed(2);
  }

  // Per-app login removed: use central login

  Future<void> _healthCheck() async {
    // set a loading UI here if desired
    try {
      final r = await http.get(_carRentalUri('/health'));
      final js = jsonDecode(r.body);
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      _toast('$e');
    } finally {
      // done
    }
  }

  Future<void> _loadVehicles({bool reset = false}) async {
    try {
      if (reset) {
        _offset = 0;
        setState(() { _vehicles = []; _total = 0; });
      }
      final qp = Map<String, String>.from(_filters);
      qp['limit'] = '$_limit';
      qp['offset'] = '$_offset';
      final uri = _carRentalUri('/market/vehicles', query: qp);
      final r = await http.get(uri);
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final list = (js['vehicles'] as List<dynamic>);
      setState(() {
        _total = (js['total'] as num?)?.toInt() ?? list.length;
        _vehicles = [..._vehicles, ...list];
        _offset = _vehicles.length;
      });
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _loadBookings() async {
    final h = await _carRentalHeaders();
    try {
      final r = await http.get(_carRentalUri('/market/bookings'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _bookings = js['bookings'] as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadFavorites() async {
    final h = await _carRentalHeaders();
    try {
      final r = await http.get(_carRentalUri('/market/vehicles/favorites'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _favorites = js['vehicles'] as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _bookVehicle(Map<String, dynamic> v) async {
    DateTime now = DateTime.now();
    final sd = await showDatePicker(context: context, initialDate: now, firstDate: now, lastDate: now.add(const Duration(days: 365)));
    if (sd == null) return;
    final ed = await showDatePicker(context: context, initialDate: sd.add(const Duration(days: 1)), firstDate: sd.add(const Duration(days: 1)), lastDate: now.add(const Duration(days: 370)));
    if (ed == null) return;
    final h = await _carRentalHeaders();
    if (!h.containsKey('Authorization')) { _toast('Please log in first'); return; }
    try {
      final id = v['id'];
      String sds = sd.toIso8601String().substring(0,10);
      String eds = ed.toIso8601String().substring(0,10);
      final r = await http.post(
          _carRentalUri('/market/vehicles/$id/book'),
          headers: h,
          body: jsonEncode({'start_date': sds, 'end_date': eds}));
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Buchung erstellt');
      _loadBookings();
    } catch (e) { _toast('$e'); }
  }

  // Seller helpers
  Future<void> _createCompany() async {
    final nameCtrl = TextEditingController();
    final locCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final data = await showDialog<Map<String, String>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Firma anlegen'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
          TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Ort')),
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
    final h = await _carRentalHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await http.post(_carRentalUri('/company'), headers: h, body: jsonEncode(data));
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Firma erstellt');
    } catch (e) { _toast('$e'); }
  }

  Future<void> _createVehicle() async {
    final makeCtrl = TextEditingController();
    final modelCtrl = TextEditingController();
    final yearCtrl = TextEditingController(text: '2020');
    String transVal = 'auto';
    final seatsCtrl = TextEditingController(text: '5');
    final locCtrl = TextEditingController();
    final priceCtrl = TextEditingController(text: '20000');
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setSt) {
        return AlertDialog(
        title: const Text('Add vehicle'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: makeCtrl, decoration: const InputDecoration(labelText: 'Marke')),
            TextField(controller: modelCtrl, decoration: const InputDecoration(labelText: 'Modell')),
            TextField(controller: yearCtrl, decoration: const InputDecoration(labelText: 'Baujahr'), keyboardType: TextInputType.number),
            DropdownButtonFormField<String>(initialValue: transVal, items: const [DropdownMenuItem(value: 'auto', child: Text('Automatik')), DropdownMenuItem(value: 'manual', child: Text('Schalter'))], onChanged: (v) => setSt(() => transVal = v ?? transVal), decoration: const InputDecoration(labelText: 'Getriebe')),
            TextField(controller: seatsCtrl, decoration: const InputDecoration(labelText: 'Sitze'), keyboardType: TextInputType.number),
            TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Ort')),
            TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price/day (cents)'), keyboardType: TextInputType.number),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, {
              'make': makeCtrl.text,
              'model': modelCtrl.text,
              'year': int.tryParse(yearCtrl.text),
              'transmission': transVal,
              'seats': int.tryParse(seatsCtrl.text),
              'location': locCtrl.text,
              'price_per_day_cents': int.tryParse(priceCtrl.text) ?? 0,
            }), child: const Text('Erstellen')),
          ],
        );
      }),
    );
    if (data == null) return;
    final h = await _carRentalHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await http.post(_carRentalUri('/vehicles'), headers: h, body: jsonEncode(data));
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Fahrzeug erstellt');
      _loadMyVehicles();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadMyVehicles() async {
    final h = await _carRentalHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await http.get(_carRentalUri('/vehicles'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      setState(() => _myVehicles = jsonDecode(r.body) as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _loadSellerOrders() async {
    final h = await _carRentalHeaders();
    if (!h.containsKey('Authorization')) { _toast('Seller login required'); return; }
    try {
      final r = await http.get(_carRentalUri('/orders'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      setState(() => _sellerOrders = (jsonDecode(r.body) as Map<String, dynamic>)['bookings'] as List<dynamic>);
    } catch (e) { _toast('$e'); }
  }

  Future<void> _editVehicle(Map<String, dynamic> v) async {
    final priceCtrl = TextEditingController(text: v['price_per_day_cents']?.toString() ?? '0');
    String statusVal = v['status'] ?? 'available';
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setSt) {
        return AlertDialog(
          title: const Text('Fahrzeug bearbeiten'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price/day (cents)'), keyboardType: TextInputType.number),
            DropdownButtonFormField<String>(initialValue: statusVal, items: const [DropdownMenuItem(value: 'available', child: Text('Available')), DropdownMenuItem(value: 'unavailable', child: Text('Unavailable'))], onChanged: (v) => setSt(() => statusVal = v ?? statusVal), decoration: const InputDecoration(labelText: 'Status')),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, {
              'price_per_day_cents': int.tryParse(priceCtrl.text),
              'status': statusVal,
            }), child: const Text('Speichern')),
          ],
        );
      }),
    );
    if (data == null) return;
    final h = await _carRentalHeaders();
    try {
      final id = v['id'];
      final r = await http.patch(_carRentalUri('/vehicles/$id'), headers: h, body: jsonEncode(data));
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Saved');
      _loadMyVehicles();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _deleteVehicle(Map<String, dynamic> v) async {
    final h = await _carRentalHeaders();
    try {
      final id = v['id'];
      final r = await http.delete(_carRentalUri('/vehicles/$id'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Deleted');
      _loadMyVehicles();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _addImage(Map<String, dynamic> v) async {
    final urlCtrl = TextEditingController();
    final sortCtrl = TextEditingController(text: '0');
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Add image URL'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: urlCtrl, decoration: const InputDecoration(labelText: 'URL')),
          TextField(controller: sortCtrl, decoration: const InputDecoration(labelText: 'Sort'), keyboardType: TextInputType.number),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {'url': urlCtrl.text, 'sort_order': int.tryParse(sortCtrl.text) ?? 0}), child: const Text('Add')),
        ],
      ),
    );
    if (data == null) return;
    final h = await _carRentalHeaders();
    try {
      final id = v['id'];
      final r = await http.post(_carRentalUri('/vehicles/$id/images'), headers: h, body: jsonEncode(data));
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Image saved');
    } catch (e) { _toast('$e'); }
  }

  Future<void> _viewImages(Map<String, dynamic> v) async {
    final h = await _carRentalHeaders();
    try {
      final id = v['id'];
      final r = await http.get(_carRentalUri('/vehicles/$id/images'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      final imgs = jsonDecode(r.body) as List<dynamic>;
      await showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Images'),
          content: SizedBox(
            width: 500,
            height: 400,
            child: imgs.isEmpty
                ? const Center(child: Text('No images'))
                : GridView.count(
                    crossAxisCount: 3,
                    crossAxisSpacing: 8,
                    mainAxisSpacing: 8,
                    children: imgs.map((i) {
                      return Stack(children: [
                        Positioned.fill(child: Image.network(i['url'], fit: BoxFit.cover)),
                        Positioned(
                          right: 0,
                          top: 0,
                          child: IconButton(
                            icon: const Icon(Icons.delete_outline, color: Colors.white),
                            onPressed: () async {
                              final rid = i['id'];
                              final dr = await http.delete(_carRentalUri('/vehicles/$id/images/$rid'), headers: h);
                              if (dr.statusCode >= 400) {
                               _toast('Delete failed');
                              } else {
                                Navigator.pop(context);
                                _viewImages(v);
                              }
                            },
                          ),
                        )
                      ]);
                    }).toList(),
                  ),
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
        ),
      );
    } catch (e) { _toast('$e'); }
  }

  Future<void> _seed() async {
    try {
      final r = await http.post(_carRentalUri('/admin/seed'));
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Seed ok');
      _loadVehicles();
    } catch (e) { _toast('Seed failed: $e'); }
  }

  // Per-app OTP login removed: use central login

  void _toast(String m) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m))); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Car Rental'),
        bottom: TabBar(controller: _tab, tabs: const [
          Tab(text: 'Market'),
          Tab(text: 'Favoriten'),
          Tab(text: 'Meine Buchungen'),
          Tab(text: 'Seller'),
        ]),
        actions: [
          TextButton(onPressed: _healthCheck, child: Text(_health)),
          const SizedBox(width: 8),
          TextButton(onPressed: _seed, child: const Text('Seed')),
          const SizedBox(width: 8),
        ],
      ),
      body: TabBarView(controller: _tab, children: [
        _buildMarket(),
        _buildFavoritesTab(),
        _buildMyBookings(),
        _buildSeller(),
      ]),
    );
  }

  Widget _buildMarket() {
    return RefreshIndicator(
      onRefresh: _loadVehicles,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(onPressed: _openFilters, icon: const Icon(Icons.filter_list), label: const Text('Filter')),
          ),
          ElevatedButton(onPressed: () => _loadVehicles(reset: true), child: const Text('Reload')),
          const SizedBox(height: 8),
          ..._vehicles.map((v) => Card(
                child: ListTile(
                  title: Text('${v['make']} ${v['model']} (${v['year'] ?? ''})'),
                  subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${v['location'] ?? ''} • ${_fmtCents(v['price_per_day_cents'])}/Tag'),
                    const SizedBox(height: 4),
                    Wrap(spacing: 6, children: [Chip(label: Text('${v['transmission'] ?? '-'}')), if (v['seats'] != null) Chip(label: Text('${v['seats']} Sitze'))]),
                  ]),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: () => _favVehicle(v), icon: const Icon(Icons.favorite_border)),
                    IconButton(onPressed: () => _openMaps(v), icon: const Icon(Icons.map_outlined)),
                    ElevatedButton(onPressed: () => _showAvailability(v), child: const Text('Termine')),
                    ElevatedButton(onPressed: () => _bookVehicle(v), child: const Text('Buchen')),
                  ]),
                ),
              )),
          if (_vehicles.length < _total)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Center(
                child: ElevatedButton(
                  onPressed: () => _loadVehicles(),
                  child: Text('Mehr laden (${_vehicles.length}/$_total)'),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _openMaps(Map<String, dynamic> v) async {
    final q = (v['location'] ?? '').toString();
    if (q.isEmpty) {
      _toast('No address');
      return;
    }
    if (!tomTomConfigured()) {
      // Ohne Key keine alternativen Dienste verwenden – klar kommunizieren.
      _toast('TomTom API key missing — map view unavailable');
      return;
    }
    try {
      final url = Uri.parse(
          'https://api.tomtom.com/search/2/geocode/${Uri.encodeComponent(q)}.json?key=${effectiveTomTomKey()}&limit=1');
      final r = await http.get(url);
      if (r.statusCode >= 400) {
        _toast('Geocoding fehlgeschlagen');
        return;
      }
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final results = (js['results'] as List?) ?? const [];
      if (results.isEmpty || results.first['position'] == null) {
        _toast('Keine Position gefunden');
        return;
      }
      final pos = results.first['position'] as Map<String, dynamic>;
      final lat = (pos['lat'] as num).toDouble();
      final lon = (pos['lon'] as num).toDouble();

      if (!mounted) return;
      await showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: Text(q),
          content: SizedBox(
            width: 400,
            height: 280,
            child: FlutterMap(
              options: MapOptions(
                initialCenter: LatLng(lat, lon),
                initialZoom: 14,
              ),
              children: [
                ...tomTomTileLayers(showTrafficFlow: false),
                MarkerLayer(markers: [
                  Marker(
                    point: LatLng(lat, lon),
                    width: 40,
                    height: 40,
                    child: const Icon(Icons.location_on, color: Colors.redAccent),
                  ),
                ]),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close')),
          ],
        ),
      );
    } catch (_) {
      _toast('Map view unavailable');
    }
  }

  Future<void> _openFilters() async {
    final locationCtrl = TextEditingController(text: _filters['location'] ?? '');
    final makeCtrl = TextEditingController(text: _filters['make'] ?? '');
    String transVal = _filters['transmission'] ?? '';
    final seatsCtrl = TextEditingController(text: _filters['seats_min'] ?? '');
    final minCtrl = TextEditingController(text: _filters['min_price'] ?? '');
    final maxCtrl = TextEditingController(text: _filters['max_price'] ?? '');
    String sortVal = _filters['sort_by'] == 'price' ? (_filters['sort_dir'] == 'asc' ? 'price_asc' : 'price_desc') : (_filters['sort_by'] == 'created' ? (_filters['sort_dir'] == 'asc' ? 'created_asc' : 'created_desc') : '');
    DateTime? startPick;
    DateTime? endPick;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setSt) {
        return AlertDialog(
          title: const Text('Filter'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextField(controller: locationCtrl, decoration: const InputDecoration(labelText: 'Ort')),
              TextField(controller: makeCtrl, decoration: const InputDecoration(labelText: 'Marke')),
              DropdownButtonFormField<String>(initialValue: transVal.isEmpty ? null : transVal, items: const [DropdownMenuItem(value: 'auto', child: Text('Automatik')), DropdownMenuItem(value: 'manual', child: Text('Schalter'))], onChanged: (v) => setSt(() => transVal = v ?? ''), decoration: const InputDecoration(labelText: 'Getriebe')),
              TextField(controller: seatsCtrl, decoration: const InputDecoration(labelText: 'Min Sitze'), keyboardType: TextInputType.number),
              TextField(controller: minCtrl, decoration: const InputDecoration(labelText: 'Min Preis/Tag (Cent)'), keyboardType: TextInputType.number),
              TextField(controller: maxCtrl, decoration: const InputDecoration(labelText: 'Max Preis/Tag (Cent)'), keyboardType: TextInputType.number),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: sortVal.isEmpty ? null : sortVal,
                items: const [
                  DropdownMenuItem(value: 'price_asc', child: Text('Preis ↑')),
                  DropdownMenuItem(value: 'price_desc', child: Text('Preis ↓')),
                  DropdownMenuItem(value: 'created_desc', child: Text('Neueste')),
                  DropdownMenuItem(value: 'created_asc', child: Text('Oldest')),
                ],
                onChanged: (v) => setSt(() => sortVal = v ?? ''),
                decoration: const InputDecoration(labelText: 'Sortierung'),
              ),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: Text(startPick == null ? 'Start: -' : 'Start: ${startPick!.toIso8601String().substring(0,10)}')),
                TextButton(onPressed: () async { final now = DateTime.now(); final p = await showDatePicker(context: context, initialDate: now, firstDate: now, lastDate: now.add(const Duration(days: 365))); if (p != null) setSt(() => startPick = p); }, child: const Text('Choose start')),
              ]),
              Row(children: [
                Expanded(child: Text(endPick == null ? 'Ende: -' : 'Ende: ${endPick!.toIso8601String().substring(0,10)}')),
                TextButton(onPressed: () async { final base = startPick ?? DateTime.now().add(const Duration(days: 1)); final p = await showDatePicker(context: context, initialDate: base, firstDate: base, lastDate: base.add(const Duration(days: 365))); if (p != null) setSt(() => endPick = p); }, child: const Text('Choose end')),
              ]),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Reset')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Anwenden')),
          ],
        );
      }),
    );
    setState(() {
      if (ok == true) {
        _filters = {
          if (locationCtrl.text.isNotEmpty) 'location': locationCtrl.text,
          if (makeCtrl.text.isNotEmpty) 'make': makeCtrl.text,
          if (transVal.isNotEmpty) 'transmission': transVal,
          if (seatsCtrl.text.isNotEmpty) 'seats_min': seatsCtrl.text,
          if (minCtrl.text.isNotEmpty) 'min_price': minCtrl.text,
          if (maxCtrl.text.isNotEmpty) 'max_price': maxCtrl.text,
          if (startPick != null) 'start_date': startPick!.toIso8601String().substring(0,10),
          if (endPick != null) 'end_date': endPick!.toIso8601String().substring(0,10),
          if (sortVal == 'price_asc') 'sort_by': 'price',
          if (sortVal == 'price_asc') 'sort_dir': 'asc',
          if (sortVal == 'price_desc') 'sort_by': 'price',
          if (sortVal == 'price_desc') 'sort_dir': 'desc',
          if (sortVal == 'created_asc') 'sort_by': 'created',
          if (sortVal == 'created_asc') 'sort_dir': 'asc',
          if (sortVal == 'created_desc') 'sort_by': 'created',
          if (sortVal == 'created_desc') 'sort_dir': 'desc',
        };
      } else {
        _filters = {};
      }
    });
    _loadVehicles(reset: true);
  }

  Widget _buildFavoritesTab() {
    return RefreshIndicator(
      onRefresh: _loadFavorites,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          ElevatedButton(onPressed: _loadFavorites, child: const Text('Aktualisieren')),
          const SizedBox(height: 8),
          ..._favorites.map((v) => Card(
                child: ListTile(
                  title: Text('${v['make']} ${v['model']} (${v['year'] ?? ''})'),
                  subtitle: Text('${v['location'] ?? ''} • ${_fmtCents(v['price_per_day_cents'])}/Tag'),
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: () => _unfavVehicle(v), icon: const Icon(Icons.delete_outline)),
                    ElevatedButton(onPressed: () => _bookVehicle(v), child: const Text('Buchen')),
                  ]),
                ),
              )),
        ],
      ),
    );
  }

  Future<void> _favVehicle(Map<String, dynamic> v) async {
    final h = await _carRentalHeaders();
    if (!h.containsKey('Authorization')) { _toast('Please log in first'); return; }
    try {
      final id = v['id'];
      final r = await http.post(
          _carRentalUri('/market/vehicles/$id/favorite'),
          headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Favorit gespeichert');
    } catch (e) { _toast('$e'); }
  }

  Future<void> _unfavVehicle(Map<String, dynamic> v) async {
    final h = await _carRentalHeaders();
    try {
      final id = v['id'];
      final r = await http.delete(
          _carRentalUri('/market/vehicles/$id/favorite'),
          headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _loadFavorites();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _showAvailability(Map<String, dynamic> v) async {
    try {
      final id = v['id'];
      final r = await http.get(
          _carRentalUri('/market/vehicles/$id/availability'));
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final booked = (js['booked'] as List<dynamic>?) ?? [];
      await showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Booked periods'),
          content: SizedBox(
            width: 400,
            child: booked.isEmpty
                ? const Text('Keine Belegungen gefunden')
                : Column(mainAxisSize: MainAxisSize.min, children: booked.map((b) => ListTile(title: Text('${b['start_date']} → ${b['end_date']}'))).toList()),
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
        ),
      );
    } catch (e) { _toast('$e'); }
  }

  Widget _buildMyBookings() {
    return RefreshIndicator(
      onRefresh: _loadBookings,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          ElevatedButton(onPressed: _loadBookings, child: const Text('Aktualisieren')),
          const SizedBox(height: 8),
          ..._bookings.map((b) => ListTile(
                title: Text('Booking ${b['id'].toString().substring(0,6)}'),
                subtitle: Row(children: [
                  Text('${b['start_date']} → ${b['end_date']} • ${b['days']} Tage • ${_fmtCents(b['total_cents'])}  '),
                  Chip(label: Text('${b['status']}')),
                ]),
              )),
        ],
      ),
    );
  }

  Widget _buildSeller() {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        const Text('Seller‑Aktionen', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          ElevatedButton(onPressed: _createCompany, child: const Text('Firma anlegen')),
          ElevatedButton(onPressed: _createVehicle, child: const Text('Add vehicle')),
          ElevatedButton(onPressed: _loadMyVehicles, child: const Text('Meine Fahrzeuge')),
          ElevatedButton(onPressed: _loadSellerOrders, child: const Text('Bestellungen')),
        ]),
        const Divider(),
        if (_myVehicles.isNotEmpty) const Text('Meine Fahrzeuge'),
        ..._myVehicles.map((v) => ListTile(
              title: Text('${v['make']} ${v['model']} (${v['year'] ?? ''})'),
              subtitle: Text('${v['location'] ?? ''} • ${_fmtCents(v['price_per_day_cents'])}/Tag • ${v['status']}'),
              trailing: Wrap(spacing: 8, children: [
                IconButton(onPressed: () => _editVehicle(v), icon: const Icon(Icons.edit)),
                IconButton(onPressed: () => _deleteVehicle(v), icon: const Icon(Icons.delete_outline)),
                IconButton(onPressed: () => _addImage(v), icon: const Icon(Icons.add_photo_alternate_outlined)),
                IconButton(onPressed: () => _viewImages(v), icon: const Icon(Icons.photo_library_outlined)),
              ]),
            )),
        if (_sellerOrders.isNotEmpty) const Divider(),
        if (_sellerOrders.isNotEmpty) const Text('Bestellungen'),
        ..._sellerOrders.map((b) => ListTile(
              title: Text('Booking ${b['id'].toString().substring(0,6)}'),
              subtitle: Text('${b['start_date']} → ${b['end_date']} • ${b['days']} Tage • ${_fmtCents(b['total_cents'])} • ${b['status']}'),
              trailing: Wrap(spacing: 8, children: [
                if (b['status'] != 'confirmed')
                  ElevatedButton(onPressed: () => _sellerConfirm(b), child: const Text('Confirm')),
                if (b['status'] != 'canceled')
                  TextButton(onPressed: () => _sellerCancel(b), child: const Text('Cancel')),
              ]),
            )),
      ],
    );
  }

  Future<void> _sellerConfirm(Map<String, dynamic> b) async {
    final h = await _carRentalHeaders();
    try {
      final id = b['id'];
      final r = await http.post(_carRentalUri('/orders/$id/confirm'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Confirmed');
      _loadSellerOrders();
    } catch (e) { _toast('$e'); }
  }

  Future<void> _sellerCancel(Map<String, dynamic> b) async {
    final h = await _carRentalHeaders();
    try {
      final id = b['id'];
      final r = await http.post(_carRentalUri('/orders/$id/cancel'), headers: h);
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Abgebrochen');
      _loadSellerOrders();
    } catch (e) { _toast('$e'); }
  }
}
// ignore_for_file: use_build_context_synchronously
