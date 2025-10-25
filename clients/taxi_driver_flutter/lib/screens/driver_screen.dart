import 'dart:async';
import 'package:flutter/material.dart';
import '../api.dart';
import '../ui/components.dart';
import 'package:url_launcher/url_launcher.dart';
import '../l10n/app_localizations.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:maplibre_gl/maplibre_gl.dart' as mgl;
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:shared_ui/glass.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:latlong2/latlong.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:io' show Platform;
import 'package:geolocator/geolocator.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../ui/notify.dart';
import 'qr_scan_screen.dart';

class DriverScreen extends StatefulWidget {
  final ApiClient api;
  const DriverScreen({super.key, required this.api});
  @override
  State<DriverScreen> createState() => _DriverScreenState();
}

class _DriverScreenState extends State<DriverScreen> {
  static const String _tileUrl = String.fromEnvironment('TILE_URL', defaultValue: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png');
  String get _tomKey => (dotenv.env['TOMTOM_TILES_KEY'] ?? dotenv.env['TOMTOM_API_KEY_TAXI'] ?? dotenv.env['TOMTOM_MAP_KEY'] ?? dotenv.env['TOMTOM_API_KEY'] ?? '').trim();
  String get _tomtomTileUrl => 'https://api.tomtom.com/map/1/tile/basic/main/{z}/{x}/{y}.png?key=${_tomKey}';
  static const bool _useMapLibre = bool.fromEnvironment('USE_MAPLIBRE', defaultValue: false);
  static const String _styleUrl = String.fromEnvironment('STYLE_URL', defaultValue: 'https://demotiles.maplibre.org/style.json');
  static const String _tomtomStyleUrl = String.fromEnvironment('TOMTOM_STYLE_URL', defaultValue: '');
  final _lat = TextEditingController(text: '33.5138');
  final _lon = TextEditingController(text: '36.2765');
  bool _loading = false;
  String _status = 'offline';
  String? _lastRideId;
  String? _lastStatus;
  String? _driverInfo;
  int? _walletBalanceCents;
  List<Map<String, dynamic>> _walletEntries = [];
  final _topupAmount = TextEditingController(text: '500');
  final _withdrawAmount = TextEditingController(text: '500');
  bool _walletLoading = false;
  final _mapCtrl = MapController();
  mgl.MaplibreMapController? _mlCtrl;
  mgl.Symbol? _mlDriver;
  LatLng _pos = LatLng(33.5138, 36.2765);
  Timer? _poll;
  WebSocketChannel? _ws;
  WebSocketChannel? _driverWs;
  bool _autoUpdate = false;
  StreamSubscription<Position>? _posSub;
  DateTime? _lastSendAt;
  DateTime? _lastFixAt;
  bool _useTomTomTiles = true;
  bool _driverWsUp = false;
  bool _rideWsUp = false;
  int _driverWsRetries = 0;
  int _rideWsRetries = 0;
  Timer? _driverWsRetryTimer;
  Timer? _rideWsRetryTimer;

  Future<void> _apply() async {
    setState(() => _loading = true);
    try {
      await widget.api.driverApply(make: 'Toyota', plate: 'ABC-123');
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(AppLocalizations.of(context)!.driverEnabled)));
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _setStatus(String s) async {
    setState(() => _loading = true);
    try {
      await widget.api.driverStatus(s);
      setState(() => _status = s);
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _setLocation() async {
    final lat = double.tryParse(_lat.text.trim());
    final lon = double.tryParse(_lon.text.trim());
    if (lat == null || lon == null) return;
    setState(() => _loading = true);
    try {
      await widget.api.driverLocation(lat: lat, lon: lon);
      setState(() => _pos = LatLng(lat, lon));
      await _mlRefreshOverlays();
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _mlRefreshOverlays() async {
    if (_mlCtrl == null) return;
    try {
      if (_mlDriver != null) {
        await _mlCtrl!.removeSymbol(_mlDriver!);
        _mlDriver = null;
      }
      _mlDriver = await _mlCtrl!.addSymbol(mgl.SymbolOptions(
        geometry: mgl.LatLng(_pos.latitude, _pos.longitude),
        iconImage: 'marker-15',
      ));
    } catch (_) {}
  }

  Future<bool> _ensureLocationPermission() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return false;
    }
    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return false;
    }
    return true;
  }

  Future<void> _toggleAutoUpdate(bool on) async {
    if (on) {
      final ok = await _ensureLocationPermission();
      if (!ok) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Location permission required.')));
        setState(() => _autoUpdate = false);
        return;
      }
      // Android: start foreground service to keep updates alive in background
      if (Platform.isAndroid) {
        await _ensureForegroundService();
        await FlutterForegroundTask.startService(
          notificationTitle: 'Taxi Driver',
          notificationText: 'Sharing location for rides',
        );
      }
      // Start position stream
      final settings = const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 25, // meters
      );
      _posSub?.cancel();
      _posSub = Geolocator.getPositionStream(locationSettings: settings)
          .listen((pos) async {
        setState(() {
          _pos = LatLng(pos.latitude, pos.longitude);
          _lat.text = pos.latitude.toStringAsFixed(6);
          _lon.text = pos.longitude.toStringAsFixed(6);
          _lastFixAt = DateTime.now();
        });
        final now = DateTime.now();
        if (_lastSendAt == null || now.difference(_lastSendAt!).inSeconds >= 5) {
          _lastSendAt = now;
          try {
            await widget.api
                .driverLocation(lat: pos.latitude, lon: pos.longitude);
          } catch (_) {}
        }
      }, onError: (_) {});
      setState(() => _autoUpdate = true);
    } else {
      await _posSub?.cancel();
      _posSub = null;
      if (Platform.isAndroid) {
        await FlutterForegroundTask.stopService();
      }
      setState(() => _autoUpdate = false);
    }
  }

