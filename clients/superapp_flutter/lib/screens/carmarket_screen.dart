import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'ai_gateway_screen.dart';
import 'package:shared_ui/message_host.dart';

class CarMarketScreen extends StatefulWidget {
  const CarMarketScreen({super.key});
  @override
  State<CarMarketScreen> createState() => _CarMarketScreenState();
}

class _CarMarketScreenState extends State<CarMarketScreen> {
  String _health = '?';
  bool _loading = false;
  final TextEditingController _qCtrl = TextEditingController();
  List<Map<String, dynamic>> _listings = [];
  List<Map<String, dynamic>> _toolCalls = [];
  String _status = '';
  final Map<String, Map<String, dynamic>> _estimates = {};

  Uri _carMarketUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('carmarket', path, query: query);
  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final r = await http.get(_carMarketUri('/health'));
      final js = jsonDecode(r.body);
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _search() async {
    setState(() {
      _loading = true;
      _status = '';
      _toolCalls = [];
    });
    final q = _qCtrl.text.trim();
    try {
      // 1) Ask assistant for tool suggestions
      final aiBase = const String.fromEnvironment('AI_GATEWAY_BASE_URL', defaultValue: '');
      final base = aiBase.isNotEmpty ? aiBase : 'http://localhost:8099';
      final chat = await http
          .post(Uri.parse('$base/v1/chat'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({
                'messages': [
                  {'role': 'user', 'content': q}
                ],
                'allow_tools': true
              }))
          .timeout(const Duration(seconds: 6));
      if (chat.statusCode < 400) {
        final data = jsonDecode(chat.body) as Map<String, dynamic>;
        _toolCalls = ((data['tool_calls'] as List?) ?? [])
            .map<Map<String, dynamic>>((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      }
    } catch (_) {}
    try {
      // 2) Fetch candidate listings
      final r = await http.get(_carMarketUri('/listings', query: {'q': q}));
      if (r.statusCode >= 400) throw Exception(r.body);
      final data = jsonDecode(r.body) as Map<String, dynamic>;
      final items = ((data['listings'] as List?) ?? [])
          .map<Map<String, dynamic>>((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      // 3) Re-rank via AI (client-side MVP)
      try {
        final aiBase = const String.fromEnvironment('AI_GATEWAY_BASE_URL', defaultValue: '');
        final base = aiBase.isNotEmpty ? aiBase : 'http://localhost:8099';
        final rank = await http
            .post(Uri.parse('$base/v1/rank'),
                headers: {'Content-Type': 'application/json'},
                body: jsonEncode({
                  'query': q,
                  'items': [
                    for (final l in items)
                      {
                        'id': l['id'],
                        'text': '${l['title']} ${l['make'] ?? ''} ${l['model'] ?? ''} ${l['city'] ?? ''}'
                      }
                  ]
                }))
            .timeout(const Duration(seconds: 4));
        if (rank.statusCode < 400) {
          final scores = (jsonDecode(rank.body)['scores'] as List?) ?? [];
          final byId = {for (final l in items) l['id']: l};
          final ordered = <Map<String, dynamic>>[];
          for (final s in scores) {
            final id = (s as Map)['id'];
            if (byId.containsKey(id)) ordered.add(byId[id]!);
          }
          if (ordered.isNotEmpty) {
            setState(() => _listings = ordered);
          } else {
            setState(() => _listings = items);
          }
        } else {
          setState(() => _listings = items);
        }
      } catch (_) {
        setState(() => _listings = items);
      }
    } catch (e) {
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _confirmTool(Map<String, dynamic> t) async {
    setState(() => _status = 'Ausführung...');
    try {
      final aiBase = const String.fromEnvironment('AI_GATEWAY_BASE_URL', defaultValue: '');
      final base = aiBase.isNotEmpty ? aiBase : 'http://localhost:8099';
      // Derive user id from any token (best-effort)
      final token = await getTokenFor('carmarket');
      String? sub;
      if (token != null) {
        try {
          final parts = token.split('.');
          final map = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1])))) as Map<String, dynamic>;
          sub = map['sub']?.toString();
        } catch (_) {}
      }
      final res = await http.post(Uri.parse('$base/v1/chat'), headers: {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token'
      }, body: jsonEncode({
        'messages': [
          {'role': 'user', 'content': '(confirm)'}
        ],
        'confirm': true,
        'selected_tool': {
          'tool': t['name'],
          'args': t['arguments'] ?? {},
          'user_id': sub ?? ''
        }
      }));
      if (res.statusCode >= 400) throw Exception(res.body);
      setState(() => _status = 'Aktion ausgeführt');
    } catch (e) {
      setState(() => _status = 'Fehler: $e');
    }
  }

  Future<void> _estimate(String id) async {
    setState(() => _status = 'Schätze Preis...');
    try {
      final r = await http.get(_carMarketUri('/listings/$id/price_estimate'));
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _estimates[id] = js);
      setState(() => _status = '');
    } catch (e) {
      setState(() => _status = 'Fehler: $e');
    }
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
        appBar: AppBar(title: const Text('Car Market'), actions: [
          IconButton(
              tooltip: 'AI Assistant',
              onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) => const AIGatewayScreen())),
              icon: const Icon(Icons.smart_toy_outlined)),
        ]),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                  child: TextField(
                controller: _qCtrl,
                decoration: const InputDecoration(
                    labelText: 'Suche oder Befehl',
                    hintText: 'z.B. Toyota Corolla Damaskus'),
              )),
              const SizedBox(width: 8),
              FilledButton(onPressed: _loading ? null : _search, child: const Text('Suchen')),
            ]),
            const SizedBox(height: 6),
            if (_status.isNotEmpty) Text(_status, style: const TextStyle(color: Colors.blue)),
            const SizedBox(height: 6),
            if (_toolCalls.isNotEmpty) ...[
              const Text('Vorgeschlagene Aktionen'),
              const SizedBox(height: 6),
              for (final t in _toolCalls)
                Card(
                    child: ListTile(
                  title: Text(t['name']?.toString() ?? 'tool'),
                  subtitle: Text(const JsonEncoder.withIndent('  ').convert(t['arguments'] ?? {})),
                  trailing: FilledButton(
                      onPressed: () => _confirmTool(t),
                      child: const Text('Bestätigen')),
                )),
            ],
            const SizedBox(height: 8),
            Expanded(
              child: _listings.isEmpty
                  ? const Center(child: Text('Keine Ergebnisse'))
                  : ListView.builder(
                      itemCount: _listings.length,
                      itemBuilder: (ctx, i) {
                        final l = _listings[i];
                        final id = (l['id'] ?? '') as String;
                        final est = _estimates[id];
                        final price = (l['price_cents'] ?? 0) as int;
                        String? badge;
                        if (est != null) {
                          final estC = (est['estimate_cents'] ?? 0) as int;
                          final diff = (price - estC).abs() / (estC == 0 ? 1 : estC);
                          if (diff <= 0.1) badge = 'FAIR';
                          else if (price < estC) badge = 'GÜNSTIG';
                          else badge = 'TEUER';
                        }
                        return Card(
                            child: ListTile(
                          title: Text(l['title']?.toString() ?? ''),
                          subtitle: Text(
                              '${l['make'] ?? ''} ${l['model'] ?? ''} ${l['year'] ?? ''} — ${l['city'] ?? ''}'),
                          trailing: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.end, children: [
                            Text('${(price) ~/ 1000}k'),
                            const SizedBox(height: 4),
                            if (badge != null) Text(badge!, style: TextStyle(color: badge=='TEUER'? Colors.red: badge=='GÜNSTIG'? Colors.green: Colors.orange, fontSize: 12)),
                            if (badge == null) TextButton(onPressed: () => _estimate(id), child: const Text('Check Preis')),
                          ]),
                        ));
                      },
                    ),
            ),
            const SizedBox(height: 8),
            Row(children: [
              OutlinedButton(onPressed: _loading ? null : _healthCheck, child: const Text('Health')),
              const SizedBox(width: 8),
              Text('Status: $_health'),
            ]),
          ]),
        ));
  }
}
