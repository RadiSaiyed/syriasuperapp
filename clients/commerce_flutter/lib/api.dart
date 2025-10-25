import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:intl/intl.dart';

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

  // Shops
  Future<List<Map<String, dynamic>>> listShops() async {
    final res = await http.get(Uri.parse('$baseUrl/shops'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List shops failed: ${res.body}');
    final list = (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
    return list;
  }
  Future<List<Map<String, dynamic>>> listProducts(String shopId, {String? q, String? category}) async {
    final qp = <String, String>{};
    if (q != null && q.trim().isNotEmpty) qp['q'] = q.trim();
    if (category != null && category.trim().isNotEmpty) qp['category'] = category.trim();
    final uri = Uri.parse('$baseUrl/shops/$shopId/products').replace(queryParameters: qp.isEmpty ? null : qp);
    final res = await http.get(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List products failed: ${res.body}');
    final list = (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
    return list;
  }

  // Cart
  Future<Map<String, dynamic>> getCart() async {
    final res = await http.get(Uri.parse('$baseUrl/cart'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Get cart failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> addCartItem({required String productId, int qty = 1}) async {
    final res = await http.post(Uri.parse('$baseUrl/cart/items'), headers: await _authHeaders(), body: jsonEncode({'product_id': productId, 'qty': qty}));
    if (res.statusCode >= 400) throw ApiError('Add item failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> updateCartItem({required String itemId, required int qty}) async {
    final res = await http.put(Uri.parse('$baseUrl/cart/items/$itemId?qty=$qty'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Update item failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<void> clearCart() async {
    final res = await http.post(Uri.parse('$baseUrl/cart/clear'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Clear cart failed: ${res.body}');
  }

  // Orders
  Future<Map<String, dynamic>> checkout({String? promoCode, String? shipName, String? shipPhone, String? shipAddr}) async {
    final body = <String, dynamic>{};
    if (promoCode != null && promoCode.trim().isNotEmpty) body['promo_code'] = promoCode.trim();
    if (shipName != null && shipName.trim().isNotEmpty) body['shipping_name'] = shipName.trim();
    if (shipPhone != null && shipPhone.trim().isNotEmpty) body['shipping_phone'] = shipPhone.trim();
    if (shipAddr != null && shipAddr.trim().isNotEmpty) body['shipping_address'] = shipAddr.trim();
    final res = await http.post(Uri.parse('$baseUrl/orders/checkout'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Checkout failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<void> cancelOrder(String orderId) async {
    final res = await http.post(Uri.parse('$baseUrl/orders/$orderId/cancel'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Cancel failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> listOrders() async {
    final res = await http.get(Uri.parse('$baseUrl/orders'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List orders failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['orders'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Wishlist
  Future<List<Map<String, dynamic>>> wishlistList() async {
    final res = await http.get(Uri.parse('$baseUrl/wishlist'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Wishlist failed: ${res.body}');
    return ((jsonDecode(res.body) as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<String> wishlistAdd(String productId) async {
    final uri = Uri.parse('$baseUrl/wishlist').replace(queryParameters: {'product_id': productId});
    final res = await http.post(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Wishlist add failed: ${res.body}');
    final m = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return (m['id'] as String?) ?? '';
  }
  Future<void> wishlistDelete(String favId) async {
    final res = await http.delete(Uri.parse('$baseUrl/wishlist/$favId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Wishlist delete failed: ${res.body}');
  }

  // Reviews
  Future<List<Map<String, dynamic>>> reviewsGet(String productId) async {
    final res = await http.get(Uri.parse('$baseUrl/reviews/$productId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Reviews failed: ${res.body}');
    return ((jsonDecode(res.body) as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> reviewsAdd(String productId, {required int rating, String? comment}) async {
    final res = await http.post(Uri.parse('$baseUrl/reviews/$productId'), headers: await _authHeaders(), body: jsonEncode({'rating': rating, 'comment': comment}));
    if (res.statusCode >= 400) throw ApiError('Add review failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
