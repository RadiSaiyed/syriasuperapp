import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../map_view.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services.dart';
import 'package:shared_ui/glass.dart';
import '../apps/freight_api.dart';
import 'package:shared_ui/toast.dart';
import 'package:flutter_map/flutter_map.dart';
import '../ui/errors.dart';

class FreightScreen extends StatefulWidget {
  const FreightScreen({super.key});
  @override
  State<FreightScreen> createState() => _FreightScreenState();
}

// ignore_for_file: use_build_context_synchronously
class _FreightScreenState extends State<FreightScreen> {
  static const _service = 'freight';
  final _api = FreightApi();
  final _tokens = MultiTokenStore();
  String _health = '?';
  bool _loading = false;
  bool _authed = false;
  String _role = 'shipper';

  @override
  void initState() {
    super.initState();
    _refreshAuthState();
  }

  Future<void> _refreshAuthState() async {
    final t = await getTokenFor('freight', store: _tokens);
    if (mounted) setState(() => _authed = t != null && t.isNotEmpty);
  }

  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson(_service, '/health');
      if (!mounted) return;
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Health check failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  // removed unused _loginDev helper

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Freight'),
        flexibleSpace: const Glass(
          padding: EdgeInsets.zero,
          blur: 24,
          opacity: 0.16,
          borderRadius: BorderRadius.zero,
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_loading) const LinearProgressIndicator(),
          Row(children: [
            Expanded(
              child: Glass(
                child: Row(children: [
                  FilledButton(
                      onPressed: _loading ? null : _healthCheck,
                      child: const Text('Health')),
                  const SizedBox(width: 12),
                  Text('Status: $_health'),
                ]),
              ),
            ),
          ]),
          const SizedBox(height: 12),
          Glass(
            child: Row(children: [
              const Text('Role:'),
              const SizedBox(width: 8),
              DropdownButton<String>(
                value: _role,
                items: const [
                  DropdownMenuItem(value: 'shipper', child: Text('Shipper')),
                  DropdownMenuItem(value: 'carrier', child: Text('Carrier')),
                ],
                onChanged: (v) => setState(() => _role = v ?? 'shipper'),
              ),
              const Spacer(),
              if (!_authed)
                const Text('Login via central Login', style: TextStyle(color: Colors.redAccent))
              else
                const Text('Logged in', style: TextStyle(color: Colors.green)),
            ]),
          ),
          const SizedBox(height: 12),
          if (_authed)
            (_role == 'shipper'
                ? ShipperPanel(api: _api)
                : CarrierPanel(api: _api))
          else
            const Glass(
              child: Padding(
                padding: EdgeInsets.all(8.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Please log in via Profile/Payments.'),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class ShipperPanel extends StatefulWidget {
  final FreightApi api;
  const ShipperPanel({super.key, required this.api});
  @override
  State<ShipperPanel> createState() => _ShipperPanelState();
}

class _ShipperPanelState extends State<ShipperPanel> {
  bool _loading = false;
  final _origin = TextEditingController(text: 'Damascus');
  final _destination = TextEditingController(text: 'Aleppo');
  final _weight = TextEditingController(text: '1000');
  final _price = TextEditingController(text: '50000');
  List<Map<String, dynamic>> _loads = [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.myShipperLoads();
      if (!mounted) return;
      setState(() => _loads = rows);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Loads fetch failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _post() async {
    final w = int.tryParse(_weight.text.trim()) ?? 0;
    final p = int.tryParse(_price.text.trim()) ?? 0;
    setState(() => _loading = true);
    try {
      await widget.api.createLoad(
        origin: _origin.text.trim(),
        destination: _destination.text.trim(),
        weightKg: w,
        priceCents: p,
      );
      await _refresh();
      _toast('Load posted');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Create load failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toast(String m) { if (!mounted) return; showToast(context, m); }

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (_loading) const LinearProgressIndicator(),
      Glass(
        child: Column(children: [
          Row(children: [
            Expanded(
              child: TextField(
                controller: _origin,
                decoration: const InputDecoration(labelText: 'Origin'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _destination,
                decoration: const InputDecoration(labelText: 'Destination'),
              ),
            ),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _weight,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Weight (kg)'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _price,
                keyboardType: TextInputType.number,
                decoration:
                    const InputDecoration(labelText: 'Price (SYP cents)'),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
                onPressed: _loading ? null : _post, child: const Text('Post')),
          ]),
        ]),
      ),
      const SizedBox(height: 8),
      const Text('My Loads', style: TextStyle(fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      Glass(
        child: SizedBox(
          height: 260,
          child: RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              itemCount: _loads.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final l = _loads[i];
                return ListTile(
                  title: Text('${l['origin']} → ${l['destination']}'),
                  subtitle: Text(
                      'Weight: ${l['weight_kg']} kg • Price: ${l['price_cents']} SYP • Status: ${l['status']}'),
                );
              },
            ),
          ),
        ),
      ),
    ]);
  }
}

class CarrierPanel extends StatefulWidget {
  final FreightApi api;
  const CarrierPanel({super.key, required this.api});
  @override
  State<CarrierPanel> createState() => _CarrierPanelState();
}

class _CarrierPanelState extends State<CarrierPanel> {
  bool _loading = false;
  List<Map<String, dynamic>> _available = [];
  Map<String, dynamic>? _current;
  String? _paymentId;
  final _latCtrl = TextEditingController(text: '33.5138');
  final _lonCtrl = TextEditingController(text: '36.2765');
  final _podCtrl = TextEditingController();
  // Filters
  final _fOrigin = TextEditingController();
  final _fDestination = TextEditingController();
  final _fMinW = TextEditingController();
  final _fMaxW = TextEditingController();
  final _mapCtrl = MapController();
  // Live options
  bool _live = false;
  Timer? _liveTimer;
  bool _autoAvail = false;
  Timer? _availTimer;

  // Prefs keys
  static const _kOrigin = 'freight_carrier_origin';
  static const _kDest = 'freight_carrier_dest';
  static const _kMinW = 'freight_carrier_minw';
  static const _kMaxW = 'freight_carrier_maxw';
  static const _kLat = 'freight_carrier_lat';
  static const _kLon = 'freight_carrier_lon';
  static const _kLive = 'freight_carrier_live';
  static const _kAutoAvail = 'freight_carrier_autoavail';

  // Simple city coordinate map for plotting routes
  static const Map<String, List<double>> _cityCoords = {
    'damascus': [33.5138, 36.2765],
    'aleppo': [36.2154, 37.1593],
    'homs': [34.7324, 36.7134],
    'hama': [35.1318, 36.7578],
    'latakia': [35.5167, 35.7833],
    'tartus': [34.8878, 35.8866],
    'idlib': [35.9306, 36.6339],
    'deir ez-zor': [35.3333, 40.1500],
    'deir ezzor': [35.3333, 40.1500],
    'raqqa': [35.9500, 39.0167],
    'hasakah': [36.4833, 40.7500],
    'daraa': [32.6189, 36.1021],
    'as-suwayda': [32.7089, 36.5695],
    'suwayda': [32.7089, 36.5695],
    'qamishli': [37.05, 41.2167],
    'al-qamishli': [37.05, 41.2167],
  };

  LatLng? _findCity(String? name) {
    if (name == null) return null;
    final key = name.trim().toLowerCase();
    final v = _cityCoords[key];
    if (v == null || v.length != 2) return null;
    return LatLng(v[0], v[1]);
  }

  @override
  void initState() {
    super.initState();
    _restorePrefs().then((_) {
      _loadAvailable();
      _maybeStartTimers();
      // Center map on restored lat/lon
      final lat = double.tryParse(_latCtrl.text.trim());
      final lon = double.tryParse(_lonCtrl.text.trim());
      if (lat != null && lon != null) {
        try {
          _mapCtrl.move(LatLng(lat, lon), 11);
        } catch (_) {}
      }
    });
  }

  @override
  void dispose() {
    _liveTimer?.cancel();
    _availTimer?.cancel();
    super.dispose();
  }

  Future<void> _restorePrefs() async {
    final p = await SharedPreferences.getInstance();
    _fOrigin.text = p.getString(_kOrigin) ?? _fOrigin.text;
    _fDestination.text = p.getString(_kDest) ?? _fDestination.text;
    _fMinW.text = p.getString(_kMinW) ?? _fMinW.text;
    _fMaxW.text = p.getString(_kMaxW) ?? _fMaxW.text;
    _latCtrl.text = p.getString(_kLat) ?? _latCtrl.text;
    _lonCtrl.text = p.getString(_kLon) ?? _lonCtrl.text;
    _live = p.getBool(_kLive) ?? false;
    _autoAvail = p.getBool(_kAutoAvail) ?? false;
    if (mounted) setState(() {});
  }

  Future<void> _saveFilters() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kOrigin, _fOrigin.text.trim());
    await p.setString(_kDest, _fDestination.text.trim());
    await p.setString(_kMinW, _fMinW.text.trim());
    await p.setString(_kMaxW, _fMaxW.text.trim());
  }

