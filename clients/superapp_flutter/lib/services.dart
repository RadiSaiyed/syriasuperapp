import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:shared_core/shared_core.dart';

const String _globalHostOverride =
    String.fromEnvironment('SUPERAPP_BASE_HOST', defaultValue: '');
// When set, the app talks to a single API base and uses path-based routing,
// e.g. <SUPERAPP_API_BASE>/payments, /taxi, /chat, ...
const String _apiBaseOverride =
    String.fromEnvironment('SUPERAPP_API_BASE', defaultValue: '');
const String _paymentsBaseOverride =
    String.fromEnvironment('PAYMENTS_BASE_URL', defaultValue: '');
const String _taxiBaseOverride =
    String.fromEnvironment('TAXI_BASE_URL', defaultValue: '');
const String _chatBaseOverride =
    String.fromEnvironment('CHAT_BASE_URL', defaultValue: '');

class ServiceConfig {
  static final Map<String, int> _servicePorts = {
    // BFF root for path-based mode (local fallback only)
    'superapp': 8070,
    'payments': 8080,
    'taxi': 8081,
    'bus': 8082,
    'commerce': 8083,
    'utilities': 8084,
    'freight': 8085,
    'carmarket': 8086,
    'jobs': 8087,
    'stays': 8088,
    'doctors': 8089,
    'food': 8090,
    'chat': 8091,
    'realestate': 8092,
    'agriculture': 8093,
    'livestock': 8094,
    'carrental': 8095,
    'parking': 8096,
    'parking_offstreet': 8097,
    'flights': 8098,
  };

  static Iterable<String> get services => _servicePorts.keys;

  static Map<String, String> get defaults => {
        for (final service in services) service: baseUrl(service),
      };

  static String baseUrl(String service) {
    // Prefer a single API base if provided
    if (_apiBaseOverride.isNotEmpty) {
      final base = _normalizeBase(_apiBaseOverride);
      if (service == 'superapp') return base;
      return '$base/$service';
    }
    final override = _overrideFor(service);
    if (override != null && override.isNotEmpty) return _normalizeBase(override);
    final port = _servicePorts[service];
    if (port == null) {
      throw ArgumentError('Unknown service "$service"');
    }
    return '${_defaultHost()}:$port';
  }

  // Direct base URL ignoring SUPERAPP_API_BASE (useful for WS until BFF supports WS proxying).
  static String directBaseUrl(String service) {
    final override = _overrideFor(service);
    if (override != null && override.isNotEmpty) return _normalizeBase(override);
    final port = _servicePorts[service];
    if (port == null) {
      throw ArgumentError('Unknown service "$service"');
    }
    return '${_defaultHost()}:$port';
  }

  static Uri endpoint(String service, String path,
      {Map<String, String>? query}) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('${baseUrl(service)}$normalizedPath').replace(
        queryParameters: query == null || query.isEmpty ? null : query);
  }

  static String _defaultHost() {
    final host = _globalHostOverride.isNotEmpty
        ? _globalHostOverride
        : (Platform.isAndroid ? 'http://10.0.2.2' : 'http://localhost');
    return _normalizeBase(host);
  }

  static String? _overrideFor(String service) {
    switch (service) {
      case 'superapp':
        return _apiBaseOverride.isNotEmpty ? _apiBaseOverride : null;
      case 'payments':
        return _paymentsBaseOverride.isNotEmpty
            ? _paymentsBaseOverride
            : null;
      case 'taxi':
        return _taxiBaseOverride.isNotEmpty ? _taxiBaseOverride : null;
      case 'chat':
        return _chatBaseOverride.isNotEmpty ? _chatBaseOverride : null;
      default:
        return null;
    }
  }

  static String _normalizeBase(String value) {
    if (value.isEmpty) return value;
    return value.endsWith('/') ? value.substring(0, value.length - 1) : value;
  }
}

final SecureTokenStore _secureTokenStore = SecureTokenStore(prefix: 'superapp_jwt_');
final ConnectivityService _connectivityService = ConnectivityService();
final Map<String, SharedHttpClient> _httpClients = {};

SharedHttpClient _clientFor(String service) {
  return _httpClients.putIfAbsent(
    service,
    () => SharedHttpClient(
      service: service,
      baseUrl: ServiceConfig.baseUrl(service),
      tokenProvider: (svc) async {
        if (svc == 'superapp') {
          // Use Payments token for BFF calls (shared JWT across services)
          return await _secureTokenStore.read('payments');
        }
        return await _secureTokenStore.read(svc);
      },
      connectivity: _connectivityService,
      log: (message, {error, stackTrace}) => debugPrint(message),
    ),
  );
}

