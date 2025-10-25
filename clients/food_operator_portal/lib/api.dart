import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiError implements Exception { final String message; ApiError(this.message); @override String toString() => message; }

class Api {
  String baseUrl;
  Api({this.baseUrl = 'http://localhost:8090'});

  static Future<Api> load() async { final p=await SharedPreferences.getInstance(); return Api(baseUrl: p.getString('api_base')??'http://localhost:8090'); }
  Future<void> setBaseUrl(String url) async { baseUrl=url; final p=await SharedPreferences.getInstance(); await p.setString('api_base', url); }

  Map<String,String> _baseHeaders()=>{'Content-Type':'application/json'};
  Future<Map<String,String>> _authHeaders() async { final p=await SharedPreferences.getInstance(); final t=p.getString('jwt'); final h=_baseHeaders(); if(t!=null&&t.isNotEmpty) h['Authorization']='Bearer $t'; return h; }

  Future<void> requestOtp(String phone) async { final r=await http.post(Uri.parse('$baseUrl/auth/request_otp'), headers:_baseHeaders(), body: jsonEncode({'phone': phone})); if(r.statusCode>=400) throw ApiError('OTP: ${r.body}'); }
  Future<void> verifyOtp(String phone, String otp, {String? name}) async {
    final r=await http.post(Uri.parse('$baseUrl/auth/verify_otp'), headers:_baseHeaders(), body: jsonEncode({'phone': phone, 'otp': otp, 'name': name})); if(r.statusCode>=400) throw ApiError('Login: ${r.body}');
    final tok=(jsonDecode(r.body) as Map<String,dynamic>)['access_token'] as String?; if(tok==null) throw ApiError('No token');
    final p=await SharedPreferences.getInstance(); await p.setString('jwt', tok);
  }

  Future<void> becomeOperatorAdmin() async { final r=await http.post(Uri.parse('$baseUrl/operator/dev/become_admin'), headers: await _authHeaders()); if(r.statusCode>=400) throw ApiError('become admin: ${r.body}'); }

  Future<List<Map<String,dynamic>>> listRestaurants() async { final r=await http.get(Uri.parse('$baseUrl/operator/restaurants'), headers: await _authHeaders()); if(r.statusCode>=400) throw ApiError('restaurants: ${r.body}'); return ((jsonDecode(r.body) as List?)??[]).cast<dynamic>().map((e)=> (e as Map).cast<String,dynamic>()).toList(); }

  Future<String> createRestaurant({required String name, String? city, String? address, String? ownerPhone}) async {
    final uri = Uri.parse('$baseUrl/operator/restaurants').replace(queryParameters: {'name': name, if(city!=null) 'city': city, if(address!=null) 'address': address, if(ownerPhone!=null) 'owner_phone': ownerPhone});
    final r=await http.post(uri, headers: await _authHeaders()); if(r.statusCode>=400) throw ApiError('create: ${r.body}'); return ((jsonDecode(r.body) as Map).cast<String,dynamic>())['id'] as String;
  }

  Future<void> updateRestaurant(String id, {String? name, String? city, String? address, String? ownerPhone}) async {
    final params = { if(name!=null) 'name': name, if(city!=null) 'city': city, if(address!=null) 'address': address, if(ownerPhone!=null) 'owner_phone': ownerPhone };
    final uri = Uri.parse('$baseUrl/operator/restaurants/$id').replace(queryParameters: params.isEmpty?null:params);
    final r=await http.patch(uri, headers: await _authHeaders()); if(r.statusCode>=400) throw ApiError('update: ${r.body}');
  }

  Future<List<Map<String,dynamic>>> listOrders({String? status}) async {
    final uri = Uri.parse('$baseUrl/operator/orders').replace(queryParameters: status!=null?{'status': status}:null);
    final r=await http.get(uri, headers: await _authHeaders()); if(r.statusCode>=400) throw ApiError('orders: ${r.body}');
    final data=(jsonDecode(r.body) as Map).cast<String,dynamic>();
    return ((data['orders'] as List?)??[]).cast<dynamic>().map((e)=> (e as Map).cast<String,dynamic>()).toList();
  }

  Future<Map<String,dynamic>> summary({int days=7}) async {
    final uri = Uri.parse('$baseUrl/operator/reports/summary').replace(queryParameters: {'days':'$days'});
    final r=await http.get(uri, headers: await _authHeaders()); if(r.statusCode>=400) throw ApiError('summary: ${r.body}'); return (jsonDecode(r.body) as Map).cast<String,dynamic>();
  }
}

