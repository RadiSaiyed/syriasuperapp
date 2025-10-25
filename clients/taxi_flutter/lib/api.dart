import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class TokenStore {
  static const _k = 'access_token';
  Future<String?> getToken() async =>
      (await SharedPreferences.getInstance()).getString(_k);
  Future<void> setToken(String token) async =>
      (await SharedPreferences.getInstance()).setString(_k, token);
  Future<void> clear() async =>
      (await SharedPreferences.getInstance()).remove(_k);
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
  // NOTE: OTP/phone-based auth is disabled for test login.
  // Keeping methods commented for future reference.
  // Future<void> requestOtp(String phone) async {
  //   final res = await http.post(Uri.parse('$baseUrl/auth/request_otp'),
  //       headers: _baseHeaders(), body: jsonEncode({'phone': phone}));
  //   if (res.statusCode >= 400)
  //     throw ApiError('OTP request failed: ${res.body}');
  // }

  // Future<void> verifyOtp(
  //     {required String phone, required String otp, String? name}) async {
  //   final res = await http.post(Uri.parse('$baseUrl/auth/verify_otp'),
  //       headers: _baseHeaders(),
  //       body: jsonEncode({'phone': phone, 'otp': otp, 'name': name}));
  //   if (res.statusCode >= 400) throw ApiError('OTP verify failed: ${res.body}');
  //   final token = (jsonDecode(res.body) as Map<String, dynamic>)['access_token']
  //       as String?;
  //   if (token == null) throw ApiError('No token');
  //   await tokenStore.setToken(token);
  // }

  Future<void> devLogin({required String username, required String password}) async {
    final res = await http.post(Uri.parse('$baseUrl/auth/dev_login'),
        headers: _baseHeaders(),
        body: jsonEncode({'username': username, 'password': password}));
    if (res.statusCode >= 400) {
      throw ApiError('Login failed: ${res.body}');
    }
    final token = (jsonDecode(res.body) as Map<String, dynamic>)['access_token'] as String?;
    if (token == null || token.isEmpty) throw ApiError('No token');
    await tokenStore.setToken(token);
  }

  // Rider app only — driver APIs removed (moved to taxi_driver_flutter)

  // Rides
  Future<Map<String, dynamic>> requestRide(
      {required double pickupLat,
      required double pickupLon,
      required double dropLat,
      required double dropLon,
      String? rideClass,
      bool? prepay,
      String? forName,
      String? forPhone,
      String? payMode,
      List<Map<String, dynamic>>? stops,
      String? promoCode}) async {
    final Map<String, dynamic> body = {
      'pickup_lat': pickupLat,
      'pickup_lon': pickupLon,
      'dropoff_lat': dropLat,
      'dropoff_lon': dropLon,
    };
    if (rideClass != null && rideClass.isNotEmpty) {
      body['ride_class'] = rideClass;
    }
    if (prepay != null) {
      body['prepay'] = prepay;
    }
    if (forName != null && forName.trim().isNotEmpty) {
      body['for_name'] = forName.trim();
    }
    if (forPhone != null && forPhone.trim().isNotEmpty) {
      body['for_phone'] = forPhone.trim();
    }
    if (payMode != null && payMode.trim().isNotEmpty) {
      body['pay_mode'] = payMode.trim();
    }
    if (stops != null && stops.isNotEmpty) {
      body['stops'] = stops;
    }
    if (promoCode != null && promoCode.trim().isNotEmpty) {
      body['promo_code'] = promoCode.trim();
    }
    final res = await http.post(Uri.parse('$baseUrl/rides/request'),
        headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) {
      throw ApiError('Ride request failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> quoteRide(
      {required double pickupLat,
      required double pickupLon,
      required double dropLat,
      required double dropLon,
      String? rideClass,
      List<Map<String, dynamic>>? stops,
      String? promoCode}) async {
    final Map<String, dynamic> body = {
      'pickup_lat': pickupLat,
      'pickup_lon': pickupLon,
      'dropoff_lat': dropLat,
      'dropoff_lon': dropLon,
    };
    if (rideClass != null && rideClass.isNotEmpty) {
      body['ride_class'] = rideClass;
    }
    if (stops != null && stops.isNotEmpty) {
      body['stops'] = stops;
    }
    if (promoCode != null && promoCode.trim().isNotEmpty) {
      body['promo_code'] = promoCode.trim();
    }
    final res = await http.post(Uri.parse('$baseUrl/rides/quote'),
        headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) {
      throw ApiError('Quote failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> rideAccept(String rideId) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/accept'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Ride accept failed: ${res.body}');
    }
  }

  Future<void> rideStart(String rideId) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/start'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Ride start failed: ${res.body}');
    }
  }

  Future<Map<String, dynamic>> rideComplete(String rideId) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/complete'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Ride complete failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> myRides() async {
    final res = await http.get(Uri.parse('$baseUrl/rides'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Rides failed: ${res.body}');
    }
    return ((jsonDecode(res.body) as Map<String, dynamic>)['rides'] as List?) ??
        [];
  }

  Future<Map<String, dynamic>> getRide(String rideId) async {
    final res = await http.get(Uri.parse('$baseUrl/rides/$rideId'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Ride get failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> cancelRideByRider(String rideId, {String? reason}) async {
    final res = await http.post(
        Uri.parse('$baseUrl/rides/$rideId/cancel_by_rider'),
        headers: await _authHeaders(),
        body: jsonEncode({'reason': reason}));
    if (res.statusCode >= 400) {
      throw ApiError('Cancel failed: ${res.body}');
    }
  }

  Future<void> rateRide(String rideId,
      {required int rating, String? comment}) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/rate'),
        headers: await _authHeaders(),
        body: jsonEncode({'rating': rating, 'comment': comment}));
    if (res.statusCode >= 400) {
      throw ApiError('Rate failed: ${res.body}');
    }
  }

  Future<List<Map<String, dynamic>>> listRides({int limit = 50, int offset = 0}) async {
    final uri = Uri.parse('$baseUrl/rides').replace(queryParameters: {
      'limit': '$limit',
      'offset': '$offset',
    });
    final res = await http.get(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Rides list failed: ${res.body}');
    }
    final js = jsonDecode(res.body) as Map<String, dynamic>;
    final items = (js['items'] as List?)?.cast<Map<String, dynamic>>() ?? <Map<String, dynamic>>[];
    return items;
  }

  // Driver extras
  // Rider app only — driver profile/ratings/earnings removed

  // Maps autocomplete
  Future<Map<String, dynamic>> getWalletBalance() async {
    final res = await http.get(Uri.parse('$baseUrl/wallet/balance'), headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Wallet balance failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> mapsAutocomplete(String q, {int limit = 5, String? lang}) async {
    final uri = Uri.parse('$baseUrl/maps/autocomplete')
        .replace(queryParameters: {
      'q': q,
      'limit': '$limit',
      if (lang != null) 'lang': lang,
    });
    final res = await http.get(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Autocomplete failed: ${res.body}');
    }
    final js = jsonDecode(res.body) as Map<String, dynamic>;
    return js['items'] as List<dynamic>? ?? [];
  }

  Future<Map<String, dynamic>> mapsReverse({required double lat, required double lon, String? lang}) async {
    final uri = Uri.parse('$baseUrl/maps/reverse').replace(queryParameters: {
      'lat': lat.toStringAsFixed(6),
      'lon': lon.toStringAsFixed(6),
      if (lang != null) 'lang': lang,
    });
    final res = await http.get(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Reverse geocode failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // Push register/unregister
  Future<void> pushRegister({required String token, required String platform, String? appMode}) async {
    final body = {
      'token': token,
      'platform': platform,
      if (appMode != null) 'app_mode': appMode,
    };
    final res = await http.post(Uri.parse('$baseUrl/push/register'),
        headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) {
      throw ApiError('Push register failed: ${res.body}');
    }
  }

  Future<void> pushUnregister({required String token}) async {
    final res = await http.post(Uri.parse('$baseUrl/push/unregister'),
        headers: await _authHeaders(), body: jsonEncode({'token': token}));
    if (res.statusCode >= 400) {
      throw ApiError('Push unregister failed: ${res.body}');
    }
  }

  // Rider app only — taxi wallet (driver) removed

  // Favorites
  Future<List<dynamic>> favoritesList() async {
    final res = await http.get(Uri.parse('$baseUrl/favorites'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Favorites failed: ${res.body}');
    }
    return jsonDecode(res.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> favoritesCreate(
      {required String label, required double lat, required double lon}) async {
    final res = await http.post(Uri.parse('$baseUrl/favorites'),
        headers: await _authHeaders(),
        body: jsonEncode({'label': label, 'lat': lat, 'lon': lon}));
    if (res.statusCode >= 400) {
      throw ApiError('Create favorite failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> favoritesDelete(String favId) async {
    final res = await http.delete(Uri.parse('$baseUrl/favorites/$favId'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) {
      throw ApiError('Delete favorite failed: ${res.body}');
    }
  }

  // Schedule
  Future<Map<String, dynamic>> scheduleRide(
      {required double pickupLat,
      required double pickupLon,
      required double dropLat,
      required double dropLon,
      DateTime? scheduledFor,
      List<Map<String, dynamic>>? stops,
      String? promoCode}) async {
    scheduledFor ??= DateTime.now().add(const Duration(minutes: 15));
    final Map<String, dynamic> body = {
      'pickup_lat': pickupLat,
      'pickup_lon': pickupLon,
      'dropoff_lat': dropLat,
      'dropoff_lon': dropLon,
      'scheduled_for': scheduledFor.toUtc().toIso8601String(),
    };
    if (stops != null && stops.isNotEmpty) {
      body['stops'] = stops;
    }
    if (promoCode != null && promoCode.trim().isNotEmpty) {
      body['promo_code'] = promoCode.trim();
    }
    final res = await http.post(Uri.parse('$baseUrl/rides/schedule'),
        headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) {
      throw ApiError('Schedule failed: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> dispatchScheduled({int windowMinutes = 10}) async {
    final res = await http.post(
        Uri.parse(
            '$baseUrl/rides/dispatch_scheduled?window_minutes=$windowMinutes'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Dispatch failed: ${res.body}');
  }

  Future<List<Map<String, dynamic>>> scheduledList() async {
    final res = await http.get(Uri.parse('$baseUrl/rides/scheduled'), headers: await _authHeaders());
    if (res.statusCode == 401 || res.statusCode == 403) throw ApiError('Unauthorized');
    if (res.statusCode >= 400) throw ApiError('Scheduled list failed: ${res.body}');
    final js = jsonDecode(res.body) as Map<String, dynamic>;
    return (js['scheduled'] as List).cast<Map<String, dynamic>>();
  }

  Future<void> scheduledCancel(String id) async {
    final res = await http.delete(Uri.parse('$baseUrl/rides/scheduled/$id'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Cancel scheduled failed: ${res.body}');
  }

  Future<void> favoritesUpdate(String id, String label) async {
    final res = await http.put(Uri.parse('$baseUrl/favorites/$id'), headers: await _authHeaders(), body: jsonEncode({'label': label}));
    if (res.statusCode >= 400) throw ApiError('Rename favorite failed: ${res.body}');
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
