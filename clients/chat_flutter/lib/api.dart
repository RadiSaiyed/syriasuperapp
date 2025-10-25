import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:uuid/uuid.dart';

class TokenStore {
  static const _k = 'access_token';
  Future<String?> getToken() async => (await SharedPreferences.getInstance()).getString(_k);
  Future<void> setToken(String token) async => (await SharedPreferences.getInstance()).setString(_k, token);
  Future<void> clear() async => (await SharedPreferences.getInstance()).remove(_k);
}

class DeviceStore {
  static const _kd = 'device_id';
  Future<String> getOrCreateDeviceId() async {
    final p = await SharedPreferences.getInstance();
    final existing = p.getString(_kd);
    if (existing != null && existing.isNotEmpty) return existing;
    final id = const Uuid().v4();
    await p.setString(_kd, id);
    return id;
  }
}

class ApiClient {
  String baseUrl;
  final TokenStore tokenStore;
  final DeviceStore deviceStore;
  ApiClient({required this.baseUrl, required this.tokenStore, required this.deviceStore});

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

  // Devices / Keys
  Future<void> publishKey({required String publicKey, String? deviceName}) async {
    final devId = await deviceStore.getOrCreateDeviceId();
    final body = {'device_id': devId, 'public_key': publicKey, 'device_name': deviceName};
    final res = await http.post(Uri.parse('$baseUrl/keys/publish'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Publish key failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> userKeys(String userId) async {
    final res = await http.get(Uri.parse('$baseUrl/keys/$userId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Get keys failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Contacts
  Future<void> addContactByPhone(String phone) async {
    final res = await http.post(Uri.parse('$baseUrl/contacts/add'), headers: await _authHeaders(), body: jsonEncode({'phone': phone}));
    if (res.statusCode >= 400) throw ApiError('Add contact failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> listContacts() async {
    final res = await http.get(Uri.parse('$baseUrl/contacts'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List contacts failed: ${res.body}');
    return (jsonDecode(res.body) as List).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // Messages
  Future<Map<String, dynamic>> sendMessage({required String recipientUserId, required String ciphertext}) async {
    final devId = await deviceStore.getOrCreateDeviceId();
    final body = {'recipient_user_id': recipientUserId, 'sender_device_id': devId, 'ciphertext': ciphertext};
    final res = await http.post(Uri.parse('$baseUrl/messages/send'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Send failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> inbox() async {
    final res = await http.get(Uri.parse('$baseUrl/messages/inbox'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Inbox failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['messages'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<void> ackDelivered(String messageId) async {
    final res = await http.post(Uri.parse('$baseUrl/messages/$messageId/ack_delivered'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Ack failed: ${res.body}');
  }
  Future<void> ackRead(String messageId) async {
    final res = await http.post(Uri.parse('$baseUrl/messages/$messageId/ack_read'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Ack read failed: ${res.body}');
  }
  Future<List<Map<String, dynamic>>> conversations() async {
    final res = await http.get(Uri.parse('$baseUrl/messages/conversations'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Conversations failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['conversations'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> conversationsSummary() async {
    final res = await http.get(Uri.parse('$baseUrl/messages/conversations_summary'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Conversations summary failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['conversations'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<List<Map<String, dynamic>>> history({required String conversationId, String? beforeIso, int limit = 50}) async {
    final params = <String>[];
    params.add('conversation_id=$conversationId');
    if (beforeIso != null && beforeIso.isNotEmpty) params.add('before=${Uri.encodeComponent(beforeIso)}');
    params.add('limit=$limit');
    final res = await http.get(Uri.parse('$baseUrl/messages/history?${params.join('&')}'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('History failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['messages'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<Map<String, dynamic>> addAttachment({required String messageId, String? contentType, required String ciphertextB64}) async {
    final body = {'content_type': contentType, 'ciphertext_b64': ciphertextB64}..removeWhere((k, v) => v == null || (v is String && v.isEmpty));
    final res = await http.post(Uri.parse('$baseUrl/messages/$messageId/attachments'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Add attachment failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<Map<String, dynamic>> uploadAttachmentBlob({required String messageId, required List<int> bytes, String? contentType, String? filename}) async {
    final uri = Uri.parse('$baseUrl/messages/$messageId/attachments/upload');
    final headers = await _authHeaders();
    if (contentType != null) headers['X-Content-Type'] = contentType;
    if (filename != null) headers['X-Filename'] = filename;
    final res = await http.post(uri, headers: headers, body: bytes);
    if (res.statusCode >= 400) throw ApiError('Upload attachment failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> listAttachments(String messageId) async {
    final res = await http.get(Uri.parse('$baseUrl/messages/$messageId/attachments'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List attachments failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['attachments'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }

  // WebSocket
  Future<WebSocketChannel> connectWs() async {
    final t = await tokenStore.getToken();
    if (t == null) throw ApiError('No token');
    final wsUrl = baseUrl.replaceFirst('http', 'ws');
    final uri = Uri.parse('$wsUrl/ws?token=$t');
    return WebSocketChannel.connect(uri);
  }

  // Reactions
  Future<Map<String, dynamic>> addReaction({required String messageId, required String emoji}) async {
    final res = await http.post(Uri.parse('$baseUrl/messages/$messageId/reactions'), headers: await _authHeaders(), body: jsonEncode({'emoji': emoji}));
    if (res.statusCode >= 400) throw ApiError('Add reaction failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<List<Map<String, dynamic>>> listReactions(String messageId) async {
    final res = await http.get(Uri.parse('$baseUrl/messages/$messageId/reactions'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('List reactions failed: ${res.body}');
    final data = (jsonDecode(res.body) as Map).cast<String, dynamic>();
    return ((data['reactions'] as List?) ?? []).cast<dynamic>().map((e) => (e as Map).cast<String, dynamic>()).toList();
  }
  Future<void> removeReaction({required String messageId, required String emoji}) async {
    final uri = Uri.parse('$baseUrl/messages/$messageId/reactions').replace(queryParameters: {'emoji': emoji});
    final res = await http.delete(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Remove reaction failed: ${res.body}');
  }

  // Presence
  Future<Map<String, dynamic>> presence(String userId) async {
    final res = await http.get(Uri.parse('$baseUrl/presence/$userId'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Presence failed: ${res.body}');
    return (jsonDecode(res.body) as Map).cast<String, dynamic>();
  }
  Future<void> pingPresence() async {
    final res = await http.post(Uri.parse('$baseUrl/presence/ping'), headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Presence ping failed: ${res.body}');
  }

  // Typing
  Future<void> typing({String? conversationId, String? peerUserId, bool isTyping = true}) async {
    final body = {'conversation_id': conversationId, 'peer_user_id': peerUserId, 'is_typing': isTyping};
    final res = await http.post(Uri.parse('$baseUrl/messages/typing'), headers: await _authHeaders(), body: jsonEncode(body));
    if (res.statusCode >= 400) throw ApiError('Typing failed: ${res.body}');
  }

  // Blocks
  Future<void> blockUser(String userId) async {
    final uri = Uri.parse('$baseUrl/blocks').replace(queryParameters: {'blocked_user_id': userId});
    final res = await http.post(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Block failed: ${res.body}');
  }
  Future<void> unblockUser(String userId) async {
    final uri = Uri.parse('$baseUrl/blocks').replace(queryParameters: {'blocked_user_id': userId});
    final res = await http.delete(uri, headers: await _authHeaders());
    if (res.statusCode >= 400) throw ApiError('Unblock failed: ${res.body}');
  }
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}
