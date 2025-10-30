import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';

const String _aiBaseOverride =
    String.fromEnvironment('AI_GATEWAY_BASE_URL', defaultValue: '');

class AIGatewayScreen extends StatefulWidget {
  const AIGatewayScreen({super.key});

  @override
  State<AIGatewayScreen> createState() => _AIGatewayScreenState();
}

class _AIGatewayScreenState extends State<AIGatewayScreen> {
  final TextEditingController _msgCtrl = TextEditingController();
  late final TextEditingController _gatewayCtrl;
  String _assistant = '';
  List<Map<String, dynamic>> _toolCalls = [];
  String _status = '';
  String? _execName;
  Map<String, dynamic>? _execResult;

  @override
  void dispose() {
    _msgCtrl.dispose();
    _gatewayCtrl.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _gatewayCtrl = TextEditingController(
        text: _aiBaseOverride.isNotEmpty ? _aiBaseOverride : 'http://localhost:8099');
  }

  Future<void> _ask() async {
    setState(() {
      _status = '';
      _assistant = '';
      _toolCalls = [];
      _execName = null;
      _execResult = null;
    });
    final uri = Uri.parse('${_gatewayCtrl.text}/v1/chat');
    try {
      final res = await http
          .post(uri,
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({
                'messages': [
                  {'role': 'user', 'content': _msgCtrl.text}
                ],
                'allow_tools': true
              }))
          .timeout(const Duration(seconds: 8));
      if (res.statusCode >= 400) {
        throw Exception('HTTP ${res.statusCode}: ${res.body}');
      }
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _assistant = (data['content'] ?? '') as String;
        _toolCalls = ((data['tool_calls'] as List?) ?? [])
            .map<Map<String, dynamic>>((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      });
    } catch (e) {
      setState(() => _status = 'Fehler: $e');
    }
  }

  Future<void> _confirm(Map<String, dynamic> t) async {
    setState(() {
      _status = 'Führe aus…';
      _execName = null;
      _execResult = null;
    });
    final userId = await _userIdFromAnyToken();
    if (userId == null) {
      setState(() => _status = 'Fehlende Anmeldung. Bitte zuerst einloggen.');
      return;
    }
    final authHeader = await _authForTool(t['name'] as String?);
    final uri = Uri.parse('${_gatewayCtrl.text}/v1/chat');
    try {
      final res = await http
          .post(uri,
              headers: {
                'Content-Type': 'application/json',
                if (authHeader != null) 'Authorization': authHeader,
              },
              body: jsonEncode({
                'messages': [
                  {'role': 'user', 'content': '(confirm)'}
                ],
                'confirm': true,
                'selected_tool': {
                  'tool': t['name'],
                  'args': t['arguments'] ?? {},
                  'user_id': userId,
                }
              }))
          .timeout(const Duration(seconds: 10));
      if (res.statusCode >= 400) {
        throw Exception('HTTP ${res.statusCode}: ${res.body}');
      }
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _status = 'Aktion ausgeführt';
        _execName = (data['executed_tool'] ?? '') as String?;
        _execResult = (data['execution_result'] as Map?)?.cast<String, dynamic>();
      });
    } catch (e) {
      setState(() => _status = 'Fehler: $e');
    }
  }

  Future<String?> _authForTool(String? toolName) async {
    final store = MultiTokenStore();
    String? svc;
    switch (toolName) {
      case 'pay_bill':
        svc = 'utilities';
        break;
      case 'start_parking_session':
        svc = 'parking';
        break;
      case 'create_car_listing':
        svc = 'carmarket';
        break;
      default:
        svc = 'payments';
    }
    final token = await getTokenFor(svc, store: store);
    return token != null ? 'Bearer $token' : null;
  }

  Future<String?> _userIdFromAnyToken() async {
    for (final svc in ['utilities', 'parking', 'carmarket', 'payments']) {
      final t = await getTokenFor(svc);
      if (t != null && t.isNotEmpty) {
        final sub = _decodeSubFromJwt(t);
        if (sub != null && sub.isNotEmpty) return sub;
      }
    }
    return null;
  }

  String? _decodeSubFromJwt(String token) {
    try {
      final parts = token.split('.');
      if (parts.length < 2) return null;
      final map = jsonDecode(String.fromCharCodes(base64Url.decode(parts[1])));
      return (map as Map<String, dynamic>)['sub'] as String?;
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('AI Assistant')),
      body: Padding(
        padding: const EdgeInsets.all(12.0),
        child: ListView(
          children: [
            TextField(
              controller: _gatewayCtrl,
              decoration: const InputDecoration(
                  labelText: 'Gateway URL', hintText: 'http://localhost:8099'),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _msgCtrl,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Nachricht',
                hintText:
                    "z.B. 'Rechnung 123 bezahlen' oder 'Parken Zone ZONE123 Kennzeichen ABC123 für 30 Minuten'",
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                FilledButton(
                    onPressed: _ask, child: const Text('Fragen / Vorschläge')),
                const SizedBox(width: 8),
                Text(_status,
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.primary)),
              ],
            ),
            const SizedBox(height: 12),
            if (_assistant.isNotEmpty) ...[
              Text('Antwort', style: theme.textTheme.titleMedium),
              const SizedBox(height: 6),
              Text(_assistant),
            ],
            const SizedBox(height: 8),
            if (_toolCalls.isNotEmpty)
              Text('Vorgeschlagene Aktionen',
                  style: theme.textTheme.titleMedium),
            for (final t in _toolCalls)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(t['name']?.toString() ?? 'tool',
                          style: theme.textTheme.titleSmall),
                      const SizedBox(height: 6),
                      Text(const JsonEncoder.withIndent('  ').convert(t['arguments'] ?? {}),
                          style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          FilledButton(
                              onPressed: () => _confirm(t),
                              child: const Text('Bestätigen & Ausführen')),
                        ],
                      )
                    ],
                  ),
                ),
              ),
            if (_execName != null) ...[
              const SizedBox(height: 8),
              Text('Ausgeführt: $_execName', style: theme.textTheme.titleMedium),
              const SizedBox(height: 6),
              Text(const JsonEncoder.withIndent('  ').convert(_execResult ?? {}),
                  style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
            ]
          ],
        ),
      ),
    );
  }
}
