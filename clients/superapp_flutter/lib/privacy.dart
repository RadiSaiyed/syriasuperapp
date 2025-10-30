import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AppPrivacy {
  static const _crashKey = 'privacy_send_crash_reports';
  static const _analyticsKey = 'privacy_send_analytics';

  static final ValueNotifier<bool> sendCrashReports = ValueNotifier<bool>(false);
  static final ValueNotifier<bool> sendAnalytics = ValueNotifier<bool>(false);

  static Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      sendCrashReports.value = prefs.getBool(_crashKey) ?? false; // opt-in
      sendAnalytics.value = prefs.getBool(_analyticsKey) ?? false; // opt-in
    } catch (_) {}
  }

  static Future<void> setCrashReports(bool v) async {
    sendCrashReports.value = v;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_crashKey, v);
    } catch (_) {}
  }

  static Future<void> setAnalytics(bool v) async {
    sendAnalytics.value = v;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_analyticsKey, v);
    } catch (_) {}
  }
}

