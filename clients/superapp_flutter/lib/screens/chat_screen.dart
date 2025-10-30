import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'ai_gateway_screen.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  String _health = '?';
  bool _loading = false;
  // Per-app OTP login removed: use central login

  Uri _chatUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('chat', path, query: query);

  void _toast(String m) { showToast(context, m); }

  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final r = await http.get(_chatUri('/health'));
      final js = jsonDecode(r.body);
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
        appBar: AppBar(title: const Text('Chat'), actions: [
          IconButton(
              tooltip: 'AI Assistant',
              onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) => const AIGatewayScreen())),
              icon: const Icon(Icons.smart_toy_outlined)),
        ]),
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
