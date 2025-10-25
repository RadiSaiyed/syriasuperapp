import 'package:flutter/material.dart';

import '../api.dart';

class HostScreen extends StatefulWidget {
  final ApiClient api;
  const HostScreen({super.key, required this.api});

  @override
  State<HostScreen> createState() => _HostScreenState();
}

class _HostScreenState extends State<HostScreen> {
  Future<List<Map<String, dynamic>>>? _propsFuture;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    setState(() { _propsFuture = widget.api.myProperties(); });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _propsFuture,
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final props = snap.data!;
        if (props.isEmpty) return _buildCreateProperty();
        return _buildProperties(props);
      },
    );
  }

  Widget _buildCreateProperty() {
    final nameCtrl = TextEditingController();
    final typeCtrl = TextEditingController(text: 'hotel');
    final cityCtrl = TextEditingController(text: 'Damascus');
    final descCtrl = TextEditingController();
    bool loading = false; String? error;
    return StatefulBuilder(builder: (context, setState) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Text('Create Property', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
              Row(children: [
                Expanded(child: TextField(controller: typeCtrl, decoration: const InputDecoration(labelText: 'Type (hotel/apartment)'))),
                const SizedBox(width: 8),
                Expanded(child: TextField(controller: cityCtrl, decoration: const InputDecoration(labelText: 'City'))),
              ]),
              const SizedBox(height: 12),
              TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Description')),
              const SizedBox(height: 12),
              if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: loading ? null : () async {
                  setState(() { loading = true; error = null; });
                  try {
                    await widget.api.createProperty(name: nameCtrl.text.trim(), type: typeCtrl.text.trim(), city: cityCtrl.text.trim(), description: descCtrl.text.trim());
                    if (mounted) _reload();
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

  Widget _buildProperties(List<Map<String, dynamic>> props) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
            onPressed: () async {
              await showDialog(context: context, builder: (_) => AlertDialog(content: SizedBox(width: 520, child: _buildCreateProperty())));
              _reload();
            },
            icon: const Icon(Icons.add_business),
            label: const Text('New Property'),
          ),
        ),
      ),
      Expanded(
        child: ListView.separated(
          itemCount: props.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final p = props[i];
            return ExpansionTile(
              title: Text(p['name'] ?? ''),
              subtitle: Text('${p['type'] ?? ''} — ${p['city'] ?? ''}'),
              children: [
                FutureBuilder<List<Map<String, dynamic>>>(
                  future: widget.api.listUnits(p['id'] as String),
                  builder: (context, snap) {
                    final units = snap.data ?? const [];
                    return Column(children: [
                      Align(
                        alignment: Alignment.centerRight,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 8.0),
                          child: FilledButton.icon(
                            onPressed: () async {
                              await _showAddUnitDialog(p['id'] as String);
                              setState(() {});
                            },
                            icon: const Icon(Icons.add),
                            label: const Text('Add Unit'),
                          ),
                        ),
                      ),
                      if (units.isEmpty) const ListTile(title: Text('No units')),
                      for (final u in units) ListTile(title: Text(u['name'] ?? ''), subtitle: Text('cap ${u['capacity']} • units ${u['total_units']} • ${(u['price_cents_per_night'] / 100).toStringAsFixed(2)}')),
                      const SizedBox(height: 8),
                    ]);
                  },
                ),
              ],
            );
          },
        ),
      ),
      ListTile(
        title: const Text('Host Reservations'),
        trailing: FilledButton(
          onPressed: () async {
            final rs = await widget.api.hostReservations();
            if (!mounted) return;
            await showDialog(context: context, builder: (_) => AlertDialog(
              title: const Text('Reservations'),
              content: SizedBox(width: 420, child: rs.isEmpty ? const Text('No reservations') : Column(mainAxisSize: MainAxisSize.min, children: rs.map((r) => ListTile(title: Text(r['id'].toString().substring(0,8)), subtitle: Text('${r['check_in']} → ${r['check_out']}'), trailing: Text(((r['total_cents'] ?? 0) / 100).toStringAsFixed(2)))).toList())),
              actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
            ));
          },
          child: const Text('View'),
        ),
      ),
    ]);
  }

  Future<void> _showAddUnitDialog(String propertyId) async {
    final nameCtrl = TextEditingController(text: 'Deluxe');
    final capCtrl = TextEditingController(text: '2');
    final totCtrl = TextEditingController(text: '1');
    final priceCtrl = TextEditingController(text: '50000');
    await showDialog(context: context, builder: (_) => AlertDialog(
      title: const Text('Add Unit'),
      content: SizedBox(width: 420, child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
        Row(children: [
          Expanded(child: TextField(controller: capCtrl, decoration: const InputDecoration(labelText: 'Capacity'))),
          const SizedBox(width: 8),
          Expanded(child: TextField(controller: totCtrl, decoration: const InputDecoration(labelText: 'Total units'))),
        ]),
        TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price per night (cents)')),
      ])),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: () async {
          try {
            await widget.api.createUnit(propertyId: propertyId, name: nameCtrl.text.trim(), capacity: int.tryParse(capCtrl.text.trim()) ?? 2, totalUnits: int.tryParse(totCtrl.text.trim()) ?? 1, priceCentsPerNight: int.tryParse(priceCtrl.text.trim()) ?? 0);
            if (context.mounted) Navigator.pop(context);
          } catch (e) {
            if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
          }
        }, child: const Text('Add')),
      ],
    ));
  }
}

