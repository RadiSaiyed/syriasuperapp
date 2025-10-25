import 'dart:convert';
import 'dart:io' show Platform;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const String _globalHostOverride =
    String.fromEnvironment('SUPERAPP_BASE_HOST', defaultValue: '');
const String _paymentsBaseOverride =
    String.fromEnvironment('PAYMENTS_BASE_URL', defaultValue: '');
const String _taxiBaseOverride =
    String.fromEnvironment('TAXI_BASE_URL', defaultValue: '');
const String _chatBaseOverride =
    String.fromEnvironment('CHAT_BASE_URL', defaultValue: '');

class ServiceConfig {
  static final Map<String, int> _servicePorts = {
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
    final override = _overrideFor(service);
    if (override != null && override.isNotEmpty) {
      return _normalizeBase(override);
    }
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

class MultiTokenStore {
  static const _prefix = 'jwt_';
  Future<String?> get(String service) async =>
      (await SharedPreferences.getInstance()).getString('$_prefix$service');
  Future<void> set(String service, String token) async =>
      (await SharedPreferences.getInstance())
          .setString('$_prefix$service', token);
  Future<void> clear(String service) async =>
      (await SharedPreferences.getInstance()).remove('$_prefix$service');

  Future<void> setAll(String token) async {
    final prefs = await SharedPreferences.getInstance();
    for (final service in ServiceConfig.services) {
      await prefs.setString('$_prefix$service', token);
    }
  }

  Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    for (final service in ServiceConfig.services) {
      await prefs.remove('$_prefix$service');
    }
  }
}

Future<void> requestOtp(String service, String phone) async {
  final uri = ServiceConfig.endpoint(service, '/auth/request_otp');
  final res = await http.post(uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'phone': phone}));
  if (res.statusCode >= 400) {
    throw Exception('OTP request failed: ${res.body}');
  }
}

Future<void> verifyOtp(String service, String phone, String otp,
    {String? name, String? role, MultiTokenStore? store}) async {
  final uri = ServiceConfig.endpoint(service, '/auth/verify_otp');
  final body = <String, dynamic>{'phone': phone, 'otp': otp};
  if (name != null) body['name'] = name;
  if (role != null) body['role'] = role;
  final res = await http.post(uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body));
  if (res.statusCode >= 400) {
    throw Exception('OTP verify failed: ${res.body}');
  }
  final token =
      (jsonDecode(res.body) as Map<String, dynamic>)['access_token'] as String?;
  if (token == null) throw Exception('No token');
  await (store ?? MultiTokenStore()).set(service, token);
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
      final uri = ServiceConfig.endpoint(service, path);
      final res = await http.get(uri, headers: headers);
      if (res.statusCode == 401 || res.statusCode == 403) {
        return false;
      }
      if (res.statusCode >= 400) {
        continue;
      }
      if (propagateAll && service == 'payments') {
        final token = headers['Authorization']!.replaceFirst('Bearer ', '');
        if (token.isNotEmpty) {
          await MultiTokenStore().setAll(token);
        }
      }
      return true;
    }
    return false;
  } catch (_) {
    return false;
  }
}
