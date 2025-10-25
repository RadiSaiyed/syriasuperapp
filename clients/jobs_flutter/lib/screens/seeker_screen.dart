import 'package:flutter/material.dart';

import '../api.dart';

class SeekerScreen extends StatefulWidget {
  final ApiClient api;
  const SeekerScreen({super.key, required this.api});

  @override
  State<SeekerScreen> createState() => _SeekerScreenState();
}

class _SeekerScreenState extends State<SeekerScreen> {
  late Future<List<Map<String, dynamic>>> _jobsFuture = widget.api.listOpenJobs();

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Column(children: [
        const TabBar(tabs: [Tab(text: 'Open Jobs'), Tab(text: 'My Applications')]),
        Expanded(
          child: TabBarView(children: [
            _buildJobs(),
            _buildApplications(),
          ]),
        )
      ]),
    );
  }

  Widget _buildJobs() {
    return RefreshIndicator(
      onRefresh: () async => setState(() => _jobsFuture = widget.api.listOpenJobs()),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _jobsFuture,
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final jobs = snap.data!;
          if (jobs.isEmpty) return const Center(child: Text('No jobs yet'));
          return ListView.separated(
            itemCount: jobs.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final j = jobs[i];
              return ListTile(
                title: Text(j['title'] ?? ''),
                subtitle: Text((j['location'] ?? '') + ((j['salary_cents'] != null) ? ' • ${(j['salary_cents'] / 100).toStringAsFixed(2)}' : '')),
                trailing: FilledButton(
                  onPressed: () async {
                    final ctrl = TextEditingController();
                    final cover = await showDialog<String>(
                      context: context,
                      builder: (_) => AlertDialog(
                        title: const Text('Apply'),
                        content: TextField(controller: ctrl, decoration: const InputDecoration(labelText: 'Cover letter (optional)')),
                        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Submit'))],
                      ),
                    );
                    if (cover == null) return;
                    try {
                      await widget.api.apply(j['id'] as String, coverLetter: cover);
                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Applied')));
                    } catch (e) {
                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                    }
                  },
                  child: const Text('Apply'),
                ),
              );
            },
          );
        },
      ),
    );
  }

  Widget _buildApplications() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: widget.api.myApplications(),
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final apps = snap.data!;
        if (apps.isEmpty) return const Center(child: Text('No applications yet'));
        return ListView.separated(
          itemCount: apps.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final a = apps[i];
            final aid = (a['id'] ?? '').toString();
            final aidHead = aid.length > 8 ? aid.substring(0, 8) : aid;
            return ListTile(
              title: Text('Application #$aidHead'),
              subtitle: Text((a['status'] ?? 'applied') + (a['cover_letter'] != null ? ' • ${a['cover_letter']}' : '')),
            );
          },
        );
      },
    );
  }
}
