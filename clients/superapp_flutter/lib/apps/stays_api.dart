import 'package:shared_core/shared_core.dart';

import '../services.dart';

class StaysApi {
  static const _service = 'stays';

  Future<List<Map<String, dynamic>>> listProperties({
    String? city,
    String? type,
    String? q,
  }) async {
    final qp = <String, String>{};
    if (city != null && city.isNotEmpty) qp['city'] = city;
    if (type != null && type.isNotEmpty) qp['type'] = type;
    if (q != null && q.isNotEmpty) qp['q'] = q;
    final response = await serviceGetJsonList(
      'superapp',
      '/v1/stays/properties',
      query: qp.isEmpty ? null : qp,
      options: const RequestOptions(cacheTtl: Duration(minutes: 10), staleIfOffline: true),
    );
    return response
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<Map<String, dynamic>> getProperty(String id) async {
    return await serviceGetJson('superapp', '/v1/stays/properties/$id', options: const RequestOptions(cacheTtl: Duration(minutes: 10), staleIfOffline: true));
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

    final data = await servicePostJson(
      _service,
      '/search_availability',
      body: body,
      options: const RequestOptions(expectValidationErrors: true),
    );
    final results = ((data['results'] as List?) ?? const [])
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
    return {
      'results': results,
      'total': data['total'],
      'next_offset': data['next_offset'],
    };
  }

  Future<Map<String, dynamic>> createReservation({
    required String unitId,
    required String checkIn,
    required String checkOut,
    required int guests,
  }) async {
    return await servicePostJson(
      _service,
      '/reservations',
      body: {
        'unit_id': unitId,
        'check_in': checkIn,
        'check_out': checkOut,
        'guests': guests,
      },
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<List<Map<String, dynamic>>> myReservations() async {
    final data = await serviceGetJson(_service, '/reservations');
    return ((data['reservations'] as List?) ?? const [])
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<void> addFavorite(String propertyId) async {
    await servicePost(
      _service,
      '/properties/$propertyId/favorite',
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<void> removeFavorite(String propertyId) async {
    await serviceDelete(
      _service,
      '/properties/$propertyId/favorite',
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<List<Map<String, dynamic>>> listFavorites() async {
    final response = await serviceGetJsonList(
      _service,
      '/properties/favorites',
      options: const RequestOptions(cacheTtl: Duration(minutes: 10), staleIfOffline: true),
    );
    return response
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<List<Map<String, dynamic>>> listReviews(String propertyId) async {
    final data = await serviceGetJson(_service, '/properties/$propertyId/reviews');
    return ((data['reviews'] as List?) ?? const [])
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<Map<String, dynamic>> createReview(
    String propertyId, {
    required int rating,
    String? comment,
  }) async {
    final body = {
      'rating': rating,
      'comment': comment,
    }..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    return await servicePostJson(
      _service,
      '/properties/$propertyId/reviews',
      body: body,
      options: const RequestOptions(expectValidationErrors: true),
    );
  }
}
