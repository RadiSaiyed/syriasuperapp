import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../auth/token_store.dart';
import '../connectivity/connectivity_service.dart';
import 'http_cache.dart';
import '../errors/core_error.dart';
import 'request_options.dart';
import 'offline_queue.dart';

class SharedHttpClient {
  SharedHttpClient({
    required this.service,
    required String baseUrl,
    TokenProvider? tokenProvider,
    ConnectivityService? connectivity,
    http.Client? httpClient,
    this.defaultTimeout = const Duration(seconds: 12),
    this.defaultMaxRetries = 2,
    this.log,
  })  : baseUri = _normalizeBaseUri(baseUrl),
        _tokenProvider = tokenProvider,
        _connectivity = connectivity ?? ConnectivityService(),
        _client = httpClient ?? http.Client(),
        _cache = HttpCache(namespace: service),
        _queue = OfflineRequestQueue(service) {
    // Attempt flush when online.
    _connectivity.onStatusChange.listen((status) async {
      if (status == ConnectivityStatus.online) {
        await _flushQueueIfAny();
      }
    });
  }

  final String service;
  final Uri baseUri;
  final TokenProvider? _tokenProvider;
  final ConnectivityService _connectivity;
  final http.Client _client;
  final Duration defaultTimeout;
  final int defaultMaxRetries;
  final SafeLogCallback? log;
  final HttpCache _cache;
  final OfflineRequestQueue _queue;

  bool _closed = false;

  static Uri _normalizeBaseUri(String baseUrl) {
    final trimmed = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    final uri = Uri.parse(trimmed);
    if (!uri.hasScheme) {
      throw ArgumentError('Base URL must include scheme (e.g. https://) — got "$baseUrl"');
    }
    return uri;
  }

