import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_core/shared_core.dart';
import '../services.dart';

class StaysReservationDetailScreen extends StatefulWidget {
  final String reservationId;
  const StaysReservationDetailScreen({super.key, required this.reservationId});
  @override
  State<StaysReservationDetailScreen> createState() => _StaysReservationDetailScreenState();
}

class _StaysReservationDetailScreenState extends State<StaysReservationDetailScreen> {
  bool _loading = false;
  Map<String, dynamic>? _res;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson('superapp', '/v1/stays/reservations', options: const RequestOptions(cacheTtl: Duration(seconds: 10)));
      final list = (js['reservations'] as List?) ?? const [];
      final id = widget.reservationId;
      final found = list.cast<Map>().map((e) => e.cast<String,dynamic>()).firstWhere((e) => (e['id'] ?? '').toString() == id, orElse: () => <String, dynamic>{});
      if (!mounted) return;
      setState(() => _res = found.isEmpty ? null : found);
    } catch (_) {} finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _cancel() async {
    setState(() => _loading = true);
    try {
      await servicePost('superapp', '/v1/stays/reservations/${widget.reservationId}/cancel', options: const RequestOptions(expectValidationErrors: true));
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Reservation canceled')));
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Cancel failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = _res ?? const <String, dynamic>{};
    final status = (r['status'] ?? '').toString();
    return Scaffold(
      appBar: AppBar(title: Text('Reservation ${widget.reservationId}'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: _loading ? const Center(child: CircularProgressIndicator()) : ListView(padding: const EdgeInsets.all(16), children: [
        Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('Status: ${status.isEmpty ? '-' : status}'))),
        const SizedBox(height: 8),
        Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('Check-in: ${r['check_in'] ?? ''} → Check-out: ${r['check_out'] ?? ''}'))),
        const SizedBox(height: 8),
        Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('Guests: ${r['guests'] ?? 0} • Total: ${r['total_cents'] ?? 0}c'))),
        const SizedBox(height: 16),
        if (status != 'canceled') FilledButton.tonal(onPressed: _loading ? null : _cancel, child: const Text('Cancel Reservation')),
      ]),
    );
  }
}

