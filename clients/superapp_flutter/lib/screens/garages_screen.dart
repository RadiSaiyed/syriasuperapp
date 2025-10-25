import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../ui/glass.dart';
import '../services.dart';
import '../map_tiles.dart';

class GaragesScreen extends StatefulWidget {
  const GaragesScreen({super.key});
  @override
  State<GaragesScreen> createState() => _GaragesScreenState();
}

class _GaragesScreenState extends State<GaragesScreen> {
  final _tokens = MultiTokenStore();
  bool _loading = false;
  final double _lat = 33.5138;
  final double _lon = 36.2765;
  List<Map<String, dynamic>> _facilities = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final base = ServiceConfig.defaults['parking_offstreet']!;
      final res = await http.get(Uri.parse('$base/facilities/near?lat=$_lat&lon=$_lon'),
          headers: await authHeaders('parking_offstreet', store: _tokens));
      if (res.statusCode >= 400) throw Exception(res.body);
      final list = (jsonDecode(res.body) as List).cast<Map<String, dynamic>>();
      setState(() => _facilities = list);
    } catch (e) {
      _toast('Load failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _reserve(Map<String, dynamic> f) async {
    final now = DateTime.now();
    final from = await showDatePicker(context: context, initialDate: now, firstDate: now, lastDate: now.add(const Duration(days: 14)));
    if (from == null) return;
    final fromTime = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(now));
    if (fromTime == null) return;
    final start = DateTime(from.year, from.month, from.day, fromTime.hour, fromTime.minute);
    final endTime = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(now.add(const Duration(hours: 2))));
    if (endTime == null) return;
    final end = DateTime(from.year, from.month, from.day, endTime.hour, endTime.minute);
    try {
      final base = ServiceConfig.defaults['parking_offstreet']!;
      final res = await http.post(Uri.parse('$base/reservations/'),
          headers: await authHeaders('parking_offstreet', store: _tokens),
          body: jsonEncode({
            "facility_id": f['id'],
            "from_ts": start.toUtc().toIso8601String(),
            "to_ts": end.toUtc().toIso8601String()
          }));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      if (!mounted) return;
      showDialog(context: context, builder: (_) => AlertDialog(
        title: const Text('Reservation QR'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          QrImageView(data: js['qr_code'] as String, size: 180),
          const SizedBox(height: 8),
          Text('Price: ${js['price_cents']}c'),
        ]),
        actions: [TextButton(onPressed: ()=>Navigator.pop(context), child: const Text('Close'))],
      ));
    } catch (e) {
      _toast('Reserve failed: $e');
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final center = LatLng(_lat, _lon);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Garages'),
        flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero),
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Glass(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('Near Facilities', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          SizedBox(
            height: 220,
            child: tomTomConfigured()
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: FlutterMap(options: MapOptions(initialCenter: center, initialZoom: 14), children: [
                      ...tomTomTileLayers(),
                      MarkerLayer(markers: [
                        for (final f in _facilities)
                          Marker(
                            point: LatLng((f['lat'] as num).toDouble(), (f['lon'] as num).toDouble()),
                            width: 36,
                            height: 36,
                            child: GestureDetector(
                              onTap: () => _reserve(f),
                              child: const Icon(Icons.local_parking, color: Colors.blueAccent, size: 32),
                            ),
                          ),
                      ])
                    ]),
                  )
                : tomTomMissingKeyPlaceholder(),
          ),
          const SizedBox(height: 8),
          if (_loading) const LinearProgressIndicator(minHeight: 2),
          ..._facilities.map((f) => ListTile(
                title: Text(f['name'] as String? ?? ''),
                subtitle: Text('~${f['distance_m']} m  ${f['height_limit_m']?.toString() ?? ''}'),
                trailing: FilledButton(onPressed: () => _reserve(f), child: const Text('Reserve')),
              )),
        ])),
      ]),
    );
  }
}
// ignore_for_file: use_build_context_synchronously
