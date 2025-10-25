import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:shared_ui/glass.dart';
import '../api.dart';
import '../utils/currency.dart';

class RideDetailScreen extends StatefulWidget {
  final ApiClient api;
  final String rideId;
  const RideDetailScreen({super.key, required this.api, required this.rideId});
  @override
  State<RideDetailScreen> createState() => _RideDetailScreenState();
}

class _RideDetailScreenState extends State<RideDetailScreen> {
  bool _loading = false;
  Map<String, dynamic>? _ride;

  String get _tomKey => (dotenv.env['TOMTOM_TILES_KEY'] ?? dotenv.env['TOMTOM_API_KEY_TAXI'] ?? dotenv.env['TOMTOM_MAP_KEY'] ?? dotenv.env['TOMTOM_API_KEY'] ?? '').trim();
  String get _tomUrl => 'https://api.tomtom.com/map/1/tile/basic/main/{z}/{x}/{y}.png?key=$_tomKey';

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final js = await widget.api.getRide(widget.rideId);
      setState(() => _ride = js);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Load failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _fmtTs(dynamic v) {
    if (v == null) return '-';
    try {
      final dt = DateTime.parse(v.toString()).toLocal();
      return '${dt.year}-${dt.month.toString().padLeft(2,'0')}-${dt.day.toString().padLeft(2,'0')} ${dt.hour.toString().padLeft(2,'0')}:${dt.minute.toString().padLeft(2,'0')}';
    } catch (_) {
      return v.toString();
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final id = widget.rideId;
    final js = _ride;
    final status = (js?['status'] ?? '').toString();
    final pickLat = (js?['pickup_lat'] as num?)?.toDouble();
    final pickLon = (js?['pickup_lon'] as num?)?.toDouble();
    final dropLat = (js?['dropoff_lat'] as num?)?.toDouble();
    final dropLon = (js?['dropoff_lon'] as num?)?.toDouble();
    final center = (pickLat != null && pickLon != null)
        ? LatLng(pickLat, pickLon)
        : const LatLng(33.5138, 36.2765);
    final stops = (js?['stops'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final priceValue = js?['final_fare_cents'] ?? js?['quoted_fare_cents'];
    final price = formatSyp(priceValue);
    final dist = (js?['distance_km'] as num?)?.toStringAsFixed(2) ?? '-';

    return Scaffold(
      appBar: AppBar(title: const Text('Ride details'), actions: [
        IconButton(onPressed: _loading ? null : _load, icon: _loading ? const SizedBox(width:18,height:18,child:CircularProgressIndicator(strokeWidth:2)) : const Icon(Icons.refresh))
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Glass(
          child: ListTile(
            title: Text('Ride $id', maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: Text('Status: $status  •  Price: $price  •  Dist: $dist km'),
          ),
        ),
        const SizedBox(height: 8),
        if (_tomKey.isNotEmpty)
          Glass(
            padding: EdgeInsets.zero,
            child: SizedBox(
              height: 220,
              child: FlutterMap(
                options: MapOptions(initialCenter: center, initialZoom: 13),
                children: [
                  TileLayer(urlTemplate: _tomUrl, subdomains: const ['a','b','c']),
                  MarkerLayer(markers: [
                    if (pickLat != null && pickLon != null)
                      Marker(point: LatLng(pickLat, pickLon), width: 36, height: 36, child: const Icon(Icons.place, color: Colors.green, size: 30)),
                    if (dropLat != null && dropLon != null)
                      Marker(point: LatLng(dropLat, dropLon), width: 36, height: 36, child: const Icon(Icons.flag, color: Colors.red, size: 30)),
                    ...stops.map((s) {
                      final la = (s['lat'] as num?)?.toDouble();
                      final lo = (s['lon'] as num?)?.toDouble();
                      if (la == null || lo == null) {
                        return const Marker(
                          point: LatLng(0, 0),
                          width: 0,
                          height: 0,
                          child: SizedBox.shrink(),
                        );
                      }
                      return Marker(
                        point: LatLng(la, lo),
                        width: 28,
                        height: 28,
                        child: const Icon(Icons.stop_circle, color: Colors.orange, size: 22),
                      );
                    }),
                  ])
                ],
              ),
            ),
          ),
        const SizedBox(height: 8),
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Cost breakdown', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text('Quoted: ${formatSyp(js?['quoted_fare_cents'])}'),
              Text('Final: ${formatSyp(js?['final_fare_cents'] ?? js?['quoted_fare_cents'])}'),
              Text('Distance: $dist km'),
            ]),
          ),
        ),
        const SizedBox(height: 8),
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Timestamps', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text('Created: ${_fmtTs(js?['created_at'])}'),
              Text('Started: ${_fmtTs(js?['started_at'])}'),
              Text('Completed: ${_fmtTs(js?['completed_at'])}'),
            ]),
          ),
        ),
        if (stops.isNotEmpty) ...[
          const SizedBox(height: 8),
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Stops', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                ...stops.asMap().entries.map((e){ final i=e.key; final s=e.value; return ListTile(dense:true, contentPadding: EdgeInsets.zero, leading: CircleAvatar(radius:12, child: Text('${i+1}')), title: Text('${s['lat']}, ${s['lon']}')); })
              ]),
            ),
          ),
        ]
      ]),
    );
  }
}
