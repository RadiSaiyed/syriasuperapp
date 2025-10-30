import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AppHaptics {
  static bool haptic = true;
  static bool sound = false;

  static Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      haptic = prefs.getBool('haptic_enabled') ?? true;
      sound = prefs.getBool('sound_enabled') ?? false;
    } catch (_) {}
  }

  static Future<void> setHaptic(bool v) async {
    haptic = v;
    try { final p=await SharedPreferences.getInstance(); await p.setBool('haptic_enabled', v); } catch (_) {}
  }

  static Future<void> setSound(bool v) async {
    sound = v;
    try { final p=await SharedPreferences.getInstance(); await p.setBool('sound_enabled', v); } catch (_) {}
  }

  static void impact() {
    if (haptic) HapticFeedback.lightImpact();
    if (sound) SystemSound.play(SystemSoundType.click);
  }

  static void notify() {
    if (haptic) HapticFeedback.mediumImpact();
    if (sound) SystemSound.play(SystemSoundType.alert);
  }
}

