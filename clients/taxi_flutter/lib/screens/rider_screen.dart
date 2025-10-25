import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:maplibre_gl/maplibre_gl.dart' as mgl;
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:latlong2/latlong.dart';
import '../api.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:convert';
import '../ui/components.dart';
import '../ui/notify.dart';
import 'package:shared_ui/glass.dart';
import 'package:local_auth/local_auth.dart';
import 'package:flutter_contacts/flutter_contacts.dart';
import '../l10n/app_localizations.dart';
import '../utils/currency.dart';
// Cash flow: no deep links or clipboard actions needed

class RiderScreen extends StatefulWidget {
  final ApiClient api;
  const RiderScreen({super.key, required this.api});
  @override
  State<RiderScreen> createState() => _RiderScreenState();
}

class _RiderScreenState extends State<RiderScreen> {
  String get _tomKey => (dotenv.env['TOMTOM_TILES_KEY'] ?? dotenv.env['TOMTOM_API_KEY_TAXI'] ?? dotenv.env['TOMTOM_MAP_KEY'] ?? dotenv.env['TOMTOM_API_KEY'] ?? '').trim();
  String get _tomtomTileUrl => 'https://api.tomtom.com/map/1/tile/basic/main/{z}/{x}/{y}.png?key=$_tomKey';
  static const bool _useMapLibre = bool.fromEnvironment('USE_MAPLIBRE', defaultValue: false);
  static const String _styleUrl = String.fromEnvironment('STYLE_URL', defaultValue: 'https://demotiles.maplibre.org/style.json');
  static const String _tomtomStyleUrl = String.fromEnvironment('TOMTOM_STYLE_URL', defaultValue: '');
  static const double _sectionSpacing = 20.0;
  final _pickupLat = TextEditingController(text: '33.5138');
  final _pickupLon = TextEditingController(text: '36.2765');
  final _dropLat = TextEditingController(text: '33.5200');
  final _dropLon = TextEditingController(text: '36.2800');
  final _stopLat = TextEditingController();
  final _stopLon = TextEditingController();
  final _promo = TextEditingController();
  final _searchCtrl = TextEditingController();
  List<dynamic> _searchItems = [];
  // Address input & autocomplete (via backend maps/autocomplete)
  final _addrPickup = TextEditingController();
  final _addrDropoff = TextEditingController();
  final FocusNode _addrPickupFocus = FocusNode();
  final FocusNode _addrDropoffFocus = FocusNode();
  Timer? _acTimer;
  List<Map<String, dynamic>> _acPickup = [];
  List<Map<String, dynamic>> _acDropoff = [];
  bool _loading = false;
  String? _lastRideId;
  String? _lastStatus;
  int? _quotedFare;
  int? _finalFare;
  double? _lastDistanceKm;
  bool _riderReward = false;
  bool _driverReward = false;
  int? _walletBalanceCents;
  String _walletCurrency = 'SYP';
  bool _walletLoading = false;
  Map<String, dynamic>? _lastQuote;
  bool _ctaShown = false;
  Timer? _poller;
  final _mapCtrl = MapController();
  mgl.MapLibreMapController? _mlCtrl;
  mgl.Line? _mlRoute;
  mgl.Symbol? _mlPickup;
  mgl.Symbol? _mlDrop;
  mgl.Symbol? _mlDriver;
  LatLng _pickup = const LatLng(33.5138, 36.2765);
  LatLng _drop = const LatLng(33.5200, 36.2800);
  LatLng? _driverPos;
  String _tapMode = 'pickup'; // or 'drop'
  WebSocketChannel? _ws;
  List<LatLng> _route = [];
  int? _etaMins;
  final bool _useTomTomTiles = true;
  bool _trackDriver = false;
  // For another person
  bool _forOther = false;
  final _otherName = TextEditingController();
  final _otherPhone = TextEditingController();
  // Scheduled rides
  bool _schedLoading = false;
  List<Map<String, dynamic>> _scheduled = [];
  // Ride class selection
  final List<String> _rideClasses = const ['standard','comfort','yellow','vip','van','electro'];
  String _rideClass = 'standard';

