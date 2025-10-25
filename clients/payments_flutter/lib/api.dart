import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:crypto/crypto.dart' as crypto;
import 'package:flutter/foundation.dart' show kIsWeb;

class TokenStore {
  static const _k = 'access_token';
  final FlutterSecureStorage _sec = const FlutterSecureStorage();

  Future<String?> getToken() async {
    try {
      if (!kIsWeb) {
        final v = await _sec.read(key: _k);
        if (v != null && v.isNotEmpty) return v;
      }
    } catch (_) {}
    final p = await SharedPreferences.getInstance();
    return p.getString(_k);
  }

  Future<void> setToken(String token) async {
    bool ok = false;
    try {
      if (!kIsWeb) {
        await _sec.write(key: _k, value: token, aOptions: const AndroidOptions(encryptedSharedPreferences: true));
        ok = true;
      }
    } catch (_) {}
    if (!ok) {
      final p = await SharedPreferences.getInstance();
      await p.setString(_k, token);
    }
  }

  Future<void> clear() async {
    try { if (!kIsWeb) await _sec.delete(key: _k); } catch (_) {}
    final p = await SharedPreferences.getInstance();
    await p.remove(_k);
  }
}

class ApiClient {
  String baseUrl;
  final TokenStore tokenStore;
  String? _adminToken;
  // Audit toggle (compile-time)
  static const bool kAuditEnabled = bool.fromEnvironment('AUDIT_ENABLED', defaultValue: false);
  // Defaults for resiliency
  final Duration _defaultTimeout = const Duration(seconds: 12);
  final int _defaultRetriesGet = 2; // GETs are safe to retry
  final int _defaultRetriesIdem = 2; // For idempotent POSTs
  static const bool kEnforceTls = bool.fromEnvironment('ENFORCE_TLS', defaultValue: false);
  static const String kPinSha256 = String.fromEnvironment('PIN_SHA256', defaultValue: '');
  bool _pinChecked = false;

  ApiClient({required this.baseUrl, required this.tokenStore});

  Map<String, String> _baseHeaders([String? idempotencyKey]) {
    final h = <String, String>{'Content-Type': 'application/json'};
    if (idempotencyKey != null) {
      h['Idempotency-Key'] = idempotencyKey;
    }
    return h;
  }

  Future<Map<String, String>> _authHeaders([String? idempotencyKey]) async {
    final token = await tokenStore.getToken();
    final h = _baseHeaders(idempotencyKey);
    if (token != null) {
      h['Authorization'] = 'Bearer $token';
    }
    if (_adminToken != null && _adminToken!.isNotEmpty) {
      h['X-Admin-Token'] = _adminToken!;
    }
    return h;
  }

  // Resiliency helpers: timeout + retry with backoff on transient errors
  Future<http.Response> _withRetry(
    Future<http.Response> Function() send, {
    int retries = 0,
    Duration? timeout,
  }) async {
    int attempt = 0;
    final to = timeout ?? _defaultTimeout;
    while (true) {
      attempt++;
      try {
        final res = await send().timeout(to);
        if (retries > 0 && (res.statusCode == 502 || res.statusCode == 503 || res.statusCode == 504)) {
          await _backoff(attempt);
          retries--;
          continue;
        }
        return res;
      } on TimeoutException {
        if (retries <= 0) {
          throw ApiError('Network timeout. Please try again.');
        }
        await _backoff(attempt);
        retries--;
      } on SocketException {
        if (retries <= 0) {
          throw ApiError('No internet connection. Please check your network.');
        }
        await _backoff(attempt);
        retries--;
      }
    }
  }

  Future<void> _backoff(int attempt) async {
    final baseMs = 400 * (1 << (attempt - 1));
    final jitter = (baseMs * 0.2).round();
    final delay = Duration(milliseconds: baseMs + (DateTime.now().millisecond % (jitter + 1)));
    await Future.delayed(delay);
  }

  Future<http.Response> _get(String path, {Map<String, String>? query}) async {
    await _preflight();
    final url = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    return _withRetry(() async => await http.get(url, headers: await _authHeaders()), retries: _defaultRetriesGet);
  }

  Future<http.Response> _post(String path, {Object? body, String? idempotencyKey, int retries = 0}) async {
    await _preflight();
    final url = Uri.parse('$baseUrl$path');
    return _withRetry(
        () async => await http.post(url, headers: await _authHeaders(idempotencyKey), body: body),
        retries: retries);
  }