  Uri _buildUri(String path, Map<String, String>? query) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    final uri = baseUri.replace(path: '${baseUri.path}$normalizedPath');
    if (query == null || query.isEmpty) return uri;
    return uri.replace(queryParameters: {...uri.queryParameters, ...query});
  }

  Future<Map<String, dynamic>> getJson(String path, {RequestOptions options = const RequestOptions()}) async {
    final uri = _buildUri(path, options.queryParameters);
    final useCache = options.cacheTtl != null;
    HttpCacheEntry? entry;
    Map<String, String>? hdrs;
    if (useCache) {
      final status = await _connectivity.checkStatus();
      entry = await _cache.getEntry(uri.toString(), allowStale: options.staleIfOffline && status == ConnectivityStatus.offline);
      if (entry != null && entry.isFresh) {
        final decoded = _tryDecodeJson(entry.body);
        if (decoded is Map<String, dynamic>) return decoded;
      }
      if (entry?.etag != null && entry!.etag!.isNotEmpty) {
        hdrs = {...?options.headers, 'If-None-Match': entry.etag!};
      }
    }
    final opt2 = hdrs == null ? options : options.copyWith(headers: hdrs);
    final response = await send(CoreHttpRequest(method: 'GET', path: path, options: opt2));
    if (response.statusCode == 304 && entry != null) {
      final decoded = _tryDecodeJson(entry.body);
      if (decoded is Map<String, dynamic>) return decoded;
    }
    if (response.body.isEmpty) return const <String, dynamic>{};
    if (useCache) {
      final ttl = options.cacheTtl!;
      final etag = response.headers['etag'];
      if (etag != null && etag.isNotEmpty) {
        unawaited(_cache.setWithEtag(uri.toString(), response.body, ttl, etag: etag));
      } else {
        unawaited(_cache.set(uri.toString(), response.body, ttl));
      }
    }
    final decoded = _tryDecodeJson(response.body);
    if (decoded is Map<String, dynamic>) return decoded;
    throw ApiError(kind: CoreErrorKind.server, message: 'Expected JSON object', body: decoded, statusCode: response.statusCode);
  }

  Future<List<dynamic>> getJsonList(String path, {RequestOptions options = const RequestOptions()}) async {
    final uri = _buildUri(path, options.queryParameters);
    final useCache = options.cacheTtl != null;
    HttpCacheEntry? entry;
    Map<String, String>? hdrs;
    if (useCache) {
      final status = await _connectivity.checkStatus();
      entry = await _cache.getEntry(uri.toString(), allowStale: options.staleIfOffline && status == ConnectivityStatus.offline);
      if (entry != null && entry.isFresh) {
        final decoded = _tryDecodeJson(entry.body);
        if (decoded is List) return decoded;
      }
      if (entry?.etag != null && entry!.etag!.isNotEmpty) {
        hdrs = {...?options.headers, 'If-None-Match': entry.etag!};
      }
    }
    final opt2 = hdrs == null ? options : options.copyWith(headers: hdrs);
    final response = await send(CoreHttpRequest(method: 'GET', path: path, options: opt2));
    if (response.statusCode == 304 && entry != null) {
      final decoded = _tryDecodeJson(entry.body);
      if (decoded is List) return decoded;
    }
    if (response.body.isEmpty) return const <dynamic>[];
    if (useCache) {
      final ttl = options.cacheTtl!;
      final etag = response.headers['etag'];
      if (etag != null && etag.isNotEmpty) {
        unawaited(_cache.setWithEtag(uri.toString(), response.body, ttl, etag: etag));
      } else {
        unawaited(_cache.set(uri.toString(), response.body, ttl));
      }
    }
    final decoded = _tryDecodeJson(response.body);
    if (decoded is List) return decoded;
    throw ApiError(kind: CoreErrorKind.server, message: 'Expected JSON list', body: decoded, statusCode: response.statusCode);
  }

  Future<Map<String, dynamic>> postJson(String path, {
    Object? body,
    RequestOptions options = const RequestOptions(),
  }) async {
    final response = await send(CoreHttpRequest(method: 'POST', path: path, body: body, options: options));
    if (response.body.isEmpty) return const <String, dynamic>{};
    final decoded = _tryDecodeJson(response.body);
    if (decoded is Map<String, dynamic>) return decoded;
    throw ApiError(kind: CoreErrorKind.server, message: 'Expected JSON object', body: decoded, statusCode: response.statusCode);
  }

  Future<CoreHttpResponse> send(CoreHttpRequest request) async {
    if (_closed) {
      throw StateError('SharedHttpClient for $service has been closed');
    }
    final connectivityStatus = await _connectivity.checkStatus();
    if (connectivityStatus == ConnectivityStatus.offline) {
      if (_shouldQueue(request)) {
        final queued = await _enqueue(request);
        log?.call('[$service] queued offline ${request.method} ${request.path}');
        // Signal to UI that it was queued (not an error to retry now)
        throw OfflineQueuedError();
      }
      throw NetworkError(message: 'offline');
    }

    final options = request.options;
    final isIdempotent = options.idempotent ?? _isMethodIdempotent(request.method);
    final retries = options.maxRetries ?? (isIdempotent ? defaultMaxRetries : 0);
    final timeout = options.timeout ?? defaultTimeout;
    final requestId = options.logName ?? _generateRequestId();
    final expectValidation = options.expectValidationErrors;

    final uri = _buildUri(request.path, options.queryParameters);
    final headers = <String, String>{
      'Accept': 'application/json',
    };
    if (options.headers != null) {
      headers.addAll(options.headers!);
    }

    final tokenProvider = _tokenProvider;
    if (options.attachAuthHeader && tokenProvider != null) {
      try {
        final token = await tokenProvider(service);
        if (token != null && token.isNotEmpty) {
          headers['Authorization'] = 'Bearer $token';
        }
      } catch (e, stack) {
        log?.call('[$service] token provider failed', error: e, stackTrace: stack);
      }
    }

    final preparedBody = _encodeBodyIfNeeded(request.body, headers);

    if (request.method.toUpperCase() == 'POST' && options.idempotent == true) {
      headers['Idempotency-Key'] = options.idempotencyKey ?? _generateIdempotencyKey();
    }

    headers['X-Request-Id'] = requestId;

    final attempts = retries + 1;
    CoreError? lastError;
    for (var attempt = 1; attempt <= attempts; attempt++) {
      final stopwatch = Stopwatch()..start();
      try {
        log?.call('[$service] ${request.method.toUpperCase()} ${uri.toString()} (attempt $attempt/$attempts)');
        final response = await _sendOnce(
          uri: uri,
          method: request.method,
          headers: headers,
          body: preparedBody,
          timeout: timeout,
          expectValidation: expectValidation,
        );
        stopwatch.stop();
        return CoreHttpResponse(
          statusCode: response.statusCode,
          headers: response.headers,
          body: response.body,
          elapsed: stopwatch.elapsed,
          requestId: requestId,
        );
      } on CoreError catch (error) {
        stopwatch.stop();
        lastError = error;
        final shouldRetry = attempt < attempts && _shouldRetry(error);
        if (!shouldRetry) {
          throw error;
        }
        Object? retryAfter;
        if (error is ApiError) {
          final details = error.details;
          if (details != null) {
            retryAfter = details['retryAfter'];
          }
        }
        final delay = _delayForAttempt(
          attempt,
          retryAfter: retryAfter,
        );
        log?.call('[$service] retrying ${request.method.toUpperCase()} ${uri.path} in ${delay.inMilliseconds}ms due to ${error.kind}');
        await Future.delayed(delay);
      }
    }
    throw lastError ?? CoreError(kind: CoreErrorKind.unknown, message: 'Unknown error after retries');
  }

  Future<_RawHttpResponse> _sendOnce({
    required Uri uri,
    required String method,
    required Map<String, String> headers,
    required _PreparedBody body,
    required Duration timeout,
    required bool expectValidation,
  }) async {
    final request = http.Request(method.toUpperCase(), uri);
    request.headers.addAll(headers);
    if (body.bytes != null) {
      request.bodyBytes = body.bytes!;
      if (!request.headers.containsKey('Content-Type')) {
        request.headers['Content-Type'] = body.contentType ?? 'application/octet-stream';
      }
    } else if (body.text != null) {
      request.body = body.text!;
      request.headers.putIfAbsent('Content-Type', () => body.contentType ?? 'text/plain');
    }

    try {
      final streamed = await _client.send(request).timeout(timeout);
      final responseBody = await streamed.stream.bytesToString();
      final responseHeaders = Map<String, String>.from(streamed.headers);
      if (streamed.statusCode >= 400) {
        throw _toApiError(
          method: method,
          uri: uri,
          statusCode: streamed.statusCode,
          headers: responseHeaders,
          body: responseBody,
          expectValidation: expectValidation,
        );
      }
      return _RawHttpResponse(
        statusCode: streamed.statusCode,
        headers: responseHeaders,
        body: responseBody,
      );
    } on TimeoutException catch (error, stack) {
      throw TimeoutError(message: 'Request to ${uri.host} timed out', cause: error, stackTrace: stack);
    } on http.ClientException catch (error, stack) {
      throw NetworkError(message: error.message, cause: error, stackTrace: stack);
    } catch (error, stack) {
      if (_looksLikeNetworkError(error)) {
        throw NetworkError(message: '$error', cause: error, stackTrace: stack);
      }
      if (error is CoreError) rethrow;
      throw CoreError(kind: CoreErrorKind.unknown, message: '$error', cause: error, stackTrace: stack);
    }
  }

  bool _shouldQueue(CoreHttpRequest request) {
    final m = request.method.toUpperCase();
    final opts = request.options;
    if (!opts.queueIfOffline) return false;
    if (m == 'GET' || m == 'HEAD' || m == 'OPTIONS' || m == 'TRACE') return false;
    return true;
  }

  Future<bool> _enqueue(CoreHttpRequest request) async {
    final options = request.options;
    final prepared = _encodeBodyIfNeeded(request.body, options.headers ?? const {});
    if (prepared.bytes != null) {
      // For simplicity, we only queue textual/JSON bodies.
      throw NetworkError(message: 'offline');
    }
    String? idk = options.idempotencyKey;
    if (idk == null && request.method.toUpperCase() == 'POST' && (options.idempotent == true)) {
      idk = _generateIdempotencyKey();
    }
    final item = OfflineQueuedRequest(
      method: request.method,
      path: request.path,
      query: options.queryParameters,
      bodyText: prepared.text,
      contentType: prepared.contentType,
      idempotencyKey: idk,
      expectValidationErrors: options.expectValidationErrors,
      createdAt: DateTime.now().toUtc().toIso8601String(),
    );
    await _queue.enqueue(item);
    return true;
  }

  Future<void> _flushQueueIfAny() async {
    try {
      final items = await _queue.load();
      if (items.isEmpty) return;
      final remaining = <OfflineQueuedRequest>[];
      for (final it in items) {
        try {
          await send(CoreHttpRequest(
            method: it.method,
            path: it.path,
            body: it.bodyText,
            options: RequestOptions(
              queryParameters: it.query,
              idempotent: true,
              idempotencyKey: it.idempotencyKey,
              attachAuthHeader: true,
              expectValidationErrors: it.expectValidationErrors,
              headers: it.contentType == null ? null : {'Content-Type': it.contentType!},
            ),
          ));
        } catch (e) {
          // Keep the request in queue on failure; stop flush if network/server fails.
          remaining.add(it);
          if (e is CoreError && !e.isRetriable) {
            // Non-retriable -> drop
            remaining.remove(it);
          } else {
            break;
          }
        }
      }
      if (remaining.length != items.length) {
        await _queue.save(remaining);
      }
    } catch (_) {
      // Swallow flush errors; will retry on next connectivity change.
    }
  }

  void close() {
    if (_closed) return;
    _client.close();
    _closed = true;
  }

  bool _shouldRetry(CoreError error) {
    switch (error.kind) {
      case CoreErrorKind.network:
      case CoreErrorKind.timeout:
      case CoreErrorKind.server:
        return true;
      case CoreErrorKind.rateLimited:
        return true;
      default:
        return false;
    }
  }

  Duration _delayForAttempt(int attempt, {Object? retryAfter}) {
    if (retryAfter is String && retryAfter.isNotEmpty) {
      final seconds = int.tryParse(retryAfter.trim());
      if (seconds != null && seconds >= 0) {
        return Duration(seconds: seconds);
      }
      final retryDate = DateTime.tryParse(retryAfter);
      if (retryDate != null) {
        final diff = retryDate.difference(DateTime.now());
        if (!diff.isNegative) {
          return diff;
        }
      }
    }
    final base = pow(2, attempt - 1).toDouble();
    final millis = (base * 200).clamp(200, 3000).toInt();
    final jitter = _random.nextInt(120);
    return Duration(milliseconds: millis + jitter);
  }

  bool _isMethodIdempotent(String method) {
    switch (method.toUpperCase()) {
      case 'GET':
      case 'HEAD':
      case 'PUT':
      case 'DELETE':
      case 'OPTIONS':
      case 'TRACE':
        return true;
      default:
        return false;
    }
  }

  _PreparedBody _encodeBodyIfNeeded(Object? body, Map<String, String> headers) {
    if (body == null) return _PreparedBody.empty();
    if (body is String) {
      return _PreparedBody(text: body, contentType: headers['Content-Type']);
    }
    if (body is List<int>) {
      return _PreparedBody(bytes: body, contentType: headers['Content-Type']);
    }
    return _PreparedBody(
      text: jsonEncode(body),
      contentType: headers['Content-Type'] ?? 'application/json',
    );
  }

  ApiError _toApiError({
    required String method,
    required Uri uri,
    required int statusCode,
    required Map<String, String> headers,
    required String body,
    required bool expectValidation,
  }) {
    final decoded = _tryDecodeJson(body);
    final details = decoded is Map<String, dynamic> ? decoded : null;
    final mergedDetails = _mergeDetailsWithRetryAfter(details, headers);
    final message = _extractErrorMessage(details) ?? body;
    final kind = _mapStatusToKind(statusCode, expectValidation: expectValidation, details: details);
    final error = ApiError(
      kind: kind,
      message: message,
      statusCode: statusCode,
      details: mergedDetails,
      body: decoded,
    );
    if (kDebugMode) {
      log?.call('[$service] $method ${uri.path} failed with $statusCode ($kind)');
    }
    return error;
  }

  CoreErrorKind _mapStatusToKind(int statusCode, {required bool expectValidation, Map<String, dynamic>? details}) {
    if (statusCode == 401) return CoreErrorKind.unauthorized;
    if (statusCode == 403) return CoreErrorKind.forbidden;
    if (statusCode == 404) return CoreErrorKind.notFound;
    if (statusCode == 409) return CoreErrorKind.conflict;
    if (statusCode == 429) return CoreErrorKind.rateLimited;
    if (statusCode == 422 || (statusCode == 400 && (expectValidation || details?['errors'] != null))) {
      return CoreErrorKind.validation;
    }
    if (statusCode >= 500) return CoreErrorKind.server;
    return CoreErrorKind.unknown;
  }

  String? _extractErrorMessage(Map<String, dynamic>? details) {
    if (details == null) return null;
    final keys = ['message', 'error', 'detail'];
    for (final key in keys) {
      final value = details[key];
      if (value is String && value.isNotEmpty) {
        return value;
      }
    }
    if (details['errors'] is Map) {
      final errors = (details['errors'] as Map).values;
      for (final entry in errors) {
        if (entry is List && entry.isNotEmpty) {
          final first = entry.first;
          if (first is String && first.isNotEmpty) return first;
        } else if (entry is String && entry.isNotEmpty) {
          return entry;
        }
      }
    }
    return null;
  }

  static Object? _tryDecodeJson(String body) {
    if (body.isEmpty) return null;
    try {
      return jsonDecode(body);
    } catch (_) {
      return body;
    }
  }

  String _generateIdempotencyKey() {
    final bytes = List<int>.generate(12, (_) => _random.nextInt(16));
    final buffer = StringBuffer();
    for (final value in bytes) {
      buffer.write(value.toRadixString(16));
    }
    return buffer.toString();
  }

  String _generateRequestId() {
    final millis = DateTime.now().millisecondsSinceEpoch;
    final randomPart = _random.nextInt(0xFFFFF).toRadixString(16);
    return '${service}_$millis$randomPart';
  }

  Map<String, dynamic>? _mergeDetailsWithRetryAfter(
    Map<String, dynamic>? details,
    Map<String, String> headers,
  ) {
    final retryAfter = _headerValue(headers, 'Retry-After');
    if (retryAfter == null) {
      return details;
    }
    final merged = <String, dynamic>{};
    if (details != null) {
      merged.addAll(details);
    }
    merged['retryAfter'] = retryAfter;
    return merged;
  }

  String? _headerValue(Map<String, String> headers, String name) {
    final lower = name.toLowerCase();
    for (final entry in headers.entries) {
      if (entry.key.toLowerCase() == lower) {
        return entry.value;
      }
    }
    return null;
  }

  bool _looksLikeNetworkError(Object error) {
    final typeName = error.runtimeType.toString();
    if (typeName.contains('SocketException') || typeName.contains('HandshakeException')) {
      return true;
    }
    return error is TimeoutException || error is http.ClientException;
  }

  static final _random = Random.secure();
}

class _RawHttpResponse {
  _RawHttpResponse({
    required this.statusCode,
    required this.headers,
    required this.body,
  });

  final int statusCode;
  final Map<String, String> headers;
  final String body;
}

class _PreparedBody {
  const _PreparedBody({this.text, this.bytes, this.contentType});

  factory _PreparedBody.empty() => const _PreparedBody();

  final String? text;
  final List<int>? bytes;
  final String? contentType;
}
