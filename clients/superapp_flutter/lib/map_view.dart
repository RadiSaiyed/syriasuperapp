import 'dart:math' as math;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart' as ll2;
import 'package:flutter_map/flutter_map.dart' as fm;
import 'package:google_maps_flutter/google_maps_flutter.dart' as gmap;

/// Default to Google Maps on mobile when available; fallback to OSM via flutter_map.
const bool kUseGoogleMaps = bool.fromEnvironment('USE_GOOGLE_MAPS', defaultValue: true);

class MapMarker {
  final ll2.LatLng point;
  final Color color;
  final double size;
  final String? id;
  const MapMarker({
    required this.point,
    this.color = Colors.red,
    this.size = 32,
    this.id,
  });
}

class MapPolyline {
  final List<ll2.LatLng> points;
  final Color color;
  final double width;
  const MapPolyline({required this.points, this.color = Colors.blue, this.width = 4});
}

class SuperMapView extends StatelessWidget {
  final ll2.LatLng center;
  final double zoom;
  final void Function(double lat, double lon)? onTap;
  final List<MapMarker> markers;
  final List<MapPolyline> polylines;
  final bool showTraffic;

  const SuperMapView({
    super.key,
    required this.center,
    this.zoom = 13,
    this.onTap,
    this.markers = const [],
    this.polylines = const [],
    this.showTraffic = false,
  });

  @override
  Widget build(BuildContext context) {
    final useGoogle = !kIsWeb && kUseGoogleMaps && (Theme.of(context).platform == TargetPlatform.iOS || Theme.of(context).platform == TargetPlatform.android);
    if (useGoogle) {
      return _GoogleMapView(
        center: center,
        zoom: zoom,
        onTap: onTap,
        markers: markers,
        polylines: polylines,
        showTraffic: showTraffic,
      );
    }
    return _OsmMapView(
      center: center,
      zoom: zoom,
      onTap: onTap,
      markers: markers,
      polylines: polylines,
    );
  }
}

class _GoogleMapView extends StatefulWidget {
  final ll2.LatLng center;
  final double zoom;
  final void Function(double lat, double lon)? onTap;
  final List<MapMarker> markers;
  final List<MapPolyline> polylines;
  final bool showTraffic;
  const _GoogleMapView({
    required this.center,
    required this.zoom,
    required this.onTap,
    required this.markers,
    required this.polylines,
    required this.showTraffic,
  });

  @override
  State<_GoogleMapView> createState() => _GoogleMapViewState();
}

class _GoogleMapViewState extends State<_GoogleMapView> {
  gmap.GoogleMapController? _ctrl;

  @override
  Widget build(BuildContext context) {
    final cam = gmap.CameraPosition(
      target: gmap.LatLng(widget.center.latitude, widget.center.longitude),
      zoom: widget.zoom.clamp(3, 20),
    );

    final markers = <gmap.Marker>{
      for (final m in widget.markers)
        gmap.Marker(
          markerId: gmap.MarkerId(
            m.id ?? '${m.point.latitude},${m.point.longitude}:${m.size}:${_colorKey(m.color)}',
          ),
          position: gmap.LatLng(m.point.latitude, m.point.longitude),
          icon: _markerIconForColor(m.color),
        ),
    };

    final lines = <gmap.Polyline>{
      for (final pl in widget.polylines)
        gmap.Polyline(
          polylineId: gmap.PolylineId(pl.hashCode.toString()),
          points: [for (final p in pl.points) gmap.LatLng(p.latitude, p.longitude)],
          color: pl.color,
          width: pl.width.toInt(),
        ),
    };

    return gmap.GoogleMap(
      initialCameraPosition: cam,
      myLocationButtonEnabled: false,
      myLocationEnabled: false,
      zoomControlsEnabled: false,
      trafficEnabled: widget.showTraffic,
      onMapCreated: (c) => _ctrl = c,
      onTap: widget.onTap != null
          ? (pos) => widget.onTap!(pos.latitude, pos.longitude)
          : null,
      markers: markers,
      polylines: lines,
    );
  }

  gmap.BitmapDescriptor _markerIconForColor(Color c) {
    // Map selected colors to Google marker hues, fallback to default red.
    double hue = gmap.BitmapDescriptor.hueRed;
    if (_isCloseColor(c, Colors.green)) hue = gmap.BitmapDescriptor.hueGreen;
    if (_isCloseColor(c, Colors.blue)) hue = gmap.BitmapDescriptor.hueBlue;
    if (_isCloseColor(c, Colors.orange)) hue = gmap.BitmapDescriptor.hueOrange;
    if (_isCloseColor(c, Colors.purple)) hue = gmap.BitmapDescriptor.hueViolet;
    if (_isCloseColor(c, Colors.yellow)) hue = gmap.BitmapDescriptor.hueYellow;
    return gmap.BitmapDescriptor.defaultMarkerWithHue(hue);
  }

  bool _isCloseColor(Color a, Color b) {
    final argbA = a.toARGB32();
    final argbB = b.toARGB32();
    final dr = ((argbA >> 16) & 0xFF) - ((argbB >> 16) & 0xFF);
    final dg = ((argbA >> 8) & 0xFF) - ((argbB >> 8) & 0xFF);
    final db = (argbA & 0xFF) - (argbB & 0xFF);
    return (dr.abs() + dg.abs() + db.abs()) < 100;
  }

  String _colorKey(Color color) => color.toARGB32().toRadixString(16).padLeft(8, '0');
}

class _OsmMapView extends StatelessWidget {
  final ll2.LatLng center;
  final double zoom;
  final void Function(double lat, double lon)? onTap;
  final List<MapMarker> markers;
  final List<MapPolyline> polylines;
  const _OsmMapView({
    required this.center,
    required this.zoom,
    required this.onTap,
    required this.markers,
    required this.polylines,
  });

  @override
  Widget build(BuildContext context) {
    return fm.FlutterMap(
      options: fm.MapOptions(
        initialCenter: center,
        initialZoom: zoom,
        onTap: onTap != null ? (tapPos, p) => onTap!(p.latitude, p.longitude) : null,
      ),
      children: [
        fm.TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'superapp_flutter',
        ),
        if (polylines.isNotEmpty)
          fm.PolylineLayer(
            polylines: [
              for (final pl in polylines)
                fm.Polyline(
                  points: pl.points,
                  color: pl.color,
                  strokeWidth: pl.width,
                ),
            ],
          ),
        if (markers.isNotEmpty)
          fm.MarkerLayer(
            markers: [
              for (final m in markers)
                fm.Marker(
                  point: m.point,
                  width: math.max(24, m.size),
                  height: math.max(24, m.size),
                  child: Icon(Icons.location_on, color: m.color, size: m.size),
                ),
            ],
          ),
      ],
    );
  }
}
