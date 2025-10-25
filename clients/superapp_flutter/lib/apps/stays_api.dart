import 'dart:convert';
import 'package:http/http.dart' as http;
import '../services.dart';

class StaysApi {
  final _tokens = MultiTokenStore();

  Future<Map<String, String>> _authHeaders() =>
      authHeaders('stays', store: _tokens);

  Uri _uri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('stays', path, query: query);

  // Public
  Future<List<Map<String, dynamic>>> listProperties({String? city, String? type, String? q}) async {
    final qp = <String, String>{};
    if (city != null && city.isNotEmpty) qp['city'] = city;
    if (type != null && type.isNotEmpty) qp['type'] = type;
    if (q != null && q.isNotEmpty) qp['q'] = q;
    final res = await http.get(_uri('/properties', query: qp.isEmpty ? null : qp));
    if (res.statusCode >= 400) throw Exception('List properties failed: ${res.body}');
    return ((jsonDecode(res.body) as List).cast()).map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> getProperty(String id) async {
    final res = await http.get(_uri('/properties/$id'));
    if (res.statusCode >= 400) throw Exception('Get property failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> searchAvailability({
    String? city,
    String? propertyType,
    required String checkIn,
    required String checkOut,
    required int guests,
    int? minPriceCents,
    int? maxPriceCents,
    int? capacityMin,
    List<String>? amenities,
    String amenitiesMode = 'any',
    int offset = 0,
    int limit = 50,
  }) async {
    final body = <String, dynamic>{
      'city': city,
      'property_type': propertyType,
      'check_in': checkIn,
      'check_out': checkOut,
      'guests': guests,
      'min_price_cents': minPriceCents,
      'max_price_cents': maxPriceCents,
      'capacity_min': capacityMin,
      'amenities': amenities,
      'amenities_mode': amenitiesMode,
      'offset': offset,
      'limit': limit,
    }..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(_uri('/search_availability'), headers: {'Content-Type': 'application/json'}, body: jsonEncode(body));
    if (res.statusCode >= 400) throw Exception('Search failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    final results = ((data['results'] as List?) ?? []).map((e) => (e as Map).cast<String, dynamic>()).toList();
    return {
      'results': results,
      'total': data['total'],
      'next_offset': data['next_offset'],
    };
  }

  // Guest (auth)
  Future<Map<String, dynamic>> createReservation({required String unitId, required String checkIn, required String checkOut, required int guests}) async {
    final res = await http.post(_uri('/reservations'), headers: await _authHeaders(), body: jsonEncode({'unit_id': unitId, 'check_in': checkIn, 'check_out': checkOut, 'guests': guests}));
    if (res.statusCode >= 400) throw Exception('Book failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> myReservations() async {
    final res = await http.get(_uri('/reservations'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw Exception('My reservations failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['reservations'] as List?) ?? []).map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Favorites (auth)
  Future<void> addFavorite(String propertyId) async {
    final res = await http.post(_uri('/properties/$propertyId/favorite'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw Exception('Favorite failed: ${res.body}');
  }

  Future<void> removeFavorite(String propertyId) async {
    final res = await http.delete(_uri('/properties/$propertyId/favorite'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw Exception('Unfavorite failed: ${res.body}');
  }

  Future<List<Map<String, dynamic>>> listFavorites() async {
    final res = await http.get(_uri('/properties/favorites'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw Exception('Favorites failed: ${res.body}');
    return ((jsonDecode(res.body) as List).cast()).map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Reviews
  Future<List<Map<String, dynamic>>> listReviews(String propertyId) async {
    final res = await http.get(_uri('/properties/$propertyId/reviews'));
    if (res.statusCode >= 400) throw Exception('Reviews failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['reviews'] as List?) ?? []).map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> createReview(String propertyId, {required int rating, String? comment}) async {
    final body = {'rating': rating, 'comment': comment}..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(_uri('/properties/$propertyId/reviews'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw Exception('Post review failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
}
