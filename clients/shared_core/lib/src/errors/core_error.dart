/// High-level classification of recoverable errors used across clients.
enum CoreErrorKind {
  network,
  timeout,
  unauthorized,
  forbidden,
  notFound,
  validation,
  conflict,
  rateLimited,
  server,
  cancelled,
  unknown,
}

/// Shared error contract for Super-App clients. Keeps enough metadata to
/// render consistent banners/toasts and to drive retry logic.
class CoreError implements Exception {
  CoreError({
    required this.kind,
    this.message,
    this.statusCode,
    this.details,
    this.cause,
    this.stackTrace,
  });

  final CoreErrorKind kind;
  final String? message;
  final int? statusCode;
  final Map<String, dynamic>? details;
  final Object? cause;
  final StackTrace? stackTrace;

  bool get isUnauthorized => kind == CoreErrorKind.unauthorized;
  bool get isRetriable =>
      kind == CoreErrorKind.network ||
      kind == CoreErrorKind.timeout ||
      kind == CoreErrorKind.rateLimited ||
      kind == CoreErrorKind.server;

  @override
  String toString() =>
      'CoreError(kind: $kind, statusCode: $statusCode, message: $message, details: $details)';
}

class ApiError extends CoreError {
  ApiError({
    required super.kind,
    super.message,
    super.statusCode,
    super.details,
    super.cause,
    super.stackTrace,
    this.body,
  });

  final Object? body;
}

class NetworkError extends CoreError {
  NetworkError({
    super.message,
    super.cause,
    super.stackTrace,
    Map<String, dynamic>? details,
  }) : super(kind: CoreErrorKind.network, details: details);
}

class TimeoutError extends CoreError {
  TimeoutError({
    super.message,
    super.cause,
    super.stackTrace,
  }) : super(kind: CoreErrorKind.timeout);
}
