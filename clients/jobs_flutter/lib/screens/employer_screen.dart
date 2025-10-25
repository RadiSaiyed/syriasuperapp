import 'package:flutter/material.dart';

import '../api.dart';

class EmployerScreen extends StatefulWidget {
  final ApiClient api;
  const EmployerScreen({super.key, required this.api});

  @override
  State<EmployerScreen> createState() => _EmployerScreenState();
}

class _EmployerScreenState extends State<EmployerScreen> {
  Future<Map<String, dynamic>?>? _companyFuture;

  @override
  void initState() {
    super.initState();
    _companyFuture = widget.api.getCompany();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>?>(
      future: _companyFuture,
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final company = snap.data;
        if (company == null) return _buildCreateCompany();
        return _buildJobs(company);
      },
    );
  }

  Widget _buildCreateCompany() {
    final nameCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    bool loading = false;
    String? error;
    return StatefulBuilder(builder: (context, setState) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Text('Create Company', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Company name')),
              const SizedBox(height: 12),
              TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Description')),
              const SizedBox(height: 12),
              if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: loading ? null : () async {
                  setState(() { loading = true; error = null; });
                  try {
                    await widget.api.createCompany(name: nameCtrl.text.trim(), description: descCtrl.text.trim());
                    if (mounted) this.setState(() { _companyFuture = widget.api.getCompany(); });
                  } catch (e) {
                    setState(() { error = e.toString(); });
                  } finally {
                    setState(() { loading = false; });
                  }
                },
                child: const Text('Create'),
              )
            ]),
          ),
        ),
      );
    });
  }

  Widget _buildJobs(Map<String, dynamic> company) {
    return Column(children: [
      ListTile(title: Text(company['name'] ?? 'Company'), subtitle: Text(company['description'] ?? '')),
      const Divider(height: 1),
      Expanded(
        child: FutureBuilder<List<Map<String, dynamic>>>(
          future: widget.api.myJobs(),
          builder: (context, snap) {
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final jobs = snap.data!;
            return Column(children: [
              Padding(
                padding: const EdgeInsets.all(8.0),
                child: Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton.icon(
                    onPressed: () async {
                      final job = await _showCreateJobDialog(context);
                      if (job != null) setState(() {});
                    },
                    icon: const Icon(Icons.add),
                    label: const Text('New Job'),
                  ),
                ),
              ),
              Expanded(
                child: ListView.separated(
                  itemCount: jobs.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final j = jobs[i];
                    return ListTile(
                      title: Text(j['title'] ?? ''),
                      subtitle: Text((j['location'] ?? '') + ((j['salary_cents'] != null) ? ' • ${(j['salary_cents'] / 100).toStringAsFixed(2)}' : '')),
                      onTap: () async {
                        final apps = await widget.api.jobApplications(j['id'] as String);
                        if (!mounted) return;
                        await showDialog(
                          context: context,
                          builder: (_) => AlertDialog(
                            title: const Text('Applications'),
                            content: SizedBox(
                              width: 400,
                              child: apps.isEmpty
                                  ? const Text('No applications yet')
                                  : Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: apps.map((a) {
                                        final uid = (a['user_id'] ?? '').toString();
                                        final head = uid.length > 8 ? uid.substring(0, 8) : uid;
                                        return ListTile(
                                          title: Text(head),
                                          subtitle: Text(a['cover_letter'] ?? ''),
                                          trailing: Text(a['status'] ?? 'applied'),
                                        );
                                      }).toList(),
                                    ),
                            ),
                            actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
            ]);
          },
        ),
      ),
    ]);
  }

  Future<Map<String, dynamic>?> _showCreateJobDialog(BuildContext context) async {
    final titleCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final locCtrl = TextEditingController();
    final salaryCtrl = TextEditingController();
    return showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Create Job'),
        content: SizedBox(
          width: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: titleCtrl, decoration: const InputDecoration(labelText: 'Title')),
              TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Description')),
              TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Location')),
              TextField(controller: salaryCtrl, decoration: const InputDecoration(labelText: 'Salary (cents)')),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              final salary = int.tryParse(salaryCtrl.text.trim());
              try {
                final job = await widget.api.createJob(title: titleCtrl.text.trim(), description: descCtrl.text.trim(), location: locCtrl.text.trim(), salaryCents: salary);
                if (context.mounted) Navigator.pop(context, job);
              } catch (e) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
              }
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }
}
