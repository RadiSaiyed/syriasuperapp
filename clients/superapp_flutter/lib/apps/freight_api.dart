import 'package:shared_core/shared_core.dart';

import '../services.dart';

class FreightApi {
  static const _service = 'freight';

  Future<Map<String, dynamic>> createLoad({
    required String origin,
    required String destination,
    required int weightKg,
    required int priceCents,
  }) async {
    return await servicePostJson(
      _service,
      '/shipper/loads',
      body: {
        'origin': origin,
        'destination': destination,
        'weight_kg': weightKg,
        'price_cents': priceCents,
      },
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<List<Map<String, dynamic>>> myShipperLoads() async {
    final data = await serviceGetJson(_service, '/shipper/loads');
    return ((data['loads'] as List?) ?? const [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<void> carrierApply({String? companyName}) async {
    await servicePost(
      _service,
      '/carrier/apply',
      body: {'company_name': companyName},
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<List<Map<String, dynamic>>> availableLoads({
    String? origin,
    String? destination,
    int? minWeight,
    int? maxWeight,
  }) async {
    final qp = <String, String>{};
    if (origin != null && origin.isNotEmpty) qp['origin'] = origin;
    if (destination != null && destination.isNotEmpty) qp['destination'] = destination;
    if (minWeight != null) qp['min_weight'] = '$minWeight';
    if (maxWeight != null) qp['max_weight'] = '$maxWeight';
    final data = await serviceGetJson(
      _service,
      '/carrier/loads/available',
      query: qp.isEmpty ? null : qp,
    );
    return ((data['loads'] as List?) ?? const [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<Map<String, dynamic>> acceptLoad(String loadId) async {
    return await servicePostJson(
      _service,
      '/loads/$loadId/accept',
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<Map<String, dynamic>> pickupLoad(String loadId) async {
    return await servicePostJson(
      _service,
      '/loads/$loadId/pickup',
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<Map<String, dynamic>> inTransitLoad(String loadId) async {
    return await servicePostJson(
      _service,
      '/loads/$loadId/in_transit',
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<Map<String, dynamic>> deliverLoad(String loadId) async {
    return await servicePostJson(
      _service,
      '/loads/$loadId/deliver',
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<List<Map<String, dynamic>>> myLoads() async {
    final data = await serviceGetJson(_service, '/loads');
    return ((data['loads'] as List?) ?? const [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<void> updateCarrierLocation({
    required double lat,
    required double lon,
  }) async {
    await servicePutJson(
      _service,
      '/carrier/location',
      body: {'lat': lat, 'lon': lon},
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<Map<String, dynamic>> getLoad(String loadId) async {
    return await serviceGetJson(_service, '/loads/$loadId');
  }

  Future<void> addPod(String loadId, String url) async {
    await servicePost(
      _service,
      '/loads/$loadId/pod',
      query: {'url': url},
      options: const RequestOptions(expectValidationErrors: true),
    );
  }

  Future<List<Map<String, dynamic>>> chatList(String loadId) async {
    final data = await serviceGetJson(_service, '/chats/load/$loadId');
    return ((data['messages'] as List?) ?? const [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<Map<String, dynamic>> chatSend(String loadId, String content) async {
    return await servicePostJson(
      _service,
      '/chats/load/$loadId',
      body: {'content': content},
      options: const RequestOptions(expectValidationErrors: true),
    );
  }
}
