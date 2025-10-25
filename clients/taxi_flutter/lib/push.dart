import 'dart:io' show Platform;
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api.dart';

class PushManager {
  final ApiClient api;
  final String appMode; // rider|driver
  PushManager({required this.api, required this.appMode});

  static const _k = 'fcm_token_registered';
  bool _inited = false;

  Future<void> init() async {
    if (_inited) return;
    try {
      await Firebase.initializeApp();
      final fm = FirebaseMessaging.instance;
      if (Platform.isIOS) {
        await fm.requestPermission(alert: true, badge: true, sound: true, provisional: true);
      }
      // Get token and register
      final token = await fm.getToken();
      if (token != null) {
        await _register(token);
      }
      FirebaseMessaging.instance.onTokenRefresh.listen((t) async {
        await _register(t);
      });
      _inited = true;
    } catch (_) {
      // Firebase not configured; ignore
    }
  }

  Future<void> _register(String token) async {
    try {
      await api.pushRegister(token: token, platform: Platform.isIOS ? 'ios' : 'android', appMode: appMode);
      final sp = await SharedPreferences.getInstance();
      await sp.setString(_k, token);
    } catch (_) {}
  }
}

