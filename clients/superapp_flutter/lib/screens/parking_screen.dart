import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_ui/glass.dart';
import '../services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:printing/printing.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import '../main.dart';
import 'ai_gateway_screen.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';

class ParkingScreen extends StatefulWidget {
  const ParkingScreen({super.key});
  @override
  State<ParkingScreen> createState() => _ParkingScreenState();
}

class _ParkingScreenState extends State<ParkingScreen> {
  final _tokens = MultiTokenStore();
  final _plateCtrl = TextEditingController(text: 'AB1234');
  String? _zoneId;
  String? _zoneName;
  int? _ppm;
  int? _feeBps;
  String? _currency;
  String? _sessionId;
  bool _loading = false;
  double _lat = 33.5138, _lon = 36.2765;
  bool _autoStop = true;
  bool _remind10m = true;
  Timer? _geoTimer;
  Map<String, dynamic>? _lastReceipt;

  Future<Map<String, String>> _authHeaders() =>
      authHeaders('parking', store: _tokens);

  Uri _parkingUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('parking', path, query: query);

  Future<void> _detectZone() async {
    setState(() => _loading = true);
    try {
      final res = await http.get(
          _parkingUri('/zones/near', query: {
            'lat': '$_lat',
            'lon': '$_lon',
          }),
          headers: await _authHeaders());
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _zoneId = js['id'] as String?;
        _zoneName = js['name'] as String?;
        _ppm = (js['tariff_per_minute_cents'] as num?)?.toInt();
        _feeBps = (js['service_fee_bps'] as num?)?.toInt();
        _currency = js['currency'] as String? ?? 'SYP';
      });
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Zone failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _start() async {
    final z = _zoneId;
    if (z == null) { MessageHost.showInfoBanner(context, 'Detect a zone first'); return; }
    setState(() => _loading = true);
    try {
      final res = await http.post(_parkingUri('/sessions/start'),
          headers: await _authHeaders(),
          body: jsonEncode({"plate": _plateCtrl.text.trim(), "zone_id": z}));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final id = js['id'] as String?;
      setState(() => _sessionId = id);
      if (_remind10m && id != null) {
        try {
          await http.post(_parkingUri('/reminders'),
              headers: await _authHeaders(),
              body: jsonEncode({"session_id": id, "minutes_before": 10, "type": "expiry"}));
        } catch (_) {}
      }
      _toast('Started');
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Start failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _stop() async {
    final id = _sessionId;
    if (id == null) return;
    setState(() => _loading = true);
    try {
      final res = await http.post(_parkingUri('/sessions/$id/stop'),
          headers: await _authHeaders());
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(()=>_lastReceipt = js);
      showDialog(
          context: context,
          builder: (_) => AlertDialog(
                title: const Text('Session ended'),
                content: Text(
                    'Minutes: ${js['minutes']}\nGross: ${js['gross_cents']}c\nFee: ${js['fee_cents']}c\nNet: ${js['net_cents']}c'),
                actions: [
                  TextButton(onPressed: _exportPdf, child: const Text('Export PDF')),
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('OK'))
                ],
              ));
      setState(() => _sessionId = null);
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Stop failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _exportPdf() async {
    final r = _lastReceipt;
    if (r == null) { _toast('No receipt'); return; }
    try {
      final pdf = pw.Document();
      pdf.addPage(pw.Page(
        pageFormat: PdfPageFormat.a4,
        build: (ctx) => pw.Padding(
          padding: const pw.EdgeInsets.all(24),
          child: pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
            pw.Text('Parking Receipt', style: pw.TextStyle(fontSize: 20, fontWeight: pw.FontWeight.bold)),
            pw.SizedBox(height: 8),
            pw.Text('Minutes: ${r['minutes']}'),
            pw.Text('Gross: ${r['gross_cents']}c'),
            pw.Text('Fee: ${r['fee_cents']}c'),
            pw.Text('Net: ${r['net_cents']}c'),
            pw.SizedBox(height: 12),
            pw.Text('Thank you!'),
          ]),
        ),
      ));
      await Printing.layoutPdf(onLayout: (format) async => pdf.save());
    } catch (e) {
      _toast('PDF failed: $e');
    }
  }

  Future<void> _checkGeofence() async {
    final id = _sessionId;
    if (id == null) return;
    try {
      final res = await http.post(_parkingUri('/sessions/$id/loc'),
          headers: await _authHeaders(),
          body: jsonEncode({"lat": _lat, "lon": _lon, "buffer_m": 50}));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      if (js['auto_stopped'] == true) { setState(() => _sessionId = null); _toast('Auto-stopped (left zone)'); }
      else { _toast('Status: ${js['status']}'); }
    } catch (e) {
      MessageHost.showErrorBanner(context, 'Geofence check failed: $e');
    }
  }

  Future<void> _ensureLocationPermission() async {
    final perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      await Geolocator.requestPermission();
    }
  }

