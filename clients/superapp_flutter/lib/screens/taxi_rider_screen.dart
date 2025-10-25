import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../map_tiles.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../ui/glass.dart';
import '../services.dart';
import '../auth.dart';
import 'package:flutter_contacts/flutter_contacts.dart';
import 'profile_screen.dart';
import 'taxi_history_screen.dart';

class TaxiRiderScreen extends StatefulWidget {
  const TaxiRiderScreen({super.key});
  @override
  State<TaxiRiderScreen> createState() => _TaxiRiderScreenState();
}

class _TaxiRiderScreenState extends State<TaxiRiderScreen> {
  final _tokens = MultiTokenStore();
  String? _quote;
  String? _rideId;
  bool _loading = false;
  bool _geoLoading = false;
  DateTime? _scheduledAt; // chosen schedule time (local)
  // Scheduled rides
  bool _schedLoading = false;
  List<Map<String, dynamic>> _scheduled = [];
  // Map pins
  double? _pickLat = 33.5138, _pickLon = 36.2765;
  double? _dropLat, _dropLon;
  bool _selectingPickup = true;
  // Favorites (My Places)
  List<Map<String, dynamic>> _favorites = [];
  bool _favLoading = false;
  // Order for someone else
  bool _forOther = false;
  final _otherName = TextEditingController();
  final _otherPhone = TextEditingController();
  // Address input
  final _addrPickup = TextEditingController();
  final _addrDropoff = TextEditingController();
  final FocusNode _addrPickupFocus = FocusNode();
  final FocusNode _addrDropoffFocus = FocusNode();
  Timer? _acTimer;
  List<Map<String, dynamic>> _acPickup = [];
  List<Map<String, dynamic>> _acDropoff = [];

  Future<Map<String, String>> _taxiHeaders() =>
      authHeaders('taxi', store: _tokens);

  Uri _taxiUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('taxi', path, query: query);

  // Ride classes (category) — aligned with Taxi standalone: standard|comfort|yellow|vip|van|electro
  final List<Map<String, String>> _rideClasses = const [
    {"label": "Standard", "code": "standard"},
    {"label": "Comfort", "code": "comfort"},
    {"label": "Yellow", "code": "yellow"},
    {"label": "VIP", "code": "vip"},
    {"label": "Van", "code": "van"},
    {"label": "Electro", "code": "electro"},
  ];
  String _rideClass = 'standard';

  String _fmtSyp(dynamic cents) {
    int c = 0;
    if (cents is int) {
      c = cents;
    } else {
      c = int.tryParse('$cents') ?? 0;
    }
    final int syp = c ~/ 100;
    return '$syp SYP';
  }

  String _fmtDateTimeLocal(DateTime dt) {
    final l = dt.toLocal();
    String two(int v) => v.toString().padLeft(2, '0');
    return '${l.year}-${two(l.month)}-${two(l.day)} ${two(l.hour)}:${two(l.minute)}';
  }

  Future<void> _pickOtherFromContacts() async {
    try {
      final granted = await FlutterContacts.requestPermission();
      if (!granted) {
        _toast('Contacts permission denied');
        return;
      }
      final c = await FlutterContacts.openExternalPick();
      if (c == null) return;
      var contact = c;
      if (contact.phones.isEmpty) {
        final full = await FlutterContacts.getContact(contact.id, withProperties: true);
        if (full != null) contact = full;
      }
      final phone = contact.phones.isNotEmpty ? contact.phones.first.number.trim() : '';
      setState(() {
        if (contact.displayName.isNotEmpty) _otherName.text = contact.displayName;
        if (phone.isNotEmpty) _otherPhone.text = phone;
      });
    } catch (e) {
      _toast('Contact pick failed: $e');
    }
  }

