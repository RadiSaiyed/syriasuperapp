import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';

class ConnectivityBanner extends StatefulWidget {
  const ConnectivityBanner({super.key});
  @override
  State<ConnectivityBanner> createState() => _ConnectivityBannerState();
}

class _ConnectivityBannerState extends State<ConnectivityBanner> {
  late final StreamSubscription _sub;
  bool _offline = false;

  @override
  void initState() {
    super.initState();
    _sub = Connectivity().onConnectivityChanged.listen((result) {
      final off = result == ConnectivityResult.none;
      if (mounted) setState(() => _offline = off);
    });
    // initial check
    Connectivity().checkConnectivity().then((r) {
      final off = r == ConnectivityResult.none;
      if (mounted) setState(() => _offline = off);
    });
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_offline) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(color: Colors.red.shade600, borderRadius: BorderRadius.circular(8)),
      child: Row(children: const [
        Icon(Icons.wifi_off, color: Colors.white, size: 18),
        SizedBox(width: 8),
        Expanded(child: Text('Offline – Some actions may fail', style: TextStyle(color: Colors.white))),
      ]),
    );
  }
}

