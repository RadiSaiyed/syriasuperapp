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

  // Restaurants
  Future<List<Map<String, dynamic>>> listRestaurants({String? city, String? q, int limit = 50, int offset = 0}) async {
    final params = <String, String>{
      if (city != null && city.isNotEmpty) 'city': city,
      if (q != null && q.isNotEmpty) 'q': q,
      'limit': '$limit',
      'offset': '$offset',
    };
    final uri = Uri.parse('$baseUrl/restaurants').replace(queryParameters: params.isEmpty ? null : params);
    final res = await http.get(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List restaurants failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> listMenu(String restaurantId) async {
    final res = await http.get(Uri.parse('$baseUrl/restaurants/$restaurantId/menu'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List menu failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> listRestaurantImages(String restaurantId) async {
    final res = await http.get(Uri.parse('$baseUrl/restaurants/$restaurantId/images'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List images failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> listFavorites() async {
    final res = await http.get(Uri.parse('$baseUrl/restaurants/favorites'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List favorites failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<void> favoriteRestaurant(String restaurantId) async {
    final res = await http.post(Uri.parse('$baseUrl/restaurants/$restaurantId/favorite'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Favorite failed: ${res.body}');
  }
  Future<void> unfavoriteRestaurant(String restaurantId) async {
    final res = await http.delete(Uri.parse('$baseUrl/restaurants/$restaurantId/favorite'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Unfavorite failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> listReviews(String restaurantId) async {
    final res = await http.get(Uri.parse('$baseUrl/restaurants/$restaurantId/reviews'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List reviews failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['reviews'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> addReview({required String restaurantId, required int rating, String? comment}) async {
    final res = await http.post(Uri.parse('$baseUrl/restaurants/$restaurantId/reviews'), headers: await _authHeaders(), body: jsonEncode({'rating': rating, 'comment': comment}));
    if (res.statusCode >= 400) throw ApiError('Add review failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  // Cart
  Future<Map<String, dynamic>> getCart() async {
    final res = await http.get(Uri.parse('$baseUrl/cart'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Get cart failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> addCartItem({required String menuItemId, required int qty}) async {
    final res = await http.post(Uri.parse('$baseUrl/cart/items'), headers: await _authHeaders(), body: jsonEncode({'menu_item_id': menuItemId, 'qty': qty}));
    if (res.statusCode >= 400) throw ApiError('Add item failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> updateCartItem({required String itemId, required int qty}) async {
    final res = await http.put(Uri.parse('$baseUrl/cart/items/$itemId'), headers: await _authHeaders(), body: jsonEncode({'menu_item_id': 'unused', 'qty': qty}));
    if (res.statusCode >= 400) throw ApiError('Update item failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> deleteCartItem({required String itemId}) async {
    final res = await http.delete(Uri.parse('$baseUrl/cart/items/$itemId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Delete item failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  // Orders
  Future<Map<String, dynamic>> checkout() async {
    final res = await http.post(Uri.parse('$baseUrl/orders/checkout'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Checkout failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> listOrders() async {
    final res = await http.get(Uri.parse('$baseUrl/orders'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List orders failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['orders'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Admin
  Future<void> adminBecomeOwner(String restaurantId) async {
    final res = await http.post(Uri.parse('$baseUrl/admin/dev/become_owner?restaurant_id=$restaurantId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Become owner failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> adminListOrders() async {
    final res = await http.get(Uri.parse('$baseUrl/admin/orders'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Admin list orders failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['orders'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<void> adminUpdateOrderStatus({required String orderId, required String statusValue}) async {
    final res = await http.post(Uri.parse('$baseUrl/admin/orders/$orderId/status?status_value=$statusValue'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Update status failed: ${res.body}');
  }

  // Courier
  Future<List<Map<String, dynamic>>> courierAvailable() async {
    final res = await http.get(Uri.parse('$baseUrl/courier/available'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Courier available failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['orders'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> courierMyOrders() async {
    final res = await http.get(Uri.parse('$baseUrl/courier/orders'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Courier my orders failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['orders'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<void> courierAccept(String orderId) async {
    final res = await http.post(Uri.parse('$baseUrl/courier/orders/$orderId/accept'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Courier accept failed: ${res.body}');
  }
  Future<void> courierPickedUp(String orderId) async {
    final res = await http.post(Uri.parse('$baseUrl/courier/orders/$orderId/picked_up'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Courier pickup failed: ${res.body}');
  }
  Future<void> courierDelivered(String orderId) async {
    final res = await http.post(Uri.parse('$baseUrl/courier/orders/$orderId/delivered'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Courier deliver failed: ${res.body}');
  }

  Future<void> courierUpdateLocation({required String orderId, required double lat, required double lon}) async {
    final res = await http.post(Uri.parse('$baseUrl/courier/orders/$orderId/location'), headers: await _authHeaders(), body: jsonEncode({'lat': lat, 'lon': lon}));
    if (res.statusCode >= 400) throw ApiError('Courier update location failed: ${res.body}');
  }
  Future<Map<String, dynamic>> getOrderTracking(String orderId) async {
    final res = await http.get(Uri.parse('$baseUrl/orders/$orderId/tracking'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Get tracking failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
