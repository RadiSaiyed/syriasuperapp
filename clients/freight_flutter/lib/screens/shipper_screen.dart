import 'package:flutter/material.dart';
import '../api.dart';

class ShipperScreen extends StatefulWidget {
  final ApiClient api;
  const ShipperScreen({super.key, required this.api});
  @override
  State<ShipperScreen> createState() => _ShipperScreenState();
}

class _ShipperScreenState extends State<ShipperScreen> {
  bool _loading = false;
  final _origin = TextEditingController(text: 'Damascus');
  final _destination = TextEditingController(text: 'Aleppo');
  final _weight = TextEditingController(text: '1000');
  final _price = TextEditingController(text: '50000');
  List<Map<String, dynamic>> _loads = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.myShipperLoads();
      setState(() => _loads = rows);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _post() async {
    final w = int.tryParse(_weight.text.trim()) ?? 0;
    final p = int.tryParse(_price.text.trim()) ?? 0;
    setState(() => _loading = true);
    try {
      await widget.api.createLoad(origin: _origin.text.trim(), destination: _destination.text.trim(), weightKg: w, priceCents: p);
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Load posted')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  @override
  void initState() { super.initState(); _load(); }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          Row(children: [
            Expanded(child: TextField(controller: _origin, decoration: const InputDecoration(labelText: 'Origin'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _destination, decoration: const InputDecoration(labelText: 'Destination'))),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _weight, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Weight (kg)'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _price, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Price (SYP cents)'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading ? null : _post, child: const Text('Post Load')),
          ]),
        ]),
      ),
      const Divider(height: 1),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: _loads.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final l = _loads[i];
              return ListTile(
                title: Text('${l['origin']} → ${l['destination']}'),
                subtitle: Text('Weight: ${l['weight_kg']} kg • Price: ${l['price_cents']} SYP • Status: ${l['status']}'),
              );
            },
          ),
        ),
      )
    ]);
  }
}

