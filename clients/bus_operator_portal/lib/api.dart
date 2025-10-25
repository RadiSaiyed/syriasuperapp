import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}

class Api {
  String baseUrl;
  Api({this.baseUrl = 'http://localhost:8082'});

  Future<void> setBaseUrl(String url) async {
    baseUrl = url;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_base', url);
  }

  static Future<Api> load() async {
    final prefs = await SharedPreferences.getInstance();
    final b = prefs.getString('api_base') ?? 'http://localhost:8082';
    return Api(baseUrl: b);
  }

  Future<Map<String, String>> _authHeaders() async {
    final prefs = await SharedPreferences.getInstance();
    final t = prefs.getString('jwt');
    final h = <String, String>{'Content-Type': 'application/json'};
    if (t != null && t.isNotEmpty) h['Authorization'] = 'Bearer $t';
    return h;
  }

  Future<void> requestOtp(String phone) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/request_otp'),
        headers: {'Content-Type': 'application/json'}, body: jsonEncode({'phone': phone}));
    if (r.statusCode >= 400) throw ApiError('OTP request failed: ${r.body}');
  }

  Future<void> verifyOtp(String phone, String otp, {String? name}) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/verify_otp'),
        headers: {'Content-Type': 'application/json'}, body: jsonEncode({'phone': phone, 'otp': otp, 'name': name}));
    if (r.statusCode >= 400) throw ApiError('Verify failed: ${r.body}');
    final token = (jsonDecode(r.body) as Map<String, dynamic>)['access_token'] as String?;
    if (token == null) throw ApiError('No token');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('jwt', token);
  }

  Future<List<Map<String, dynamic>>> myOperators() async {
    final r = await http.get(Uri.parse('$baseUrl/operators/me'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Operators failed: ${r.body}');
    return ((jsonDecode(r.body) as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> registerOperator(String name, {String? merchantPhone}) async {
    final q = <String, String>{'name': name};
    if (merchantPhone != null && merchantPhone.isNotEmpty) q['merchant_phone'] = merchantPhone;
    final uri = Uri.parse('$baseUrl/operators/register').replace(queryParameters: q);
    final r = await http.post(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Register failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> listTrips(String operatorId) async {
    final r = await http.get(Uri.parse('$baseUrl/operators/$operatorId/trips'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Trips failed: ${r.body}');
    final data = (jsonDecode(r.body) as Map).cast<String, dynamic>();
    return ((data['trips'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> createTrip(String operatorId, Map<String, dynamic> body) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/trips'), headers: await _authHeaders(), body: jsonEncode(body));
    if (r.statusCode >= 400) throw ApiError('Create trip failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> updateTrip(String operatorId, String tripId, Map<String, dynamic> body) async {
    final r = await http.patch(Uri.parse('$baseUrl/operators/$operatorId/trips/$tripId'), headers: await _authHeaders(), body: jsonEncode(body));
    if (r.statusCode >= 400) throw ApiError('Update failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<void> deleteTrip(String operatorId, String tripId) async {
    final r = await http.delete(Uri.parse('$baseUrl/operators/$operatorId/trips/$tripId'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Delete failed: ${r.body}');
  }

  Future<List<Map<String, dynamic>>> listBookings(String operatorId, {String? status, String? phone, DateTime? from, DateTime? to}) async {
    final qp = <String, String>{};
    if (status != null) qp['status'] = status;
    if (phone != null && phone.isNotEmpty) qp['phone'] = phone;
    if (from != null) qp['from'] = from.toUtc().toIso8601String();
    if (to != null) qp['to'] = to.toUtc().toIso8601String();
    final uri = Uri.parse('$baseUrl/operators/$operatorId/bookings').replace(queryParameters: qp.isNotEmpty ? qp : null);
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Bookings failed: ${r.body}');
    final data = (jsonDecode(r.body) as Map).cast<String, dynamic>();
    return ((data['bookings'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<void> confirmBooking(String operatorId, String bookingId) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/bookings/$bookingId/confirm'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Confirm failed: ${r.body}');
  }

  Future<void> cancelBooking(String operatorId, String bookingId) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/bookings/$bookingId/cancel'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Cancel failed: ${r.body}');
  }

  Future<Map<String, dynamic>> summary(String operatorId, {int sinceDays = 7}) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/reports/summary').replace(queryParameters: {'since_days': '$sinceDays'});
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Summary failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> validateTicket(String operatorId, String qr) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/tickets/validate').replace(queryParameters: {'qr': qr});
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Validate failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<void> markBoarded(String operatorId, String bookingId) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/tickets/board').replace(queryParameters: {'booking_id': bookingId});
    final r = await http.post(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Board failed: ${r.body}');
  }

  Future<Map<String, dynamic>> tripSeats(String operatorId, String tripId) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/trips/$tripId/seats');
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Seats failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  // Operator members management (admin)
  Future<List<Map<String, dynamic>>> listMembers(String operatorId) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/members');
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Members failed: ${r.body}');
    final data = (jsonDecode(r.body) as Map).cast<String, dynamic>();
    return ((data['members'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> addMember(String operatorId, {required String phone, String role = 'agent'}) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/members');
    final body = jsonEncode({'phone': phone, 'role': role});
    final r = await http.post(uri, headers: await _authHeaders(), body: body);
    if (r.statusCode >= 400) throw ApiError('Add member failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<void> setMemberRole(String operatorId, String memberId, String role) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/members/$memberId/role');
    final r = await http.post(uri, headers: await _authHeaders(), body: jsonEncode({'role': role}));
    if (r.statusCode >= 400) throw ApiError('Set role failed: ${r.body}');
  }

  Future<void> removeMember(String operatorId, String memberId) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/members/$memberId');
    final r = await http.delete(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Remove member failed: ${r.body}');
  }

  // Trips: clone and manifest
  Future<Map<String, dynamic>> cloneTrip(String operatorId, String tripId, {required DateTime startDate, required DateTime endDate, List<int>? weekdays}) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/trips/$tripId/clone');
    final body = {
      'start_date': DateTime.utc(startDate.year, startDate.month, startDate.day).toIso8601String(),
      'end_date': DateTime.utc(endDate.year, endDate.month, endDate.day).toIso8601String(),
      if (weekdays != null) 'weekdays': weekdays,
    };
    final r = await http.post(uri, headers: await _authHeaders(), body: jsonEncode(body));
    if (r.statusCode >= 400) throw ApiError('Clone failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> manifest(String operatorId, String tripId) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/trips/$tripId/manifest');
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Manifest failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<String> bookingsCsv(String operatorId, {String? status, String? phone, DateTime? from, DateTime? to}) async {
    final qp = <String, String>{};
    if (status != null) qp['status'] = status;
    if (phone != null && phone.isNotEmpty) qp['phone'] = phone;
    if (from != null) qp['from'] = from.toUtc().toIso8601String();
    if (to != null) qp['to'] = to.toUtc().toIso8601String();
    final uri = Uri.parse('$baseUrl/operators/$operatorId/bookings.csv').replace(queryParameters: qp.isNotEmpty ? qp : null);
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('CSV export failed: ${r.body}');
    return r.body;
  }

  // Vehicles
  Future<List<Map<String, dynamic>>> listVehicles(String operatorId) async {
    final r = await http.get(Uri.parse('$baseUrl/operators/$operatorId/vehicles'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Vehicles failed: ${r.body}');
    return ((jsonDecode(r.body) as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> createVehicle(String operatorId, {required String name, required int seatsTotal, int? seatColumns}) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/vehicles'), headers: await _authHeaders(), body: jsonEncode({'name': name, 'seats_total': seatsTotal, 'seat_columns': seatColumns}));
    if (r.statusCode >= 400) throw ApiError('Create vehicle failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> updateVehicle(String operatorId, String vehicleId, {required String name, required int seatsTotal, int? seatColumns}) async {
    final r = await http.patch(Uri.parse('$baseUrl/operators/$operatorId/vehicles/$vehicleId'), headers: await _authHeaders(), body: jsonEncode({'name': name, 'seats_total': seatsTotal, 'seat_columns': seatColumns}));
    if (r.statusCode >= 400) throw ApiError('Update vehicle failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<void> deleteVehicle(String operatorId, String vehicleId) async {
    final r = await http.delete(Uri.parse('$baseUrl/operators/$operatorId/vehicles/$vehicleId'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Delete vehicle failed: ${r.body}');
  }

  // Promos
  Future<List<Map<String, dynamic>>> listPromos(String operatorId) async {
    final r = await http.get(Uri.parse('$baseUrl/operators/$operatorId/promos'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Promos failed: ${r.body}');
    return ((jsonDecode(r.body) as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> createPromo(String operatorId, Map<String, dynamic> body) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/promos'), headers: await _authHeaders(), body: jsonEncode(body));
    if (r.statusCode >= 400) throw ApiError('Create promo failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> updatePromo(String operatorId, String promoId, Map<String, dynamic> body) async {
    final r = await http.patch(Uri.parse('$baseUrl/operators/$operatorId/promos/$promoId'), headers: await _authHeaders(), body: jsonEncode(body));
    if (r.statusCode >= 400) throw ApiError('Update promo failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<void> deletePromo(String operatorId, String promoId) async {
    final r = await http.delete(Uri.parse('$baseUrl/operators/$operatorId/promos/$promoId'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Delete promo failed: ${r.body}');
  }

  // Branches
  Future<List<Map<String, dynamic>>> listBranches(String operatorId) async {
    final r = await http.get(Uri.parse('$baseUrl/operators/$operatorId/branches'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Branches failed: ${r.body}');
    return ((jsonDecode(r.body) as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> createBranch(String operatorId, {required String name, int? commissionBps}) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/branches'), headers: await _authHeaders(), body: jsonEncode({'name': name, 'commission_bps': commissionBps}));
    if (r.statusCode >= 400) throw ApiError('Create branch failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> updateBranch(String operatorId, String branchId, {required String name, int? commissionBps}) async {
    final r = await http.patch(Uri.parse('$baseUrl/operators/$operatorId/branches/$branchId'), headers: await _authHeaders(), body: jsonEncode({'name': name, 'commission_bps': commissionBps}));
    if (r.statusCode >= 400) throw ApiError('Update branch failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<void> deleteBranch(String operatorId, String branchId) async {
    final r = await http.delete(Uri.parse('$baseUrl/operators/$operatorId/branches/$branchId'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Delete branch failed: ${r.body}');
  }

  Future<void> setMemberBranch(String operatorId, String memberId, {String? branchId}) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/members/$memberId/branch'), headers: await _authHeaders(), body: jsonEncode({'branch_id': branchId}));
    if (r.statusCode >= 400) throw ApiError('Set member branch failed: ${r.body}');
  }

  // Settlements & Analytics
  Future<Map<String, dynamic>> settlementsDaily(String operatorId, {DateTime? from, DateTime? to}) async {
    final qp = <String, String>{}; if (from!=null) qp['from']=from.toUtc().toIso8601String(); if (to!=null) qp['to']=to.toUtc().toIso8601String();
    final uri = Uri.parse('$baseUrl/operators/$operatorId/settlements/daily').replace(queryParameters: qp.isNotEmpty? qp : null);
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Settlements failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<String> settlementsDailyCsv(String operatorId, {DateTime? from, DateTime? to}) async {
    final qp = <String, String>{}; if (from!=null) qp['from']=from.toUtc().toIso8601String(); if (to!=null) qp['to']=to.toUtc().toIso8601String();
    final uri = Uri.parse('$baseUrl/operators/$operatorId/settlements/daily.csv').replace(queryParameters: qp.isNotEmpty? qp : null);
    final r = await http.get(uri, headers: await _authHeaders()); if (r.statusCode >= 400) throw ApiError('Settlements CSV failed: ${r.body}'); return r.body;
  }

  Future<Map<String, dynamic>> analyticsRoutes(String operatorId, {int days = 30}) async {
    final uri = Uri.parse('$baseUrl/operators/$operatorId/analytics/routes').replace(queryParameters: {'days': '$days'});
    final r = await http.get(uri, headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Analytics failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  // Webhooks
  Future<List<Map<String, dynamic>>> listWebhooks(String operatorId) async {
    final r = await http.get(Uri.parse('$baseUrl/operators/$operatorId/webhooks'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Webhooks failed: ${r.body}');
    return ((jsonDecode(r.body) as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> createWebhook(String operatorId, {required String url, required String secret, bool active = true}) async {
    final r = await http.post(Uri.parse('$baseUrl/operators/$operatorId/webhooks'), headers: await _authHeaders(), body: jsonEncode({'url': url, 'secret': secret, 'active': active}));
    if (r.statusCode >= 400) throw ApiError('Create webhook failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> updateWebhook(String operatorId, String webhookId, {required String url, required String secret, required bool active}) async {
    final r = await http.patch(Uri.parse('$baseUrl/operators/$operatorId/webhooks/$webhookId'), headers: await _authHeaders(), body: jsonEncode({'url': url, 'secret': secret, 'active': active}));
    if (r.statusCode >= 400) throw ApiError('Update webhook failed: ${r.body}');
    return (jsonDecode(r.body) as Map).cast<String, dynamic>();
  }

  Future<void> deleteWebhook(String operatorId, String webhookId) async {
    final r = await http.delete(Uri.parse('$baseUrl/operators/$operatorId/webhooks/$webhookId'), headers: await _authHeaders());
    if (r.statusCode >= 400) throw ApiError('Delete webhook failed: ${r.body}');
  }

  Future<String> settlementsBranchesCsv(String operatorId, {DateTime? from, DateTime? to}) async {
    final qp = <String, String>{}; if (from!=null) qp['from']=from.toUtc().toIso8601String(); if (to!=null) qp['to']=to.toUtc().toIso8601String();
    final uri = Uri.parse('$baseUrl/operators/$operatorId/settlements/branches.csv').replace(queryParameters: qp.isNotEmpty? qp : null);
    final r = await http.get(uri, headers: await _authHeaders()); if (r.statusCode >= 400) throw ApiError('Branches CSV failed: ${r.body}'); return r.body;
  }
}
