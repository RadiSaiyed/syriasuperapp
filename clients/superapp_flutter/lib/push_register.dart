import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_core/shared_core.dart';
import 'services.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:shared_ui/message_host.dart';
import 'deeplinks.dart';
import 'package:flutter/material.dart';
import 'push_history.dart';
import 'haptics.dart';

class PushRegister {
  static const _key = 'device_id';

  static Future<String> _deviceId() async {
    final prefs = await SharedPreferences.getInstance();
    final cur = prefs.getString(_key);
    if (cur != null && cur.isNotEmpty) return cur;
    final id = _randomId();
    await prefs.setString(_key, id);
    return id;
  }

  static String _randomId({int len = 22}) {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    final r = Random();
    return List.generate(len, (_) => chars[r.nextInt(chars.length)]).join();
  }

  static Future<void> registerIfPossible() async {
    try {
      final id = await _deviceId();
      final token = await getTokenFor('payments');
      if (token == null || token.isEmpty) return;
      String fcm = '';
      try {
        await Firebase.initializeApp();
        final perms = await FirebaseMessaging.instance.requestPermission();
        if (perms.authorizationStatus == AuthorizationStatus.authorized || perms.authorizationStatus == AuthorizationStatus.provisional) {
          fcm = (await FirebaseMessaging.instance.getToken()) ?? '';
          // Foreground handler: show toast/snackbar for incoming messages
          FirebaseMessaging.onMessage.listen((RemoteMessage msg) {
            final title = msg.notification?.title ?? 'Notification';
            final body = msg.notification?.body ?? '';
            final text = body.isEmpty ? title : '$title — $body';
            final ctx = MessageHost.messengerKey.currentContext;
            if (ctx != null) {
              ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(text)));
            }
            final deeplink = msg.data['deeplink'] as String?;
            PushHistoryStore.append(PushHistoryEntry(title: title, body: body, deeplink: deeplink, atIso: DateTime.now().toIso8601String()));
            AppHaptics.notify();
          });
          // App opened from notification
          FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage msg) {
            final link = msg.data['deeplink'] as String?;
            final ctx = MessageHost.messengerKey.currentContext;
            if (link != null && link.isNotEmpty && ctx != null) {
              try { DeepLinks.handleUri(ctx, Uri.parse(link)); } catch (_) {}
            }
            final title = msg.notification?.title ?? 'Notification';
            final body = msg.notification?.body ?? '';
            PushHistoryStore.append(PushHistoryEntry(title: title, body: body, deeplink: link, atIso: DateTime.now().toIso8601String()));
          });
          // Initial message (app launched from terminated)
          final initial = await FirebaseMessaging.instance.getInitialMessage();
          if (initial != null) {
            final link = initial.data['deeplink'] as String?;
            final ctx = MessageHost.messengerKey.currentContext;
            if (link != null && link.isNotEmpty && ctx != null) {
              try { DeepLinks.handleUri(ctx, Uri.parse(link)); } catch (_) {}
            }
            final title = initial.notification?.title ?? 'Notification';
            final body = initial.notification?.body ?? '';
            PushHistoryStore.append(PushHistoryEntry(title: title, body: body, deeplink: link, atIso: DateTime.now().toIso8601String()));
          }
        }
      } catch (_) {
        // Firebase not configured; continue without token
      }
      await servicePostJson('superapp', '/v1/push/register', body: {
        'platform': 'flutter',
        'token': fcm,
        'device_id': id,
      }, options: const RequestOptions(idempotent: true));
    } catch (_) {}
  }

  static Future<void> subscribeTopic(String topic) async {
    try {
      await servicePostJson('superapp', '/v1/push/topic/subscribe', body: {'topic': topic}, options: const RequestOptions(idempotent: true));
    } catch (_) {}
  }

  static Future<void> unsubscribeTopic(String topic) async {
    try {
      await servicePostJson('superapp', '/v1/push/topic/unsubscribe', body: {'topic': topic}, options: const RequestOptions(idempotent: true));
    } catch (_) {}
  }
}
