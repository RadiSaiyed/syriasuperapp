import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class PushHistoryEntry {
  final String title;
  final String body;
  final String? deeplink;
  final String atIso;
  PushHistoryEntry({required this.title, required this.body, this.deeplink, required this.atIso});
  Map<String, dynamic> toJson() => {'title': title, 'body': body, if (deeplink != null) 'deeplink': deeplink, 'at': atIso};
  static PushHistoryEntry fromJson(Map<String, dynamic> js) => PushHistoryEntry(title: (js['title'] ?? '').toString(), body: (js['body'] ?? '').toString(), deeplink: (js['deeplink'] as String?), atIso: (js['at'] ?? '').toString());
}

class PushHistoryStore {
  static const _key = 'push_history_v1';
  static const _max = 100;
  static const _seenKey = 'push_history_seen_iso';
  static final ValueNotifier<int> unread = ValueNotifier<int>(0);

  static Future<List<PushHistoryEntry>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return const [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map>().map((e) => e.cast<String, dynamic>()).map(PushHistoryEntry.fromJson).toList();
      return list;
    } catch (_) {
      return const [];
    }
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
    await prefs.remove(_seenKey);
    unread.value = 0;
  }

  static Future<void> append(PushHistoryEntry entry) async {
    final prefs = await SharedPreferences.getInstance();
    final list = await load();
    final next = [entry, ...list].take(_max).toList();
    await prefs.setString(_key, jsonEncode(next.map((e) => e.toJson()).toList()));
    await _refreshUnreadInternal();
  }

  static Future<void> setSeenNow() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_seenKey, DateTime.now().toIso8601String());
    await _refreshUnreadInternal();
  }

  static Future<int> refreshUnread() async {
    await _refreshUnreadInternal();
    return unread.value;
  }

  static Future<void> _refreshUnreadInternal() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final seenIso = prefs.getString(_seenKey) ?? '';
      DateTime? seen;
      if (seenIso.isNotEmpty) {
        try { seen = DateTime.parse(seenIso); } catch (_) {}
      }
      final items = await load();
      int count = 0;
      if (seen == null) {
        count = items.length;
      } else {
        for (final it in items) {
          try {
            final at = DateTime.parse(it.atIso);
            if (at.isAfter(seen)) count++;
          } catch (_) { count++; }
        }
      }
      unread.value = count;
    } catch (_) {}
  }
}
