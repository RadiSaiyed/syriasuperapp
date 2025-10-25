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

  // Driver
  Future<void> driverApply({String? make, String? plate}) async {
    final res = await http.post(Uri.parse('$baseUrl/driver/apply'),
        headers: await _authHeaders(),
        body: jsonEncode({'vehicle_make': make, 'vehicle_plate': plate}));
    if (res.statusCode >= 400)
      throw ApiError('Driver apply failed: ${res.body}');
  }

  Future<void> driverStatus(String status) async {
    final res = await http.put(Uri.parse('$baseUrl/driver/status'),
        headers: await _authHeaders(), body: jsonEncode({'status': status}));
    if (res.statusCode >= 400)
      throw ApiError('Driver status failed: ${res.body}');
  }

  Future<void> driverLocation(
      {required double lat, required double lon}) async {
    final res = await http.put(Uri.parse('$baseUrl/driver/location'),
        headers: await _authHeaders(),
        body: jsonEncode({'lat': lat, 'lon': lon}));
    if (res.statusCode >= 400)
      throw ApiError('Driver location failed: ${res.body}');
  }

  Future<void> rideAccept(String rideId) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/accept'),
        headers: await _authHeaders());
    if (res.statusCode >= 400)
      throw ApiError('Ride accept failed: ${res.body}');
  }

  Future<void> rideStart(String rideId) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/start'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Ride start failed: ${res.body}');
  }

  Future<Map<String, dynamic>> rideComplete(String rideId) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/complete'),
        headers: await _authHeaders());
    if (res.statusCode >= 400)
      throw ApiError('Ride complete failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> callRider(String rideId) async {
    final res = await http.post(Uri.parse('$baseUrl/rides/$rideId/call_rider'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Call rider failed: ${res.body}');
  }

  Future<List<dynamic>> myRides() async {
    final res = await http.get(Uri.parse('$baseUrl/rides'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Rides failed: ${res.body}');
    return ((jsonDecode(res.body) as Map<String, dynamic>)['rides'] as List?) ?? [];
  }

  Future<Map<String, dynamic>> getRide(String rideId) async {
    final res = await http.get(Uri.parse('$baseUrl/rides/$rideId'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Ride get failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> driverProfile() async {
    final res = await http.get(Uri.parse('$baseUrl/driver/profile'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Profile failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> driverRatings() async {
    final res = await http.get(Uri.parse('$baseUrl/driver/ratings'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Ratings failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> driverEarnings({int days = 7}) async {
    final res = await http.get(Uri.parse('$baseUrl/driver/earnings?days=$days'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Earnings failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> pushRegister({required String token, required String platform, String? appMode}) async {
    final body = {
      'token': token,
      'platform': platform,
      if (appMode != null) 'app_mode': appMode,
    };
    final res = await http.post(Uri.parse('$baseUrl/push/register'),
        headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Push register failed: ${res.body}');
  }

  Future<void> pushUnregister({required String token}) async {
    final res = await http.post(Uri.parse('$baseUrl/push/unregister'),
        headers: await _authHeaders(), body: jsonEncode({'token': token}));
    if (res.statusCode >= 400) throw ApiError('Push unregister failed: ${res.body}');
  }

  // Taxi wallet (Driver)
  Future<Map<String, dynamic>> taxiWalletGet() async {
    final res = await http.get(Uri.parse('$baseUrl/driver/taxi_wallet'),
        headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Taxi wallet failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> taxiWalletTopup(int amountCents) async {
    final res = await http.post(Uri.parse('$baseUrl/driver/taxi_wallet/topup'),
        headers: await _authHeaders(),
        body: jsonEncode({'amount_cents': amountCents}));
    if (res.statusCode >= 400) throw ApiError('Topup failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> taxiWalletWithdraw(int amountCents) async {
    final res = await http.post(Uri.parse('$baseUrl/driver/taxi_wallet/withdraw'),
        headers: await _authHeaders(),
        body: jsonEncode({'amount_cents': amountCents}));
    if (res.statusCode >= 400) throw ApiError('Withdraw failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