  Future<void> _ensureForegroundService() async {
    // Android only; configure channel and options once
    if (!Platform.isAndroid) return;
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'taxi_location',
        channelName: 'Location Service',
        channelDescription: 'Shares your location while driving',
        channelImportance: NotificationChannelImportance.LOW,
        priority: NotificationPriority.LOW,
        enableVibration: false,
        playSound: false,
      ),
      iosNotificationOptions: IOSNotificationOptions(showNotification: false),
      foregroundTaskOptions: ForegroundTaskOptions(
        interval: 5000,
        autoRunOnBoot: false,
        allowWakeLock: false,
        allowWifiLock: false,
      ),
    );
  }

  Future<void> _openTopup() async {
    final uri = Uri.parse('payments://');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context)!.paymentsNotAvailable)));
    }
  }

  Future<void> _refresh() async {
    try {
      final rides = await widget.api.myRides();
      rides.sort((a, b) => (b['created_at'] ?? '').compareTo(a['created_at'] ?? ''));
      if (rides.isNotEmpty) {
        final r = rides.first as Map<String, dynamic>;
        _lastRideId = r['id'] as String?;
        _lastStatus = r['status'] as String?;
        if (_lastRideId != null && !_rideWsUp) {
          await _connectWs(rideId: _lastRideId!);
        }
      }
      setState(() {});
    } catch (_) {}
  }

  Future<void> _accept() async {
    if (_lastRideId == null) return;
    setState(() => _loading = true);
    try {
      await widget.api.rideAccept(_lastRideId!);
      setState(() => _lastStatus = 'accepted');
    } catch (e) {
      final s = e.toString();
      if (s.contains('insufficient_taxi_wallet_balance')) {
        await _handleWalletShortfall(s);
      } else {
        if (mounted)
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(friendlyError(e))));
      }
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _start() async {
    if (_lastRideId == null) return;
    setState(() => _loading = true);
    try {
      await widget.api.rideStart(_lastRideId!);
      setState(() => _lastStatus = 'enroute');
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _complete() async {
    if (_lastRideId == null) return;
    setState(() => _loading = true);
    try {
      final res = await widget.api.rideComplete(_lastRideId!);
      setState(() => _lastStatus = 'completed');
      final cents = res['final_fare_cents'];
      if (mounted) {
        final loc = AppLocalizations.of(context)!;
        await Notify.show(loc.rideCompleted, loc.priceOfRide(cents: cents ?? 0));
      }
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _connectWs({required String rideId}) async {
    try {
      await _ws?.sink.close();
    } catch (_) {}
    try {
      final base = Uri.parse(widget.api.baseUrl);
      final token = await widget.api.tokenStore.getToken();
      if (token == null || token.isEmpty) return;
      final scheme = base.scheme == 'https' ? 'wss' : 'ws';
      final host = base.host;
      final port = base.hasPort ? ':${base.port}' : '';
      final wsUrl = Uri.parse('$scheme://$host$port/ws/rides/$rideId?token=$token');
      _ws = WebSocketChannel.connect(wsUrl);
      _ws!.stream.listen((msg) {
        try {
          final ev = jsonDecode(msg) as Map<String, dynamic>;
          if (ev['type'] == 'ride_status') {
            setState(() => _lastStatus = ev['status'] as String?);
          }
        } catch (_) {}
      }, onError: (_) {
        _rideWsUp = false;
        _scheduleRideWsReconnect();
        _ensurePolling();
      }, onDone: () {
        _rideWsUp = false;
        _scheduleRideWsReconnect();
        _ensurePolling();
      });
      _rideWsUp = true;
      _rideWsRetries = 0;
      _rideWsRetryTimer?.cancel();
      _rideWsRetryTimer = null;
      _stopPolling();
    } catch (_) {}
  }

  Future<void> _connectDriverWs() async {
    try {
      await _driverWs?.sink.close();
    } catch (_) {}
    try {
      final base = Uri.parse(widget.api.baseUrl);
      final token = await widget.api.tokenStore.getToken();
      if (token == null || token.isEmpty) return;
      final scheme = base.scheme == 'https' ? 'wss' : 'ws';
      final host = base.host;
      final port = base.hasPort ? ':${base.port}' : '';
      final wsUrl = Uri.parse('$scheme://$host$port/ws/driver?token=$token');
      _driverWs = WebSocketChannel.connect(wsUrl);
      _driverWs!.stream.listen((msg) async {
        try {
          final ev = jsonDecode(msg) as Map<String, dynamic>;
          final type = ev['type'];
          if (type == 'driver_assignment') {
            final rid = ev['ride_id'] as String?;
            if (rid != null && rid.isNotEmpty) {
              setState(() {
                _lastRideId = rid;
                _lastStatus = 'assigned';
              });
              try {
                final sp = await SharedPreferences.getInstance();
                await sp.setString('pending_ride_id', rid);
              } catch (_) {}
              try {
                await Notify.showAssignment(rideId: rid, title: 'New ride assigned', body: 'Tap to accept');
              } catch (_) {}
              await _connectWs(rideId: rid);
            }
          }
        } catch (_) {}
      }, onError: (_) {
        _driverWsUp = false;
        _scheduleDriverWsReconnect();
        _ensurePolling();
      }, onDone: () {
        _driverWsUp = false;
        _scheduleDriverWsReconnect();
        _ensurePolling();
      });
      _driverWsUp = true;
      _driverWsRetries = 0;
      _driverWsRetryTimer?.cancel();
      _driverWsRetryTimer = null;
      _stopPolling();
    } catch (_) {}
  }

  void _stopPolling() {
    try {
      _poll?.cancel();
      _poll = null;
    } catch (_) {}
  }

  void _ensurePolling() {
    if (_poll == null && !_driverWsUp && !_rideWsUp) {
      _poll = Timer.periodic(const Duration(seconds: 3), (_) => _refresh());
    }
  }

  Duration _wsBackoff(int attempt) {
    final capped = attempt.clamp(0, 6);
    final baseMs = 500 * (1 << capped); // 0.5s, 1s, 2s, ... up to ~32s
    final jitter = (100 * (1 + (math.Random().nextDouble()))).toInt();
    return Duration(milliseconds: baseMs + jitter);
  }

  void _scheduleDriverWsReconnect() {
    if (_driverWsRetryTimer != null) return;
    final delay = _wsBackoff(_driverWsRetries);
    _driverWsRetryTimer = Timer(delay, () async {
      _driverWsRetryTimer = null;
      _driverWsRetries++;
      if (!mounted) return;
      await _connectDriverWs();
    });
  }

  void _scheduleRideWsReconnect() {
    if (_rideWsRetryTimer != null) return;
    final rid = _lastRideId;
    if (rid == null || rid.isEmpty) {
      // No current ride to reconnect to
      return;
    }
    final delay = _wsBackoff(_rideWsRetries);
    _rideWsRetryTimer = Timer(delay, () async {
      _rideWsRetryTimer = null;
      _rideWsRetries++;
      if (!mounted) return;
      await _connectWs(rideId: rid);
    });
  }

  Future<void> _checkPendingRide() async {
    try {
      final sp = await SharedPreferences.getInstance();
      final rid = sp.getString('pending_ride_id');
      if (rid != null && rid.isNotEmpty) {
        await sp.remove('pending_ride_id');
        setState(() {
          _lastRideId = rid;
          _lastStatus = _lastStatus ?? 'assigned';
        });
        await _connectWs(rideId: rid);
      }
    } catch (_) {}
  }

  Future<void> _loadWallet() async {
    setState(() => _walletLoading = true);
    try {
      final js = await widget.api.taxiWalletGet();
      setState(() {
        _walletBalanceCents = (js['balance_cents'] as int? ?? 0);
        final list = (js['entries'] as List<dynamic>? ?? []);
        _walletEntries = list.cast<Map<String, dynamic>>();
      });
    } catch (_) {}
    setState(() => _walletLoading = false);
  }

  Future<void> _handleWalletShortfall(String details) async {
    final m = RegExp(r'shortfall_cents\":\s*(\d+)').firstMatch(details);
    final needed = m != null ? int.tryParse(m.group(1)!) ?? 0 : 0;
    final res = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(AppLocalizations.of(context)!.topup),
        content: Text(needed > 0
            ? 'Taxi-Wallet unzureichend. Fehlbetrag: ${needed}c'
            : 'Taxi-Wallet unzureichend.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(AppLocalizations.of(context)!.cancel)),
          TextButton(
              onPressed: () => Navigator.pop(context, 'payments'),
              child: const Text('Open Payments')),
          FilledButton(
              onPressed: () => Navigator.pop(context, 'inapp'),
              child: const Text('Top up now (Dev)')),
        ],
      ),
    );
    if (res == 'payments') {
      await _openTopup();
      return;
    }
    if (res == 'inapp') {
      await _walletTopupDev(needed > 0 ? needed : null);
      if (_lastRideId != null) {
        try {
          await widget.api.rideAccept(_lastRideId!);
        } catch (e) {
          if (!mounted) return;
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(friendlyError(e))));
        }
      }
    }
  }

  Future<void> _walletTopupDev([int? override]) async {
    final amountText = override != null ? override.toString() : _topupAmount.text;
    final cents = int.tryParse(amountText.trim());
    if (cents == null || cents <= 0) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Invalid amount for top-up')));
      }
      return;
    }
    try {
      await widget.api.taxiWalletTopup(cents);
      await _loadWallet();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Top-up success: ${cents}c')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
      }
    }
  }

  Future<void> _walletTopupScan() async {
    try {
      final code = await Navigator.push<String?>(context, MaterialPageRoute(builder: (_) => QrScanScreen(title: 'Scan Topup QR', hint: 'QR should contain amount in cents, e.g., amount_cents=5000 or {\"amount_cents\":5000}')));
      if (!mounted || code == null || code.trim().isEmpty) return;
      final amt = _parseAmountCents(code);
      if (amt == null || amt <= 0) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No valid amount in QR')));
        return;
      }
      final ok = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Confirm topup'),
          content: Text('Top up ${amt}c to Taxi Wallet?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Top up')),
          ],
        ),
      );
      if (ok != true) return;
      setState(() => _walletLoading = true);
      await widget.api.taxiWalletTopup(amt);
      await _loadWallet();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Topup successful')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Topup failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _walletLoading = false);
    }
  }

  int? _parseAmountCents(String code) {
    try {
      final js = jsonDecode(code);
      if (js is Map && js['amount_cents'] is num) return (js['amount_cents'] as num).toInt();
    } catch (_) {}
    final lower = code.toLowerCase();
    final rx = RegExp(r'(amount_cents|amount)\s*[=:]\s*([0-9]+)');
    final m = rx.firstMatch(lower);
    if (m != null) {
      final v = int.tryParse(m.group(2)!);
      if (v != null) return v;
    }
    final any = RegExp(r'(\d{2,})').firstMatch(lower);
    if (any != null) return int.tryParse(any.group(1)!);
    return null;
  }

  Future<void> _walletWithdrawDev() async {
    final cents = int.tryParse(_withdrawAmount.text.trim());
    if (cents == null || cents <= 0) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Invalid amount for withdraw')));
      }
      return;
    }
    try {
      await widget.api.taxiWalletWithdraw(cents);
      await _loadWallet();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Withdraw success: ${cents}c')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
      }
    }
  }

  Future<void> _loadProfile() async {
    try {
      final p = await widget.api.driverProfile();
      final r = await widget.api.driverRatings();
      final e = await widget.api.driverEarnings(days: 7);
      setState(() => _driverInfo = 'Status: ' +
          (p['status'] ?? '-') +
          ', Rating: ' +
          ((r['avg_rating']?.toStringAsFixed(2)) ?? '-') +
          ' (' +
          (r['ratings_count']?.toString() ?? '0') +
          ')  7d: ' +
          (e['total_earnings_cents']?.toString() ?? '0') +
          'c');
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Driver info loaded')));
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  void initState() {
    super.initState();
    _poll = Timer.periodic(const Duration(seconds: 3), (_) => _refresh());
    Future.microtask(() async {
      await _loadWallet();
      await _loadProfile();
      await _checkPendingRide();
      await _connectDriverWs();
    });
  }

  @override
  void dispose() {
    _poll?.cancel();
    _ws?.sink.close();
    _driverWs?.sink.close();
    _posSub?.cancel();
    _topupAmount.dispose();
    _withdrawAmount.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final markers = <Marker>[
      Marker(
          point: _pos,
          width: 40,
          height: 40,
          child: const Icon(Icons.local_taxi, color: Colors.orange, size: 32)),
    ];
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
          height: 200,
          child: Glass(
            padding: EdgeInsets.zero,
            child: !_useMapLibre
                ? (_tomKey.isEmpty
                    ? const Center(child: Text('TomTom key missing — add TOMTOM_TILES_KEY to .env', style: TextStyle(color: Colors.redAccent)))
                    : FlutterMap(
                    mapController: _mapCtrl,
                    options: MapOptions(
                      initialCenter: _pos,
                      initialZoom: 14,
                      onTap: (tapPos, latlng) {
                        setState(() {
                          _pos = latlng;
                          _lat.text = latlng.latitude.toStringAsFixed(6);
                          _lon.text = latlng.longitude.toStringAsFixed(6);
                        });
                      },
                    ),
                    children: [
                      TileLayer(urlTemplate: _tomtomTileUrl,
                        subdomains: _tomtomTileUrl.contains('{s}') ? const ['a', 'b', 'c'] : const []),
                      MarkerLayer(markers: markers),
                    ],
                  ))
                : mgl.MaplibreMap(
                    styleString: (_useTomTomTiles && _tomtomStyleUrl.isNotEmpty) ? _tomtomStyleUrl : _styleUrl,
                    initialCameraPosition: mgl.CameraPosition(target: mgl.LatLng(_pos.latitude, _pos.longitude), zoom: 14),
                    onMapCreated: (ctrl) async {
                      _mlCtrl = ctrl;
                      await _mlRefreshOverlays();
                    },
                    onStyleLoadedCallback: () async {
                      await _mlRefreshOverlays();
                    },
                    onMapClick: (pt, latlng) async {
                      setState(() {
                        _pos = LatLng(latlng.latitude, latlng.longitude);
                        _lat.text = latlng.latitude.toStringAsFixed(6);
                        _lon.text = latlng.longitude.toStringAsFixed(6);
                      });
                      await _mlRefreshOverlays();
                    },
                  ),
          ),
        ),
        Row(children: [
          FilledButton(
              onPressed: _loading ? null : _apply,
              child: Text(AppLocalizations.of(context)!.applyDev)),
          const SizedBox(width: 8),
          if (_lastRideId != null && (_lastStatus == 'assigned' || _lastStatus == 'accepted' || _lastStatus == 'enroute'))
            FilledButton.icon(
              onPressed: _loading ? null : () async {
                final rid = _lastRideId;
                if (rid == null) return;
                final bridge = (dotenv.env['CALL_BRIDGE_NUMBER'] ?? '').trim();
                try {
                  if (bridge.isNotEmpty) {
                    final uri = Uri.parse('tel:$bridge');
                    if (await canLaunchUrl(uri)) {
                      await launchUrl(uri);
                    } else {
                      if (!context.mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cannot launch dialer')));
                    }
                  } else {
                    await widget.api.callRider(rid);
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Call request sent')));
                  }
                } catch (e) {
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Call failed: $e')));
                }
              },
              icon: const Icon(Icons.call),
              label: const Text('Call rider'),
            ),
          const SizedBox(width: 8),
          DropdownButton<String>(
            value: _status,
            items: const [
              DropdownMenuItem(value: 'offline', child: Text('offline')),
              DropdownMenuItem(value: 'available', child: Text('available')),
              DropdownMenuItem(value: 'busy', child: Text('busy'))
            ],
            onChanged: (v) => v != null ? _setStatus(v) : null,
          ),
        ]),
        const SizedBox(height: 12),
        // TomTom ist Pflicht – kein Fallback/Toggle
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          value: _autoUpdate,
          title: const Text('Auto-Update Location (background-capable)'),
          subtitle: const Text('Sends location periodically using device GPS'),
          onChanged: (v) => _toggleAutoUpdate(v),
        ),
        _GpsStatus(
          auto: _autoUpdate,
          lastFixAt: _lastFixAt,
          lastSendAt: _lastSendAt,
          position: _pos,
        ),
        Glass(
          margin: const EdgeInsets.symmetric(vertical: 8),
          padding: EdgeInsets.zero,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Icon(Icons.account_balance_wallet_outlined, size: 18),
                  const SizedBox(width: 8),
                  const Text('Taxi Wallet',
                      style:
                          TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
                  const Spacer(),
                  if (_walletLoading)
                    const SizedBox(
                        height: 16,
                        width: 16,
                        child: CircularProgressIndicator(strokeWidth: 2))
                  else
                    IconButton(
                        tooltip: 'Refresh wallet',
                        onPressed: _loadWallet,
                        icon: const Icon(Icons.refresh)),
                ]),
                Text(
                  _walletBalanceCents != null
                      ? 'Balance: ${_walletBalanceCents}c'
                      : 'Balance: -',
                ),
                const SizedBox(height: 6),
                Row(children: [
                  Expanded(
                    child: TextField(
                        controller: _topupAmount,
                        keyboardType: TextInputType.number,
                        decoration:
                            const InputDecoration(labelText: 'Topup amount (cents)')),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(onPressed: _walletTopupDev, child: const Text('Top up')),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(onPressed: _walletTopupScan, icon: const Icon(Icons.qr_code_scanner), label: const Text('Scan QR'))
                ]),
                const SizedBox(height: 6),
                Row(children: [
                  Expanded(
                    child: TextField(
                        controller: _withdrawAmount,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                            labelText: 'Withdraw amount (cents)')),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                      onPressed: _walletWithdrawDev,
                      child: const Text('Withdraw (Dev)'))
                ]),
                const SizedBox(height: 8),
                const Text('Last 20 entries:'),
                const SizedBox(height: 6),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 220),
                  child: ListView.builder(
                          shrinkWrap: true,
                          itemCount: _walletEntries.length,
                          itemBuilder: (_, idx) {
                            final e = _walletEntries[idx];
                            final type = e['type'] ?? '';
                            final amount = e['amount_cents_signed'] ?? 0;
                            final created = e['created_at'] ?? '';
                            final rideId = e['ride_id'];
                            final icon = amount >= 0 ? Icons.add : Icons.remove;
                            final color = amount >= 0
                                ? Colors.lightGreen
                                : Colors.redAccent;
                            return ListTile(
                              dense: true,
                              leading: Icon(icon, color: color, size: 18),
                              title: Text('$type  ${amount}c'),
                              subtitle: Text(rideId != null
                                  ? '$created • ride $rideId'
                                  : created),
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 6),
        Row(children: [
          Expanded(
              child: TextField(
                  controller: _lat,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Lat'))),
          const SizedBox(width: 8),
          Expanded(
              child: TextField(
                  controller: _lon,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Lon'))),
          const SizedBox(width: 8),
          OutlinedButton(
              onPressed: _loading ? null : _setLocation,
              child: Text(AppLocalizations.of(context)!.setLoc)),
        ]),
        const SizedBox(height: 16),
        Row(children: [
          const Text('Last ride:'),
          const SizedBox(width: 8),
          Text(_lastRideId ?? '-'),
          IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh))
        ]),
        if (_driverInfo != null) Text(_driverInfo!),
        const SizedBox(height: 8),
        Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
                onPressed: _loadProfile,
                icon: const Icon(Icons.person),
                label: Text(AppLocalizations.of(context)!.profileEarnings))),
        if (_lastStatus != null)
          StatusChip(status: _lastStatus!)
        else
          const Text('Status: -'),
        const SizedBox(height: 8),
        Wrap(spacing: 8, children: [
          FilledButton(onPressed: _accept, child: Text(AppLocalizations.of(context)!.accept)),
          FilledButton(onPressed: _start, child: Text(AppLocalizations.of(context)!.start)),
          FilledButton(onPressed: _complete, child: Text(AppLocalizations.of(context)!.complete)),
        ])
      ]),
    );
  }
}

