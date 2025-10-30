import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'offline_queue.dart';

class OfflineQueueHistoryEntry {
  OfflineQueueHistoryEntry({
    required this.service,
    required this.action, // 'sent' | 'removed'
    required this.method,
    required this.path,
    this.query,
    this.at,
    this.idempotencyKey,
    this.bodyPreview,
  });

  final String service;
  final String action;
  final String method;
  final String path;
  final Map<String, String>? query;
  final String? at; // ISO8601
  final String? idempotencyKey;
  final String? bodyPreview;

  Map<String, dynamic> toJson() => {
        'service': service,
        'action': action,
        'method': method,
        'path': path,
        'query': query,
        'at': at,
        'idempotencyKey': idempotencyKey,
        'bodyPreview': bodyPreview,
      };

  static OfflineQueueHistoryEntry fromJson(Map<String, dynamic> m) {
    return OfflineQueueHistoryEntry(
      service: m['service'] as String,
      action: m['action'] as String,
      method: m['method'] as String,
      path: m['path'] as String,
      query: (m['query'] as Map?)?.cast<String, String>(),
      at: m['at'] as String?,
      idempotencyKey: m['idempotencyKey'] as String?,
      bodyPreview: m['bodyPreview'] as String?,
    );
  }
}

class OfflineQueueHistoryStore {
  static const _key = 'sc_offline_history_global';
  static const _max = 50;

  Future<List<OfflineQueueHistoryEntry>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return <OfflineQueueHistoryEntry>[];
    try {
      final arr = jsonDecode(raw) as List<dynamic>;
      return arr
          .map((e) => OfflineQueueHistoryEntry.fromJson((e as Map).cast<String, dynamic>()))
          .toList();
    } catch (_) {
      return <OfflineQueueHistoryEntry>[];
    }
  }

  Future<void> save(List<OfflineQueueHistoryEntry> items) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = jsonEncode(items.map((e) => e.toJson()).toList());
    await prefs.setString(_key, raw);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }

  Future<void> appendFromQueued(String service, OfflineQueuedRequest it, String action) async {
    final items = await load();
    String? preview;
    final body = it.bodyText;
    if (body != null && body.isNotEmpty) {
      preview = body.length > 120 ? body.substring(0, 120) + '…' : body;
    }
    final entry = OfflineQueueHistoryEntry(
      service: service,
      action: action,
      method: it.method,
      path: it.path,
      query: it.query,
      at: DateTime.now().toUtc().toIso8601String(),
      idempotencyKey: it.idempotencyKey,
      bodyPreview: preview,
    );
    items.insert(0, entry);
    while (items.length > _max) {
      items.removeLast();
    }
    await save(items);
  }
}
