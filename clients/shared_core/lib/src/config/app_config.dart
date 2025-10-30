import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Known deployment environments. Used to toggle behavior (e.g. logging).
enum AppEnvironment { dev, staging, prod }

AppEnvironment _parseEnvironment(String raw) {
  switch (raw.toLowerCase()) {
    case 'prod':
    case 'production':
      return AppEnvironment.prod;
    case 'staging':
      return AppEnvironment.staging;
    case 'dev':
    case 'development':
    default:
      return AppEnvironment.dev;
  }
}

/// Static (dart-define) configuration for a client.
class AppConfig {
  const AppConfig({
    required this.environment,
    this.remoteConfigUrl,
    this.defaults = const <String, dynamic>{},
    this.cacheDuration = const Duration(minutes: 5),
  });

  factory AppConfig.fromEnvironment({
    String environmentKey = 'APP_ENV',
    String remoteConfigKey = 'APP_CONFIG_URL',
    Map<String, dynamic> defaults = const <String, dynamic>{},
  }) {
    final envValue = String.fromEnvironment(environmentKey, defaultValue: 'dev');
    final remoteValue = String.fromEnvironment(remoteConfigKey, defaultValue: '');
    return AppConfig(
      environment: _parseEnvironment(envValue),
      remoteConfigUrl: remoteValue.isEmpty ? null : Uri.tryParse(remoteValue),
      defaults: defaults,
    );
  }

  final AppEnvironment environment;
  final Uri? remoteConfigUrl;
  final Map<String, dynamic> defaults;
  final Duration cacheDuration;

  bool get isProd => environment == AppEnvironment.prod;
  bool get isStaging => environment == AppEnvironment.staging;
  bool get isDev => environment == AppEnvironment.dev;
}

/// Immutable snapshot of configuration + feature flags.
class AppConfigSnapshot {
  const AppConfigSnapshot({
    required this.data,
    required this.fetchedAt,
  });

  final Map<String, dynamic> data;
  final DateTime fetchedAt;

  String? string(String key, {String? defaultValue}) {
    final value = data[key];
    if (value is String) return value;
    return defaultValue;
  }

  bool? boolValue(String key, {bool? defaultValue}) {
    final value = data[key];
    if (value is bool) return value;
    if (value is String) {
      return value.toLowerCase() == 'true' ? true : value.toLowerCase() == 'false' ? false : defaultValue;
    }
    if (value is num) return value != 0;
    return defaultValue;
  }

  int? intValue(String key, {int? defaultValue}) {
    final value = data[key];
    if (value is int) return value;
    if (value is num) return value.toInt();
    return defaultValue;
  }

  Map<String, dynamic> json(String key) {
    final value = data[key];
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return value.cast<String, dynamic>();
    return const <String, dynamic>{};
  }
}

/// Loader that merges remote JSON configuration with compile-time defaults.
class AppConfigLoader {
  AppConfigLoader({
    required this.baseConfig,
    http.Client? httpClient,
  }) : _httpClient = httpClient ?? http.Client();

  final AppConfig baseConfig;
  final http.Client _httpClient;

  AppConfigSnapshot? _snapshot;
  DateTime? _lastFetch;

  AppConfigSnapshot get snapshot => _snapshot ?? AppConfigSnapshot(
        data: Map<String, dynamic>.unmodifiable(baseConfig.defaults),
        fetchedAt: DateTime.fromMillisecondsSinceEpoch(0),
      );

  Future<AppConfigSnapshot> ensureLoaded({bool forceRefresh = false}) async {
    if (!forceRefresh && _snapshot != null && _lastFetch != null) {
      final age = DateTime.now().difference(_lastFetch!);
      if (age < baseConfig.cacheDuration) {
        return _snapshot!;
      }
    }
    return refresh();
  }

  Future<AppConfigSnapshot> refresh() async {
    final now = DateTime.now();
    if (baseConfig.remoteConfigUrl == null) {
      _snapshot = AppConfigSnapshot(
        data: Map<String, dynamic>.unmodifiable(baseConfig.defaults),
        fetchedAt: now,
      );
      _lastFetch = now;
      return _snapshot!;
    }

    try {
      final response = await _httpClient
          .get(baseConfig.remoteConfigUrl!)
          .timeout(const Duration(seconds: 5));
      if (response.statusCode >= 400) {
        throw http.ClientException(
          'Remote config responded with ${response.statusCode}',
          baseConfig.remoteConfigUrl,
        );
      }
      final decoded = jsonDecode(response.body);
      final merged = _mergeConfig(baseConfig.defaults, decoded);
      _snapshot = AppConfigSnapshot(
        data: Map<String, dynamic>.unmodifiable(merged),
        fetchedAt: now,
      );
      _lastFetch = now;
      return _snapshot!;
    } catch (_) {
      // Keep previous snapshot if available, otherwise fall back to defaults.
      _snapshot ??= AppConfigSnapshot(
        data: Map<String, dynamic>.unmodifiable(baseConfig.defaults),
        fetchedAt: now,
      );
      _lastFetch ??= now;
      return _snapshot!;
    }
  }

  Map<String, dynamic> _mergeConfig(
    Map<String, dynamic> defaults,
    Object? remote,
  ) {
    final merged = <String, dynamic>{}..addAll(defaults);
    if (remote is Map<String, dynamic>) {
      for (final entry in remote.entries) {
        merged[entry.key] = entry.value;
      }
    } else if (remote is Map) {
      merged.addAll(remote.cast<String, dynamic>());
    }
    return merged;
  }

  void dispose() {
    _httpClient.close();
  }
}
