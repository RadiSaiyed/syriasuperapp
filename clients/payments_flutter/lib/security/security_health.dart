import 'dart:async';
import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;
import 'package:flutter_jailbreak_detection/flutter_jailbreak_detection.dart';

class SecurityHealth {
  static Future<bool> isCompromisedDevice() async {
    if (kIsWeb) return false;
    try {
      final jail = await FlutterJailbreakDetection.jailbroken;
      final devMode = await FlutterJailbreakDetection.developerMode;
      return jail || devMode;
    } catch (_) {
      return false;
    }
  }

  static bool isDebugBuild() => kDebugMode;
  static bool isEmulator() {
    // Lightweight hint; more robust checks would use device_info_plus
    return false;
  }
}
