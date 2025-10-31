import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_ui/message_host.dart';
import '../services.dart';

class FlightsScreen extends StatefulWidget {
  const FlightsScreen({super.key});
  @override
  State<FlightsScreen> createState() => _FlightsScreenState();
}

class _FlightsScreenState extends State<FlightsScreen> {
  String _health = '?';
  bool _loading = false;
  // Per-app OTP login removed: use central login

  Uri _flightsUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('flights', path, query: query);


  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final r = await http.get(_flightsUri('/health'));
      final js = jsonDecode(r.body);
      if (!mounted) return;
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      if (!mounted) return;
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
        appBar: AppBar(title: const Text('Flights')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          const Text('Use zentralen Login über Profil/Payments.'),
          const Divider(height: 32),
          ElevatedButton(
              onPressed: _loading ? null : _healthCheck,
              child: const Text('Health')),
          const SizedBox(height: 8),
          Text('Status: $_health')
        ]));
  }
}
