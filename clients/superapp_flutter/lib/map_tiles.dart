import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

const String _tomTomApiKeyEnv =
    String.fromEnvironment('TOMTOM_MAP_KEY', defaultValue: '');
String _tomTomKeyOverride = '';

void setTomTomKey(String key) {
  _tomTomKeyOverride = key.trim();
}

String effectiveTomTomKey() {
  return _tomTomKeyOverride.isNotEmpty ? _tomTomKeyOverride : _tomTomApiKeyEnv;
}
const String tomTomMapStyle =
    String.fromEnvironment('TOMTOM_TILE_STYLE', defaultValue: 'basic/main');
const bool tomTomDefaultTrafficFlow =
    bool.fromEnvironment('TOMTOM_SHOW_TRAFFIC_FLOW', defaultValue: false);
const String tomTomTrafficFlowStyle = String.fromEnvironment(
    'TOMTOM_TRAFFIC_FLOW_STYLE',
    defaultValue: 'relative');
const bool tomTomDefaultTrafficIncidents =
    bool.fromEnvironment('TOMTOM_SHOW_TRAFFIC_INCIDENTS', defaultValue: false);

bool tomTomConfigured() => effectiveTomTomKey().isNotEmpty;

String _resolveStylePath() {
  final raw = tomTomMapStyle.trim();
  if (raw.isEmpty) return 'basic/main';
  final lower = raw.toLowerCase();
  if (lower.startsWith('style/')) return raw;
  const guidPattern =
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';
  if (RegExp(guidPattern).hasMatch(raw)) {
    return 'style/$raw';
  }
  return raw;
}

String tomTomBaseTileUrl() {
  final stylePath = _resolveStylePath();
  final key = effectiveTomTomKey();
  return 'https://api.tomtom.com/map/1/tile/$stylePath/{z}/{x}/{y}.png?key=$key';
}

String tomTomTrafficFlowTileUrl({String? style}) {
  final resolvedStyle = (style ?? tomTomTrafficFlowStyle).trim().isEmpty
      ? 'relative'
      : (style ?? tomTomTrafficFlowStyle).trim();
  return 'https://api.tomtom.com/traffic/map/4/tile/flow/$resolvedStyle/{z}/{x}/{y}.png?key=${effectiveTomTomKey()}';
  // using env key; effective key not needed for flow when base tiles use same key
}

String tomTomTrafficIncidentsTileUrl() {
  return 'https://api.tomtom.com/traffic/map/4/tile/incidents/s3/{z}/{x}/{y}.png?key=${effectiveTomTomKey()}';
}

List<Widget> tomTomTileLayers({
  bool? showTrafficFlow,
  bool? showTrafficIncidents,
  double trafficFlowOpacity = 0.65,
  double trafficIncidentsOpacity = 0.9,
}) {
  if (!tomTomConfigured()) {
    return const [];
  }
  final layers = <Widget>[
    TileLayer(
      urlTemplate: tomTomBaseTileUrl(),
      userAgentPackageName: 'superapp_flutter',
    ),
  ];
  if (showTrafficFlow ?? tomTomDefaultTrafficFlow) {
    layers.add(Opacity(
      opacity: trafficFlowOpacity.clamp(0, 1).toDouble(),
      child: TileLayer(
        urlTemplate: tomTomTrafficFlowTileUrl(),
        userAgentPackageName: 'superapp_flutter',
      ),
    ));
  }
  if (showTrafficIncidents ?? tomTomDefaultTrafficIncidents) {
    layers.add(Opacity(
      opacity: trafficIncidentsOpacity.clamp(0, 1).toDouble(),
      child: TileLayer(
        urlTemplate: tomTomTrafficIncidentsTileUrl(),
        userAgentPackageName: 'superapp_flutter',
      ),
    ));
  }
  return layers;
}

Widget tomTomMissingKeyPlaceholder({String? message}) {
  return Container(
    decoration: BoxDecoration(
      color: Colors.black.withValues(alpha: 0.6),
      borderRadius: BorderRadius.circular(12),
    ),
    padding: const EdgeInsets.all(16),
    alignment: Alignment.center,
    child: Text(
      message ??
          'TomTom API key missing. Launch with --dart-define=TOMTOM_MAP_KEY=your_key.',
      style: const TextStyle(color: Colors.white, fontSize: 13),
      textAlign: TextAlign.center,
    ),
  );
}