  Future<void> _quoteRide() async {
    final t = await getTokenFor('taxi', store: _tokens);
    if (t == null) {
      _toast('Login first');
      return;
    }
    if (_pickLat == null ||
        _pickLon == null ||
        _dropLat == null ||
        _dropLon == null) {
      return;
    }
    setState(() => _loading = true);
    try {
      final body = {
        'pickup_lat': _pickLat,
        'pickup_lon': _pickLon,
        'dropoff_lat': _dropLat,
        'dropoff_lon': _dropLon,
        'ride_class': _rideClass,
      };
      final res = await http.post(_taxiUri('/rides/quote'),
          headers: await _taxiHeaders(),
          body: jsonEncode(body));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final int price =
          (js['final_quote_cents'] ?? js['quoted_fare_cents']) as int? ?? 0;
      final double dist = (js['distance_km'] as num?)?.toDouble() ?? 0.0;
      final String distStr = dist.toStringAsFixed(1);
      final int? eta = (js['eta_to_pickup_minutes'] as num?)?.toInt();
      setState(() => _quote =
          '${_fmtSyp(price)}, $distStr km${eta != null ? ', ETA: $eta min' : ''}');
    } catch (e) {
      _toast('Quote failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _loadFavorites();
    _loadScheduled();
  }

  @override
  void dispose() {
    _otherName.dispose();
    _otherPhone.dispose();
    _addrPickup.dispose();
    _addrDropoff.dispose();
    _addrPickupFocus.dispose();
    _addrDropoffFocus.dispose();
    _acTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadFavorites() async {
    setState(() => _favLoading = true);
    try {
      final r = await http.get(_taxiUri('/favorites'),
          headers: await _taxiHeaders());
      if (r.statusCode < 400) {
        final list = (jsonDecode(r.body) as List).cast<Map<String, dynamic>>();
        setState(() => _favorites = list);
      }
    } catch (_) {
    } finally {
      if (mounted) setState(() => _favLoading = false);
    }
  }

  Future<void> _addFavorite() async {
    final lat = _selectingPickup ? _pickLat : _dropLat;
    final lon = _selectingPickup ? _pickLon : _dropLon;
    if (lat == null || lon == null) {
      _toast('Please pick a point on the map first');
      return;
    }
    final ctrl =
        TextEditingController(text: _selectingPickup ? 'Home' : 'Work');
    final ok = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
                title: const Text('Add to "My Places"'),
                content: TextField(
                    controller: ctrl,
                    decoration: const InputDecoration(
                        labelText: 'Label (e.g., Home, Work)')),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Add'))
                ]));
    if (ok != true) return;
    final label = ctrl.text.trim();
    if (label.isEmpty) return;
    try {
      final r = await http.post(_taxiUri('/favorites'),
          headers: await _taxiHeaders(),
          body: jsonEncode({"label": label, "lat": lat, "lon": lon}));
      if (r.statusCode >= 400) {
        _toast('Save failed: ${r.body}');
        return;
      }
      await _loadFavorites();
      _toast('Saved');
    } catch (e) {
      _toast('Error: $e');
    }
  }

