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

  // Trips
  Future<List<Map<String, dynamic>>> searchTrips({required String origin, required String destination, required DateTime date}) async {
    final dateStr = DateFormat('yyyy-MM-dd').format(date);
    final res = await http.post(Uri.parse('$baseUrl/trips/search'), headers: await _authHeaders(), body: jsonEncode({'origin': origin, 'destination': destination, 'date': dateStr}));
    if (res.statusCode >= 400) throw ApiError('Search failed: ${res.body}');
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    final trips = (data['trips'] as List? ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
    return trips;
  }

  // Bookings
  Future<Map<String, dynamic>> createBooking({required String tripId, int seatsCount = 1, List<int>? seatNumbers, String? promoCode}) async {
    final body = {'trip_id': tripId, 'seats_count': seatsCount};
    if (seatNumbers != null && seatNumbers.isNotEmpty) body['seat_numbers'] = seatNumbers;
    if (promoCode != null && promoCode.trim().isNotEmpty) body['promo_code'] = promoCode.trim();
    final res = await http.post(Uri.parse('$baseUrl/bookings'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Booking failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> listBookings() async {
    final res = await http.get(Uri.parse('$baseUrl/bookings'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List bookings failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['bookings'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<void> cancelBooking(String bookingId) async {
    final res = await http.post(Uri.parse('$baseUrl/bookings/$bookingId/cancel'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Cancel failed: ${res.body}');
  }

  Future<Map<String, dynamic>> tripSeats(String tripId) async {
    final res = await http.get(Uri.parse('$baseUrl/trips/$tripId/seats'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Trip seats failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> bookingTicket(String bookingId) async {
    final res = await http.get(Uri.parse('$baseUrl/bookings/$bookingId/ticket'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Ticket failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
