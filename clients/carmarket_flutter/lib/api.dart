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

  // Listings
  Future<Map<String, dynamic>> createListing({required String title, String? make, String? model, int? year, required int priceCents, String? description}) async {
    final res = await http.post(Uri.parse('$baseUrl/listings'), headers: await _authHeaders(), body: jsonEncode({'title': title, 'make': make, 'model': model, 'year': year, 'price_cents': priceCents, 'description': description}));
    if (res.statusCode >= 400) throw ApiError('Create listing failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> browseListings() async {
    final res = await http.get(Uri.parse('$baseUrl/listings'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Browse failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['listings'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> searchListings({
    String? q,
    String? make,
    String? model,
    String? city,
    int? yearMin,
    int? yearMax,
    int? minPrice,
    int? maxPrice,
    int limit = 50,
    int offset = 0,
  }) async {
    final params = <String, String>{};
    void add(String k, Object? v) { if (v != null && v.toString().isNotEmpty) params[k] = v.toString(); }
    add('q', q);
    add('make', make);
    add('model', model);
    add('city', city);
    add('year_min', yearMin);
    add('year_max', yearMax);
    add('min_price', minPrice);
    add('max_price', maxPrice);
    add('limit', limit);
    add('offset', offset);
    final uri = Uri.parse('$baseUrl/listings').replace(queryParameters: params);
    final res = await http.get(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Browse failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['listings'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> myListings() async {
    final res = await http.get(Uri.parse('$baseUrl/listings/mine'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('My listings failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['listings'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  // Favorites
  Future<void> addFavorite(String listingId) async {
    final res = await http.post(Uri.parse('$baseUrl/favorites/$listingId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Add favorite failed: ${res.body}');
  }
  Future<void> removeFavorite(String listingId) async {
    final res = await http.delete(Uri.parse('$baseUrl/favorites/$listingId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Remove favorite failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> listFavorites() async {
    final res = await http.get(Uri.parse('$baseUrl/favorites'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Favorites failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['listings'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Offers
  Future<Map<String, dynamic>> createOffer({required String listingId, required int amountCents}) async {
    final res = await http.post(Uri.parse('$baseUrl/offers/listing/$listingId'), headers: await _authHeaders(), body: jsonEncode({'amount_cents': amountCents}));
    if (res.statusCode >= 400) throw ApiError('Create offer failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> myOffers() async {
    final res = await http.get(Uri.parse('$baseUrl/offers'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('My offers failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['offers'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> offersForListing(String listingId) async {
    final res = await http.get(Uri.parse('$baseUrl/offers/listing/$listingId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Listing offers failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['offers'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> acceptOffer(String offerId) async {
    final res = await http.post(Uri.parse('$baseUrl/offers/$offerId/accept'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Accept offer failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> rejectOffer(String offerId) async {
    final res = await http.post(Uri.parse('$baseUrl/offers/$offerId/reject'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Reject offer failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> cancelOffer(String offerId) async {
    final res = await http.post(Uri.parse('$baseUrl/offers/$offerId/cancel'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Cancel offer failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> rateOffer(String offerId, {required int rating, String? comment}) async {
    final res = await http.post(Uri.parse('$baseUrl/offers/$offerId/rate'), headers: await _authHeaders(), body: jsonEncode({'rating': rating, 'comment': comment}));
    if (res.statusCode >= 400) throw ApiError('Rate failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  // Listing detail & images
  Future<Map<String, dynamic>> getListing(String listingId) async {
    final res = await http.get(Uri.parse('$baseUrl/listings/$listingId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Get listing failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<void> addListingImage(String listingId, String url) async {
    final res = await http.post(Uri.parse('$baseUrl/listings/$listingId/images'), headers: await _authHeaders(), body: jsonEncode({'url': url}));
    if (res.statusCode >= 400) throw ApiError('Add image failed: ${res.body}');
  }

  // Chats
  Future<List<Map<String, dynamic>>> chatMessages(String listingId) async {
    final res = await http.get(Uri.parse('$baseUrl/chats/listing/$listingId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Messages failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['messages'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> chatSend(String listingId, String content, {String? toUserId}) async {
    final body = {'content': content, if (toUserId != null) 'to_user_id': toUserId};
    final res = await http.post(Uri.parse('$baseUrl/chats/listing/$listingId'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Send message failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