class MultiTokenStore {
  MultiTokenStore({SecureTokenStore? secureStore})
      : _store = secureStore ?? _secureTokenStore;

  final SecureTokenStore _store;

  Future<String?> get(String service) => _store.read(service);
  Future<void> set(String service, String token) => _store.write(service, token);
  Future<void> clear(String service) => _store.delete(service);

  Future<void> setAll(String token) async {
    await _store.writeAll(token, ServiceConfig.services);
  }

  Future<void> clearAll() async {
    await _store.deleteAll(ServiceConfig.services);
  }
}

class DevAuthResult {
  final String accessToken;
  DevAuthResult(this.accessToken);
}

/// Register a new user in Payments with username + password.
/// On success, stores the returned token under 'payments' and propagates to all services.
Future<void> registerUser({
  required String username,
  required String password,
  required String phone,
  String? name,
  MultiTokenStore? store,
}) async {
  final payload = <String, dynamic>{
    'username': username,
    'password': password,
    'phone': phone,
  };
  if (name != null && name.isNotEmpty) payload['name'] = name;
  final resp = await _clientFor('superapp').postJson(
    '/auth/register',
    body: payload,
    options: const RequestOptions(expectValidationErrors: true, idempotent: true),
  );
  final token = resp['access_token'] as String?;
  if (token == null || token.isEmpty) {
    throw Exception('Registration did not return a token');
  }
  final s = store ?? MultiTokenStore();
  await s.set('payments', token);
  await s.setAll(token);
}

/// Login with username + password against Payments /auth/login.
/// On success, stores the token under 'payments' and propagates to all services.
Future<void> passwordLogin({
  required String username,
  required String password,
  MultiTokenStore? store,
}) async {
  final resp = await _clientFor('superapp').postJson(
    '/auth/login',
    body: {'username': username, 'password': password},
    options: const RequestOptions(expectValidationErrors: true, idempotent: true),
  );
  final token = resp['access_token'] as String?;
  if (token == null || token.isEmpty) {
    throw Exception('Login did not return a token');
  }
  final s = store ?? MultiTokenStore();
  await s.set('payments', token);
  await s.setAll(token);
}

/// Dev-only username/password login. Defaults to the 'payments' service which
/// exposes /auth/dev_login and is used for single-login token propagation.
Future<DevAuthResult> devLogin({
  required String username,
  required String password,
  String service = 'superapp',
  MultiTokenStore? store,
}) async {
  final response = await _clientFor(service).postJson(
    '/auth/dev_login',
    body: {'username': username, 'password': password},
    options: const RequestOptions(expectValidationErrors: true, idempotent: true),
  );
  final token = response['access_token'] as String?;
  if (token == null || token.isEmpty) {
    throw Exception('No token returned');
  }
  final s = store ?? MultiTokenStore();
  await s.set(service, token);
  // Propagate to all services for single-login UX
  await s.setAll(token);
  return DevAuthResult(token);
}

Future<void> requestOtp(String service, String phone) async {
  // Route via BFF so login is unified
  await _clientFor('superapp').postJson(
    '/auth/request_otp',
    body: {'phone': phone},
    options: const RequestOptions(expectValidationErrors: true, idempotent: true),
  );
}

Future<void> verifyOtp(String service, String phone, String otp,
    {String? name, String? role, MultiTokenStore? store}) async {
  final payload = <String, dynamic>{'phone': phone, 'otp': otp};
  if (name != null) payload['name'] = name;
  if (role != null) payload['role'] = role;
  // Route via BFF; token issuer is Payments
  final response = await _clientFor('superapp').postJson(
    '/auth/verify_otp',
    body: payload,
    options: const RequestOptions(expectValidationErrors: true, idempotent: true),
  );
  final token = response['access_token'] as String?;
  if (token == null) throw Exception('No token');
  final s = store ?? MultiTokenStore();
  // Store under payments and propagate to all services for SSO
  await s.set('payments', token);
  await s.setAll(token);
}

Future<String?> getTokenFor(String service, {MultiTokenStore? store}) async {
  final s = store ?? MultiTokenStore();
  final t = await s.get(service);
  if (t != null && t.isNotEmpty) return t;
  // Fallback to Payments token for single-login
  final p = await s.get('payments');
  return (p != null && p.isNotEmpty) ? p : null;
}