  @override
  void initState() {
    super.initState();
    _loadScheduled();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshWallet(silent: true);
    });
  }

  List<LatLng> _decodePolyline6(String poly) {
    List<LatLng> pts = [];
    int index = 0, lat = 0, lon = 0;
    while (index < poly.length) {
      int b, shift = 0, result = 0;
      do {
        b = poly.codeUnitAt(index++) - 63;
        result |= (b & 0x1f) << shift;
        shift += 5;
      } while (b >= 0x20);
      int dlat = ((result & 1) != 0 ? ~(result >> 1) : (result >> 1));
      lat += dlat;

      shift = 0; result = 0;
      do {
        b = poly.codeUnitAt(index++) - 63;
        result |= (b & 0x1f) << shift;
        shift += 5;
      } while (b >= 0x20);
      int dlon = ((result & 1) != 0 ? ~(result >> 1) : (result >> 1));
      lon += dlon;
      pts.add(LatLng(lat / 1e6, lon / 1e6));
    }
    return pts;
  }

  Future<void> _mlRefreshOverlays() async {
    if (_mlCtrl == null) return;
    final c = _mlCtrl!;
    try {
      if (_mlRoute != null) {
        await c.removeLine(_mlRoute!);
        _mlRoute = null;
      }
      if (_mlPickup != null) {
        await c.removeSymbol(_mlPickup!);
        _mlPickup = null;
      }
      if (_mlDrop != null) {
        await c.removeSymbol(_mlDrop!);
        _mlDrop = null;
      }
      if (_mlDriver != null) {
        await c.removeSymbol(_mlDriver!);
        _mlDriver = null;
      }
      if (_route.isNotEmpty) {
        final pts = _route.map((e) => mgl.LatLng(e.latitude, e.longitude)).toList();
        _mlRoute = await c.addLine(mgl.LineOptions(
          geometry: pts,
          lineColor: '#3f51b5',
          lineWidth: 4.0,
        ));
      }
      _mlPickup = await c.addSymbol(mgl.SymbolOptions(
        geometry: mgl.LatLng(_pickup.latitude, _pickup.longitude),
        iconImage: 'marker-15',
      ));
      _mlDrop = await c.addSymbol(mgl.SymbolOptions(
        geometry: mgl.LatLng(_drop.latitude, _drop.longitude),
        iconImage: 'marker-15',
      ));
      if (_driverPos != null) {
        _mlDriver = await c.addSymbol(mgl.SymbolOptions(
          geometry: mgl.LatLng(_driverPos!.latitude, _driverPos!.longitude),
          iconImage: 'marker-15',
        ));
      }
    } catch (_) {}
  }

  Future<void> _fillAddressFromCoords({required bool forPickup, required double lat, required double lon}) async {
    try {
      final js = await widget.api.mapsReverse(lat: lat, lon: lon);
      final name = (js['display_name'] ?? '').toString();
      if (name.isEmpty) return;
      setState(() {
        if (forPickup) {
          _addrPickup.text = name;
        } else {
          _addrDropoff.text = name;
        }
      });
    } catch (_) {}
  }

  Future<Map<String, dynamic>> _requestRideInternal({required bool prepay, required String payMode}) async {
    final pLat = double.tryParse(_pickupLat.text.trim());
    final pLon = double.tryParse(_pickupLon.text.trim());
    final dLat = double.tryParse(_dropLat.text.trim());
    final dLon = double.tryParse(_dropLon.text.trim());
    if (pLat == null || pLon == null || dLat == null || dLon == null) {
      throw Exception('invalid_coordinates');
    }
    final List<Map<String, dynamic>> stops = [];
    final sLat = double.tryParse((_stopLat.text).trim());
    final sLon = double.tryParse((_stopLon.text).trim());
    if (sLat != null && sLon != null) stops.add({'lat': sLat, 'lon': sLon});
    final promo = _promo.text.trim().isEmpty ? null : _promo.text.trim();
    return widget.api.requestRide(
      pickupLat: pLat,
      pickupLon: pLon,
      dropLat: dLat,
      dropLon: dLon,
      rideClass: _rideClass,
      prepay: prepay,
      payMode: payMode,
      stops: stops.isEmpty ? null : stops,
      promoCode: promo,
      forName: _forOther ? _otherName.text.trim() : null,
      forPhone: _forOther ? _otherPhone.text.trim() : null,
    );
  }

  List<LatLng> _decodePolylinePointsOrPoly6(String poly) {
    // If backend sends pipe-separated lat,lon pairs, parse them first.
    if (poly.contains('|')) {
      final parts = poly.split('|');
      final pts = <LatLng>[];
      for (final p in parts) {
        final xy = p.split(',');
        if (xy.length == 2) {
          final lat = double.tryParse(xy[0].trim());
          final lon = double.tryParse(xy[1].trim());
          if (lat != null && lon != null) pts.add(LatLng(lat, lon));
        }
      }
      return pts;
    }
    // Fallback to polyline6 decoder
    try {
      return _decodePolyline6(poly);
    } catch (_) {
      return <LatLng>[];
    }
  }

  Future<void> _quote() async {
    final pLat = double.tryParse(_pickupLat.text.trim());
    final pLon = double.tryParse(_pickupLon.text.trim());
    final dLat = double.tryParse(_dropLat.text.trim());
    final dLon = double.tryParse(_dropLon.text.trim());
    if (pLat == null || pLon == null || dLat == null || dLon == null) return;
    setState(() => _loading = true);
    try {
      final List<Map<String, dynamic>> stops = [];
      final sLat = double.tryParse((_stopLat.text).trim());
      final sLon = double.tryParse((_stopLon.text).trim());
      if (sLat != null && sLon != null) stops.add({'lat': sLat, 'lon': sLon});
      final promo = _promo.text.trim().isEmpty ? null : _promo.text.trim();
      final res = await widget.api.quoteRide(
          pickupLat: pLat,
          pickupLon: pLon,
          dropLat: dLat,
          dropLon: dLon,
          rideClass: _rideClass,
          stops: stops.isEmpty ? null : stops,
          promoCode: promo);
      final q = res['final_quote_cents'] ?? res['quoted_fare_cents'];
      final surge = res['surge_multiplier'];
      final poly = res['route_polyline'] as String?;
      final distKm = (res['distance_km'] as num?)?.toDouble();
      setState(() {
        _route = (poly != null && poly.isNotEmpty) ? _decodePolylinePointsOrPoly6(poly) : [];
        _etaMins = distKm != null ? (distKm / 30.0 * 60.0).round() : null; // ~30km/h
        _lastQuote = res;
      });
      await _mlRefreshOverlays();
      if (mounted) {
        final etaText = _etaMins != null
            ? ' • ${AppLocalizations.of(context)!.eta((_etaMins!).toString())}'
            : '';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Quote: ${formatSyp(q)}  (x${surge ?? 1})$etaText')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _refresh() async {
    try {
      final rides = await widget.api.myRides();
      if (rides.isNotEmpty) {
        final r = rides.first as Map<String, dynamic>;
        setState(() {
          _lastRideId = r['id'] as String?;
          _lastStatus = r['status'] as String?;
          _quotedFare = r['quoted_fare_cents'] as int?;
          _finalFare = r['final_fare_cents'] as int?;
          _lastDistanceKm = (r['distance_km'] as num?)?.toDouble();
          _riderReward = (r['rider_reward_applied'] as bool?) ?? false;
          _driverReward = (r['driver_reward_fee_waived'] as bool?) ?? false;
        });
        if (_lastStatus == 'completed') {
          _stopPolling();
          if (!_ctaShown) {
            _ctaShown = true;
            _showPaymentCta();
          }
        }
      }
      _refreshWallet(silent: true);
    } catch (_) {}
  }

  void _startPolling() {
    _poller?.cancel();
    _poller = Timer.periodic(const Duration(seconds: 3), (_) => _refresh());
  }

  void _stopPolling() {
    _poller?.cancel();
    _poller = null;
  }

  void _openWs() {
    _ws?.sink.close();
    final id = _lastRideId;
    if (id == null) return;
    try {
      // derive ws base from api base
      // naive: replace http with ws
      String base = (widget.api.baseUrl)
          .replaceFirst('https://', 'wss://')
          .replaceFirst('http://', 'ws://');
      final uri = Uri.parse('$base/ws/rides/$id');
      final ch = WebSocketChannel.connect(uri);
      setState(() => _ws = ch);
      ch.stream.listen((event) async {
        try {
          final data = jsonDecode(event as String);
          if (data is Map && data['ride_id'] == id) {
            final typ = data['type'] as String?;
            if (typ == 'ride_status') {
              setState(() {
                _lastStatus = data['status'] as String? ?? _lastStatus;
                _quotedFare =
                    (data['quoted_fare_cents'] as int?) ?? _quotedFare;
                _finalFare = (data['final_fare_cents'] as int?) ?? _finalFare;
                _riderReward = (data['rider_reward_applied'] as bool?) ?? _riderReward;
                _driverReward = (data['driver_reward_fee_waived'] as bool?) ?? _driverReward;
              });
              if (_lastStatus == 'accepted') {
                Notify.show('Ride accepted', 'Your driver is on the way');
              } else if (_lastStatus == 'enroute') {
                Notify.show('Trip started', 'Enjoy your ride');
              } else if (_lastStatus == 'completed') {
                Notify.show('Ride completed', 'Thanks for riding with us');
              }
              if (_lastStatus == 'completed') {
                _stopPolling();
                if (!_ctaShown) {
                  _ctaShown = true;
                  _showPaymentCta();
                }
              }
            } else if (typ == 'driver_location') {
              final lat = (data['lat'] as num?)?.toDouble();
              final lon = (data['lon'] as num?)?.toDouble();
              if (_trackDriver && lat != null && lon != null) {
                setState(() => _driverPos = LatLng(lat, lon));
                await _mlRefreshOverlays();
              }
            }
          }
        } catch (_) {}
      }, onError: (_) {}, onDone: () {});
    } catch (_) {}
  }

  @override
  void dispose() {
    _addrPickup.dispose();
    _addrDropoff.dispose();
    _addrPickupFocus.dispose();
    _addrDropoffFocus.dispose();
    _acTimer?.cancel();
    _otherName.dispose();
    _otherPhone.dispose();
    _poller?.cancel();
    _ws?.sink.close();
    super.dispose();
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
    try {
      final items = await widget.api.mapsAutocomplete(query, limit: 6);
      final mapped = items.map((e) {
        final it = e as Map<String, dynamic>;
        return {
          'text': (it['display_name'] ?? query).toString(),
          'lat': double.tryParse((it['lat'] ?? '').toString()),
          'lon': double.tryParse((it['lon'] ?? '').toString()),
        };
      }).where((m) => m['lat'] != null && m['lon'] != null).take(6).toList();
      setState(() {
        if (forPickup) {
          _acPickup = mapped.cast<Map<String, dynamic>>();
        } else {
          _acDropoff = mapped.cast<Map<String, dynamic>>();
        }
      });
    } catch (_) {}
  }

  Widget _buildSuggestions({required bool forPickup}) {
    final list = forPickup ? _acPickup : _acDropoff;
    if (list.isEmpty) return const SizedBox.shrink();
    return Glass(
      child: ListView.builder(
        shrinkWrap: true,
        itemCount: list.length,
        itemBuilder: (ctx, i) {
          final it = list[i];
          final text = it['text']?.toString() ?? '';
          final lat = (it['lat'] as num?)?.toDouble();
          final lon = (it['lon'] as num?)?.toDouble();
          return ListTile(
            dense: true,
            title: Text(text, maxLines: 2, overflow: TextOverflow.ellipsis),
            subtitle: Text(lat != null && lon != null ? '${lat.toStringAsFixed(6)}, ${lon.toStringAsFixed(6)}' : ''),
            onTap: () {
              if (lat != null && lon != null) {
                setState(() {
                  if (forPickup) {
                    _pickup = LatLng(lat, lon);
                    _pickupLat.text = lat.toStringAsFixed(6);
                    _pickupLon.text = lon.toStringAsFixed(6);
                    _addrPickup.text = text;
                  } else {
                    _drop = LatLng(lat, lon);
                    _dropLat.text = lat.toStringAsFixed(6);
                    _dropLon.text = lon.toStringAsFixed(6);
                    _addrDropoff.text = text;
                  }
                });
                _mapCtrl.move(forPickup ? _pickup : _drop, 14);
              }
            },
          );
        },
      ),
    );
  }

  Future<void> _refreshWallet({bool silent = false}) async {
    setState(() => _walletLoading = true);
    try {
      final res = await widget.api.getWalletBalance();
      setState(() {
        _walletBalanceCents = (res['balance_cents'] as num?)?.toInt();
        _walletCurrency = (res['currency_code'] as String?) ?? 'SYP';
      });
    } catch (e) {
      if (!silent && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Wallet refresh failed: $e'))
        );
      }
    } finally {
      if (mounted) setState(() => _walletLoading = false);
    }
  }

  Future<void> _loadScheduled() async {
    setState(() => _schedLoading = true);
    try {
      final list = await widget.api.scheduledList();
      setState(() => _scheduled = list);
    } catch (_) {} finally {
      if (mounted) setState(() => _schedLoading = false);
    }
  }

  Widget _sectionCard({
    required BuildContext context,
    required String title,
    IconData icon = Icons.layers_outlined,
    Widget? trailing,
    required List<Widget> children,
  }) {
    final theme = Theme.of(context);
    final bodyStyle = theme.textTheme.bodyMedium ?? const TextStyle();
    final titleStyle = theme.textTheme.titleLarge?.copyWith(
      fontWeight: FontWeight.w600,
      letterSpacing: 0.2,
    );
    final spaced = <Widget>[];
    for (var i = 0; i < children.length; i++) {
      spaced.add(children[i]);
      if (i != children.length - 1) {
        spaced.add(const SizedBox(height: 16));
      }
    }
    return Glass(
      padding: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: DefaultTextStyle(
          style: bodyStyle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Icon(icon, color: theme.colorScheme.primary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      title,
                      style: titleStyle,
                    ),
                  ),
                  if (trailing != null) ...[
                    const SizedBox(width: 8),
                    IconTheme(
                      data: theme.iconTheme.copyWith(size: 22),
                      child: trailing,
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 16),
              ...spaced,
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _cancelScheduled(String id) async {
    setState(() => _schedLoading = true);
    try {
      await widget.api.scheduledCancel(id);
      await _loadScheduled();
    } catch (_) {} finally {
      if (mounted) setState(() => _schedLoading = false);
    }
  }

  Future<void> _pickScheduleDateTime() async {
    final now = DateTime.now();
    final initial = now.add(const Duration(minutes: 15));
    final date = await showDatePicker(context: context, initialDate: initial, firstDate: now, lastDate: now.add(const Duration(days: 30)));
    if (!mounted) return;
    if (date == null) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(initial));
    if (!mounted) return;
    if (time == null) return;
    final picked = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    _scheduleRide(when: picked);
  }

  Future<void> _scheduleRide({DateTime? when}) async {
    if (_pickupLat.text.isEmpty || _pickupLon.text.isEmpty || _dropLat.text.isEmpty || _dropLon.text.isEmpty) return;
    setState(() => _loading = true);
    try {
      await widget.api.scheduleRide(
        pickupLat: double.parse(_pickupLat.text),
        pickupLon: double.parse(_pickupLon.text),
        dropLat: double.parse(_dropLat.text),
        dropLon: double.parse(_dropLon.text),
        scheduledFor: when,
      );
      await _loadScheduled();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Scheduled')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _requestAndPrepay() async {
    if (_pickupLat.text.isEmpty || _pickupLon.text.isEmpty || _dropLat.text.isEmpty || _dropLon.text.isEmpty) return;
    setState(() => _loading = true);
    try {
      // Biometric confirmation (optional)
      try {
        final auth = LocalAuthentication();
        if (await auth.canCheckBiometrics) {
          final ok = await auth.authenticate(localizedReason: 'Confirm taxi prepayment');
          if (!ok) { setState(() => _loading = false); return; }
        }
      } catch (_) {}
      final res = await _requestRideInternal(prepay: true, payMode: 'self');
      final rideId = res['id'] as String?;
      setState(() => _lastRideId = rideId);
      if (rideId != null) {
        _startPolling();
        _openWs();
      }
      await _refreshWallet(silent: true);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Requested & paid. Ride: ${_lastRideId ?? '-'}')),
        );
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Request failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _requestCash() async {
    if (_pickupLat.text.isEmpty || _pickupLon.text.isEmpty || _dropLat.text.isEmpty || _dropLon.text.isEmpty) return;
    setState(() => _loading = true);
    try {
      final res = await _requestRideInternal(prepay: false, payMode: 'cash');
      final rideId = res['id'] as String?;
      setState(() => _lastRideId = rideId);
      if (rideId != null) {
        _startPolling();
        _openWs();
      }
      await _refreshWallet(silent: true);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Requested (cash). Ride: ${_lastRideId ?? '-'}')),
        );
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Request failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickOtherFromContacts() async {
    try {
      final granted = await FlutterContacts.requestPermission(readonly: true);
      if (!granted) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Contacts permission denied')));
        }
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Contact pick failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    final markers = <Marker>[
      Marker(
          point: _pickup,
          width: 40,
          height: 40,
          child: const Icon(Icons.location_on, color: Colors.green, size: 32)),
      Marker(
          point: _drop,
          width: 40,
          height: 40,
          child: const Icon(Icons.flag, color: Colors.blue, size: 28)),
      if (_driverPos != null)
        Marker(
            point: _driverPos!,
            width: 40,
            height: 40,
            child:
                const Icon(Icons.local_taxi, color: Colors.orange, size: 30)),
    ];
    if (_tomKey.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'TomTom key missing. Please add TOMTOM_TILES_KEY to .env',
            style: TextStyle(color: Colors.redAccent),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    final mapSection = _sectionCard(
      context: context,
      title: loc.mapSectionTitle,
      icon: Icons.map_outlined,
      children: [
        _buildMapView(context, markers),
      ],
    );

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          mapSection,
          const SizedBox(height: _sectionSpacing),
          _buildWalletSection(context),
          const SizedBox(height: _sectionSpacing),
          _buildTripSection(context),
          const SizedBox(height: _sectionSpacing),
          _buildRideOptionsSection(context),
          const SizedBox(height: _sectionSpacing),
          _buildActionSection(context),
          if (_lastQuote != null) ...[
            const SizedBox(height: _sectionSpacing),
            _buildQuoteSection(context),
          ],
          const SizedBox(height: _sectionSpacing),
          _buildLastRideSection(context),
          const SizedBox(height: _sectionSpacing),
          _buildScheduledSection(context),
        ],
      ),
    );
  }

  Widget _buildMapView(BuildContext context, List<Marker> markers) {
    final loc = AppLocalizations.of(context)!;
    Widget overlayButtons({required void Function() onToggleTrack, required void Function() onOpenFullscreen}) {
      return Positioned(
        right: 8,
        top: 8,
        child: Column(
          children: [
            Card(
              child: IconButton(
                tooltip: _trackDriver ? loc.hideDriverLocation : loc.showDriverLocation,
                icon: Icon(_trackDriver ? Icons.location_on : Icons.location_searching),
                onPressed: onToggleTrack,
              ),
            ),
            const SizedBox(height: 8),
            Card(
              child: IconButton(
                tooltip: loc.fullscreenMap,
                icon: const Icon(Icons.open_in_full),
                onPressed: onOpenFullscreen,
              ),
            ),
          ],
        ),
      );
    }

    if (!_useMapLibre) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: SizedBox(
          height: 220,
          child: Stack(
            children: [
              FlutterMap(
                mapController: _mapCtrl,
                options: MapOptions(
                  initialCenter: _pickup,
                  initialZoom: 14,
                  onTap: (tapPos, latlng) {
                    setState(() {
                      if (_tapMode == 'pickup') {
                        _pickup = latlng;
                        _pickupLat.text = latlng.latitude.toStringAsFixed(6);
                        _pickupLon.text = latlng.longitude.toStringAsFixed(6);
                      } else {
                        _drop = latlng;
                        _dropLat.text = latlng.latitude.toStringAsFixed(6);
                        _dropLon.text = latlng.longitude.toStringAsFixed(6);
                      }
                    });
                    _fillAddressFromCoords(forPickup: _tapMode == 'pickup', lat: latlng.latitude, lon: latlng.longitude);
                    if (!_loading && _pickupLat.text.isNotEmpty && _dropLat.text.isNotEmpty) {
                      _quote();
                    }
                  },
                ),
                children: [
                  TileLayer(
                    urlTemplate: _tomtomTileUrl,
                    subdomains: _tomtomTileUrl.contains('{s}') ? const ['a', 'b', 'c'] : const [],
                  ),
                  MarkerLayer(markers: markers),
                  if (_route.isNotEmpty)
                    PolylineLayer(
                      polylines: [
                        Polyline(points: _route, color: Colors.indigo, strokeWidth: 4),
                      ],
                    ),
                ],
              ),
              overlayButtons(
                onToggleTrack: () {
                  setState(() {
                    _trackDriver = !_trackDriver;
                    if (!_trackDriver) {
                      _driverPos = null;
                      try {
                        _ws?.sink.close();
                      } catch (_) {}
                      _ws = null;
                    } else {
                      if (_lastRideId != null) _openWs();
                    }
                  });
                },
                onOpenFullscreen: () async {
                  final res = await Navigator.push<_MapResult>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => _MapFullscreen(initialPickup: _pickup, initialDropoff: _drop),
                    ),
                  );
                  if (res != null) {
                    setState(() {
                      _pickup = res.pickup ?? _pickup;
                      _drop = res.dropoff ?? _drop;
                      _pickupLat.text = _pickup.latitude.toStringAsFixed(6);
                      _pickupLon.text = _pickup.longitude.toStringAsFixed(6);
                      _dropLat.text = _drop.latitude.toStringAsFixed(6);
                      _dropLon.text = _drop.longitude.toStringAsFixed(6);
                    });
                    _quote();
                  }
                },
              ),
            ],
          ),
        ),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: SizedBox(
        height: 220,
        child: Stack(
          children: [
            mgl.MapLibreMap(
              styleString: (_useTomTomTiles && _tomtomStyleUrl.isNotEmpty) ? _tomtomStyleUrl : _styleUrl,
              initialCameraPosition: mgl.CameraPosition(target: mgl.LatLng(_pickup.latitude, _pickup.longitude), zoom: 14),
              onMapCreated: (ctrl) async {
                _mlCtrl = ctrl;
                await _mlRefreshOverlays();
              },
              onStyleLoadedCallback: () async {
                await _mlRefreshOverlays();
              },
              onMapClick: (pt, latlng) async {
                setState(() {
                  if (_tapMode == 'pickup') {
                    _pickup = LatLng(latlng.latitude, latlng.longitude);
                    _pickupLat.text = latlng.latitude.toStringAsFixed(6);
                    _pickupLon.text = latlng.longitude.toStringAsFixed(6);
                  } else {
                    _drop = LatLng(latlng.latitude, latlng.longitude);
                    _dropLat.text = latlng.latitude.toStringAsFixed(6);
                    _dropLon.text = latlng.longitude.toStringAsFixed(6);
                  }
                });
                await _mlRefreshOverlays();
                _fillAddressFromCoords(forPickup: _tapMode == 'pickup', lat: latlng.latitude, lon: latlng.longitude);
                if (!_loading && _pickupLat.text.isNotEmpty && _dropLat.text.isNotEmpty) {
                  _quote();
                }
              },
            ),
            overlayButtons(
              onToggleTrack: () {
                setState(() {
                  _trackDriver = !_trackDriver;
                  if (!_trackDriver) {
                    _driverPos = null;
                    try {
                      _mlRefreshOverlays();
                    } catch (_) {}
                    try {
                      _ws?.sink.close();
                    } catch (_) {}
                    _ws = null;
                  } else {
                    if (_lastRideId != null) _openWs();
                  }
                });
              },
              onOpenFullscreen: () async {
                final res = await Navigator.push<_MapResult>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => _MapFullscreen(initialPickup: _pickup, initialDropoff: _drop),
                  ),
                );
                if (res != null) {
                  setState(() {
                    _pickup = res.pickup ?? _pickup;
                    _drop = res.dropoff ?? _drop;
                    _pickupLat.text = _pickup.latitude.toStringAsFixed(6);
                    _pickupLon.text = _pickup.longitude.toStringAsFixed(6);
                    _dropLat.text = _drop.latitude.toStringAsFixed(6);
                    _dropLon.text = _drop.longitude.toStringAsFixed(6);
                  });
                  _quote();
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWalletSection(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    final balanceText = _walletBalanceCents != null
        ? formatSyp(_walletBalanceCents)
        : '—';
    return _sectionCard(
      context: context,
      title: loc.walletTitle,
      icon: Icons.account_balance_wallet_outlined,
      trailing: IconButton(
        tooltip: loc.refresh,
        onPressed: _walletLoading ? null : () => _refreshWallet(),
        icon: _walletLoading
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.refresh),
      ),
      children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.account_balance_wallet),
          title: Text(loc.walletBalanceLabel),
          subtitle: Text(_walletCurrency),
          trailing: Text(
            balanceText,
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
        ),
      ],
    );
  }

  Widget _buildTripSection(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return _sectionCard(
      context: context,
      title: loc.tripPlannerSectionTitle,
      icon: Icons.route_outlined,
      children: [
        Text(loc.tapSets),
        Wrap(
          spacing: 12,
          children: [
            ChoiceChip(
              label: Text(loc.pickup),
              selected: _tapMode == 'pickup',
              onSelected: (_) => setState(() => _tapMode = 'pickup'),
            ),
            ChoiceChip(
              label: Text(loc.dropoff),
              selected: _tapMode == 'drop',
              onSelected: (_) => setState(() => _tapMode = 'drop'),
            ),
          ],
        ),
        _buildAddressInputs(context),
        _buildCoordinateInputs(context),
      ],
    );
  }

  Widget _buildAddressInputs(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _addrPickup,
                focusNode: _addrPickupFocus,
                decoration: InputDecoration(
                  labelText: loc.pickup,
                  hintText: loc.typeAnAddress,
                ),
                onChanged: (_) => _scheduleAutocomplete(forPickup: true),
                onSubmitted: (_) => _scheduleAutocomplete(forPickup: true),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              tooltip: loc.searchAddress,
              onPressed: () => _scheduleAutocomplete(forPickup: true),
              icon: const Icon(Icons.search),
            ),
          ],
        ),
        const SizedBox(height: 8),
        _buildSuggestions(forPickup: true),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _addrDropoff,
                focusNode: _addrDropoffFocus,
                decoration: InputDecoration(
                  labelText: loc.dropoff,
                  hintText: loc.typeAnAddress,
                ),
                onChanged: (_) => _scheduleAutocomplete(forPickup: false),
                onSubmitted: (_) => _scheduleAutocomplete(forPickup: false),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              tooltip: loc.searchAddress,
              onPressed: () => _scheduleAutocomplete(forPickup: false),
              icon: const Icon(Icons.search),
            ),
          ],
        ),
        const SizedBox(height: 8),
        _buildSuggestions(forPickup: false),
      ],
    );
  }

  Widget _buildCoordinateInputs(BuildContext context) {
    final theme = Theme.of(context);
    return Theme(
      data: theme.copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Advanced coordinates'),
        children: [
          const SizedBox(height: 8),
          _buildLatLonRow(
            context,
            latController: _pickupLat,
            latLabel: 'Pickup lat',
            lonController: _pickupLon,
            lonLabel: 'Pickup lon',
            onSearch: () => _openSearchDialog(target: 'pickup'),
          ),
          const SizedBox(height: 8),
          _buildLatLonRow(
            context,
            latController: _dropLat,
            latLabel: 'Dropoff lat',
            lonController: _dropLon,
            lonLabel: 'Dropoff lon',
            onSearch: () => _openSearchDialog(target: 'drop'),
          ),
        ],
      ),
    );
  }

  Widget _buildLatLonRow(
    BuildContext context, {
    required TextEditingController latController,
    required String latLabel,
    required TextEditingController lonController,
    required String lonLabel,
    required VoidCallback onSearch,
  }) {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: latController,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(labelText: latLabel),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: TextField(
            controller: lonController,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(labelText: lonLabel),
          ),
        ),
        IconButton(
          tooltip: AppLocalizations.of(context)!.searchAddress,
          onPressed: onSearch,
          icon: const Icon(Icons.search),
        ),
      ],
    );
  }

  Widget _buildRideOptionsSection(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return _sectionCard(
      context: context,
      title: loc.rideOptionsSectionTitle,
      icon: Icons.tune,
      children: [
        _buildRideClassSelector(context),
        _buildBookForOther(context),
        _buildOptionalExtras(context),
        _buildFavoritesBlock(context),
      ],
    );
  }

  Widget _buildRideClassSelector(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: _rideClasses.map((c) {
        final label = c == 'standard'
            ? loc.rideClassStandard
            : c == 'comfort'
                ? loc.rideClassComfort
                : c == 'yellow'
                    ? loc.rideClassYellow
                    : c == 'vip'
                        ? loc.rideClassVIP
                        : c == 'van'
                            ? loc.rideClassVAN
                            : c == 'electro'
                                ? loc.rideClassElectro
                                : c;
        final selected = _rideClass == c;
        return ChoiceChip(
          label: Text(label),
          selected: selected,
          onSelected: (v) {
            if (v) setState(() => _rideClass = c);
          },
        );
      }).toList(),
    );
  }

  Widget _buildBookForOther(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          value: _forOther,
          onChanged: (v) => setState(() => _forOther = v),
          title: const Text('Book for another person'),
        ),
        if (_forOther)
          Column(
            children: [
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _otherName,
                      decoration: const InputDecoration(labelText: 'Name (optional)'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _otherPhone,
                            keyboardType: TextInputType.phone,
                            decoration: const InputDecoration(labelText: 'Phone (+963...)'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton(
                          onPressed: _loading ? null : _pickOtherFromContacts,
                          icon: const Icon(Icons.contacts_outlined),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
      ],
    );
  }

  Widget _buildOptionalExtras(BuildContext context) {
    final theme = Theme.of(context);
    final loc = AppLocalizations.of(context)!;
    return Theme(
      data: theme.copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: Text(loc.optionalStopPromo),
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _stopLat,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(labelText: loc.stopLatOptional),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _stopLon,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(labelText: loc.stopLonOptional),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _promo,
            decoration: InputDecoration(labelText: loc.promoCodeOptional),
          ),
        ],
      ),
    );
  }

  Widget _buildFavoritesBlock(BuildContext context) {
    final theme = Theme.of(context);
    return Theme(
      data: theme.copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: Text(AppLocalizations.of(context)!.favorites),
        children: [
          const SizedBox(height: 12),
          _FavoritesSection(
            api: widget.api,
            onSetPickup: (lat, lon) {
              setState(() {
                _pickup = LatLng(lat, lon);
                _pickupLat.text = lat.toStringAsFixed(6);
                _pickupLon.text = lon.toStringAsFixed(6);
              });
            },
            onSetDrop: (lat, lon) {
              setState(() {
                _drop = LatLng(lat, lon);
                _dropLat.text = lat.toStringAsFixed(6);
                _dropLon.text = lon.toStringAsFixed(6);
              });
            },
            currentPickup: _pickup,
          ),
        ],
      ),
    );
  }

  Widget _buildActionSection(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return _sectionCard(
      context: context,
      title: loc.actions,
      icon: Icons.play_circle_fill_rounded,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            FilledButton.icon(
              onPressed: _loading ? null : _requestAndPrepay,
              icon: const Icon(Icons.credit_card),
              label: Text(loc.bookPayApp),
            ),
            FilledButton.tonalIcon(
              onPressed: _loading ? null : _requestCash,
              icon: const Icon(Icons.payments_outlined),
              label: Text(loc.bookPayCash),
            ),
            OutlinedButton.icon(
              onPressed: _loading ? null : _quote,
              icon: const Icon(Icons.calculate_outlined),
              label: Text(loc.quote),
            ),
          ],
        ),
        if (_loading)
          const Padding(
            padding: EdgeInsets.only(top: 12),
            child: LinearProgressIndicator(),
          ),
      ],
    );
  }

  Widget _buildQuoteSection(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    final quote = _lastQuote!;
    final price = formatSyp(quote['final_quote_cents'] ?? quote['quoted_fare_cents']);
    final surge = quote['surge_multiplier'];
    final dist = (quote['distance_km'] as num?)?.toDouble();
    return _sectionCard(
      context: context,
      title: loc.quoteSummarySectionTitle,
      icon: Icons.receipt_long,
      children: [
        _infoTile(Icons.attach_money, loc.quotePriceLabel, price),
        if (surge != null)
          _infoTile(Icons.trending_up, loc.quoteSurgeLabel, 'x$surge'),
        if (dist != null)
          _infoTile(Icons.social_distance, loc.quoteDistanceLabel, '${dist.toStringAsFixed(2)} km'),
        if (_etaMins != null)
          _infoTile(Icons.timer, loc.quoteEtaLabel, '$_etaMins min'),
      ],
    );
  }

  Widget _infoTile(IconData icon, String label, String value) {
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon),
      title: Text(label),
      trailing: Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
    );
  }

  Widget _buildLastRideSection(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return _sectionCard(
      context: context,
      title: loc.lastRide,
      icon: Icons.history,
      trailing: IconButton(
        tooltip: loc.actions,
        onPressed: _refresh,
        icon: const Icon(Icons.refresh),
      ),
      children: [
        if (_lastRideId == null)
          Text('${loc.status} -')
        else ...[
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('Ride $_lastRideId', maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: Text('${loc.status} ${_lastStatus ?? '-'}'),
            trailing: (_finalFare != null)
                ? Text(formatSyp(_finalFare), style: const TextStyle(fontWeight: FontWeight.w600))
                : (_quotedFare != null)
                    ? Text(formatSyp(_quotedFare), style: const TextStyle(fontWeight: FontWeight.w600))
                    : null,
          ),
          if (_lastStatus != null) StatusChip(status: _lastStatus!),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              if (_riderReward)
                Chip(
                  avatar: const Icon(Icons.card_giftcard, color: Colors.white, size: 18),
                  label: Text(loc.riderRewardApplied),
                  backgroundColor: Colors.green.shade400,
                  labelStyle: const TextStyle(color: Colors.white),
                ),
              if (_driverReward)
                Chip(
                  avatar: const Icon(Icons.emoji_events, color: Colors.white, size: 18),
                  label: Text(loc.driverRewardApplied),
                  backgroundColor: Colors.blue.shade400,
                  labelStyle: const TextStyle(color: Colors.white),
                ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildScheduledSection(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return _sectionCard(
      context: context,
      title: loc.scheduledRidesSectionTitle,
      icon: Icons.schedule_send_outlined,
      trailing: IconButton(
        tooltip: loc.refresh,
        onPressed: _schedLoading ? null : _loadScheduled,
        icon: _schedLoading
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.refresh),
      ),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            OutlinedButton.icon(
              onPressed: _loading ? null : _pickScheduleDateTime,
              icon: const Icon(Icons.event_outlined),
              label: Text(loc.pickScheduleDateTime),
            ),
            FilledButton.icon(
              onPressed: _loading ? null : () => _scheduleRide(when: null),
              icon: const Icon(Icons.schedule_send),
              label: Text(loc.scheduleRideCta),
            ),
          ],
        ),
        if (_schedLoading)
          const Padding(
            padding: EdgeInsets.only(top: 12),
            child: LinearProgressIndicator(),
          ),
        if (_scheduled.isEmpty && !_schedLoading)
          Text(loc.scheduledEmpty),
        if (_scheduled.isNotEmpty)
          Column(
            children: _scheduled.map((e) {
              final id = e['id']?.toString() ?? '';
              final tsRaw = e['scheduled_for']?.toString() ?? '';
              return ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(tsRaw),
                subtitle: Text('${loc.pickup}: ${(e['pickup_lat'] ?? '').toString()}, ${(e['pickup_lon'] ?? '').toString()}'),
                trailing: TextButton.icon(
                  onPressed: _schedLoading ? null : () => _cancelScheduled(id),
                  icon: const Icon(Icons.cancel),
                  label: Text(loc.cancel),
                ),
              );
            }).toList(),
          ),
      ],
    );
  }

  Future<void> _openSearchDialog({required String target}) async {
    _searchCtrl.text = '';
    _searchItems = [];
    await showDialog(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setStateDlg) {
        Future<void> runSearch(String q) async {
          if (q.trim().isEmpty) {
            setStateDlg(() => _searchItems = []);
            return;
          }
          try {
            final items = await widget.api.mapsAutocomplete(q, limit: 8);
            setStateDlg(() => _searchItems = items);
          } catch (_) {}
        }
        return AlertDialog(
          title: Text(AppLocalizations.of(context)!.searchAddress),
          content: SizedBox(
            width: 400,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(hintText: AppLocalizations.of(context)!.typeAnAddress),
                  onChanged: (v) => runSearch(v),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  height: 240,
                  child: ListView.builder(
                    itemCount: _searchItems.length,
                    itemBuilder: (c, i) {
                      final it = _searchItems[i] as Map<String, dynamic>;
                      final name = it['display_name'] as String? ?? '';
                      final lat = double.tryParse((it['lat'] ?? '').toString());
                      final lon = double.tryParse((it['lon'] ?? '').toString());
                      return ListTile(
                        title: Text(name, maxLines: 2, overflow: TextOverflow.ellipsis),
                        subtitle: Text(lat != null && lon != null ? '${lat.toStringAsFixed(6)}, ${lon.toStringAsFixed(6)}' : ''),
                        onTap: () {
                          if (lat != null && lon != null) {
                            Navigator.pop(ctx);
                            if (target == 'pickup') {
                              setState(() {
                                _pickup = LatLng(lat, lon);
                                _pickupLat.text = lat.toStringAsFixed(6);
                                _pickupLon.text = lon.toStringAsFixed(6);
                                _mapCtrl.move(_pickup, 14);
                              });
                            } else {
                              setState(() {
                                _drop = LatLng(lat, lon);
                                _dropLat.text = lat.toStringAsFixed(6);
                                _dropLon.text = lon.toStringAsFixed(6);
                                _mapCtrl.move(_drop, 14);
                              });
                            }
                          }
                        },
                      );
                    },
                  ),
                )
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text(AppLocalizations.of(context)!.close)),
          ],
        );
      }),
    );
  }

  Future<void> _showPaymentCta() async {
    final amount = _finalFare ?? _quotedFare;
    await showModalBottomSheet(
      context: context,
      isScrollControlled: false,
      showDragHandle: true,
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(children: [
                Icon(Icons.check_circle_outline, color: Colors.green, size: 28),
                SizedBox(width: 8),
                Text('Ride completed',
                    style:
                        TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ]),
              const SizedBox(height: 8),
              if (amount != null)
                Text(AppLocalizations.of(context)!
                    .priceOfRide(formatSyp(amount))),
              if (_lastDistanceKm != null)
                Text('Distance: ${_lastDistanceKm!.toStringAsFixed(2)} km'),
              if (_lastRideId != null)
                Text('Ride ID: $_lastRideId'),
              const SizedBox(height: 8),
              Text(AppLocalizations.of(context)!.cashPlease),
              if (_riderReward)
                Text(AppLocalizations.of(context)!.riderRewardApplied,
                    style: const TextStyle(color: Colors.green)),
              if (_driverReward)
                Text(AppLocalizations.of(context)!.driverRewardApplied,
                    style: const TextStyle(color: Colors.green)),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('Close')),
              ),
            ],
          ),
        );
      },
    );
    if (mounted) {
      await _refreshWallet(silent: true);
    }
  }

}

