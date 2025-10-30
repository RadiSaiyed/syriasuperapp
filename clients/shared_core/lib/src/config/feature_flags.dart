import 'app_config.dart';

/// Immutable snapshot of feature flags.
class FeatureFlagSet {
  FeatureFlagSet({Map<String, dynamic>? source, this.configKey = 'feature_flags'})
      : _flags = Map.unmodifiable(source ?? const <String, dynamic>{});

  FeatureFlagSet.fromConfig(AppConfigSnapshot snapshot, {this.configKey = 'feature_flags'})
      : _flags = Map.unmodifiable(snapshot.json(configKey));

  final Map<String, dynamic> _flags;
  final String configKey;

  bool isEnabled(String flag, {bool defaultValue = false}) {
    final value = _flags[flag];
    if (value is bool) return value;
    if (value is num) return value != 0;
    if (value is String) {
      final lower = value.toLowerCase();
      if (lower == 'true' || lower == '1') return true;
      if (lower == 'false' || lower == '0') return false;
    }
    return defaultValue;
  }

  double? rollout(String flag) {
    final value = _flags[flag];
    if (value is num) return value.toDouble();
    if (value is String) {
      final parsed = double.tryParse(value);
      return parsed;
    }
    return null;
  }

  Map<String, dynamic> asMap() => _flags;
}

/// Convenience wrapper to expose flags from an [AppConfigLoader].
class FeatureFlagProvider {
  FeatureFlagProvider({
    required this.loader,
    this.configKey = 'feature_flags',
  });

  final AppConfigLoader loader;
  final String configKey;

  FeatureFlagSet get current => FeatureFlagSet.fromConfig(loader.snapshot, configKey: configKey);

  Future<FeatureFlagSet> refresh() async {
    final snapshot = await loader.refresh();
    return FeatureFlagSet.fromConfig(snapshot, configKey: configKey);
  }
}