  Future<void> _deleteFavorite(String id) async {
    final ok = await showDialog<bool>(
        context: context,
        builder: (_) =>
            AlertDialog(title: const Text('Delete favorite?'), actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Cancel')),
              FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Delete'))
            ]));
    if (ok != true) return;
    try {
      final r = await http.delete(_taxiUri('/favorites/$id'),
          headers: await _taxiHeaders());
      if (r.statusCode >= 400) {
        _toast('Delete failed: ${r.body}');
        return;
      }
      setState(() => _favorites.removeWhere((e) => e['id'] == id));
    } catch (e) {
      _toast('Error: $e');
    }
  }

  Future<void> _renameFavorite(Map<String, dynamic> f) async {
    final ctrl = TextEditingController(text: (f['label'] as String?) ?? '');
    final ok = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
                title: const Text('Rename place'),
                content: TextField(
                    controller: ctrl,
                    decoration: const InputDecoration(labelText: 'Label')),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Save'))
                ]));
    if (ok != true) return;
    final label = ctrl.text.trim();
    if (label.isEmpty) return;
    try {
      final id = f['id'] as String;
      final r = await http.put(_taxiUri('/favorites/$id'),
          headers: await _taxiHeaders(),
          body: jsonEncode({"label": label}));
      if (r.statusCode >= 400) {
        _toast('Rename failed: ${r.body}');
        return;
      }
      await _loadFavorites();
    } catch (e) {
      _toast('Error: $e');
    }
  }

  Future<void> _requestAndPrepay() async {
    final t = await getTokenFor('taxi', store: _tokens);
    if (t == null) {
      _toast('Login first');
      return;
    }
    if (_pickLat == null ||
        _pickLon == null ||
        _dropLat == null ||
        _dropLon == null) {
      _toast('Please set pickup and dropoff');
      return;
    }
    if (_forOther && _otherPhone.text.trim().isEmpty) {
      _toast('Telefonnummer des Fahrgasts fehlt');
      return;
    }
    setState(() => _loading = true);
    try {
      // 1) Quote for confirmation
      final qRes = await http.post(_taxiUri('/rides/quote'),
          headers: await _taxiHeaders(),
          body: jsonEncode({
            'pickup_lat': _pickLat,
            'pickup_lon': _pickLon,
            'dropoff_lat': _dropLat,
            'dropoff_lon': _dropLon
          }));
      if (qRes.statusCode >= 400) throw Exception(qRes.body);
      final q = jsonDecode(qRes.body) as Map<String, dynamic>;
      final int price =
          q['final_quote_cents'] as int? ?? q['quoted_fare_cents'] as int? ?? 0;
      final ok = await _confirm('Request Taxi',
          'Price: ${_fmtSyp(price)}\nJetzt bezahlen und Fahrt anfragen?');
      if (!ok) return;
      final bioOk = await requireBiometricIfEnabled(context,
          reason: 'Confirm taxi prepayment');
      if (!bioOk) return;
      // 2) Request with prepay
      final rRes = await http.post(_taxiUri('/rides/request'),
          headers: await _taxiHeaders(),
          body: jsonEncode({
            'pickup_lat': _pickLat,
            'pickup_lon': _pickLon,
            'dropoff_lat': _dropLat,
            'dropoff_lon': _dropLon,
            'ride_class': _rideClass,
            'prepay': true,
            if (_forOther) 'for_name': _otherName.text.trim(),
            if (_forOther) 'for_phone': _otherPhone.text.trim(),
            'pay_mode': 'self',
          }));
      if (rRes.statusCode == 200) {
        final js = jsonDecode(rRes.body) as Map<String, dynamic>;
        if (!mounted) return;
        setState(() => _rideId = js['id'] as String?);
        _toast('Requested & paid. Ride: ${_rideId ?? '-'}');
      } else {
        final Map<String, dynamic>? js = () {
          try {
            return jsonDecode(rRes.body);
          } catch (_) {
            return null;
          }
        }();
        final detail = js?['detail'];
        if (detail is Map && detail['code'] == 'insufficient_rider_balance') {
          _toast('Insufficient rider balance. Please top up.');
        } else {
          _toast('Request failed: ${rRes.body}');
        }
      }
    } catch (e) {
      _toast('Request error: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _requestCash() async {
    setState(() => _loading = true);
    try {
      final res = await http.post(_taxiUri('/rides/request'),
          headers: await _taxiHeaders(),
          body: jsonEncode({
            'pickup_lat': _pickLat,
            'pickup_lon': _pickLon,
            'dropoff_lat': _dropLat,
            'dropoff_lon': _dropLon,
            'ride_class': _rideClass,
            if (_forOther) 'for_name': _otherName.text.trim(),
            if (_forOther) 'for_phone': _otherPhone.text.trim(),
            'pay_mode': 'cash',
          }));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      if (!mounted) return;
      setState(() => _rideId = js['id'] as String?);
      _toast('Requested (cash). Ride: ${_rideId ?? '-'}');
    } catch (e) {
      _toast('Request failed: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _scheduleRide({DateTime? when}) async {
    final t = await getTokenFor('taxi', store: _tokens);
    if (t == null) {
      _toast('Login first');
      return;
    }
    if (_pickLat == null || _pickLon == null || _dropLat == null || _dropLon == null) {
      _toast('Please set pickup and dropoff');
      return;
    }
    final scheduled = (when ?? DateTime.now().add(const Duration(minutes: 15))).toUtc();
    setState(() => _loading = true);
    try {
      final res = await http.post(_taxiUri('/rides/schedule'),
          headers: await _taxiHeaders(),
          body: jsonEncode({
            'pickup_lat': _pickLat,
            'pickup_lon': _pickLon,
            'dropoff_lat': _dropLat,
            'dropoff_lon': _dropLon,
            'scheduled_for': scheduled.toIso8601String(),
          }));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final at = js['scheduled_for']?.toString() ?? scheduled.toIso8601String();
      _toast('Scheduled at $at');
      await _loadScheduled();
    } catch (e) {
      _toast('Schedule failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  // Removed manual dispatch trigger.

  Future<void> _pickScheduleDateTime() async {
    final now = DateTime.now();
    final initial = _scheduledAt ?? now.add(const Duration(minutes: 15));
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: now,
      lastDate: now.add(const Duration(days: 30)),
    );
    if (date == null) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initial),
    );
    if (time == null) return;
    final picked = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    if (!picked.isAfter(now.add(const Duration(minutes: 1)))) {
      _toast('Please choose a time in the future');
      return;
    }
    setState(() => _scheduledAt = picked);
  }

  Future<void> _loadScheduled() async {
    setState(() => _schedLoading = true);
    try {
      final res = await http.get(_taxiUri('/rides/scheduled'),
          headers: await _taxiHeaders());
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _scheduled = (js['scheduled'] as List).cast<Map<String, dynamic>>());
    } catch (_) {
      // ignore transient errors in UI
    } finally {
      if (mounted) setState(() => _schedLoading = false);
    }
  }

  Future<void> _cancelScheduled(String id) async {
    setState(() => _schedLoading = true);
    try {
      final res = await http.delete(_taxiUri('/rides/scheduled/$id'),
          headers: await _taxiHeaders());
      if (res.statusCode >= 400) throw Exception(res.body);
      await _loadScheduled();
      _toast('Scheduled ride canceled');
    } catch (e) {
      _toast('Cancel failed: $e');
    } finally {
      if (mounted) setState(() => _schedLoading = false);
    }
  }

  Future<bool> _confirm(String title, String msg) async {
    final ok = await showDialog<bool>(
        context: context,
        builder: (_) =>
            AlertDialog(title: Text(title), content: Text(msg), actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Cancel')),
              FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('OK'))
            ]));
    return ok == true;
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _geocodeAndSet({required bool forPickup}) async {
    if (!tomTomConfigured()) {
      _toast('TomTom API key missing');
      return;
    }
    final q = (forPickup ? _addrPickup.text : _addrDropoff.text).trim();
    if (q.isEmpty) return;
    setState(() => _geoLoading = true);
    try {
      final url = Uri.parse(
          'https://api.tomtom.com/search/2/geocode/${Uri.encodeComponent(q)}.json?key=${effectiveTomTomKey()}&limit=5');
      final r = await http.get(url);
      if (r.statusCode >= 400) {
        _toast('Geocoding fehlgeschlagen');
        return;
      }
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final results = (js['results'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      if (results.isEmpty) {
      _toast('No address found');
        return;
      }
      Map<String, dynamic> pick(Map<String, dynamic> it) => it;
      Map<String, dynamic>? chosen;
      if (results.length == 1) {
        chosen = results.first;
      } else {
        if (!mounted) return;
        chosen = await showDialog<Map<String, dynamic>>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Choose address'),
            content: SizedBox(
              width: 420,
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: results.length,
                itemBuilder: (ctx, i) {
                  final it = results[i];
                  final addr = (it['address'] ?? {}) as Map<String, dynamic>;
                  final poi = (it['poi'] ?? {}) as Map<String, dynamic>;
                  final free = (addr['freeformAddress'] ?? poi['name'] ?? q).toString();
                  return ListTile(
                    title: Text(free),
                    onTap: () => Navigator.pop(ctx, pick(it)),
                  );
                },
              ),
            ),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'))
            ],
          ),
        );
        if (chosen == null) return;
      }
      final pos = (chosen['position'] ?? {}) as Map<String, dynamic>;
      final lat = (pos['lat'] as num?)?.toDouble();
      final lon = (pos['lon'] as num?)?.toDouble();
      if (lat == null || lon == null) {
        _toast('Invalid coordinates');
        return;
      }
      setState(() {
        if (forPickup) {
          _pickLat = lat;
          _pickLon = lon;
        } else {
          _dropLat = lat;
          _dropLon = lon;
        }
      });
      // Quote wenn beide vorhanden
      if (_pickLat != null && _pickLon != null && _dropLat != null && _dropLon != null && !_loading) {
        _quoteRide();
      }
    } catch (_) {
      _toast('Geocoding error');
    } finally {
      if (mounted) setState(() => _geoLoading = false);
    }
  }

  Future<void> _reverseGeocodeAndFill({required bool forPickup, required double lat, required double lon}) async {
    if (!tomTomConfigured()) return;
    try {
      final url = Uri.parse('https://api.tomtom.com/search/2/reverseGeocode/${lat.toStringAsFixed(6)},${lon.toStringAsFixed(6)}.json?key=${effectiveTomTomKey()}&radius=50');
      final r = await http.get(url);
      if (r.statusCode >= 400) return;
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final addresses = (js['addresses'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      if (addresses.isEmpty) return;
      final addr = (addresses.first['address'] ?? {}) as Map<String, dynamic>;
      final free = (addr['freeformAddress'] ?? '').toString();
      if (free.isEmpty) return;
      setState(() {
        if (forPickup) {
          _addrPickup.text = free;
        } else {
          _addrDropoff.text = free;
        }
      });
    } catch (_) {}
  }

  void _scheduleAutocomplete({required bool forPickup}) {
    _acTimer?.cancel();
    final q = (forPickup ? _addrPickup.text : _addrDropoff.text).trim();
    if (q.length < 3) {
      setState(() {
        if (forPickup) {
          _acPickup = [];
        } else {
          _acDropoff = [];
        }
      });
      return;
    }
    _acTimer = Timer(const Duration(milliseconds: 250), () => _autocomplete(forPickup: forPickup, query: q));
  }

  Future<void> _autocomplete({required bool forPickup, required String query}) async {
    if (!tomTomConfigured()) return;
    // show busy cursor via focus/indicator instead of explicit loading flag
    try {
      final url = Uri.parse('https://api.tomtom.com/search/2/search/${Uri.encodeComponent(query)}.json?key=${effectiveTomTomKey()}&limit=6');
      final r = await http.get(url);
      if (r.statusCode >= 400) return;
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final results = (js['results'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      final mapped = results.map((e) {
        final addr = (e['address'] ?? {}) as Map<String, dynamic>;
        final poi = (e['poi'] ?? {}) as Map<String, dynamic>;
        final free = (addr['freeformAddress'] ?? poi['name'] ?? query).toString();
        final pos = (e['position'] ?? {}) as Map<String, dynamic>;
        final lat = (pos['lat'] as num?)?.toDouble();
        final lon = (pos['lon'] as num?)?.toDouble();
        return { 'text': free, 'lat': lat, 'lon': lon };
      }).where((m) => m['lat'] != null && m['lon'] != null).take(6).toList();
      setState(() { if (forPickup) {
        _acPickup = mapped;
      } else {
        _acDropoff = mapped;
      } });
    } catch (_) {
    } finally {
      // no-op
    }
  }

  void _selectSuggestion({required bool forPickup, required Map<String, dynamic> s}) {
    final text = s['text']?.toString() ?? '';
    final double lat = (s['lat'] as num).toDouble();
    final double lon = (s['lon'] as num).toDouble();
    setState(() {
      if (forPickup) {
        _addrPickup.text = text;
        _pickLat = lat; _pickLon = lon; _acPickup = [];
        _addrPickupFocus.unfocus();
      } else {
        _addrDropoff.text = text;
        _dropLat = lat; _dropLon = lon; _acDropoff = [];
        _addrDropoffFocus.unfocus();
      }
    });
    if (_pickLat != null && _pickLon != null && _dropLat != null && _dropLon != null && !_loading) {
      _quoteRide();
    }
  }

  Widget _buildSuggestions({required bool forPickup}) {
    final data = forPickup ? _acPickup : _acDropoff;
    final focus = forPickup ? _addrPickupFocus.hasFocus : _addrDropoffFocus.hasFocus;
    if (!focus || data.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.only(top: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.08), blurRadius: 8)],
      ),
      constraints: const BoxConstraints(maxHeight: 220),
      child: ListView.builder(
        shrinkWrap: true,
        itemCount: data.length,
        itemBuilder: (ctx, i) {
          final s = data[i];
          return ListTile(
            dense: true,
            title: Text(s['text']?.toString() ?? ''),
            onTap: () => _selectSuggestion(forPickup: forPickup, s: s),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: const Text('Taxi — Rider'),
          flexibleSpace: const Glass(
              padding: EdgeInsets.zero,
              blur: 24,
              opacity: 0.16,
              borderRadius: BorderRadius.zero),
          actions: [
            IconButton(
                onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const TaxiHistoryScreen())),
                tooltip: 'Ride History',
                icon: const Icon(Icons.history)),
            IconButton(
                onPressed: () => Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const ProfileScreen())),
                icon: const Icon(Icons.person))
          ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Glass(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text('Set pickup and dropoff — Quote oben sichtbar.',
                  style: TextStyle(fontWeight: FontWeight.bold))),
          // Quote preview on top (no scrolling needed)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                    color: Colors.black.withValues(alpha: 0.06), blurRadius: 10),
              ],
            ),
            child: Row(
              children: [
                const Icon(Icons.local_taxi, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _quote ?? 'Preis wird angezeigt, sobald Pickup & Dropoff gesetzt sind.',
                    style: const TextStyle(fontSize: 14),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  tooltip: 'Quote aktualisieren',
                  icon: const Icon(Icons.refresh, size: 18),
                  onPressed: (_pickLat != null && _pickLon != null && _dropLat != null && _dropLon != null && !_loading)
                      ? _quoteRide
                      : null,
                ),
              ],
            ),
          ),
          // Ride class selector (chips)
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final item in _rideClasses)
                  Padding(
                    padding: const EdgeInsets.only(right: 6.0, bottom: 8.0),
                    child: ChoiceChip(
                      label: Text(item['label']!),
                      selected: _rideClass == item['code'],
                      onSelected: (sel) {
                        if (!sel) return;
                        setState(() => _rideClass = item['code']!);
                        if (_pickLat != null && _pickLon != null && _dropLat != null && _dropLon != null && !_loading) {
                          _quoteRide();
                        }
                      },
                    ),
                  ),
              ],
            ),
          ),
          SizedBox(
              height: 220,
              child: _MiniMap(
                pickup: _pickLat != null && _pickLon != null
                    ? LatLng(_pickLat!, _pickLon!)
                    : null,
                dropoff: _dropLat != null && _dropLon != null
                    ? LatLng(_dropLat!, _dropLon!)
                    : null,
                onTap: (lat, lon) {
                  setState(() {
                    if (_selectingPickup) {
                      _pickLat = lat;
                      _pickLon = lon;
                    } else {
                      _dropLat = lat;
                      _dropLon = lon;
                    }
                  });
                  // Reverse geocode to fill address fields
                  _reverseGeocodeAndFill(
                      forPickup: _selectingPickup, lat: lat, lon: lon);
                  if (_pickLat != null &&
                      _pickLon != null &&
                      _dropLat != null &&
                      _dropLon != null &&
                      !_loading) {
                    _quoteRide();
                  }
                },
                onPositionsChanged: (p, d) {
                  setState(() {
                    _pickLat = p?.latitude;
                    _pickLon = p?.longitude;
                    _dropLat = d?.latitude;
                    _dropLon = d?.longitude;
                  });
                  if (_pickLat != null &&
                      _pickLon != null &&
                      _dropLat != null &&
                      _dropLon != null &&
                      !_loading) {
                    _quoteRide();
                  }
                },
              )),
          const SizedBox(height: 8),
          // Address inputs
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: TextField(
                        controller: _addrPickup,
                        decoration: const InputDecoration(
                          labelText: 'Pickup address',
                          hintText: 'z. B. Umayyad Square, Damascus',
                        ),
                        focusNode: _addrPickupFocus,
                        onChanged: (_) => _scheduleAutocomplete(forPickup: true),
                        onSubmitted: (_) => _geocodeAndSet(forPickup: true),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      tooltip: 'Pickup suchen',
                      onPressed: _geoLoading ? null : () => _geocodeAndSet(forPickup: true),
                      icon: _geoLoading ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.search),
                    ),
                  ]),
                  _buildSuggestions(forPickup: true),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                      child: TextField(
                        controller: _addrDropoff,
                        decoration: const InputDecoration(
                          labelText: 'Dropoff address',
                          hintText: 'z. B. Aleppo Citadel',
                        ),
                        focusNode: _addrDropoffFocus,
                        onChanged: (_) => _scheduleAutocomplete(forPickup: false),
                        onSubmitted: (_) => _geocodeAndSet(forPickup: false),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      tooltip: 'Dropoff suchen',
                      onPressed: _geoLoading ? null : () => _geocodeAndSet(forPickup: false),
                      icon: _geoLoading ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.search),
                    ),
                  ]),
                  _buildSuggestions(forPickup: false),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(children: [
            ChoiceChip(
                label: const Text('Pickup'),
                selected: _selectingPickup,
                onSelected: (_) => setState(() => _selectingPickup = true)),
            const SizedBox(width: 8),
            ChoiceChip(
                label: const Text('Dropoff'),
                selected: !_selectingPickup,
                onSelected: (_) => setState(() => _selectingPickup = false)),
          ]),
          const SizedBox(height: 8),
          // My Places (Favorites)
          if (_favLoading)
            const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: LinearProgressIndicator(minHeight: 2)),
          Wrap(spacing: 8, runSpacing: 4, children: [
            ..._favorites.map((f) {
              final String id = f['id'] as String;
              final String label = f['label'] as String;
              final double lat = (f['lat'] as num).toDouble();
              final double lon = (f['lon'] as num).toDouble();
              return GestureDetector(
                onLongPress: () => _renameFavorite(f),
                child: InputChip(
                  label: Text(label),
                  avatar: const Icon(Icons.place, size: 18),
                  onPressed: () {
                    setState(() {
                      if (_selectingPickup) {
                        _pickLat = lat;
                        _pickLon = lon;
                      } else {
                        _dropLat = lat;
                        _dropLon = lon;
                      }
                    });
                    _quoteRide();
                  },
                  onDeleted: () {
                    _deleteFavorite(id);
                  },
                ),
              );
            }),
            ActionChip(
                label: const Text('Add current…'),
                avatar: const Icon(Icons.add, size: 18),
                onPressed: _addFavorite),
          ]),
          const SizedBox(height: 8),
          Glass(
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                    onPressed: _loading ? null : _requestAndPrepay,
                    child: const Text('Book a ride & pay in app')),
                FilledButton(
                    onPressed: _loading ? null : _requestCash,
                    child: const Text('Book a ride & pay cash')),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 4, children: [
            OutlinedButton.icon(
                onPressed: _loading ? null : _pickScheduleDateTime,
                icon: const Icon(Icons.event_outlined),
                label: Text(_scheduledAt == null
                    ? 'Pick date/time'
                    : 'Picked: ${_fmtDateTimeLocal(_scheduledAt!)}')),
            FilledButton.icon(
                onPressed: _loading ? null : () => _scheduleRide(when: _scheduledAt),
                icon: const Icon(Icons.schedule_send),
                label: const Text('Schedule')),
            // Removed manual dispatch trigger button
          ]),
          const SizedBox(height: 8),
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    const Icon(Icons.person_add_alt_outlined),
                    const SizedBox(width: 8),
                    const Text('Book for another person'),
                    const Spacer(),
                    Switch(
                        value: _forOther,
                        onChanged: (v) => setState(() => _forOther = v)),
                  ]),
                  if (_forOther) ...[
                    const SizedBox(height: 8),
                    Row(children: [
                      Expanded(
                        child: TextField(
                          controller: _otherName,
                          decoration: const InputDecoration(
                              labelText: 'Name (optional)'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Row(children: [
                          Expanded(
                            child: TextField(
                              controller: _otherPhone,
                              keyboardType: TextInputType.phone,
                              decoration: const InputDecoration(
                                  labelText: 'Phone (+963...)'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton(
                              onPressed: _loading ? null : _pickOtherFromContacts,
                              icon: const Icon(Icons.contacts_outlined))
                        ]),
                      ),
                    ]),
                    const SizedBox(height: 4),
                    const Text(
                        'Payment: "Pay in app" charges you; "Pay cash" means the passenger pays on pickup.'),
                  ],
                ],
              ),
            ),
          ),
          // Quote is shown at the top; remove duplicate from bottom
          if (_rideId != null)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('Ride ID: $_rideId')),
        const SizedBox(height: 8),
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Text('Scheduled rides', style: TextStyle(fontWeight: FontWeight.bold)),
                  const Spacer(),
                  IconButton(
                      tooltip: 'Refresh',
                      onPressed: _schedLoading ? null : _loadScheduled,
                      icon: _schedLoading
                          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.refresh)),
                ]),
                if (_scheduled.isEmpty && !_schedLoading)
                  const Padding(
                      padding: EdgeInsets.symmetric(vertical: 8),
                      child: Text('No scheduled rides')),
                if (_scheduled.isNotEmpty)
                  ..._scheduled.map((e) {
                    final id = e['id'] as String? ?? '';
                    final tsRaw = e['scheduled_for']?.toString() ?? '';
                    DateTime? ts;
                    try { ts = DateTime.parse(tsRaw); } catch (_) {}
                    final whenStr = ts != null ? _fmtDateTimeLocal(ts) : tsRaw;
                    return ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      title: Text(whenStr),
                      subtitle: Text('Pickup: ${(e['pickup_lat'] ?? '').toString()}, ${(e['pickup_lon'] ?? '').toString()}'),
                      trailing: TextButton.icon(
                        onPressed: _schedLoading ? null : () => _cancelScheduled(id),
                        icon: const Icon(Icons.cancel),
                        label: const Text('Cancel'),
                      ),
                    );
                  }),
              ],
            ),
          ),
        ),
      ])),
    ]),
  );
}
}