class _MapResult {
  final LatLng? pickup;
  final LatLng? dropoff;
  const _MapResult(this.pickup, this.dropoff);
}

class _MapFullscreen extends StatefulWidget {
  final LatLng? initialPickup;
  final LatLng? initialDropoff;
  const _MapFullscreen({this.initialPickup, this.initialDropoff});
  @override
  State<_MapFullscreen> createState() => _MapFullscreenState();
}

class _MapFullscreenState extends State<_MapFullscreen> {
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
    final loc = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(title: Text(loc.mapSectionTitle), actions: [
        TextButton(onPressed: ()=>Navigator.pop(context, _MapResult(_pickup, _dropoff)), child: Text(loc.save))
      ]),
      body: Stack(children:[
        FlutterMap(
          options: MapOptions(
            initialCenter: _center,
            initialZoom: 13,
            onTap: (p, ll){ setState((){ if(_selectingPickup){ _pickup=ll; } else { _dropoff=ll; } }); },
          ),
          children: [
            TileLayer(urlTemplate: 'https://api.tomtom.com/map/1/tile/basic/main/{z}/{x}/{y}.png?key=${dotenv.env['TOMTOM_TILES_KEY'] ?? ''}', subdomains: const ['a','b','c']),
            MarkerLayer(markers:[
              if(_pickup!=null) Marker(point: _pickup!, width: 36, height:36, child: const Icon(Icons.place, color: Colors.green, size: 30)),
              if(_dropoff!=null) Marker(point: _dropoff!, width: 36, height:36, child: const Icon(Icons.flag, color: Colors.red, size: 30)),
            ])
          ],
        ),
        Positioned(
          left: 8, top: 8,
          child: Card(child: Padding(padding: const EdgeInsets.symmetric(horizontal: 8), child: Row(mainAxisSize: MainAxisSize.min, children:[
            Text(loc.pickup),
            Switch(value: _selectingPickup, onChanged: (v)=>setState(()=>_selectingPickup=v)),
            Text(loc.dropoff),
          ]))),
        )
      ]),
    );
  }
}

