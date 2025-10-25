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
  Future<void> verifyOtp({required String phone, required String otp, String? name}) async {
    final res = await http.post(Uri.parse('$baseUrl/auth/verify_otp'), headers: _baseHeaders(), body: jsonEncode({'phone': phone, 'otp': otp, 'name': name}));
    if (res.statusCode >= 400) throw ApiError('OTP verify failed: ${res.body}');
    final token = (jsonDecode(res.body) as Map<String, dynamic>)['access_token'] as String?;
    if (token == null) throw ApiError('No token');
    await tokenStore.setToken(token);
  }

  // Shipper
  Future<Map<String, dynamic>> createLoad({required String origin, required String destination, required int weightKg, required int priceCents}) async {
    final res = await http.post(Uri.parse('$baseUrl/shipper/loads'), headers: await _authHeaders(), body: jsonEncode({'origin': origin, 'destination': destination, 'weight_kg': weightKg, 'price_cents': priceCents}));
    if (res.statusCode >= 400) throw ApiError('Create load failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> myShipperLoads() async {
    final res = await http.get(Uri.parse('$baseUrl/shipper/loads'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List loads failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['loads'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Carrier
  Future<void> carrierApply({String? companyName}) async {
    final res = await http.post(Uri.parse('$baseUrl/carrier/apply'), headers: await _authHeaders(), body: jsonEncode({'company_name': companyName}));
    if (res.statusCode >= 400) throw ApiError('Carrier apply failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> availableLoads() async {
    final res = await http.get(Uri.parse('$baseUrl/carrier/loads/available'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Available loads failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['loads'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> acceptLoad(String loadId) async {
    final res = await http.post(Uri.parse('$baseUrl/loads/$loadId/accept'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Accept load failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> pickupLoad(String loadId) async {
    final res = await http.post(Uri.parse('$baseUrl/loads/$loadId/pickup'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Pickup failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> inTransitLoad(String loadId) async {
    final res = await http.post(Uri.parse('$baseUrl/loads/$loadId/in_transit'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('In transit failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> deliverLoad(String loadId) async {
    final res = await http.post(Uri.parse('$baseUrl/loads/$loadId/deliver'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Deliver failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> myLoads() async {
    final res = await http.get(Uri.parse('$baseUrl/loads'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('My loads failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['loads'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Tracking
  Future<void> updateCarrierLocation({required double lat, required double lon}) async {
    final res = await http.put(Uri.parse('$baseUrl/carrier/location'), headers: await _authHeaders(), body: jsonEncode({'lat': lat, 'lon': lon}));
    if (res.statusCode >= 400) throw ApiError('Update location failed: ${res.body}');
  }
  Future<Map<String, dynamic>> getLoad(String loadId) async {
    final res = await http.get(Uri.parse('$baseUrl/loads/$loadId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Get load failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<void> addPod(String loadId, String url) async {
    final uri = Uri.parse('$baseUrl/loads/$loadId/pod').replace(queryParameters: {'url': url});
    final res = await http.post(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Add POD failed: ${res.body}');
  }

  // Chat
  Future<List<Map<String, dynamic>>> chatList(String loadId) async {
    final res = await http.get(Uri.parse('$baseUrl/chats/load/$loadId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Chat list failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['messages'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> chatSend(String loadId, String content) async {
    final res = await http.post(Uri.parse('$baseUrl/chats/load/$loadId'), headers: await _authHeaders(), body: jsonEncode({'content': content}));
    if (res.statusCode >= 400) throw ApiError('Chat send failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
