import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class TokenStore {
  static const _k = 'access_token';
  Future<String?> getToken() async => (await SharedPreferences.getInstance()).getString(_k);
  Future<void> setToken(String token) async => (await SharedPreferences.getInstance()).setString(_k, token);
  Future<void> clear() async => (await SharedPreferences.getInstance()).remove(_k);
}

class ApiClient {
  String baseUrl;
  final TokenStore tokenStore;
  ApiClient({required this.baseUrl, required this.tokenStore});

  Map<String, String> _baseHeaders() => {'Content-Type': 'application/json'};
  Future<Map<String, String>> _authHeaders() async {
    final h = _baseHeaders();
    final t = await tokenStore.getToken();
    if (t != null) h['Authorization'] = 'Bearer $t';
    return h;
  }

  // Auth
  Future<void> requestOtp(String phone) async {
    final res = await http.post(Uri.parse('$baseUrl/auth/request_otp'), headers: _baseHeaders(), body: jsonEncode({'phone': phone}));
    if (res.statusCode >= 400) throw ApiError('OTP request failed: ${res.body}');
  }
  Future<void> verifyOtp({required String phone, required String otp, String? name, String? role}) async {
    final body = {'phone': phone, 'otp': otp, 'name': name, 'role': role}..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(Uri.parse('$baseUrl/auth/verify_otp'), headers: _baseHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('OTP verify failed: ${res.body}');
    final token = (jsonDecode(res.body) as Map<String, dynamic>)['access_token'] as String?;
    if (token == null) throw ApiError('No token');
    await tokenStore.setToken(token);
  }

  // Public
  Future<List<Map<String, dynamic>>> listProperties({String? city}) async {
    final url = city == null || city.isEmpty ? '$baseUrl/properties' : '$baseUrl/properties?city=${Uri.encodeComponent(city)}';
    final res = await http.get(Uri.parse(url), headers: _baseHeaders());
    if (res.statusCode >= 400) throw ApiError('List properties failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> getProperty(String id) async {
    final res = await http.get(Uri.parse('$baseUrl/properties/$id'), headers: _baseHeaders());
    if (res.statusCode >= 400) throw ApiError('Get property failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> searchAvailability({String? city, required String checkIn, required String checkOut, required int guests}) async {
    final body = {'city': city, 'check_in': checkIn, 'check_out': checkOut, 'guests': guests}..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(Uri.parse('$baseUrl/search_availability'), headers: _baseHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Search failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['results'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Reservations (guest)
  Future<Map<String, dynamic>> createReservation({required String unitId, required String checkIn, required String checkOut, required int guests}) async {
    final res = await http.post(Uri.parse('$baseUrl/reservations'), headers: await _authHeaders(), body: jsonEncode({'unit_id': unitId, 'check_in': checkIn, 'check_out': checkOut, 'guests': guests}));
    if (res.statusCode >= 400) throw ApiError('Book failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> myReservations() async {
    final res = await http.get(Uri.parse('$baseUrl/reservations'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('My reservations failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['reservations'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Host
  Future<Map<String, dynamic>> createProperty({required String name, String? type, String? city, String? description}) async {
    final body = {'name': name, 'type': type, 'city': city, 'description': description}..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(Uri.parse('$baseUrl/host/properties'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Create property failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> myProperties() async {
    final res = await http.get(Uri.parse('$baseUrl/host/properties'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List properties failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> createUnit({required String propertyId, required String name, required int capacity, required int totalUnits, required int priceCentsPerNight}) async {
    final body = {'name': name, 'capacity': capacity, 'total_units': totalUnits, 'price_cents_per_night': priceCentsPerNight};
    final res = await http.post(Uri.parse('$baseUrl/host/properties/$propertyId/units'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Create unit failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> listUnits(String propertyId) async {
    final res = await http.get(Uri.parse('$baseUrl/host/properties/$propertyId/units'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List units failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> hostReservations() async {
    final res = await http.get(Uri.parse('$baseUrl/host/reservations'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Host reservations failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['reservations'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}