class _FavoritesSection extends StatefulWidget {
  final ApiClient api;
  final void Function(double, double) onSetPickup;
  final void Function(double, double) onSetDrop;
  final LatLng currentPickup;
  const _FavoritesSection(
      {required this.api,
      required this.onSetPickup,
      required this.onSetDrop,
      required this.currentPickup});
  @override
  State<_FavoritesSection> createState() => _FavoritesSectionState();
}

class _FavoritesSectionState extends State<_FavoritesSection> {
  List<dynamic> _favs = [];
  bool _loading = false;

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      _favs = await widget.api.favoritesList();
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _saveCurrentPickup() async {
    setState(() => _loading = true);
    try {
      await widget.api.favoritesCreate(
          label: 'Fav ${DateTime.now().millisecondsSinceEpoch % 1000}',
          lat: widget.currentPickup.latitude,
          lon: widget.currentPickup.longitude);
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _delete(String id) async {
    try {
      await widget.api.favoritesDelete(id);
      await _load();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text(AppLocalizations.of(context)!.favorites,
            style: const TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(width: 8),
        IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        const Spacer(),
        OutlinedButton.icon(
            onPressed: _loading ? null : _saveCurrentPickup,
            icon: const Icon(Icons.star_border),
            label: Text(AppLocalizations.of(context)!.saveCurrentPickup))
      ]),
      if (_loading) const LinearProgressIndicator(),
      Wrap(
          spacing: 8,
          runSpacing: 4,
          children: _favs.map<Widget>((f) {
            final id = f['id'] as String;
            final lbl = f['label'] as String;
            final lat = (f['lat'] as num).toDouble();
            final lon = (f['lon'] as num).toDouble();
            return GestureDetector(
              onLongPress: () async {
                  final ctrl = TextEditingController(text: lbl);
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
                  if (ok == true) {
                    final newLbl = ctrl.text.trim();
                    if (newLbl.isNotEmpty) {
                      try {
                        await widget.api.favoritesUpdate(id, newLbl);
                        await _load();
                      } catch (_) {}
                    }
                  }
                },
              child: InputChip(
                label: Text(lbl),
                avatar: const Icon(Icons.place),
                onPressed: () => widget.onSetPickup(lat, lon),
                onDeleted: () => _delete(id),
              ),
            );
          }).toList()),
      Wrap(
          spacing: 8,
          children: _favs.map<Widget>((f) {
            final lat = (f['lat'] as num).toDouble();
            final lon = (f['lon'] as num).toDouble();
            return Row(mainAxisSize: MainAxisSize.min, children: [
              TextButton(
                  onPressed: () => widget.onSetPickup(lat, lon),
                  child: Text(AppLocalizations.of(context)!.setPickup)),
              TextButton(
                  onPressed: () => widget.onSetDrop(lat, lon),
                  child: Text(AppLocalizations.of(context)!.setDrop))
            ]);
          }).toList()),
    ]);
  }
}
