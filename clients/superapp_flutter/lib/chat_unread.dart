import 'package:flutter/foundation.dart';
import 'dart:async';
import 'package:shared_core/shared_core.dart';
import 'services.dart';

class ChatUnreadStore {
  static final ValueNotifier<int> count = ValueNotifier<int>(0);
  static Timer? _timer;

  static Future<void> refresh() async {
    try {
      // Do not poll when not logged in (avoid unauthorized /v1/me calls at startup)
      final hasPayments = await hasTokenFor('payments');
      if (!hasPayments) return;
      final js = await serviceGetJson('superapp', '/v1/me', options: const RequestOptions(idempotent: true));
      final svc = (js['services'] as Map?)?.cast<String, dynamic>();
      final chat = (svc?['chat'] as Map?)?.cast<String, dynamic>();
      final convs = (chat?['conversations'] as List?) ?? const [];
      int unread = 0;
      for (final c in convs) {
        try { unread += int.tryParse(((c as Map)['unread_count'] ?? '0').toString()) ?? 0; } catch (_) {}
      }
      count.value = unread;
    } catch (_) {}
  }

  static void set(int v) { count.value = v; }

  static void start({Duration interval = const Duration(seconds: 20)}) {
    _timer?.cancel();
    _timer = Timer.periodic(interval, (_) => refresh());
  }

  static void stop() {
    _timer?.cancel();
    _timer = null;
  }
}
