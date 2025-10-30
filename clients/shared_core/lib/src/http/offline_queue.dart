import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../errors/core_error.dart';
import 'request_options.dart';

class OfflineQueuedRequest {
  OfflineQueuedRequest({
    required this.method,
    required this.path,
    this.query,
    this.bodyText,
    this.contentType,
    this.idempotencyKey,
    this.expectValidationErrors = false,
    this.createdAt,
  });

  final String method;
  final String path;
  final Map<String, String>? query;
  final String? bodyText;
  final String? contentType;
  final String? idempotencyKey;
  final bool expectValidationErrors;
  // ISO8601 UTC timestamp when enqueued
  final String? createdAt;

  Map<String, dynamic> toJson() => {
        'method': method,
        'path': path,
        'query': query,
        'bodyText': bodyText,
        'contentType': contentType,
        'idempotencyKey': idempotencyKey,
        'expectValidationErrors': expectValidationErrors,
        'createdAt': createdAt,
      };

  static OfflineQueuedRequest fromJson(Map<String, dynamic> m) {
    return OfflineQueuedRequest(
      method: m['method'] as String,
      path: m['path'] as String,
      query: (m['query'] as Map?)?.cast<String, String>(),
      bodyText: m['bodyText'] as String?,
      contentType: m['contentType'] as String?,
      idempotencyKey: m['idempotencyKey'] as String?,
      expectValidationErrors: (m['expectValidationErrors'] as bool?) ?? false,
      createdAt: m['createdAt'] as String?,
    );
  }
}

class OfflineRequestQueue {
  OfflineRequestQueue(this.service);

  final String service;

  String get _storageKey => 'sc_offline_queue_$service';

  Future<List<OfflineQueuedRequest>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey);
    if (raw == null) return <OfflineQueuedRequest>[];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list
          .map((e) => OfflineQueuedRequest.fromJson((e as Map).cast<String, dynamic>()))
          .toList();
    } catch (_) {
      return <OfflineQueuedRequest>[];
    }
  }

  Future<void> save(List<OfflineQueuedRequest> items) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = jsonEncode(items.map((e) => e.toJson()).toList());
    await prefs.setString(_storageKey, raw);
  }

  Future<void> enqueue(OfflineQueuedRequest item) async {
    final items = await load();
    items.add(item);
    await save(items);
  }

  Future<void> removeAt(int index) async {
    final items = await load();
    if (index < 0 || index >= items.length) return;
    items.removeAt(index);
    await save(items);
  }
}

/// Error used to signal that a request has been queued for later.
class OfflineQueuedError extends NetworkError {
  OfflineQueuedError({String? message})
      : super(message: message ?? 'offline_queued', details: const {'queued': true});
}
