import 'dart:convert';
import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'profile_screen.dart';
import 'package:latlong2/latlong.dart';
import '../map_view.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/messages.dart';
import 'package:shared_ui/toast.dart';

const bool _mapShowTraffic =
    bool.fromEnvironment('MAPS_SHOW_TRAFFIC', defaultValue: true);

class TaxiScreen extends StatefulWidget {
  const TaxiScreen({super.key});

  @override
  State<TaxiScreen> createState() => _TaxiScreenState();
}

class _MiniMap extends StatelessWidget {
  final LatLng? pickup;
  final LatLng? dropoff;
  final void Function(double lat, double lon) onTap;
  const _MiniMap(
      {required this.pickup, required this.dropoff, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final center = pickup ?? dropoff ?? const LatLng(33.5138, 36.2765);
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: SuperMapView(
        center: center,
        zoom: 13,
        onTap: (lat, lon) => onTap(lat, lon),
        showTraffic: _mapShowTraffic,
        markers: [
          if (pickup != null)
            MapMarker(point: pickup!, color: Colors.green, size: 28),
          if (dropoff != null)
            MapMarker(point: dropoff!, color: Colors.red, size: 28),
        ],
      ),
    );
  }
}

class _TaxiScreenState extends State<TaxiScreen> {
  final _tokens = MultiTokenStore();
  String? _quote;
  String? _rideId;
  bool _loading = false;
  String? _last;
  // Map
  double? _pickLat = 33.5138, _pickLon = 36.2765;
  double? _dropLat, _dropLon;
  bool _selectingPickup = true;
  // Scheduling
  DateTime? _scheduledFor;
  // Favorites
  List<Map<String, dynamic>> _favorites = [];
  bool _favLoading = false;
  // Driver state
  bool _driverOnline = false;
  Timer? _locTimer;
  double? _drvLat = 33.5138, _drvLon = 36.2765;
  String? _rideStatus; // requested|assigned|accepted|enroute|completed
  double? _targetPickupLat, _targetPickupLon, _targetDropLat, _targetDropLon;

  Future<Map<String, String>> _taxiHeaders() =>
      authHeaders('taxi', store: _tokens);

  Uri _taxiUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('taxi', path, query: query);

