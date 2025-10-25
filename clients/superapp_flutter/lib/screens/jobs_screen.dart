import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'ai_gateway_screen.dart';

class JobsScreen extends StatefulWidget {
  const JobsScreen({super.key});
  @override
  State<JobsScreen> createState() => _JobsScreenState();
}

class _JobsScreenState extends State<JobsScreen> {
  String _health = '?';
  bool _loading = false;
  final TextEditingController _qCtrl = TextEditingController();
  List<Map<String, dynamic>> _jobs = [];
  Uri _jobsUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('jobs', path, query: query);
  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final r = await http.get(_jobsUri('/health'));
      final js = jsonDecode(r.body);
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      _toast('$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _search() async {
    setState(() => _loading = true);
    try {
      final q = _qCtrl.text.trim();
      final r = await http.get(_jobsUri('/jobs/recommendations', query: {'q': q}));
      if (r.statusCode >= 400) throw Exception(r.body);
      final data = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() {
        _jobs = ((data['jobs'] as List?) ?? [])
            .map<Map<String, dynamic>>((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      });
    } catch (e) {
      _toast('$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
        appBar: AppBar(title: const Text('Jobs'), actions: [
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
                      labelText: 'Suche oder Befehl', hintText: 'z.B. Java Backend Damaskus'),
                )),
                const SizedBox(width: 8),
                FilledButton(
                    onPressed: _loading ? null : _search, child: const Text('Suchen')),
              ]),
              const SizedBox(height: 8),
              Expanded(
                child: _jobs.isEmpty
                    ? const Center(child: Text('Keine Ergebnisse'))
                    : ListView.builder(
                        itemCount: _jobs.length,
                        itemBuilder: (ctx, i) {
                          final j = _jobs[i];
                          return Card(
                              child: ListTile(
                            title: Text(j['title']?.toString() ?? ''),
                            subtitle: Text('${j['location'] ?? ''} — ${(j['tags'] as List?)?.take(3).join(', ') ?? ''}'),
                          ));
                        },
                      ),
              ),
              const SizedBox(height: 8),
              Row(children: [
                OutlinedButton(
                    onPressed: _loading ? null : _healthCheck,
                    child: const Text('Health')),
                const SizedBox(width: 8),
                Text('Status: $_health')
              ]),
            ])));
  }
}
