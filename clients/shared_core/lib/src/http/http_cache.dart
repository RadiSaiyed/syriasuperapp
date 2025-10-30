import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Very lightweight string cache with TTL persisted via SharedPreferences.
/// Keys should be stable (e.g., full request URL with sorted query params).
class HttpCacheEntry {
  HttpCacheEntry({required this.body, required this.expiry, this.etag});
  final String body;
  final DateTime expiry;
  final String? etag;
  bool get isFresh => DateTime.now().isBefore(expiry);
}

class HttpCache {
  HttpCache({required this.namespace});

  final String namespace;

  String _keyFor(String key) => 'sc_httpcache_${namespace}_${_hash(key)}';

  /// Returns cached body if not expired. If [allowStale] is true, returns
  /// body even if expired (used for offline reads), otherwise null when stale.
  Future<String?> get(String key, {bool allowStale = false}) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyFor(key));
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      final expiryIso = decoded['expiry'] as String?;
      final body = decoded['body'] as String?;
      final etag = decoded['etag'] as String?;
      if (body == null || expiryIso == null) return null;
      final expiry = DateTime.tryParse(expiryIso);
      if (expiry == null) return null;
      if (DateTime.now().isBefore(expiry) || allowStale) {
        return body;
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  /// Returns full cache entry including ETag if present.
  Future<HttpCacheEntry?> getEntry(String key, {bool allowStale = false}) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyFor(key));
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      final expiryIso = decoded['expiry'] as String?;
      final body = decoded['body'] as String?;
      final etag = decoded['etag'] as String?;
      if (body == null || expiryIso == null) return null;
      final expiry = DateTime.tryParse(expiryIso);
      if (expiry == null) return null;
      final entry = HttpCacheEntry(body: body, expiry: expiry, etag: etag);
      if (entry.isFresh || allowStale) return entry;
      return null;
    } catch (_) {
      return null;
    }
  }

  Future<void> set(String key, String body, Duration ttl) async {
    final prefs = await SharedPreferences.getInstance();
    final expiry = DateTime.now().add(ttl).toUtc().toIso8601String();
    final payload = jsonEncode({'expiry': expiry, 'body': body});
    await prefs.setString(_keyFor(key), payload);
  }

  Future<void> setWithEtag(String key, String body, Duration ttl, {String? etag}) async {
    final prefs = await SharedPreferences.getInstance();
    final expiry = DateTime.now().add(ttl).toUtc().toIso8601String();
    final payload = jsonEncode({'expiry': expiry, 'body': body, if (etag != null && etag.isNotEmpty) 'etag': etag});
    await prefs.setString(_keyFor(key), payload);
  }

  String _hash(String input) {
    // Simple stable hash; not cryptographic. Keep deterministic across runs.
    var hash = 0x811c9dc5;
    const prime = 16777619;
    for (var i = 0; i < input.length; i++) {
      hash ^= input.codeUnitAt(i);
      hash = (hash * prime) & 0xFFFFFFFF;
    }
    return hash.toRadixString(16);
  }
}
