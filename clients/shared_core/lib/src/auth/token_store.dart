import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Secure token storage that defaults to platform keychain/keystore and
/// transparently falls back to shared preferences on the web where secure
/// storage is not available.
class SecureTokenStore {
  SecureTokenStore({
    FlutterSecureStorage? secureStorage,
    this.prefix = 'sc_jwt_',
  }) : _secureStorage = secureStorage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _secureStorage;
  final String prefix;

  Future<String?> read(String service) async {
    final key = _buildKey(service);
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(key);
    }
    return _secureStorage.read(key: key);
  }

  Future<void> write(String service, String token) async {
    final key = _buildKey(service);
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(key, token);
      return;
    }
    await _secureStorage.write(key: key, value: token);
  }

  Future<void> delete(String service) async {
    final key = _buildKey(service);
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(key);
      return;
    }
    await _secureStorage.delete(key: key);
  }

  Future<void> writeAll(String token, Iterable<String> services) async {
    for (final service in services) {
      await write(service, token);
    }
  }

  Future<void> deleteAll(Iterable<String> services) async {
    for (final service in services) {
      await delete(service);
    }
  }

  String _buildKey(String service) => '$prefix$service';
}

/// Signature for providing an auth token prior to making a request.
typedef TokenProvider = Future<String?> Function(String service);
