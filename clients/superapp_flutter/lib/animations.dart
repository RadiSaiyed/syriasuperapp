import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum AnimMode { off, normal, smooth }

class AppAnimations {
  static final ValueNotifier<AnimMode> mode = ValueNotifier(AnimMode.normal);

  static Duration get switcherDuration {
    switch (mode.value) {
      case AnimMode.off:
        return const Duration(milliseconds: 0);
      case AnimMode.smooth:
        return const Duration(milliseconds: 350);
      case AnimMode.normal:
      default:
        return const Duration(milliseconds: 200);
    }
  }

  static Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = prefs.getString('anim_mode') ?? 'normal';
      switch (v) {
        case 'off':
          mode.value = AnimMode.off;
          break;
        case 'smooth':
          mode.value = AnimMode.smooth;
          break;
        default:
          mode.value = AnimMode.normal;
      }
    } catch (_) {}
  }

  static Future<void> setMode(AnimMode m) async {
    mode.value = m;
    try {
      final prefs = await SharedPreferences.getInstance();
      final s = m == AnimMode.off ? 'off' : m == AnimMode.smooth ? 'smooth' : 'normal';
      await prefs.setString('anim_mode', s);
    } catch (_) {}
  }
}