class _MiniMap extends StatelessWidget {
  final LatLng? pickup;
  final LatLng? dropoff;
  final void Function(double, double) onTap;
  final void Function(LatLng?, LatLng?)? onPositionsChanged;
  const _MiniMap(
      {required this.pickup, required this.dropoff, required this.onTap, this.onPositionsChanged});
  @override
  Widget build(BuildContext context) {
    final center = pickup ?? dropoff ?? const LatLng(33.5138, 36.2765);
    if (!tomTomConfigured()) {
      return tomTomMissingKeyPlaceholder();
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: Stack(children: [
        FlutterMap(
          options: MapOptions(
            initialCenter: center,
            initialZoom: 13,
                onTap: (p, ll) => onTap(ll.latitude, ll.longitude),
          ),
          children: [
            ...tomTomTileLayers(),
            MarkerLayer(markers: [
              if (pickup != null)
                Marker(
                  point: pickup!,
                  width: 32,
                  height: 32,
                  child: const Icon(Icons.place, color: Colors.green, size: 28),
                ),
              if (dropoff != null)
                Marker(
                  point: dropoff!,
                  width: 32,
                  height: 32,
                  child: const Icon(Icons.flag, color: Colors.red, size: 28),
                ),
            ]),
          ],
        ),
        Positioned(
          right: 8,
          top: 8,
          child: Card(
            child: IconButton(
              tooltip: 'Vollbild Karte',
              icon: const Icon(Icons.open_in_full),
              onPressed: () async {
                final res = await Navigator.push<_RiderMapResult>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => _RiderMapFullscreen(
                      initialPickup: pickup,
                      initialDropoff: dropoff,
                    ),
                  ),
                );
                if (res != null && onPositionsChanged != null) {
                  onPositionsChanged!(res.pickup, res.dropoff);
                }
              },
            ),
          ),
        )
      ]),
    );
  }
}

