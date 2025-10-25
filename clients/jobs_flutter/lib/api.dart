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

  // Jobs (public)
  Future<List<Map<String, dynamic>>> listOpenJobs() async {
    final res = await http.get(Uri.parse('$baseUrl/jobs'), headers: _baseHeaders());
    if (res.statusCode >= 400) throw ApiError('List jobs failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['jobs'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> getJob(String jobId) async {
    final res = await http.get(Uri.parse('$baseUrl/jobs/$jobId'), headers: _baseHeaders());
    if (res.statusCode >= 400) throw ApiError('Get job failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> apply(String jobId, {String? coverLetter}) async {
    final res = await http.post(Uri.parse('$baseUrl/jobs/$jobId/apply'), headers: await _authHeaders(), body: jsonEncode({'cover_letter': coverLetter}));
    if (res.statusCode >= 400) throw ApiError('Apply failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  // Applications (seeker)
  Future<List<Map<String, dynamic>>> myApplications() async {
    final res = await http.get(Uri.parse('$baseUrl/applications'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List applications failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['applications'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Employer
  Future<Map<String, dynamic>> createCompany({required String name, String? description}) async {
    final res = await http.post(Uri.parse('$baseUrl/employer/company'), headers: await _authHeaders(), body: jsonEncode({'name': name, 'description': description}));
    if (res.statusCode >= 400) throw ApiError('Create company failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>?> getCompany() async {
    final res = await http.get(Uri.parse('$baseUrl/employer/company'), headers: await _authHeaders());
    if (res.statusCode == 404) return null;
    if (res.statusCode >= 400) throw ApiError('Get company failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> createJob({required String title, String? description, String? location, int? salaryCents}) async {
    final body = {'title': title, 'description': description, 'location': location, 'salary_cents': salaryCents}
      ..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(Uri.parse('$baseUrl/employer/jobs'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Create job failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> myJobs() async {
    final res = await http.get(Uri.parse('$baseUrl/employer/jobs'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List my jobs failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> jobApplications(String jobId) async {
    final res = await http.get(Uri.parse('$baseUrl/employer/jobs/$jobId/applications'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List job applications failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['applications'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}

