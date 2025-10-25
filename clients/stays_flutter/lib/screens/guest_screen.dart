import 'package:flutter/material.dart';

import '../api.dart';

class GuestScreen extends StatefulWidget {
  final ApiClient api;
  const GuestScreen({super.key, required this.api});

  @override
  State<GuestScreen> createState() => _GuestScreenState();
}

class _GuestScreenState extends State<GuestScreen> {
  final _cityCtrl = TextEditingController(text: 'Damascus');
  final _checkInCtrl = TextEditingController();
  final _checkOutCtrl = TextEditingController();
  final _guestsCtrl = TextEditingController(text: '2');
  List<Map<String, dynamic>> _results = [];
  bool _searching = false;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    final ci = DateTime(now.year, now.month, now.day).add(const Duration(days: 1));
    final co = ci.add(const Duration(days: 2));
    _checkInCtrl.text = ci.toIso8601String().substring(0, 10);
    _checkOutCtrl.text = co.toIso8601String().substring(0, 10);
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Column(children: [
        const TabBar(tabs: [Tab(text: 'Search'), Tab(text: 'My Reservations')]),
        Expanded(
          child: TabBarView(children: [
            _buildSearch(),
            _buildMyReservations(),
          ]),
        )
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
          Expanded(child: TextField(controller: _checkInCtrl, decoration: const InputDecoration(labelText: 'Check-in (YYYY-MM-DD)'))),
          const SizedBox(width: 8),
          Expanded(child: TextField(controller: _checkOutCtrl, decoration: const InputDecoration(labelText: 'Check-out (YYYY-MM-DD)'))),
          const SizedBox(width: 8),
          SizedBox(width: 80, child: TextField(controller: _guestsCtrl, decoration: const InputDecoration(labelText: 'Guests'))),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: _searching ? null : () async {
              setState(() { _searching = true; });
              try {
                final res = await widget.api.searchAvailability(city: _cityCtrl.text.trim(), checkIn: _checkInCtrl.text.trim(), checkOut: _checkOutCtrl.text.trim(), guests: int.tryParse(_guestsCtrl.text.trim()) ?? 1);
                setState(() { _results = res; });
              } catch (e) {
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
              } finally {
                setState(() { _searching = false; });
              }
            },
            child: const Text('Search'),
          )
        ]),
        const SizedBox(height: 12),
        Expanded(
          child: _results.isEmpty
              ? const Center(child: Text('No results'))
              : ListView.separated(
                  itemCount: _results.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final r = _results[i];
                    final title = '${r['property_name']} — ${r['unit_name']}';
                    final subtitle = 'Cap: ${r['capacity']} • ${((r['nightly_price_cents'] ?? 0) / 100).toStringAsFixed(2)} / night • total ${((r['total_cents'] ?? 0) / 100).toStringAsFixed(2)}';
                    return ListTile(
                      title: Text(title),
                      subtitle: Text(subtitle),
                      trailing: FilledButton(
                        onPressed: () async {
                          try {
                            await widget.api.createReservation(unitId: r['unit_id'] as String, checkIn: _checkInCtrl.text.trim(), checkOut: _checkOutCtrl.text.trim(), guests: int.tryParse(_guestsCtrl.text.trim()) ?? 1);
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Booked')));
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

  Widget _buildMyReservations() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: widget.api.myReservations(),
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final rs = snap.data!;
        if (rs.isEmpty) return const Center(child: Text('No reservations'));
        return ListView.separated(
          itemCount: rs.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final r = rs[i];
            return ListTile(
              title: Text('Reservation #${(r['id'] ?? '').toString().substring(0, 8)}'),
              subtitle: Text('${r['check_in']} → ${r['check_out']} • ${(r['total_cents'] / 100).toStringAsFixed(2)}'),
            );
          },
        );
      },
    );
  }
}

