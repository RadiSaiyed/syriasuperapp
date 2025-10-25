import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiError implements Exception { final String message; ApiError(this.message); @override String toString() => message; }

class Api {
  String baseUrl;
  Api({this.baseUrl = 'http://localhost:8090'});

  static Future<Api> load() async {
    final prefs = await SharedPreferences.getInstance();
    return Api(baseUrl: prefs.getString('api_base') ?? 'http://localhost:8090');
  }
  Future<void> setBaseUrl(String url) async { baseUrl = url; final p = await SharedPreferences.getInstance(); await p.setString('api_base', url); }

  Map<String,String> _baseHeaders() => {'Content-Type':'application/json'};
  Future<Map<String,String>> _authHeaders() async { final p=await SharedPreferences.getInstance(); final t=p.getString('jwt'); final h=_baseHeaders(); if (t!=null&&t.isNotEmpty) h['Authorization']='Bearer $t'; return h; }

  Future<void> requestOtp(String phone) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/request_otp'), headers: _baseHeaders(), body: jsonEncode({'phone': phone}));
    if (r.statusCode >= 400) throw ApiError('OTP: ${r.body}');
  }
  Future<void> verifyOtp(String phone, String otp, {String? name}) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/verify_otp'), headers: _baseHeaders(), body: jsonEncode({'phone': phone, 'otp': otp, 'name': name}));
    if (r.statusCode >= 400) throw ApiError('Login: ${r.body}');
    final token = (jsonDecode(r.body) as Map<String,dynamic>)['access_token'] as String?; if (token==null) throw ApiError('No token');
    final p = await SharedPreferences.getInstance(); await p.setString('jwt', token);
  }

  Future<List<Map<String,dynamic>>> myRestaurants() async {
    final r = await http.get(Uri.parse('$baseUrl/admin/restaurants/mine'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('mine: ${r.body}');
    return ((jsonDecode(r.body) as List?)??[]).cast<dynamic>().map((e)=> (e as Map).cast<String,dynamic>()).toList();
  }

  Future<List<Map<String,dynamic>>> menuAll(String restaurantId) async {
    final r = await http.get(Uri.parse('$baseUrl/admin/restaurants/$restaurantId/menu_all'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('menu_all: ${r.body}');
    return ((jsonDecode(r.body) as List?)??[]).cast<dynamic>().map((e)=> (e as Map).cast<String,dynamic>()).toList();
  }

  Future<String> createMenuItem(String restaurantId, {required String name, required int priceCents, String? description, bool available=true}) async {
    final params = {
      'name': name,
      'price_cents': '$priceCents',
      if (description!=null) 'description': description,
      'available': '$available',
    };
    final uri = Uri.parse('$baseUrl/admin/restaurants/$restaurantId/menu').replace(queryParameters: params);
    final r = await http.post(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('create menu: ${r.body}');
    return ((jsonDecode(r.body) as Map).cast<String,dynamic>())['id'] as String;
  }

  Future<void> updateMenuItem(String menuItemId, {String? name, int? priceCents, String? description, bool? available}) async {
    final params = {
      if (name!=null) 'name': name,
      if (priceCents!=null) 'price_cents': '$priceCents',
      if (description!=null) 'description': description,
      if (available!=null) 'available': '$available',
    };
    final uri = Uri.parse('$baseUrl/admin/menu/$menuItemId').replace(queryParameters: params.isEmpty?null:params);
    final r = await http.patch(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('update menu: ${r.body}');
  }

  Future<void> deleteMenuItem(String menuItemId) async {
    final r = await http.delete(Uri.parse('$baseUrl/admin/menu/$menuItemId'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('delete menu: ${r.body}');
  }

  Future<List<Map<String,dynamic>>> listOrders() async {
    final r = await http.get(Uri.parse('$baseUrl/admin/orders'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('orders: ${r.body}');
    final data = (jsonDecode(r.body) as Map).cast<String,dynamic>();
    return ((data['orders'] as List?)??[]).cast<dynamic>().map((e)=> (e as Map).cast<String,dynamic>()).toList();
  }

  Future<void> setOrderStatus(String orderId, String statusValue) async {
    final uri = Uri.parse('$baseUrl/admin/orders/$orderId/status').replace(queryParameters: {'status_value': statusValue});
    final r = await http.post(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('status: ${r.body}');
  }
}

