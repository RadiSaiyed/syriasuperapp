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

  // Billers
  Future<List<Map<String, dynamic>>> listBillers({String? category}) async {
    final uri = category != null && category.isNotEmpty
        ? Uri.parse('$baseUrl/billers').replace(queryParameters: {'category': category})
        : Uri.parse('$baseUrl/billers');
    final res = await http.get(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List billers failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Accounts
  Future<List<Map<String, dynamic>>> listAccounts() async {
    final res = await http.get(Uri.parse('$baseUrl/accounts'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List accounts failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> linkAccount({required String billerId, required String accountRef, String? alias}) async {
    final res = await http.post(Uri.parse('$baseUrl/accounts/link'), headers: await _authHeaders(), body: jsonEncode({'biller_id': billerId, 'account_ref': accountRef, 'alias': alias}));
    if (res.statusCode >= 400) throw ApiError('Link account failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> updateAccountAlias({required String accountId, String? alias}) async {
    final uri = Uri.parse('$baseUrl/accounts/$accountId').replace(queryParameters: {'alias': alias ?? ''});
    final res = await http.put(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Update account failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<void> deleteAccount(String accountId) async {
    final res = await http.delete(Uri.parse('$baseUrl/accounts/$accountId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Delete account failed: ${res.body}');
  }

  // Bills
  Future<List<Map<String, dynamic>>> refreshBills(String accountId) async {
    final res = await http.post(Uri.parse('$baseUrl/bills/refresh?account_id=$accountId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Refresh bills failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['bills'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> listBills() async {
    final res = await http.get(Uri.parse('$baseUrl/bills'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List bills failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['bills'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> payBill(String billId) async {
    final res = await http.post(Uri.parse('$baseUrl/bills/$billId/pay'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Pay bill failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  // Topups
  Future<Map<String, dynamic>> createTopup({required String operatorBillerId, required String targetPhone, required int amountCents, String? promoCode}) async {
    final body = {'operator_biller_id': operatorBillerId, 'target_phone': targetPhone, 'amount_cents': amountCents};
    if (promoCode != null && promoCode.trim().isNotEmpty) body['promo_code'] = promoCode.trim();
    final res = await http.post(Uri.parse('$baseUrl/topups'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Create topup failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> listTopups() async {
    final res = await http.get(Uri.parse('$baseUrl/topups'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List topups failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['topups'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