  Future<void> _preflight() async {
    if (kEnforceTls) {
      if (baseUrl.startsWith('http://')) {
        throw ApiError('Insecure HTTP blocked by ENFORCE_TLS');
      }
    }
    if (!_pinChecked && kPinSha256.isNotEmpty) {
      try {
        final host = Uri.parse(baseUrl).host;
        final port = Uri.parse(baseUrl).port == 0 ? 443 : Uri.parse(baseUrl).port;
        final socket = await SecureSocket.connect(host, port, timeout: const Duration(seconds: 5));
        final cert = socket.peerCertificate;
        await socket.close();
        if (cert == null) throw Exception('No certificate');
        final der = cert.der;
        final sha256 = sha256of(der);
        if (sha256.toLowerCase() != kPinSha256.toLowerCase()) {
          throw ApiError('Certificate pin mismatch');
        }
        _pinChecked = true;
      } catch (e) {
        throw ApiError('TLS pinning failed: $e');
      }
    }
  }

  String sha256of(List<int> der) => crypto.sha256.convert(der).toString();

  // --- Compliance & Audit ---
  Future<void> audit(String type, Map<String, dynamic> details) async {
    if (!kAuditEnabled) return;
    try {
      final body = jsonEncode({
        'type': type,
        'ts': DateTime.now().toUtc().toIso8601String(),
        'details': details,
      });
      await _post('/compliance/audit', body: body, retries: 1);
    } catch (_) {
      // Best-effort; ignore failures
    }
  }

  Future<Map<String, dynamic>?> limitsSummary() async {
    try {
      final res = await _get('/limits/summary');
      if (res.statusCode >= 400) return null;
      return (jsonDecode(res.body) as Map).cast<String, dynamic>();
    } catch (_) {
      return null;
    }
  }

  // Admin token handling
  static const _adminKey = 'admin_token';
  Future<void> setAdminToken(String? token) async {
    _adminToken = token;
    final p = await SharedPreferences.getInstance();
    if (token == null || token.isEmpty) {
      await p.remove(_adminKey);
    } else {
      await p.setString(_adminKey, token);
    }
  }

  Future<String?> getAdminToken() async {
    if (_adminToken != null) return _adminToken;
    final p = await SharedPreferences.getInstance();
    _adminToken = p.getString(_adminKey);
    return _adminToken;
  }

  // Auth
  Future<void> requestOtp(String phone) async {
    final url = Uri.parse('$baseUrl/auth/request_otp');
    final res = await _withRetry(
        () async => await http.post(url, headers: _baseHeaders(), body: jsonEncode({'phone': phone})),
        retries: 1);
    if (res.statusCode >= 400) {
      throw ApiError('OTP request failed: ${res.body}');
    }
  }

  Future<void> verifyOtp({required String phone, required String otp, String? name}) async {
    final url = Uri.parse('$baseUrl/auth/verify_otp');
    final res = await _withRetry(
        () async => await http.post(url, headers: _baseHeaders(), body: jsonEncode({'phone': phone, 'otp': otp, 'name': name})),
        retries: 1);
    if (res.statusCode >= 400) {
      throw ApiError('OTP verify failed: ${res.body}');
    }
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    final token = data['access_token'] as String?;
    if (token == null) throw ApiError('No token in response');
    await tokenStore.setToken(token);
  }

