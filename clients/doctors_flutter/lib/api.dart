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
  Future<List<Map<String, dynamic>>> listDoctors({String? city, String? specialty}) async {
    final params = <String>[];
    if (city != null && city.isNotEmpty) params.add('city=${Uri.encodeComponent(city)}');
    if (specialty != null && specialty.isNotEmpty) params.add('specialty=${Uri.encodeComponent(specialty)}');
    final q = params.isEmpty ? '' : '?${params.join('&')}';
    final res = await http.get(Uri.parse('$baseUrl/doctors$q'), headers: _baseHeaders());
    if (res.statusCode >= 400) throw ApiError('List doctors failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> getDoctor(String id) async {
    final res = await http.get(Uri.parse('$baseUrl/doctors/$id'), headers: _baseHeaders());
    if (res.statusCode >= 400) throw ApiError('Get doctor failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> searchSlots({String? doctorId, String? city, String? specialty, required String startTime, required String endTime}) async {
    final body = {'doctor_id': doctorId, 'city': city, 'specialty': specialty, 'start_time': startTime, 'end_time': endTime}
      ..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(Uri.parse('$baseUrl/search_slots'), headers: _baseHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Search slots failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['slots'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Patient
  Future<Map<String, dynamic>> book(String slotId) async {
    final res = await http.post(Uri.parse('$baseUrl/appointments'), headers: await _authHeaders(), body: jsonEncode({'slot_id': slotId}));
    if (res.statusCode >= 400) throw ApiError('Booking failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> myAppointments() async {
    final res = await http.get(Uri.parse('$baseUrl/appointments'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('My appointments failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['appointments'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Doctor
  Future<Map<String, dynamic>> upsertProfile({required String specialty, String? city, String? clinicName}) async {
    final body = {'specialty': specialty, 'city': city, 'clinic_name': clinicName}..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(Uri.parse('$baseUrl/doctor/profile'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Upsert profile failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> addSlot({required String startTime, required String endTime}) async {
    final res = await http.post(Uri.parse('$baseUrl/doctor/slots'), headers: await _authHeaders(), body: jsonEncode({'start_time': startTime, 'end_time': endTime}));
    if (res.statusCode >= 400) throw ApiError('Add slot failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> mySlots() async {
    final res = await http.get(Uri.parse('$baseUrl/doctor/slots'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('My slots failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> doctorAppointments() async {
    final res = await http.get(Uri.parse('$baseUrl/doctor/appointments'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Doctor appointments failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['appointments'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}