  void _startGeoTimer() {
    _geoTimer?.cancel();
    if (!_autoStop) return;
    // Lite mode reduces polling to save data; or disables it entirely.
    final bool lite = AppSettings.liteMode.value;
    final Duration interval = lite ? const Duration(seconds: 120) : const Duration(seconds: 30);
    if (lite) {
      // In Lite mode do not auto‑poll; user can trigger manual geofence check.
      return;
    }
    _geoTimer = Timer.periodic(interval, (_) async {
      try {
        final pos = await Geolocator.getCurrentPosition();
        setState(() { _lat = pos.latitude; _lon = pos.longitude; });
        await _checkGeofence();
      } catch (_) {}
    });
  }

  @override
  void dispose() {
    _geoTimer?.cancel();
    super.dispose();
  }

  void _toast(String msg) { if (!mounted) return; showToast(context, msg); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: const Text('Parking'),
          actions: [
            IconButton(
                tooltip: 'AI Assistant',
                onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const AIGatewayScreen())),
                icon: const Icon(Icons.smart_toy_outlined)),
          ],
          flexibleSpace: const Glass(
              padding: EdgeInsets.zero,
              blur: 24,
              opacity: 0.16,
              borderRadius: BorderRadius.zero)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Glass(
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('On‑Street', style: TextStyle(fontWeight: FontWeight.bold)),
            if (AppSettings.liteMode.value)
              const Padding(
                padding: EdgeInsets.only(top: 4.0),
                child: Text('Lite Mode aktiv: Automatische Geofence‑Prüfung aus',
                    style: TextStyle(fontSize: 12, color: Colors.orange)),
              ),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: TextField(
                  decoration: const InputDecoration(labelText: 'Lat'),
                  keyboardType: TextInputType.number,
                  controller: TextEditingController(text: _lat.toStringAsFixed(6)),
                  onSubmitted: (v) { final d = double.tryParse(v); if (d!=null) setState(()=>_lat=d); },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  decoration: const InputDecoration(labelText: 'Lon'),
                  keyboardType: TextInputType.number,
                  controller: TextEditingController(text: _lon.toStringAsFixed(6)),
                  onSubmitted: (v) { final d = double.tryParse(v); if (d!=null) setState(()=>_lon=d); },
                ),
              ),
            ]),
            const SizedBox(height: 8),
            // Toggles
            Row(children: [
              Expanded(child: Row(children: [
                const Text('Auto‑stop on leave'),
                const SizedBox(width: 8),
                Switch(value: _autoStop, onChanged: (v)=>setState(()=>_autoStop=v))
              ])),
              Expanded(child: Row(children: [
                const Text('Remind 10m'),
                const SizedBox(width: 8),
                Switch(value: _remind10m, onChanged: (v)=>setState(()=>_remind10m=v))
              ])),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _loading ? null : _detectZone,
                  icon: const Icon(Icons.place),
                  label: const Text('Detect Zone'),
                ),
              ),
              const SizedBox(width: 8),
              if (_sessionId != null)
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _autoStop ? _checkGeofence : null,
                    icon: const Icon(Icons.gps_fixed),
                    label: const Text('Check Geofence'),
                  ),
                ),
            ]),
            if (_zoneName != null) ...[
              const SizedBox(height: 8),
              Text('Zone: $_zoneName'),
              if (_ppm != null) Text('Tariff: ${_ppm}c/min  Fee: ${_feeBps ?? 0}bps  ${_currency ?? ''}')
            ],
            const SizedBox(height: 8),
            TextField(
              controller: _plateCtrl,
              decoration: const InputDecoration(labelText: 'Plate'),
            ),
            const SizedBox(height: 8),
            if (_sessionId == null)
              FilledButton(
                  onPressed: _loading ? null : () async { await _ensureLocationPermission(); await _detectZone(); await _start(); _startGeoTimer(); },
                  child: const Text('Start'))
            else
              FilledButton(
                  onPressed: _loading ? null : _stop,
                  child: const Text('Stop')),
          ]),
        )
      ]),
    );
  }
}
// ignore_for_file: use_build_context_synchronously
