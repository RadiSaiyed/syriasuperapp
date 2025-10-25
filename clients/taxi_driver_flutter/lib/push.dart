import 'dart:io' show Platform;
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api.dart';
import 'ui/notify.dart';

// Background handler must be a top-level function.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp();
  } catch (_) {}
  try {
    final data = message.data;
    final type = data['type'];
    final rideId = data['ride_id'];
    if (type == 'driver_assignment' && rideId is String && rideId.isNotEmpty) {
      final sp = await SharedPreferences.getInstance();
      await sp.setString('pending_ride_id', rideId);
    }
  } catch (_) {}
}

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
      // Listen for foreground messages
      FirebaseMessaging.onMessage.listen((RemoteMessage msg) async {
        try {
          final data = msg.data;
          final type = data['type'];
          final rideId = data['ride_id'];
          if (type == 'driver_assignment' && rideId is String && rideId.isNotEmpty) {
            final sp = await SharedPreferences.getInstance();
            await sp.setString('pending_ride_id', rideId);
            // Show local heads-up notification with Accept action
            await Notify.showAssignment(rideId: rideId, title: msg.notification?.title ?? 'New ride assigned', body: msg.notification?.body ?? '');
          }
        } catch (_) {}
      });
      // When a notification is tapped to open the app
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage msg) async {
        try {
          final data = msg.data;
          final rideId = data['ride_id'];
          if (rideId is String && rideId.isNotEmpty) {
            final sp = await SharedPreferences.getInstance();
            await sp.setString('pending_ride_id', rideId);
          }
        } catch (_) {}
      });
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
