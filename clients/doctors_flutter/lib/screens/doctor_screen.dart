import 'package:flutter/material.dart';

import '../api.dart';

class DoctorScreen extends StatefulWidget {
  final ApiClient api;
  const DoctorScreen({super.key, required this.api});

  @override
  State<DoctorScreen> createState() => _DoctorScreenState();
}

class _DoctorScreenState extends State<DoctorScreen> {
  Future<List<Map<String, dynamic>>>? _slotsFuture;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    setState(() { _slotsFuture = widget.api.mySlots(); });
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(12),
        child: Align(
          alignment: Alignment.centerRight,
          child: Wrap(spacing: 8, children: [
            FilledButton.icon(onPressed: () async { await _showProfileDialog(); }, icon: const Icon(Icons.badge), label: const Text('Profile')),
            FilledButton.icon(onPressed: () async { await _showAddSlotDialog(); _reload(); }, icon: const Icon(Icons.add_alarm), label: const Text('Add Slot')),
            FilledButton.icon(onPressed: () async { final a = await widget.api.doctorAppointments(); if (!mounted) return; await showDialog(context: context, builder: (_) => AlertDialog(title: const Text('Appointments'), content: SizedBox(width: 420, child: a.isEmpty ? const Text('No appointments') : Column(mainAxisSize: MainAxisSize.min, children: a.map((e) => ListTile(title: Text(e['id'].toString().substring(0,8)), subtitle: Text(e['status'] ?? ''))).toList())), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],)); }, icon: const Icon(Icons.event_note), label: const Text('Appointments')),
          ]),
        ),
      ),
      Expanded(child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _slotsFuture,
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final slots = snap.data!;
          if (slots.isEmpty) return const Center(child: Text('No slots yet'));
          return ListView.separated(
            itemCount: slots.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final s = slots[i];
              return ListTile(
                title: Text('${s['start_time']} → ${s['end_time']}'),
                trailing: Text((s['is_booked'] == true) ? 'Booked' : 'Free'),
              );
            },
          );
        },
      )),
    ]);
  }

  Future<void> _showProfileDialog() async {
    final specCtrl = TextEditingController(text: 'dentist');
    final cityCtrl = TextEditingController(text: 'Damascus');
    final clinicCtrl = TextEditingController(text: 'Clinic');
    await showDialog(context: context, builder: (_) => AlertDialog(
      title: const Text('Doctor Profile'),
      content: SizedBox(width: 420, child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: specCtrl, decoration: const InputDecoration(labelText: 'Specialty')),
        TextField(controller: cityCtrl, decoration: const InputDecoration(labelText: 'City')),
        TextField(controller: clinicCtrl, decoration: const InputDecoration(labelText: 'Clinic name')),
      ])),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: () async {
          try {
            await widget.api.upsertProfile(specialty: specCtrl.text.trim(), city: cityCtrl.text.trim(), clinicName: clinicCtrl.text.trim());
            if (context.mounted) Navigator.pop(context);
          } catch (e) {
            if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
          }
        }, child: const Text('Save')),
      ],
    ));
  }

  Future<void> _showAddSlotDialog() async {
    final now = DateTime.now().toUtc();
    final startCtrl = TextEditingController(text: now.add(const Duration(hours: 1)).toIso8601String());
    final endCtrl = TextEditingController(text: now.add(const Duration(hours: 1, minutes: 30)).toIso8601String());
    await showDialog(context: context, builder: (_) => AlertDialog(
      title: const Text('Add Slot'),
      content: SizedBox(width: 420, child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: startCtrl, decoration: const InputDecoration(labelText: 'Start (ISO8601 UTC)')),
        TextField(controller: endCtrl, decoration: const InputDecoration(labelText: 'End (ISO8601 UTC)')),
      ])),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: () async {
          try {
            await widget.api.addSlot(startTime: startCtrl.text.trim(), endTime: endCtrl.text.trim());
            if (!context.mounted) return; 
            Navigator.pop(context);
          } catch (e) {
            if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
          }
        }, child: const Text('Add')),
      ],
    ));
  }
}

