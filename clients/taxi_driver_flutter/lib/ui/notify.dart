import 'dart:convert';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class Notify {
  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  static bool _inited = false;
  static Future<void> Function(String actionId, String? payload)? _handler;

  static Future<void> init({Future<void> Function(String actionId, String? payload)? onAction}) async {
    if (_inited) return;
    _handler = onAction;
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    final ios = DarwinInitializationSettings(
      // Register a category used for action buttons on iOS
      notificationCategories: <DarwinNotificationCategory>[
        DarwinNotificationCategory(
          'taxi_actions',
          actions: <DarwinNotificationAction>[
            DarwinNotificationAction.plain('ACCEPT_RIDE', 'Annehmen'),
          ],
        ),
      ],
    );
    await _plugin.initialize(
      InitializationSettings(
        android: android,
        iOS: ios,
      ),
      onDidReceiveNotificationResponse: (NotificationResponse response) async {
        if (_handler != null) {
          await _handler!(response.actionId ?? '', response.payload);
        }
      },
    );
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
    await _plugin.show(
      0,
      title,
      body,
      const NotificationDetails(android: android, iOS: ios),
    );
  }

  static Future<void> showAssignment({required String rideId, String title = 'New ride', String body = 'Tap to view or accept'}) async {
    await init();
    // Add action button for accepting the ride
    const android = AndroidNotificationDetails(
      'taxi_events',
      'Taxi Events',
      channelDescription: 'Ride assignment and status updates',
      importance: Importance.high,
      priority: Priority.high,
      actions: <AndroidNotificationAction>[
        AndroidNotificationAction('ACCEPT_RIDE', 'Annehmen'),
      ],
    );
    const ios = DarwinNotificationDetails(
      categoryIdentifier: 'taxi_actions',
    );
    final payload = jsonEncode(<String, dynamic>{'type': 'driver_assignment', 'ride_id': rideId});
    await _plugin.show(
      1, // separate id from generic notifications
      title,
      body,
      const NotificationDetails(android: android, iOS: ios),
      payload: payload,
    );
  }
}
