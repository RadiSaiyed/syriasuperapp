import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'package:url_launcher/url_launcher.dart';

class RealEstateScreen extends StatefulWidget {
  const RealEstateScreen({super.key});
  @override
  State<RealEstateScreen> createState() => _RealEstateScreenState();
}

class _RealEstateScreenState extends State<RealEstateScreen> {
  final _tokens = MultiTokenStore();
  List<dynamic> _listings = [];
  List<dynamic> _favorites = [];
  List<dynamic> _inquiries = [];
  List<dynamic> _myListings = [];
  List<dynamic> _ownerReservations = [];
  List<dynamic> _myReservations = [];
  bool _loading = false;

  Future<Map<String, String>> _realEstateHeaders() =>
      authHeaders('realestate', store: _tokens);

  Uri _realEstateUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('realestate', path, query: query);

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  // Filter inputs
  final _cityCtrl = TextEditingController();
  final _minCtrl = TextEditingController();
  final _maxCtrl = TextEditingController();
  String _typeFilter = 'any'; // any|rent|sale

  Future<void> _seed() async {
    try {
      await http.post(_realEstateUri('/admin/seed'));
      _toast('Seed done');
    } catch (_) {}
  }

  // Per-app OTP login removed: use central login

  Future<void> _list() async {
    setState(() => _loading = true);
    try {
      final params = <String, String>{};
      if (_cityCtrl.text.trim().isNotEmpty) {
        params['city'] = _cityCtrl.text.trim();
      }
      if (_typeFilter != 'any') params['type'] = _typeFilter;
      final mn = int.tryParse(
          _minCtrl.text.trim().isEmpty ? '-1' : _minCtrl.text.trim());
      final mx = int.tryParse(
          _maxCtrl.text.trim().isEmpty ? '-1' : _maxCtrl.text.trim());
      if (mn != null && mn >= 0) params['min_price'] = mn.toString();
      if (mx != null && mx >= 0) params['max_price'] = mx.toString();
      final uri = _realEstateUri('/listings',
          query: params.isEmpty ? null : params);
      final res = await http.get(uri);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _listings = js['listings'] as List? ?? []);
    } catch (e) {
      _toast('List failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _fav(String id) async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await http.post(_realEstateUri('/favorites/$id'), headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Favorited');
      await _listFavs();
    } catch (e) {
      _toast('Fav failed: $e');
    }
  }

  Future<void> _listFavs() async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await http.get(_realEstateUri('/favorites'), headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _favorites = js['items'] as List? ?? []);
    } catch (e) {
      _toast('Fav list failed: $e');
    }
  }

  Future<void> _inq(String id) async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await http.post(_realEstateUri('/inquiries'),
          headers: h,
          body: jsonEncode({'listing_id': id, 'message': 'Please contact me'}));
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Inquiry sent');
      await _listInq();
    } catch (e) {
      _toast('Inquiry failed: $e');
    }
  }

  Future<void> _listInq() async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await http.get(_realEstateUri('/inquiries'), headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _inquiries = js['items'] as List? ?? []);
    } catch (e) {
      _toast('Inquiries failed: $e');
    }
  }

  Future<void> _reserve(String id) async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.post(
          _realEstateUri('/reservations', query: {'listing_id': id}),
          headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final rid = js['payment_request_id'] as String?;
      _toast('Reservierung erstellt');
      if (rid != null) {
        final uri = Uri.parse('payments://request/$rid');
        if (await canLaunchUrl(uri)) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      }
    } catch (e) {
      _toast('Reserve failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Real Estate')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Row(children: [
          OutlinedButton(onPressed: _seed, child: const Text('Seed')),
        ]),
        const Divider(height: 24),
        // Filterleiste
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Filter'),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: TextField(
                        controller: _cityCtrl,
                        decoration: const InputDecoration(labelText: 'City'))),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _typeFilter,
                  items: const [
                    DropdownMenuItem(value: 'any', child: Text('any')),
                    DropdownMenuItem(value: 'rent', child: Text('rent')),
                    DropdownMenuItem(value: 'sale', child: Text('sale')),
                  ],
                  onChanged: (v) => setState(() => _typeFilter = v ?? 'any'),
                ),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: TextField(
                        controller: _minCtrl,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                            labelText: 'Min price (cents)'))),
                const SizedBox(width: 8),
                Expanded(
                    child: TextField(
                        controller: _maxCtrl,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                            labelText: 'Max price (cents)'))),
                const SizedBox(width: 8),
                FilledButton(
                    onPressed: _loading ? null : _list,
                    child: const Text('Apply')),
              ]),
            ]),
          ),
        ),
        Wrap(spacing: 8, runSpacing: 8, children: [
          ElevatedButton(
              onPressed: _loading ? null : _list,
              child: const Text('Listings')),
          ElevatedButton(
              onPressed: _loading ? null : _listFavs,
              child: const Text('Favorites')),
          ElevatedButton(
              onPressed: _loading ? null : _listInq,
              child: const Text('Inquiries')),
          ElevatedButton(
              onPressed: _loading ? null : _myRes,
              child: const Text('My Reservations')),
          OutlinedButton(
              onPressed: _loading ? null : _ownerList,
              child: const Text('Owner: My Listings')),
          OutlinedButton(
              onPressed: _loading ? null : _ownerRes,
              child: const Text('Owner: Reservations')),
          // Owner quick-create listing (DEV)
          OutlinedButton(
              onPressed: _loading ? null : _ownerQuickCreate,
              child: const Text('Owner: + Listing')),
        ]),
        const SizedBox(height: 8),
        for (final l in _listings)
          Card(
              child: ListTile(
            title: Text(l['title'] ?? ''),
            subtitle:
                Text('${l['city']}  •  ${l['type']}  •  ${l['price_cents']}c'),
            trailing: Wrap(spacing: 8, children: [
              IconButton(
                  onPressed: () => _fav(l['id'] as String),
                  icon: const Icon(Icons.favorite_border)),
              IconButton(
                  onPressed: () => _inq(l['id'] as String),
                  icon: const Icon(Icons.mail_outline)),
              IconButton(
                  onPressed: () => _reserve(l['id'] as String),
                  icon: const Icon(Icons.payments_outlined)),
            ]),
          )),
        if (_favorites.isNotEmpty) const Divider(),
        if (_favorites.isNotEmpty) const Text('Favoriten'),
        for (final f in _favorites)
          ListTile(
              title: Text(f['title'] ?? ''),
              subtitle: Text(
                  '${f['city']}  •  ${f['type']}  •  ${f['price_cents']}c')),
        if (_inquiries.isNotEmpty) const Divider(),
        if (_inquiries.isNotEmpty) const Text('Meine Anfragen'),
        for (final i in _inquiries)
          ListTile(
              title: Text('Inquiry ${i['id']}'),
              subtitle: Text(
                  'listing: ${i['listing_id']}  •  ${i['message'] ?? ''}')),
        if (_myReservations.isNotEmpty) const Divider(),
        if (_myReservations.isNotEmpty) const Text('Meine Reservierungen'),
        for (final r in _myReservations)
          ListTile(
            title: Text(r['title'] ?? 'Reservation'),
            subtitle: Text(
                'amount: ${r['amount_cents']}c  •  status: ${r['status']}  •  decision: ${r['owner_decision']}'),
            trailing: IconButton(
                onPressed: () => _syncReservation(r['id'] as String),
                icon: const Icon(Icons.sync)),
          ),
        if (_myListings.isNotEmpty) const Divider(),
        if (_myListings.isNotEmpty) const Text('Eigene Listings'),
        for (final m in _myListings)
          ListTile(
              title: Text(m['title'] ?? ''),
              subtitle:
                  Text('${m['city']} • ${m['type']} • ${m['price_cents']}c')),
        if (_ownerReservations.isNotEmpty) const Divider(),
        if (_ownerReservations.isNotEmpty) const Text('Owner: Reservierungen'),
        for (final r in _ownerReservations)
          ListTile(
            title: Text(r['title'] ?? 'Reservation'),
            subtitle: Text(
                'amount: ${r['amount_cents']}c  •  status: ${r['status']}  •  decision: ${r['owner_decision']}'),
            trailing: Wrap(spacing: 8, children: [
              IconButton(
                  onPressed: () => _syncReservation(r['id'] as String),
                  icon: const Icon(Icons.sync)),
              IconButton(
                  onPressed: () => _decide(r['id'] as String, 'accepted'),
                  icon: const Icon(Icons.check_circle_outline)),
              IconButton(
                  onPressed: () => _decide(r['id'] as String, 'rejected'),
                  icon: const Icon(Icons.cancel_outlined)),
            ]),
          ),
      ]),
    );
  }

  Future<void> _ownerQuickCreate() async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login as owner phone');
      return;
    }
    setState(() => _loading = true);
    try {
      final uri = _realEstateUri('/owner/listings', query: {
        'title': 'Demo Objekt',
        'city': 'Damascus',
        'type': 'rent',
        'property_type': 'apartment',
        'price_cents': '1500000',
      });
      final res = await http.post(uri, headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Listing erstellt');
      await _ownerList();
    } catch (e) {
      _toast('Create failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _myRes() async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.get(_realEstateUri('/reservations'), headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _myReservations = js['items'] as List? ?? []);
    } catch (e) {
      _toast('My reservations failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _syncReservation(String id) async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    try {
      final res = await http.post(
          _realEstateUri('/reservations/$id/sync'),
          headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Synced');
      await _myRes();
      await _ownerRes();
    } catch (e) {
      _toast('Sync failed: $e');
    }
  }

  Future<void> _ownerList() async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login as owner phone');
      return;
    }
    try {
      final res =
          await http.get(_realEstateUri('/owner/listings'), headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _myListings = js['items'] as List? ?? []);
    } catch (e) {
      _toast('Owner listings failed: $e');
    }
  }

  Future<void> _ownerRes() async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login as owner phone');
      return;
    }
    try {
      final res =
          await http.get(_realEstateUri('/owner/reservations'), headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _ownerReservations = js['items'] as List? ?? []);
    } catch (e) {
      _toast('Owner reservations failed: $e');
    }
  }

  Future<void> _decide(String id, String decision) async {
    final h = await _realEstateHeaders();
    if (!h.containsKey('Authorization')) {
      _toast('Login as owner phone');
      return;
    }
    try {
      final uri = _realEstateUri('/owner/reservations/$id/decision',
          query: {'decision': decision});
      final res = await http.post(uri, headers: h);
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Entscheidung: $decision');
      await _ownerRes();
    } catch (e) {
      _toast('Decision failed: $e');
    }
  }
}
