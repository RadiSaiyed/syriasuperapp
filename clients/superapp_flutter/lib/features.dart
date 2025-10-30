import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:shared_core/shared_core.dart';
import 'services.dart';

class FeatureRegistry {
  // Empty set means: no remote constraints (show all).
  static final ValueNotifier<Set<String>> enabled = ValueNotifier<Set<String>>(<String>{});

  static Future<void> load() async {
    try {
      final js = await serviceGetJsonList('superapp', '/v1/features', options: const RequestOptions(idempotent: true));
      final ids = <String>{};
      for (final it in js) {
        if (it is Map) {
          final id = (it['id'] ?? '').toString();
          final en = (it['enabled'] ?? true) == true;
          if (id.isNotEmpty && en) ids.add(id);
        }
      }
      // Only publish if non-empty; empty continues to mean "no gating".
      if (ids.isNotEmpty) enabled.value = ids;
    } catch (e) {
      // Best-effort: ignore and keep showing all features
      debugPrint('FeatureRegistry.load failed: $e');
    }
  }

  static bool isEnabled(String id) {
    final cur = enabled.value;
    if (cur.isEmpty) return true; // default: allow all
    return cur.contains(id);
  }
}

