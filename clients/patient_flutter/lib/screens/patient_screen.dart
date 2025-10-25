import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';

class PatientScreen extends StatefulWidget {
  final ApiClient api;
  const PatientScreen({super.key, required this.api});

  @override
  State<PatientScreen> createState() => _PatientScreenState();
}

class _PatientScreenState extends State<PatientScreen> {
  final _cityCtrl = TextEditingController(text: 'Damascus');
  final _specialtyCtrl = TextEditingController(text: 'dentist');
  final _startCtrl = TextEditingController();
  final _endCtrl = TextEditingController();
  bool _searching = false;
  List<Map<String, dynamic>> _slots = [];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now().toUtc();
    final start = now.add(const Duration(hours: 1));
    final end = now.add(const Duration(days: 2));
    _startCtrl.text = start.toIso8601String();
    _endCtrl.text = end.toIso8601String();
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Column(children: [
        const TabBar(tabs: [Tab(text: 'Search Slots'), Tab(text: 'My Appointments')]),
        Expanded(child: TabBarView(children: [ _buildSearch(), _buildMyAppointments() ])),
      ]),
    );
  }

  Widget _buildSearch() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(children: [
        Row(children: [
          Expanded(child: TextField(controller: _cityCtrl, decoration: const InputDecoration(labelText: 'City'))),
          const SizedBox(width: 8),
          Expanded(child: TextField(controller: _specialtyCtrl, decoration: const InputDecoration(labelText: 'Specialty'))),
        ]),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: TextField(controller: _startCtrl, decoration: const InputDecoration(labelText: 'Start (ISO8601 UTC)'))),
          const SizedBox(width: 8),
          Expanded(child: TextField(controller: _endCtrl, decoration: const InputDecoration(labelText: 'End (ISO8601 UTC)'))),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: _searching ? null : () async {
              setState(() { _searching = true; });
              try {
                final res = await widget.api.searchSlots(city: _cityCtrl.text.trim(), specialty: _specialtyCtrl.text.trim(), startTime: _startCtrl.text.trim(), endTime: _endCtrl.text.trim());
                setState(() { _slots = res; });
              } catch (e) {
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
              } finally {
                setState(() { _searching = false; });
              }
            },
            child: const Text('Search'),
          )
        ]),
        const SizedBox(height: 8),
        Expanded(
          child: _slots.isEmpty
              ? const Center(child: Text('No slots'))
              : ListView.separated(
                  itemCount: _slots.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final s = _slots[i];
                    final title = '${s['doctor_name'] ?? ''} — ${s['specialty'] ?? ''}';
                    final subtitle = '${s['city'] ?? ''} • ${s['start_time']} → ${s['end_time']}';
                    return ListTile(
                      title: Text(title),
                      subtitle: Text(subtitle),
                      trailing: FilledButton(
                        onPressed: () async {
                          try {
                            final res = await widget.api.book(s['slot_id'] as String);
                            if (!mounted) return;
                            final reqId = res['payment_request_id'] as String?;
                            if (reqId != null && reqId.isNotEmpty) {
                              // Show CTA to open in Payments app
                              // ignore: use_build_context_synchronously
                              // bottom sheet
                              // ignore: use_build_context_synchronously
                              showModalBottomSheet(context: context, builder: (ctx) {
                                return Padding(
                                  padding: const EdgeInsets.all(16),
                                  child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    const Text('Payment Created', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                                    const SizedBox(height: 8),
                                    Text('Request ID: $reqId'),
                                    const SizedBox(height: 12),
                                    Row(children: [
                                      FilledButton.icon(onPressed: () async {
                                        final uri = Uri.parse('payments://request/$reqId');
                                        try { await launchUrl(uri); } catch (_) {}
                                      }, icon: const Icon(Icons.open_in_new), label: const Text('Open in Payments')),
                                      const SizedBox(width: 8),
                                      TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
                                    ])
                                  ]),
                                );
                              });
                            } else {
                              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Booked')));
                            }
                          } catch (e) {
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                          }
                        },
                        child: const Text('Book'),
                      ),
                    );
                  },
                ),
        )
      ]),
    );
  }

  Widget _buildMyAppointments() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: widget.api.myAppointments(),
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final apps = snap.data!;
        if (apps.isEmpty) return const Center(child: Text('No appointments'));
        return ListView.separated(
          itemCount: apps.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final a = apps[i];
            return ListTile(
              title: Text('Appointment #${(a['id'] ?? '').toString().substring(0, 8)}'),
              subtitle: Text('Slot: ${a['slot_id']} • ${a['status']}'),
            );
          },
        );
      },
    );
  }
}
