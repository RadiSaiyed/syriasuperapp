import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class Notify {
  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  static bool _inited = false;

  static Future<void> init() async {
    if (_inited) return;
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const ios = DarwinInitializationSettings();
    await _plugin.initialize(const InitializationSettings(
      android: android,
      iOS: ios,
    ));
    _inited = true;
  }

  static Future<void> show(String title, String body) async {
    await init();
    const android = AndroidNotificationDetails(
      'taxi_events',
      'Taxi Events',
      channelDescription: 'Ride assignment and status updates',
      importance: Importance.defaultImportance,
      priority: Priority.defaultPriority,
    );
    const ios = DarwinNotificationDetails();
    await _plugin.show(0, title, body,
        const NotificationDetails(android: android, iOS: ios));
  }
}

