import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import 'ai_gateway_screen.dart';
import 'package:shared_ui/message_host.dart';
import '../animations.dart';
import 'package:shared_ui/glass.dart';

class _SkeletonTile extends StatelessWidget {
  const _SkeletonTile();
  @override
  Widget build(BuildContext context) {
    return GlassCard(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Container(width: 36, height: 36, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8))),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(height: 12, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(4))),
            const SizedBox(height: 6),
            Container(height: 10, width: 160, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(4))),
          ])),
        ]),
      ),
    );
  }
}

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
      if (!mounted) return;
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      if (!mounted) return;
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _search() async {
    setState(() => _loading = true);
    try {
      final q = _qCtrl.text.trim();
      final r = await http.get(_jobsUri('/jobs/recommendations', query: {'q': q}));
      if (r.statusCode >= 400) throw Exception(r.body);
      final data = jsonDecode(r.body) as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _jobs = ((data['jobs'] as List?) ?? [])
            .map<Map<String, dynamic>>((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      });
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
                child: AnimatedSwitcher(
                  duration: AppAnimations.switcherDuration,
                  child: _loading && _jobs.isEmpty
                      ? Column(key: const ValueKey('skel'), children: List.generate(5, (i) => const _SkeletonTile()))
                      : (_jobs.isEmpty
                          ? const Center(key: ValueKey('empty'), child: Text('Keine Ergebnisse'))
                          : ListView.builder(
                              key: const ValueKey('list'),
                              itemCount: _jobs.length,
                              itemBuilder: (ctx, i) {
                                final j = _jobs[i];
                                return GlassCard(
                                  child: ListTile(
                                    title: Text(j['title']?.toString() ?? ''),
                                    subtitle: Text('${j['location'] ?? ''} — ${(j['tags'] as List?)?.take(3).join(', ') ?? ''}'),
                                  ),
                                );
                              },
                            )),
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