class _RiderMapResult {
  final LatLng? pickup;
  final LatLng? dropoff;
  const _RiderMapResult(this.pickup, this.dropoff);
}

class _RiderMapFullscreen extends StatefulWidget {
  final LatLng? initialPickup;
  final LatLng? initialDropoff;
  const _RiderMapFullscreen({this.initialPickup, this.initialDropoff});
  @override
  State<_RiderMapFullscreen> createState() => _RiderMapFullscreenState();
}

class _RiderMapFullscreenState extends State<_RiderMapFullscreen> {
  late LatLng _center;
  LatLng? _pickup;
  LatLng? _dropoff;
  bool _selectingPickup = true;

  @override
  void initState() {
    super.initState();
    _pickup = widget.initialPickup;
    _dropoff = widget.initialDropoff;
    _center = _pickup ?? _dropoff ?? const LatLng(33.5138, 36.2765);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Karte'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(
                  context, _RiderMapResult(_pickup, _dropoff)),
              child: const Text('Apply')),
        ],
      ),
      body: Stack(children: [
        FlutterMap(
          options: MapOptions(
            initialCenter: _center,
            initialZoom: 13,
            onTap: (p, ll) {
              setState(() {
                if (_selectingPickup) {
                  _pickup = ll;
                } else {
                  _dropoff = ll;
                }
              });
            },
          ),
          children: [
            ...tomTomTileLayers(),
            MarkerLayer(markers: [
              if (_pickup != null)
                Marker(
                    point: _pickup!,
                    width: 36,
                    height: 36,
                    child:
                        const Icon(Icons.place, color: Colors.green, size: 30)),
              if (_dropoff != null)
                Marker(
                    point: _dropoff!,
                    width: 36,
                    height: 36,
                    child:
                        const Icon(Icons.flag, color: Colors.red, size: 30)),
            ])
          ],
        ),
        Positioned(
          left: 8,
          top: 8,
          child: Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Text('Pickup'),
                Switch(
                    value: _selectingPickup,
                    onChanged: (v) => setState(() => _selectingPickup = v)),
                const Text('Dropoff'),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}
// ignore_for_file: use_build_context_synchronously