class _GpsStatus extends StatelessWidget {
  final bool auto;
  final DateTime? lastFixAt;
  final DateTime? lastSendAt;
  final LatLng position;
  const _GpsStatus({
    required this.auto,
    required this.lastFixAt,
    required this.lastSendAt,
    required this.position,
  });

  String _fmt(DateTime? dt) {
    if (dt == null) return '-';
    final now = DateTime.now();
    final ago = now.difference(dt).inSeconds;
    final hhmm = DateFormat('HH:mm:ss').format(dt);
    return '$hhmm (${ago}s ago)';
  }

  Color _statusColor(BuildContext ctx) {
    if (!auto) return Colors.grey;
    final now = DateTime.now();
    final age = lastFixAt != null ? now.difference(lastFixAt!).inSeconds : 9999;
    if (age <= 10) return Colors.green;
    if (age <= 60) return Colors.orange;
    return Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    final c = _statusColor(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: c.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: c.withOpacity(0.4)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(auto ? Icons.gps_fixed : Icons.gps_off, color: c, size: 18),
          const SizedBox(width: 6),
          Text(
            auto ? 'GPS Live' : 'GPS Idle',
            style: TextStyle(color: c, fontWeight: FontWeight.w600),
          ),
        ]),
        const SizedBox(height: 4),
        Text('Last fix: ' + _fmt(lastFixAt),
            style: const TextStyle(fontSize: 12)),
        Text('Last send: ' + _fmt(lastSendAt),
            style: const TextStyle(fontSize: 12)),
        Text(
            'Pos: ${position.latitude.toStringAsFixed(6)}, ${position.longitude.toStringAsFixed(6)}',
            style: const TextStyle(fontSize: 12)),
      ]),
    );
  }
}
