import 'package:flutter/foundation.dart';

/// Additional options controlling a request's behaviour (timeouts, retries,
/// idempotency, etc.).
@immutable
class RequestOptions {
  const RequestOptions({
    this.headers,
    this.queryParameters,
    this.timeout,
    this.idempotent,
    this.attachAuthHeader = true,
    this.maxRetries,
    this.idempotencyKey,
    this.logName,
    this.expectValidationErrors = false,
    this.cacheTtl,
    this.staleIfOffline = false,
    this.queueIfOffline = false,
  });

  final Map<String, String>? headers;
  final Map<String, String>? queryParameters;
  final Duration? timeout;
  final bool? idempotent;
  final bool attachAuthHeader;
  final int? maxRetries;
  final String? idempotencyKey;
  final String? logName;
  final bool expectValidationErrors;
  // Optional in-memory/disk cache TTL for idempotent GETs.
  final Duration? cacheTtl;
  // If true and offline, returns cached response even if TTL expired.
  final bool staleIfOffline;
  // If true and offline, enqueue non-GET requests to a local queue for retry.
  final bool queueIfOffline;

  RequestOptions copyWith({
    Map<String, String>? headers,
    Map<String, String>? queryParameters,
    Duration? timeout,
    bool? idempotent,
    bool? attachAuthHeader,
    int? maxRetries,
    String? idempotencyKey,
    String? logName,
    bool? expectValidationErrors,
    Duration? cacheTtl,
    bool? staleIfOffline,
    bool? queueIfOffline,
  }) {
    return RequestOptions(
      headers: headers ?? this.headers,
      queryParameters: queryParameters ?? this.queryParameters,
      timeout: timeout ?? this.timeout,
      idempotent: idempotent ?? this.idempotent,
      attachAuthHeader: attachAuthHeader ?? this.attachAuthHeader,
      maxRetries: maxRetries ?? this.maxRetries,
      idempotencyKey: idempotencyKey ?? this.idempotencyKey,
      logName: logName ?? this.logName,
      expectValidationErrors: expectValidationErrors ?? this.expectValidationErrors,
      cacheTtl: cacheTtl ?? this.cacheTtl,
      staleIfOffline: staleIfOffline ?? this.staleIfOffline,
      queueIfOffline: queueIfOffline ?? this.queueIfOffline,
    );
  }
}

/// Declarative request container used by [SharedHttpClient].
class CoreHttpRequest {
  CoreHttpRequest({
    required this.method,
    required this.path,
    this.body,
    this.options = const RequestOptions(),
  });

  final String method;
  final String path;
  final Object? body;
  final RequestOptions options;
}

class CoreHttpResponse {
  CoreHttpResponse({
    required this.statusCode,
    required this.headers,
    required this.body,
    required this.elapsed,
    this.requestId,
  });

  final int statusCode;
  final Map<String, String> headers;
  final String body;
  final Duration elapsed;
  final String? requestId;
}

/// Signature used for safe logging hooks that must avoid PII.
typedef SafeLogCallback = void Function(String message, {Object? error, StackTrace? stackTrace});