  // Wallet
  Future<Map<String, dynamic>> getWallet() async {
    final res = await _get('/wallet');
    if (res.statusCode >= 400) throw ApiError('Wallet failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> topup({required int amountCents, required String idempotencyKey}) async {
    final res = await _post('/wallet/topup',
        body: jsonEncode({'amount_cents': amountCents, 'idempotency_key': idempotencyKey}),
        idempotencyKey: idempotencyKey,
        retries: _defaultRetriesIdem);
    if (res.statusCode >= 400) throw ApiError('Topup failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> transfer({required String toPhone, required int amountCents, required String idempotencyKey, String? memo}) async {
    final body = <String, dynamic>{'to_phone': toPhone, 'amount_cents': amountCents, 'idempotency_key': idempotencyKey};
    if (memo != null && memo.isNotEmpty) body['memo'] = memo;
    final res = await _post('/wallet/transfer',
        body: jsonEncode(body),
        idempotencyKey: idempotencyKey,
        retries: _defaultRetriesIdem);
    if (res.statusCode >= 400) throw ApiError('Transfer failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> transactions() async {
    final res = await _get('/wallet/transactions');
    if (res.statusCode >= 400) throw ApiError('Transactions failed: ${res.body}');
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return (data['entries'] as List<dynamic>?) ?? [];
  }

  // Merchant + QR
  Future<void> devBecomeMerchant() async {
    final res = await _post('/payments/dev/become_merchant');
    if (res.statusCode >= 400) throw ApiError('Become merchant failed: ${res.body}');
  }

  Future<Map<String, dynamic>> merchantStatus() async {
    final res = await _get('/payments/merchant/status');
    if (res.statusCode >= 400) throw ApiError('Merchant status failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> applyMerchant() async {
    final res = await _post('/payments/merchant/apply');
    if (res.statusCode >= 400) throw ApiError('Merchant apply failed: ${res.body}');
  }

  Future<Map<String, dynamic>> createQr({required int amountCents, String currencyCode = 'SYP'}) async {
    final res = await _post('/payments/merchant/qr', body: jsonEncode({'amount_cents': amountCents, 'currency_code': currencyCode}));
    if (res.statusCode >= 400) throw ApiError('Create QR failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // Vouchers (Top-up)
  Future<Map<String, dynamic>> createVoucher({required int amountSyp, String currencyCode = 'SYP'}) async {
    final res = await _post('/vouchers', body: jsonEncode({'amount_syp': amountSyp, 'currency_code': currencyCode}));
    if (res.statusCode >= 400) throw ApiError('Create voucher failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> listVouchers() async {
    final res = await _get('/vouchers');
    if (res.statusCode >= 400) throw ApiError('List vouchers failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    final items = (data['items'] as List? ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
    return items;
  }

  Future<Map<String, dynamic>> redeemVoucher({required String code}) async {
    final res = await _post('/vouchers/$code/redeem');
    if (res.statusCode >= 400) throw ApiError('Redeem failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  // Admin: vouchers bulk
  Future<List<Map<String, dynamic>>> adminVouchersBulk({required int amountSyp, required int count, String? prefix}) async {
    final url = Uri.parse('$baseUrl/vouchers/admin/vouchers/bulk');
    final Map<String, dynamic> body = {'amount_syp': amountSyp, 'count': count};
    if (prefix != null && prefix.isNotEmpty) body['prefix'] = prefix;
    final res = await _withRetry(() async => await http.post(url, headers: await _authHeaders(), body: jsonEncode(body)), retries: 1);
    if (res.statusCode >= 400) throw ApiError('Bulk create failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['items'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> adminVouchersSummary({bool createdByMe = true}) async {
    final res = await _get('/vouchers/admin/summary', query: createdByMe ? {'created_by': 'me'} : null);
    if (res.statusCode >= 400) throw ApiError('Summary failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> adminVouchersList({String? status, String? prefix, bool createdByMe = true, int limit = 200}) async {
    final qp = <String, String>{};
    if (status != null && status.isNotEmpty) qp['status'] = status;
    if (prefix != null && prefix.isNotEmpty) qp['prefix'] = prefix;
    if (createdByMe) qp['created_by'] = 'me';
    qp['limit'] = '$limit';
    final res = await _get('/vouchers/admin/list', query: qp);
    if (res.statusCode >= 400) throw ApiError('List failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['items'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> adminVoucherRevoke(String code) async {
    final res = await _post('/vouchers/admin/$code/revoke');
    if (res.statusCode >= 400) throw ApiError('Revoke failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }

  Future<String> adminVouchersExport({String? status, String? prefix, bool createdByMe = true}) async {
    final qp = <String, String>{};
    if (status != null && status.isNotEmpty) qp['status'] = status;
    if (prefix != null && prefix.isNotEmpty) qp['prefix'] = prefix;
    if (createdByMe) qp['created_by'] = 'me';
    final res = await _get('/vouchers/admin/export', query: qp);
    if (res.statusCode >= 400) throw ApiError('Export failed: ${res.body}');
    return res.body;
  }

  Future<List<Map<String, dynamic>>> adminFeesEntries({int limit = 200}) async {
    final res = await _get('/vouchers/admin/fees/entries', query: {'limit': '$limit'});
    if (res.statusCode >= 400) throw ApiError('Fees entries failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['items'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  Future<Map<String, dynamic>> payQr({required String code, required String idempotencyKey}) async {
    final res = await _post('/payments/merchant/pay',
        body: jsonEncode({'code': code, 'idempotency_key': idempotencyKey}),
        idempotencyKey: idempotencyKey,
        retries: _defaultRetriesIdem);
    if (res.statusCode >= 400) throw ApiError('Pay QR failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // Links
  Future<Map<String, dynamic>> createLink({int? amountCents, int? expiresInMinutes}) async {
    final body = <String, dynamic>{};
    if (amountCents != null) body['amount_cents'] = amountCents;
    if (expiresInMinutes != null) body['expires_in_minutes'] = expiresInMinutes;
    final res = await _post('/payments/links', body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Create link failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> payLink({required String code, required String idempotencyKey, int? amountCents}) async {
    final body = <String, dynamic>{'code': code, 'idempotency_key': idempotencyKey};
    if (amountCents != null) body['amount_cents'] = amountCents;
    final res = await _post('/payments/links/pay',
        body: jsonEncode(body), idempotencyKey: idempotencyKey, retries: _defaultRetriesIdem);
    if (res.statusCode >= 400) throw ApiError('Pay link failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // Subscriptions
  Future<List<dynamic>> listSubscriptions() async {
    final res = await _get('/subscriptions');
    if (res.statusCode >= 400) throw ApiError('List subscriptions failed: ${res.body}');
    return jsonDecode(res.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> createSubscription({required String merchantPhone, required int amountCents, int intervalDays = 30}) async {
    final res = await _post('/subscriptions',
        body: jsonEncode({'merchant_phone': merchantPhone, 'amount_cents': amountCents, 'interval_days': intervalDays}));
    if (res.statusCode >= 400) throw ApiError('Create subscription failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> cancelSubscription(String id) async {
    final res = await _post('/subscriptions/$id/cancel');
    if (res.statusCode >= 400) throw ApiError('Cancel subscription failed: ${res.body}');
  }

  Future<void> devForceDue(String id) async {
    final res = await _post('/subscriptions/$id/dev_force_due');
    if (res.statusCode >= 400) throw ApiError('Force due failed: ${res.body}');
  }

  Future<Map<String, dynamic>> processDue({int maxCount = 50}) async {
    final res = await _post('/subscriptions/process_due', body: jsonEncode({'max_count': maxCount}));
    if (res.statusCode >= 400) throw ApiError('Process due failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // Statement
  Future<Map<String, dynamic>> merchantStatement({String? fromIso, String? toIso}) async {
    final q = <String, String>{};
    if (fromIso != null) q['from_ts'] = fromIso;
    if (toIso != null) q['to_ts'] = toIso;
    final res = await _get('/payments/merchant/statement', query: q.isEmpty ? null : q);
    if (res.statusCode >= 400) throw ApiError('Statement failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // KYC
  Future<Map<String, dynamic>> getKyc() async {
    final res = await _get('/kyc');
    if (res.statusCode >= 400) throw ApiError('Get KYC failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> submitKyc() async {
    final res = await _post('/kyc/submit');
    if (res.statusCode >= 400) throw ApiError('Submit KYC failed: ${res.body}');
  }

  Future<void> devApproveKyc() async {
    final res = await _post('/kyc/dev/approve');
    if (res.statusCode >= 400) throw ApiError('Dev approve KYC failed: ${res.body}');
  }

  // Payment Requests
  Future<Map<String, dynamic>> createRequest({required String toPhone, required int amountCents}) async {
    final res = await _post('/requests', body: jsonEncode({'to_phone': toPhone, 'amount_cents': amountCents}));
    if (res.statusCode >= 400) throw ApiError('Create request failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> listRequests() async {
    final res = await _get('/requests');
    if (res.statusCode >= 400) throw ApiError('List requests failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getRequest(String id) async {
    final res = await _get('/requests/$id');
    if (res.statusCode >= 400) throw ApiError('Get request failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> acceptRequest(String requestId) async {
    final res = await _post('/requests/$requestId/accept');
    if (res.statusCode >= 400) throw ApiError('Accept request failed: ${res.body}');
  }

  Future<void> rejectRequest(String requestId) async {
    final res = await _post('/requests/$requestId/reject');
    if (res.statusCode >= 400) throw ApiError('Reject request failed: ${res.body}');
  }

  Future<void> cancelRequest(String requestId) async {
    final res = await _post('/requests/$requestId/cancel');
    if (res.statusCode >= 400) throw ApiError('Cancel request failed: ${res.body}');
  }

  // Cash In/Out
  Future<Map<String, dynamic>> createCashIn({required int amountCents}) async {
    final res = await _post('/cash/cashin/request', body: jsonEncode({'amount_cents': amountCents}));
    if (res.statusCode >= 400) throw ApiError('Create cash-in failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createCashOut({required int amountCents}) async {
    final res = await _post('/cash/cashout/request', body: jsonEncode({'amount_cents': amountCents}));
    if (res.statusCode >= 400) throw ApiError('Create cash-out failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> listCashRequests() async {
    final res = await _get('/cash/requests');
    if (res.statusCode >= 400) throw ApiError('List cash requests failed: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> acceptCashRequest(String id) async {
    final res = await _post('/cash/requests/$id/accept');
    if (res.statusCode >= 400) throw ApiError('Accept cash request failed: ${res.body}');
  }

  Future<void> rejectCashRequest(String id) async {
    final res = await _post('/cash/requests/$id/reject');
    if (res.statusCode >= 400) throw ApiError('Reject cash request failed: ${res.body}');
  }

  Future<void> cancelCashRequest(String id) async {
    final res = await _post('/cash/requests/$id/cancel');
    if (res.statusCode >= 400) throw ApiError('Cancel cash request failed: ${res.body}');
  }

  Future<void> devBecomeAgent() async {
    final res = await _post('/cash/agents/dev/become_agent');
    if (res.statusCode >= 400) throw ApiError('Become agent failed: ${res.body}');
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