  Future<void> _quoteRide() async {
    final t = await getTokenFor('taxi', store: _tokens);
    if (t == null) { MessageHost.showInfoBanner(context, SharedMessages.loginFirst(context)); return; }
    setState(() => _loading = true);
    try {
      final body = {
        'pickup_lat': 33.5138,
        'pickup_lon': 36.2765,
        'dropoff_lat': 33.52,
        'dropoff_lon': 36.28,
      };
      final res = await http.post(_taxiUri('/rides/quote'),
          headers: await _taxiHeaders(),
          body: jsonEncode(body));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final int price =
          (js['final_quote_cents'] ?? js['quoted_fare_cents']) as int? ?? 0;
      setState(() => _quote = '${_fmtSyp(price)}, ${js['distance_km']} km');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Quote failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _loadFavorites();
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
      MessageHost.showErrorBanner(context, 'Error: $e');
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
      MessageHost.showErrorBanner(context, 'Delete failed: ${r.body}');
      return;
      }
      setState(() => _favorites.removeWhere((e) => e['id'] == id));
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Error: $e');
    }
  }

  Future<void> _requestAndPrepay() async {
    final t = await getTokenFor('taxi', store: _tokens);
    if (t == null) { MessageHost.showInfoBanner(context, SharedMessages.loginFirst(context)); return; }
    if (_pickLat == null ||
        _pickLon == null ||
        _dropLat == null ||
        _dropLon == null) {
      _toast('Please set pickup and dropoff');
      return;
    }
    setState(() => _loading = true);
    try {
      // 1) Quote
      final qRes = await http.post(_taxiUri('/rides/quote'),
          headers: await _taxiHeaders(),
          body: jsonEncode({
            'pickup_lat': _pickLat,
            'pickup_lon': _pickLon,
            'dropoff_lat': _dropLat,
            'dropoff_lon': _dropLon,
          }));
      if (qRes.statusCode >= 400) throw Exception(qRes.body);
      final q = jsonDecode(qRes.body) as Map<String, dynamic>;
      final int price =
          q['final_quote_cents'] as int? ?? q['quoted_fare_cents'] as int? ?? 0;
      final ok = await _confirm('Request Taxi',
          'Price: ${_fmtSyp(price)}\nJetzt bezahlen und Fahrt anfragen?');
      if (!ok) return;
      // 2) Create ride + prepay
      final rRes = await http.post(_taxiUri('/rides/request'),
          headers: await _taxiHeaders(),
          body: jsonEncode({
            'pickup_lat': _pickLat,
            'pickup_lon': _pickLon,
            'dropoff_lat': _dropLat,
            'dropoff_lon': _dropLon,
            'prepay': true,
          }));
      if (rRes.statusCode == 200) {
        final js = jsonDecode(rRes.body) as Map<String, dynamic>;
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
          MessageHost.showInfoBanner(context, 'Insufficient rider balance in Payments. Please top up.');
        } else {
          MessageHost.showErrorBanner(context, 'Request failed: ${rRes.body}');
        }
      }
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Request error: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _scheduleRide() async {
    final t = await getTokenFor('taxi', store: _tokens);
    if (t == null) { MessageHost.showInfoBanner(context, 'Login first'); return; }
    if (_pickLat == null ||
        _pickLon == null ||
        _dropLat == null ||
        _dropLon == null) {
      _toast('Please set pickup and dropoff');
      return;
    }
    final when = _scheduledFor ?? DateTime.now().add(const Duration(minutes: 15));
    setState(() => _loading = true);
    try {
      final body = {
        'pickup_lat': _pickLat,
        'pickup_lon': _pickLon,
        'dropoff_lat': _dropLat,
        'dropoff_lon': _dropLon,
        'scheduled_for': when.toUtc().toIso8601String(),
      };
      final res = await http.post(_taxiUri('/rides/schedule'),
          headers: await _taxiHeaders(),
          body: jsonEncode(body));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      _toast('Scheduled for ${js['scheduled_for'] ?? when.toIso8601String()}');
    } catch (e) {
      _toast('Schedule failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _pickDateTime() async {
    final now = DateTime.now();
    final initialDate = now.add(const Duration(minutes: 15));
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: initialDate,
      firstDate: now,
      lastDate: now.add(const Duration(days: 30)),
    );
    if (pickedDate == null) return;
    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initialDate),
    );
    if (pickedTime == null) return;
    final dt = DateTime(
        pickedDate.year, pickedDate.month, pickedDate.day, pickedTime.hour, pickedTime.minute);
    setState(() => _scheduledFor = dt);
  }

  Future<void> _applyDriver() async {
    try {
      final res = await http.post(_taxiUri('/driver/apply'),
          headers: await _taxiHeaders(),
          body: jsonEncode({"vehicle_make": "Toyota", "vehicle_plate": "APP"}));
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Driver enabled');
    } catch (e) {
      _toast('Apply failed: $e');
    }
  }

  // removed unused _goAvailable helper (deprecated by Online toggle)

  Future<void> _requestRide() async {
    setState(() => _loading = true);
    try {
      final body = {
        'pickup_lat': 33.5138,
        'pickup_lon': 36.2765,
        'dropoff_lat': 33.52,
        'dropoff_lon': 36.28,
      };
      final res = await http.post(_taxiUri('/rides/request'),
          headers: await _taxiHeaders(),
          body: jsonEncode(body));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _rideId = js['id'] as String?);
      _toast('Ride requested: ${_rideId ?? '-'}');
    } catch (e) {
      _toast('Request failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _acceptRide() async {
    final id = _rideId;
    if (id == null) {
      _toast('No ride to accept');
      return;
    }
    setState(() => _loading = true);
    try {
      final headers = await _taxiHeaders();
      final res = await http.post(_taxiUri('/rides/$id/accept'),
          headers: headers);
      if (res.statusCode == 200) {
        _rideStatus = 'accepted';
        // Load ride details for targets
        try {
          final info = await http.get(_taxiUri('/rides/$id'),
              headers: await _taxiHeaders());
          if (info.statusCode == 200) {
            final js = jsonDecode(info.body) as Map<String, dynamic>;
            _targetPickupLat = (js['pickup_lat'] as num?)?.toDouble();
            _targetPickupLon = (js['pickup_lon'] as num?)?.toDouble();
            _targetDropLat = (js['dropoff_lat'] as num?)?.toDouble();
            _targetDropLon = (js['dropoff_lon'] as num?)?.toDouble();
          }
        } catch (_) {}
        _toast('Accepted');
        return;
      }
      // Try parse structured error
      Map<String, dynamic>? detail;
      try {
        final js = jsonDecode(res.body) as Map<String, dynamic>;
        detail = js['detail'] is Map<String, dynamic> ? js['detail'] : null;
      } catch (_) {}
      if (res.statusCode == 400 &&
          detail != null &&
          detail['code'] == 'insufficient_taxi_wallet_balance') {
        final int shortfall = (detail['shortfall_cents'] ?? 0) is int
            ? detail['shortfall_cents'] as int
            : int.tryParse('${detail['shortfall_cents']}') ?? 0;
        final int required = (detail['required_fee_cents'] ?? 0) is int
            ? detail['required_fee_cents'] as int
            : int.tryParse('${detail['required_fee_cents']}') ?? 0;
        final bool ok = await _confirm(
            'Insufficient taxi wallet', '''Required fee: ${_fmtSyp(required)}
Current balance: ${_fmtSyp(detail['wallet_balance_cents'])}
Top up shortfall now? (${_fmtSyp(shortfall)})''');
        if (ok) {
          final top = await http.post(
              _taxiUri('/driver/taxi_wallet/topup'),
              headers: await _taxiHeaders(),
              body: jsonEncode({"amount_cents": shortfall}));
          if (top.statusCode >= 400) {
            _toast('Topup failed: ${top.body}');
          } else {
            _toast('Topup ok, retrying accept...');
            final r2 = await http.post(
                _taxiUri('/rides/$id/accept'),
                headers: await _taxiHeaders());
            if (r2.statusCode == 200) {
              _toast('Accepted');
              return;
            } else {
              _toast('Accept failed: ${r2.body}');
            }
          }
        }
      } else {
        _toast('Accept failed: ${res.body}');
      }
    } catch (e) {
      _toast('Accept error: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _startRide() async {
    final id = _rideId;
    if (id == null) {
      _toast('No ride');
      return;
    }
    try {
      final r = await http.post(_taxiUri('/rides/$id/start'),
          headers: await _taxiHeaders());
      if (r.statusCode >= 400) throw Exception(r.body);
      _rideStatus = 'enroute';
      _toast('Ride started');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Start failed: $e');
    }
  }

  Future<void> _completeRide() async {
    final id = _rideId;
    if (id == null) { MessageHost.showInfoBanner(context, 'No ride'); return; }
    try {
      if (!_canComplete()) { MessageHost.showInfoBanner(context, 'Not near dropoff yet'); return; }
      final r = await http.post(_taxiUri('/rides/$id/complete'),
          headers: await _taxiHeaders());
      if (r.statusCode >= 400) throw Exception(r.body);
      _rideStatus = 'completed';
      _toast('Ride completed');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Complete failed: $e');
    }
  }

  Future<void> _showWallet() async {
    try {
      final r = await http.get(_taxiUri('/driver/taxi_wallet'),
          headers: await _taxiHeaders());
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final bal = js['balance_cents'];
      final entries = (js['entries'] as List?) ?? [];
      final fee = entries
          .cast<Map>()
          .cast<Map<String, dynamic>?>()
          .firstWhere((e) => e?['type'] == 'fee', orElse: () => null);
      setState(() => _last =
          'Balance: ${_fmtSyp(bal)}\nLast fee: ${fee != null ? jsonEncode(fee) : 'none'}');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Wallet failed: $e');
    }
  }

  Future<bool> _confirm(String title, String msg) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(title),
        content: Text(msg),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('OK')),
        ],
      ),
    );
    return ok == true;
  }

  void _toast(String msg) { if (!mounted) return; showToast(context, msg); }

  // ----- Driver Online & Auto-Location -----
  Future<void> _setDriverOnline(bool online) async {
    try {
      final res = await http.put(_taxiUri('/driver/status'),
          headers: await _taxiHeaders(),
          body: jsonEncode({"status": online ? "available" : "offline"}));
      if (res.statusCode >= 400) throw Exception(res.body);
      setState(() => _driverOnline = online);
      _locTimer?.cancel();
      if (online) {
        _locTimer = Timer.periodic(
            const Duration(seconds: 3), (_) => _autoMoveAndUpdateLocation());
      }
    } catch (e) {
      _toast('Status failed: $e');
    }
  }

  double _haversineKm(double lat1, double lon1, double lat2, double lon2) {
    const R = 6371.0;
    double dLat = (lat2 - lat1) * math.pi / 180.0;
    double dLon = (lon2 - lon1) * math.pi / 180.0;
    double a = (math.sin(dLat / 2) * math.sin(dLat / 2)) +
        math.cos(lat1 * math.pi / 180.0) *
            math.cos(lat2 * math.pi / 180.0) *
            (math.sin(dLon / 2) * math.sin(dLon / 2));
    double c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a));
    return R * c;
  }

  bool _canComplete() {
    if (_rideStatus != 'enroute') return false;
    if (_drvLat == null ||
        _drvLon == null ||
        _targetDropLat == null ||
        _targetDropLon == null) {
      return false;
    }
    return _haversineKm(_drvLat!, _drvLon!, _targetDropLat!, _targetDropLon!) <=
        0.2;
  }

  Future<void> _autoMoveAndUpdateLocation() async {
    // Simple simulated movement: move towards pickup if accepted, towards dropoff if enroute
    double lat = _drvLat ?? 33.5138;
    double lon = _drvLon ?? 36.2765;
    double? tLat;
    double? tLon;
    if (_rideStatus == 'accepted' &&
        _targetPickupLat != null &&
        _targetPickupLon != null) {
      tLat = _targetPickupLat;
      tLon = _targetPickupLon;
    } else if (_rideStatus == 'enroute' &&
        _targetDropLat != null &&
        _targetDropLon != null) {
      tLat = _targetDropLat;
      tLon = _targetDropLon;
    }
    if (tLat != null && tLon != null) {
      final dLat = (tLat - lat);
      final dLon = (tLon - lon);
      // step fractionally towards target
      lat += dLat * 0.15;
      lon += dLon * 0.15;
    }
    _drvLat = lat;
    _drvLon = lon;
    try {
      await http.put(_taxiUri('/driver/location'),
          headers: await _taxiHeaders(),
          body: jsonEncode({"lat": _drvLat, "lon": _drvLon}));
    } catch (_) {}
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: const Text('Taxi'),
          flexibleSpace: const Glass(
              padding: EdgeInsets.zero,
              blur: 24,
              opacity: 0.16,
              borderRadius: BorderRadius.zero)),
      body: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 0, vertical: 16),
          children: [
        const Text('Use single‑login via Profile/Payments.'),
        TextButton(
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const ProfileScreen())),
            child: const Text('Zum Profil (Login)')),
        const Divider(height: 16),
        Glass(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child:
                  Text('Rider', style: TextStyle(fontWeight: FontWeight.bold))),
          // Simple map: tap to set pickup/dropoff
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
                // Auto-estimate when both pins are set
                if (_pickLat != null &&
                    _pickLon != null &&
                    _dropLat != null &&
                    _dropLon != null) {
                  if (!_loading) {
                    _quoteRide();
                  }
                }
              },
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
          // end Rider block
        ])),
        const SizedBox(height: 12),
        // Primary CTAs — full‑width, top‑level card to match siblings
        Glass(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                    style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(48)),
                    onPressed: _loading ? null : _requestAndPrepay,
                    child: const Text('Book a ride & pay in app')),
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                    style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(48)),
                    onPressed: _loading ? null : _requestRide,
                    child: const Text('Book a ride & pay cash')),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        // Scheduling card — also top‑level for consistent width
        Glass(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                    minimumSize: const Size.fromHeight(48)),
                onPressed: _loading ? null : _pickDateTime,
                icon: const Icon(Icons.event),
                label: Text(_scheduledFor == null
                    ? 'Pick date/time'
                    : 'Picked: ${_scheduledFor!.toLocal()}'),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(48)),
                onPressed: _loading ? null : _scheduleRide,
                icon: const Icon(Icons.schedule),
                label: const Text('Schedule'),
              ),
              if (_quote != null)
                Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text('Quote: $_quote')),
              if (_rideId != null)
                Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text('Ride ID: $_rideId')),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Glass(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text('Driver',
                  style: TextStyle(fontWeight: FontWeight.bold))),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton.tonal(
                onPressed: _applyDriver, child: const Text('Apply Driver')),
            Row(mainAxisSize: MainAxisSize.min, children: [
              const Text('Online'),
              Switch(
                  value: _driverOnline, onChanged: (v) => _setDriverOnline(v)),
            ]),
            FilledButton(
                onPressed: _acceptRide,
                child: const Text('Accept (with Top‑Up if needed)')),
            FilledButton.tonal(
                onPressed: _startRide, child: const Text('Start')),
            FilledButton.tonal(
                onPressed: _canComplete() ? _completeRide : null,
                child: const Text('Complete')),
            FilledButton.tonal(
                onPressed: _showWallet, child: const Text('Show Taxi Wallet')),
          ]),
          if (_last != null)
            Padding(
                padding: const EdgeInsets.only(top: 8), child: Text(_last!)),
        ])),
      ]),
    );
  }
}

String _fmtSyp(dynamic cents) {
  int c = 0;
  if (cents is int) {
    c = cents;
  } else {
    c = int.tryParse('$cents') ?? 0;
  }
  final int syp = c ~/ 100;
  return 'SYP $syp';
}
// ignore_for_file: use_build_context_synchronously
