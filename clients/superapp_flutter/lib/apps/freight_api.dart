import 'dart:convert';
import 'package:http/http.dart' as http;
import '../services.dart';

class FreightApi {
  final _tokens = MultiTokenStore();

  Future<Map<String, String>> _authHeaders() =>
      authHeaders('freight', store: _tokens);

  Uri _uri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('freight', path, query: query);

  // Shipper
  Future<Map<String, dynamic>> createLoad({
    required String origin,
    required String destination,
    required int weightKg,
    required int priceCents,
  }) async {
    final res = await http.post(
      _uri('/shipper/loads'),
      headers: await _authHeaders(),
      body: jsonEncode({
        'origin': origin,
        'destination': destination,
        'weight_kg': weightKg,
        'price_cents': priceCents,
      }),
    );
    if (res.statusCode >= 400) {
      throw Exception('Create load failed: ${res.body}');
    }
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> myShipperLoads() async {
    final res = await http.get(
      _uri('/shipper/loads'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('List loads failed: ${res.body}');
    }
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['loads'] as List?) ?? [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  // Carrier
  Future<void> carrierApply({String? companyName}) async {
    final res = await http.post(
      _uri('/carrier/apply'),
      headers: await _authHeaders(),
      body: jsonEncode({'company_name': companyName}),
    );
    if (res.statusCode >= 400) {
      throw Exception('Carrier apply failed: ${res.body}');
    }
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
    final res = await http.get(
      _uri('/carrier/loads/available',
          query: qp.isEmpty ? null : qp),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('Available loads failed: ${res.body}');
    }
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['loads'] as List?) ?? [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<Map<String, dynamic>> acceptLoad(String loadId) async {
    final res = await http.post(
      _uri('/loads/$loadId/accept'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('Accept load failed: ${res.body}');
    }
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> pickupLoad(String loadId) async {
    final res = await http.post(
      _uri('/loads/$loadId/pickup'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('Pickup failed: ${res.body}');
    }
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> inTransitLoad(String loadId) async {
    final res = await http.post(
      _uri('/loads/$loadId/in_transit'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('In transit failed: ${res.body}');
    }
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> deliverLoad(String loadId) async {
    final res = await http.post(
      _uri('/loads/$loadId/deliver'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('Deliver failed: ${res.body}');
    }
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> myLoads() async {
    final res = await http.get(
      _uri('/loads'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('My loads failed: ${res.body}');
    }
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['loads'] as List?) ?? [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  // Tracking
  Future<void> updateCarrierLocation({
    required double lat,
    required double lon,
  }) async {
    final res = await http.put(
      _uri('/carrier/location'),
      headers: await _authHeaders(),
      body: jsonEncode({'lat': lat, 'lon': lon}),
    );
    if (res.statusCode >= 400) {
      throw Exception('Update location failed: ${res.body}');
    }
  }

  Future<Map<String, dynamic>> getLoad(String loadId) async {
    final res = await http.get(
      _uri('/loads/$loadId'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('Get load failed: ${res.body}');
    }
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<void> addPod(String loadId, String url) async {
    final res = await http.post(
      _uri('/loads/$loadId/pod', query: {'url': url}),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('Add POD failed: ${res.body}');
    }
  }

  // Chat
  Future<List<Map<String, dynamic>>> chatList(String loadId) async {
    final res = await http.get(
      _uri('/chats/load/$loadId'),
      headers: await _authHeaders(),
    );
    if (res.statusCode >= 400) {
      throw Exception('Chat list failed: ${res.body}');
    }
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['messages'] as List?) ?? [])
        .cast<dynamic>()
        .map((e) => (e as Map).cast<String, dynamic>())
        .toList();
  }

  Future<Map<String, dynamic>> chatSend(String loadId, String content) async {
    final res = await http.post(
      _uri('/chats/load/$loadId'),
      headers: await _authHeaders(),
      body: jsonEncode({'content': content}),
    );
    if (res.statusCode >= 400) {
      throw Exception('Chat send failed: ${res.body}');
    }
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
}