Future<Map<String, String>> authHeaders(String service,
    {MultiTokenStore? store}) async {
  final t = await getTokenFor(service, store: store);
  final h = <String, String>{'Content-Type': 'application/json'};
  if (t != null) h['Authorization'] = 'Bearer $t';
  return h;
}

/// Validate the token for a service (default: payments) by calling a protected endpoint.
/// Returns true if valid; false if missing/invalid. Provide [probePaths] to override which
/// endpoints are probed (first success wins). If [propagateAll] is true and a valid
/// payments token is found, it will be copied to all services (single-login UX).
Future<bool> validateTokenAndMaybePropagate({
  String service = 'payments',
  bool propagateAll = true,
  List<String>? probePaths,
}) async {
  final headers = await authHeaders(service);
  if (!headers.containsKey('Authorization')) return false;
  final paths = probePaths ??
      (service == 'payments'
          ? const ['/wallet']
          : const ['/health']);
  try {
    for (final path in paths) {
      try {
        await _clientFor(service).send(
          CoreHttpRequest(
            method: 'GET',
            path: path,
            options: const RequestOptions(idempotent: true),
          ),
        );
        if (propagateAll && service == 'payments') {
          final token = headers['Authorization']!.replaceFirst('Bearer ', '');
          if (token.isNotEmpty) {
            await MultiTokenStore().setAll(token);
          }
        }
        return true;
      } on ApiError catch (error) {
        if (error.kind == CoreErrorKind.unauthorized ||
            error.kind == CoreErrorKind.forbidden) {
          return false;
        }
        continue;
      } on CoreError {
        continue;
      }
    }
    return false;
  } catch (_) {
    return false;
  }
}

Future<bool> hasTokenFor(String service) async {
  final token = await getTokenFor(service);
  return token != null && token.isNotEmpty;
}

Future<Map<String, dynamic>> serviceGetJson(
  String service,
  String path, {
  Map<String, String>? query,
  RequestOptions options = const RequestOptions(),
}) {
  return _clientFor(service).getJson(
    path,
    options: options.copyWith(queryParameters: query ?? options.queryParameters),
  );
}

Future<List<dynamic>> serviceGetJsonList(
  String service,
  String path, {
  Map<String, String>? query,
  RequestOptions options = const RequestOptions(),
}) {
  return _clientFor(service).getJsonList(
    path,
    options: options.copyWith(queryParameters: query ?? options.queryParameters),
  );
}

Future<Map<String, dynamic>> servicePostJson(
  String service,
  String path, {
  Object? body,
  Map<String, String>? query,
  RequestOptions options = const RequestOptions(),
}) {
  return _clientFor(service).postJson(
    path,
    body: body,
    options: options.copyWith(queryParameters: query ?? options.queryParameters),
  );
}

Future<void> servicePost(
  String service,
  String path, {
  Object? body,
  Map<String, String>? query,
  RequestOptions options = const RequestOptions(),
}) async {
  await _clientFor(service).send(
    CoreHttpRequest(
      method: 'POST',
      path: path,
      body: body,
      options: options.copyWith(queryParameters: query ?? options.queryParameters),
    ),
  );
}

Future<void> serviceDelete(
  String service,
  String path, {
  Map<String, String>? query,
  RequestOptions options = const RequestOptions(),
}) async {
  await _clientFor(service).send(
    CoreHttpRequest(
      method: 'DELETE',
      path: path,
      options: options.copyWith(queryParameters: query ?? options.queryParameters),
    ),
  );
}

Future<Map<String, dynamic>> servicePatchJson(
  String service,
  String path, {
  Object? body,
  Map<String, String>? query,
  RequestOptions options = const RequestOptions(),
}) async {
  final response = await _clientFor(service).send(
    CoreHttpRequest(
      method: 'PATCH',
      path: path,
      body: body,
      options: options.copyWith(queryParameters: query ?? options.queryParameters),
    ),
  );
  if (response.body.isEmpty) return const <String, dynamic>{};
  return jsonDecode(response.body) as Map<String, dynamic>;
}

Future<Map<String, dynamic>> servicePutJson(
  String service,
  String path, {
  Object? body,
  Map<String, String>? query,
  RequestOptions options = const RequestOptions(),
}) async {
  final response = await _clientFor(service).send(
    CoreHttpRequest(
      method: 'PUT',
      path: path,
      body: body,
      options: options.copyWith(queryParameters: query ?? options.queryParameters),
    ),
  );
  if (response.body.isEmpty) return const <String, dynamic>{};
  return jsonDecode(response.body) as Map<String, dynamic>;
}
