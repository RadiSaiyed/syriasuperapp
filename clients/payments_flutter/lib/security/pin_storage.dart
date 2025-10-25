import 'dart:convert';
import 'dart:math';
import 'package:crypto/crypto.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

class PinStorage {
  static const _pinHashKey = 'app_pin_hash';
  static const _pinSaltKey = 'app_pin_salt';
  static const _bioKey = 'biometric_enabled';
  final FlutterSecureStorage _sec = const FlutterSecureStorage();

  Future<bool> hasPin() async {
    try {
      if (!kIsWeb) {
        final h = await _sec.read(key: _pinHashKey);
        return (h ?? '').isNotEmpty;
      }
    } catch (_) {}
    final p = await SharedPreferences.getInstance();
    return (p.getString(_pinHashKey) ?? '').isNotEmpty;
  }

  Future<void> setPin(String pin) async {
    final salt = _randomSalt();
    final hash = _hash(pin, salt);
    bool ok = false;
    try {
      if (!kIsWeb) {
        await _sec.write(key: _pinSaltKey, value: salt, aOptions: const AndroidOptions(encryptedSharedPreferences: true));
        await _sec.write(key: _pinHashKey, value: hash, aOptions: const AndroidOptions(encryptedSharedPreferences: true));
        ok = true;
      }
    } catch (_) {}
    if (!ok) {
      final p = await SharedPreferences.getInstance();
      await p.setString(_pinSaltKey, salt);
      await p.setString(_pinHashKey, hash);
    }
  }

  Future<bool> verifyPin(String pin) async {
    String salt = '';
    String hash = '';
    try {
      if (!kIsWeb) {
        salt = (await _sec.read(key: _pinSaltKey)) ?? '';
        hash = (await _sec.read(key: _pinHashKey)) ?? '';
      }
    } catch (_) {}
    if (salt.isEmpty || hash.isEmpty) {
      final p = await SharedPreferences.getInstance();
      salt = p.getString(_pinSaltKey) ?? '';
      hash = p.getString(_pinHashKey) ?? '';
    }
    if (salt.isEmpty || hash.isEmpty) return false;
    return _hash(pin, salt) == hash;
  }

  Future<void> clearPin() async {
    try { if (!kIsWeb) { await _sec.delete(key: _pinSaltKey); await _sec.delete(key: _pinHashKey); } } catch (_) {}
    final p = await SharedPreferences.getInstance();
    await p.remove(_pinSaltKey);
    await p.remove(_pinHashKey);
  }

  Future<bool> isBiometricEnabled() async {
    try { if (!kIsWeb) { final v = await _sec.read(key: _bioKey); if (v != null) return v == '1'; } } catch (_) {}
    final p = await SharedPreferences.getInstance();
    return p.getBool(_bioKey) ?? false;
  }

  Future<void> setBiometricEnabled(bool v) async {
    bool ok = false;
    try { if (!kIsWeb) { await _sec.write(key: _bioKey, value: v ? '1' : '0', aOptions: const AndroidOptions(encryptedSharedPreferences: true)); ok = true; } } catch (_) {}
    if (!ok) { final p = await SharedPreferences.getInstance(); await p.setBool(_bioKey, v); }
  }

  String _randomSalt() {
    final r = Random.secure();
    final bytes = List<int>.generate(16, (_) => r.nextInt(256));
    return base64Url.encode(bytes);
    }

  String _hash(String pin, String salt) {
    final h = sha256.convert(utf8.encode('$salt:$pin'));
    return h.toString();
  }
}
