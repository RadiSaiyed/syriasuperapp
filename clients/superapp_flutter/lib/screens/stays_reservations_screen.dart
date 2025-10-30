import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_core/shared_core.dart';
import '../services.dart';
import 'stays_reservation_detail_screen.dart';

class StaysReservationsScreen extends StatefulWidget {
  const StaysReservationsScreen({super.key});
  @override
  State<StaysReservationsScreen> createState() => _StaysReservationsScreenState();
}

class _StaysReservationsScreenState extends State<StaysReservationsScreen> {
  bool _loading = false;
  List<dynamic> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson('superapp', '/v1/stays/reservations', options: const RequestOptions(cacheTtl: Duration(seconds: 30)));
      if (!mounted) return;
      setState(() => _items = (js['reservations'] as List?) ?? const []);
    } catch (_) {} finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reservations'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: _loading ? const Center(child: CircularProgressIndicator()) : ListView.builder(
        itemCount: _items.length,
        itemBuilder: (_, i) {
          final it = _items[i] as Map<String, dynamic>? ?? const {};
          final id = (it['id'] ?? '').toString();
          return GlassCard(child: ListTile(
            title: Text('Reservation $id'),
            subtitle: Text('${it['status'] ?? '-'} • ${it['check_in'] ?? ''} → ${it['check_out'] ?? ''}'),
            onTap: id.isEmpty ? null : () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => StaysReservationDetailScreen(reservationId: id)));
            },
          ));
        },
      ),
    );
  }
}
