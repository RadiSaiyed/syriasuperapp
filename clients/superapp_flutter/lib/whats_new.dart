import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class WhatsNew {
  // Bump this key when content changes to re-show once per version
  static const _key = 'whats_new_v2_shown';

  static Future<void> maybeShow(BuildContext context) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final shown = prefs.getBool(_key) ?? false;
      if (shown) return;
      await Future.delayed(const Duration(milliseconds: 300));
      if (!context.mounted) return;
      await showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text("What's New"),
          content: const Text(
              '• Unified API (BFF) + WS proxy\n'
              '• Deep‑links (Taxi, Payments, Commerce, Stays)\n'
              '• Notifications: Topics + Inbox\n'
              '• Profile: KYC/Merchant quick actions\n'
              '• Animated lists and skeletons\n'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK')),
          ],
        ),
      );
      await prefs.setBool(_key, true);
    } catch (_) {}
  }
}