  Future<void> _saveLocation() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kLat, _latCtrl.text.trim());
    await p.setString(_kLon, _lonCtrl.text.trim());
  }

  Future<void> _saveToggles() async {
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kLive, _live);
    await p.setBool(_kAutoAvail, _autoAvail);
  }

  Future<void> _apply() async {
    setState(() => _loading = true);
    try {
      await widget.api.carrierApply(companyName: 'Carrier Co');
      _toast('Carrier approved (dev)');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Carrier apply failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadAvailable() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.availableLoads(
        origin: _fOrigin.text.trim().isEmpty ? null : _fOrigin.text.trim(),
        destination: _fDestination.text.trim().isEmpty
            ? null
            : _fDestination.text.trim(),
        minWeight: int.tryParse(_fMinW.text.trim()),
        maxWeight: int.tryParse(_fMaxW.text.trim()),
      );
      if (!mounted) return;
      setState(() => _available = rows);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Loads refresh failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _accept(String id) async {
    setState(() => _loading = true);
    try {
      final l = await widget.api.acceptLoad(id);
      if (!mounted) return;
      setState(() => _current = l);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Load acceptance failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickup() async {
    if (_current == null) return;
    setState(() => _loading = true);
    try {
      final l = await widget.api.pickupLoad(_current!['id'] as String);
      if (!mounted) return;
      setState(() => _current = l);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Pickup failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _inTransit() async {
    if (_current == null) return;
    setState(() => _loading = true);
    try {
      final l = await widget.api.inTransitLoad(_current!['id'] as String);
      if (!mounted) return;
      setState(() => _current = l);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Update to in-transit failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _deliver() async {
    if (_current == null) return;
    setState(() => _loading = true);
    try {
      final l = await widget.api.deliverLoad(_current!['id'] as String);
      if (!mounted) return;
      setState(() {
        _current = l;
        _paymentId = l['payment_request_id'] as String?;
      });
      if (_paymentId != null) await _showPaymentCta(_paymentId!);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Delivery update failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _updateLocation() async {
    final lat = double.tryParse(_latCtrl.text.trim());
    final lon = double.tryParse(_lonCtrl.text.trim());
    if (lat == null || lon == null) return;
    setState(() => _loading = true);
    try {
      await widget.api.updateCarrierLocation(lat: lat, lon: lon);
      _toast('Location updated');
      try {
        _mapCtrl.move(LatLng(lat, lon), 12);
      } catch (_) {}
      await _saveLocation();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Update location failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _maybeStartTimers() {
    if (_live && (_liveTimer == null || !_liveTimer!.isActive)) {
      _liveTimer =
          Timer.periodic(const Duration(seconds: 10), (_) => _updateLocation());
    }
    if (_autoAvail && (_availTimer == null || !_availTimer!.isActive)) {
      _availTimer =
          Timer.periodic(const Duration(seconds: 15), (_) => _loadAvailable());
    }
  }

  Future<void> _toggleLive(bool v) async {
    setState(() => _live = v);
    _liveTimer?.cancel();
    if (v) {
      _liveTimer =
          Timer.periodic(const Duration(seconds: 10), (_) => _updateLocation());
    }
    await _saveToggles();
  }

  Future<void> _toggleAutoAvail(bool v) async {
    setState(() => _autoAvail = v);
    _availTimer?.cancel();
    if (v) {
      _availTimer =
          Timer.periodic(const Duration(seconds: 15), (_) => _loadAvailable());
    }
    await _saveToggles();
  }

  Future<void> _addPod() async {
    if (_current == null) return;
    final url = _podCtrl.text.trim();
    if (url.isEmpty) return;
    setState(() => _loading = true);
    try {
      await widget.api.addPod(_current!['id'] as String, url);
      _toast('POD added');
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openChat() async {
    final id = _current?['id'] as String?;
    if (id == null) return;
    final msgCtrl = TextEditingController();
    List<Map<String, dynamic>> msgs = [];
    try {
      msgs = await widget.api.chatList(id);
    } catch (_) {}
    if (!mounted) return;
    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setS) {
          Future<void> reload() async {
            try {
              final rows = await widget.api.chatList(id);
              setS(() => msgs = rows);
            } catch (_) {}
          }

          return Padding(
            padding:
                EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom)
                    .add(const EdgeInsets.all(16)),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Load chat',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                SizedBox(
                  height: 220,
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemBuilder: (c, i) {
                      final m = msgs[i];
                      return ListTile(
                          title: Text(m['content'] ?? ''),
                          subtitle: Text(m['from_user_id'] ?? ''));
                    },
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemCount: msgs.length,
                  ),
                ),
                Row(children: [
                  Expanded(
                      child: TextField(
                          controller: msgCtrl,
                          decoration:
                              const InputDecoration(hintText: 'Message'))),
                  const SizedBox(width: 8),
                  FilledButton(
                      onPressed: () async {
                        final t = msgCtrl.text.trim();
                        if (t.isEmpty) return;
                        try {
                          await widget.api.chatSend(id, t);
                          msgCtrl.clear();
                          await reload();
                        } catch (e) {
                          presentError(ctx, e, message: 'Chat send failed');
                        }
                      },
                      child: const Text('Send'))
                ])
              ],
            ),
          );
        });
      },
    );
  }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      await Clipboard.setData(ClipboardData(text: requestId));
      _toast('Payments app not installed. Copied request ID.');
    }
  }

  Future<void> _showPaymentCta(String requestId) async {
    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(children: [
              Icon(Icons.local_shipping_outlined, size: 28),
              SizedBox(width: 8),
              Text('Load delivered',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))
            ]),
            const SizedBox(height: 8),
            const Text('Open the Payments app to receive your payout.'),
            const SizedBox(height: 16),
            Row(children: [
              Expanded(
                child: FilledButton.icon(
                    onPressed: () {
                      Navigator.pop(ctx);
                      _openPayment(requestId);
                    },
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('Open in Payments')),
              )
            ]),
            const SizedBox(height: 8),
            TextButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: requestId));
                  _toast('Copied payment request ID');
                },
                icon: const Icon(Icons.copy_outlined),
                label: const Text('Copy request ID')),
          ],
        ),
      ),
    );
  }

  void _toast(String m) {
    if (!mounted) return;
    showToast(context, m);
  }

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (_loading) const LinearProgressIndicator(),
      // Map view of current carrier position
      Glass(
        child: SizedBox(
          height: 220,
          child: Builder(builder: (context) {
            final lat = double.tryParse(_latCtrl.text.trim()) ?? 33.5138;
            final lon = double.tryParse(_lonCtrl.text.trim()) ?? 36.2765;
            final center = LatLng(lat, lon);
            final oc = _findCity(_current?['origin'] as String?);
            final dc = _findCity(_current?['destination'] as String?);
            return SuperMapView(
              center: center,
              zoom: 11,
              markers: [
                MapMarker(point: center, color: Colors.redAccent, size: 36),
                if (oc != null) MapMarker(point: oc, color: Colors.green, size: 30),
                if (dc != null) MapMarker(point: dc, color: Colors.blue, size: 30),
              ],
              polylines: [
                if (oc != null && dc != null)
                  MapPolyline(points: [oc, dc], color: Colors.blueAccent, width: 4),
              ],
            );
          }),
        ),
      ),
      const SizedBox(height: 8),
      Row(children: [
        FilledButton(
            onPressed: _loading ? null : _apply,
            child: const Text('Apply (dev)')),
        const SizedBox(width: 8),
        OutlinedButton(
            onPressed: _loading ? null : _loadAvailable,
            child: const Text('Refresh available')),
      ]),
      const SizedBox(height: 8),
      // Filters
      Glass(
        child: Column(children: [
          Row(children: [
            Expanded(
                child: TextField(
                    controller: _fOrigin,
                    decoration:
                        const InputDecoration(labelText: 'Origin filter'))),
            const SizedBox(width: 8),
            Expanded(
                child: TextField(
                    controller: _fDestination,
                    decoration: const InputDecoration(
                        labelText: 'Destination filter'))),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
                child: TextField(
                    controller: _fMinW,
                    keyboardType: TextInputType.number,
                    decoration:
                        const InputDecoration(labelText: 'Min weight'))),
            const SizedBox(width: 8),
            Expanded(
                child: TextField(
                    controller: _fMaxW,
                    keyboardType: TextInputType.number,
                    decoration:
                        const InputDecoration(labelText: 'Max weight'))),
            const SizedBox(width: 8),
            FilledButton(
                onPressed: _loading
                    ? null
                    : () async {
                        await _saveFilters();
                        await _loadAvailable();
                      },
                child: const Text('Apply filters')),
          ]),
        ]),
      ),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(
            child: TextField(
                controller: _latCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Lat'))),
        const SizedBox(width: 8),
        Expanded(
            child: TextField(
                controller: _lonCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Lon'))),
        const SizedBox(width: 8),
        OutlinedButton(
            onPressed: _loading ? null : _updateLocation,
            child: const Text('Send loc')),
      ]),
      const SizedBox(height: 8),
      Glass(
        child: Row(children: [
          Expanded(
              child: SwitchListTile(
                  title: const Text('Live tracking'),
                  contentPadding: EdgeInsets.zero,
                  value: _live,
                  onChanged: (v) => _toggleLive(v))),
          const SizedBox(width: 8),
          Expanded(
              child: SwitchListTile(
                  title: const Text('Auto-refresh available'),
                  contentPadding: EdgeInsets.zero,
                  value: _autoAvail,
                  onChanged: (v) => _toggleAutoAvail(v))),
        ]),
      ),
      const SizedBox(height: 8),
      const Text('Available Loads',
          style: TextStyle(fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      for (final l in _available)
        Card(
          child: ListTile(
            title: Text('${l['origin']} → ${l['destination']}'),
            subtitle: Text(
                'Weight: ${l['weight_kg']} kg • Price: ${l['price_cents']} SYP'),
            trailing: FilledButton(
                onPressed: _loading ? null : () => _accept(l['id'] as String),
                child: const Text('Accept')),
          ),
        ),
      const SizedBox(height: 12),
      const Divider(),
      const Text('Current Load', style: TextStyle(fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      if (_current != null) ...[
        ListTile(
          title: Text('${_current!['origin']} → ${_current!['destination']}'),
          subtitle: Text(
              'Status: ${_current!['status']} • Price: ${_current!['price_cents']} SYP'),
        ),
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: _loading ? null : _pickup,
              child: const Text('Pickup')),
          FilledButton(
              onPressed: _loading ? null : _inTransit,
              child: const Text('In transit')),
          FilledButton(
              onPressed: _loading ? null : _deliver,
              child: const Text('Deliver')),
          OutlinedButton(
              onPressed: _loading ? null : _openChat,
              child: const Text('Chat')),
        ]),
        Row(children: [
          Expanded(
              child: TextField(
                  controller: _podCtrl,
                  decoration:
                      const InputDecoration(hintText: 'POD URL (optional)'))),
          const SizedBox(width: 8),
          OutlinedButton(
              onPressed: _loading ? null : _addPod,
              child: const Text('Save POD'))
        ]),
      ] else
        const Text('No current load'),
    ]);
  }
}
