import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import '../services.dart';
import 'bus_booking_detail_screen.dart';
import '../ui/steering_wheel_icon.dart';
import '../auth.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';
import 'package:shared_core/shared_core.dart';

import '../ui/errors.dart';

class BusTripScreen extends StatefulWidget {
  final String tripId;
  const BusTripScreen({super.key, required this.tripId});

  @override
  State<BusTripScreen> createState() => _BusTripScreenState();
}

class _BusTripScreenState extends State<BusTripScreen> {
  static const _service = 'bus';
  Map<String, dynamic>? _trip;
  int _seatsTotal = 0;
  Set<int> _reserved = {};
  final Set<int> _selected = {};
  bool _loading = false;
  bool _showSuccess = false;

  Future<void> _showPaymentSuccess() async {
    if (!mounted) return;
    setState(() => _showSuccess = true);
    await Future.delayed(const Duration(milliseconds: 900));
    if (!mounted) return;
    setState(() => _showSuccess = false);
  }

  String _fmtTime(dynamic iso) {
    if (iso == null) return '--:--';
    try {
      final dt = DateTime.parse(iso.toString()).toLocal();
      final hh = dt.hour.toString().padLeft(2, '0');
      final mm = dt.minute.toString().padLeft(2, '0');
      return '$hh:$mm';
    } catch (_) {
      return '--:--';
    }
  }

  String _fmtDuration(dynamic startIso, dynamic endIso) {
    if (startIso == null || endIso == null) return '';
    try {
      final a = DateTime.parse(startIso.toString());
      final b = DateTime.parse(endIso.toString());
      final mins = b.difference(a).inMinutes.abs();
      if (mins <= 59) {
        final mm = mins.toString().padLeft(2, '0');
        return '$mm:00';
      }
      final hh = (mins ~/ 60).toString().padLeft(2, '0');
      final mm = (mins % 60).toString().padLeft(2, '0');
      return '$hh:$mm';
    } catch (_) {
      return '';
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final trip = await serviceGetJson(
        _service,
        '/trips/${widget.tripId}',
        options: const RequestOptions(cacheTtl: Duration(minutes: 5), staleIfOffline: true),
      );
      final seats = await serviceGetJson(
        _service,
        '/trips/${widget.tripId}/seats',
        options: const RequestOptions(cacheTtl: Duration(seconds: 20), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() {
        _trip = trip;
        _seatsTotal = (seats['seats_total'] as int? ?? 0);
        _reserved = ((seats['reserved'] as List?) ?? [])
            .map((e) => int.tryParse('$e') ?? 0)
            .toSet();
      });
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Trip load failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _book() async {
    if (_selected.isEmpty) { MessageHost.showInfoBanner(context, 'Select at least 1 seat'); return; }
    final price = (_trip?['price_cents'] as int? ?? 0);
    final total = price * _selected.length;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Pay to book'),
        content: Text('You will pay $total SYP to book ${_selected.length} seat(s). Continue?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Pay & Book')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _loading = true);
    String? bookingId;
    try {
      // 1) Create booking (reserve seats). Allow offline queueing to create later.
      final booking = await servicePostJson(
        _service,
        '/bookings',
        body: {
          'trip_id': widget.tripId,
          'seats_count': _selected.length,
          'seat_numbers': _selected.toList(),
        },
        options: const RequestOptions(expectValidationErrors: true, idempotent: true, queueIfOffline: true),
      );
      bookingId = booking['id']?.toString();
      final toPhone = booking['merchant_phone']?.toString();
      final amount = (booking['total_price_cents'] as int? ?? total);

      // 2) Pay now from wallet (biometric confirmation if enabled)
      // If booking was queued offline (no id/id missing), skip payment/confirm and inform user.
      if (bookingId == null) {
        if (mounted) {
          showToast(context, 'Offline – Buchung wird erstellt, sobald Verbindung besteht. Zahlung später möglich.');
        }
        return;
      }
      if (toPhone == null || toPhone.isEmpty) {
        throw Exception('Missing merchant');
      }
      final bioOk = await requireBiometricIfEnabled(context, reason: 'Confirm payment');
      if (!bioOk) throw Exception('Payment canceled');
      try {
        await servicePostJson(
          'payments',
          '/wallet/transfer',
          body: {'to_phone': toPhone, 'amount_cents': amount},
          options: const RequestOptions(idempotent: true, expectValidationErrors: true),
        );
      } catch (error) {
        try {
          await servicePost(
            _service,
            '/bookings/$bookingId/cancel',
            options: const RequestOptions(idempotent: true),
          );
        } catch (_) {}
        rethrow;
      }

      // 3) Confirm booking
      await servicePost(
        _service,
        '/bookings/$bookingId/confirm',
        options: const RequestOptions(idempotent: true),
      );

      // 4) Update local seats and show success before navigating to detail
      _reserved.addAll(_selected);
      _selected.clear();
      if (!mounted) return;
      await _showPaymentSuccess();
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => BusBookingDetailScreen(bookingId: bookingId!)));
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Booking failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = _trip;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trip'),
        flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero),
      ),
      body: Stack(children: [
        if (t == null)
          const Center(child: CircularProgressIndicator())
        else
          ListView(padding: const EdgeInsets.all(16), children: [
              Glass(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${t['origin']} → ${t['destination']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Text('${t['operator_name']}'),
                    Text('Depart: ${_fmtTime(t['depart_at'])}  •  Arrive: ${_fmtTime(t['arrive_at'])}  •  Dur: ${_fmtDuration(t['depart_at'], t['arrive_at'])}'),
                    const SizedBox(height: 8),
                    Text('Price: ${t['price_cents']} SYP'),
                    Text('Seats available: ${t['seats_available']}'),
                    Text('Bus: ${t['bus_model'] != null ? t['bus_model'].toString() : '—'}${t['bus_year'] != null ? ' (${t['bus_year']})' : ''}'),
                  ]),
                ),
              ),
              const SizedBox(height: 12),
              Glass(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    const Text('Select seats', style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    _seatGrid(),
                    const SizedBox(height: 8),
                    FilledButton(onPressed: _loading ? null : _book, child: Text('Book ${_selected.length} seat(s)')),
                  ]),
                ),
              ),
            ]),
        if (_showSuccess)
          Positioned.fill(
            child: Container(
              color: Colors.black.withValues(alpha: 0.35),
              alignment: Alignment.center,
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0.9, end: 1.0),
                duration: const Duration(milliseconds: 300),
                curve: Curves.easeOutBack,
                builder: (_, s, child) => Transform.scale(scale: s, child: child),
                child: const Icon(Icons.check_circle, color: Colors.greenAccent, size: 120),
              ),
            ),
          ),
      ]),
    );
  }

  Widget _seatGrid() {
    // 2+2 Layout mit Gang in der Mitte
    final total = _seatsTotal <= 0 ? 40 : _seatsTotal;
    const leftPerRow = 2;
    const rightPerRow = 2;
    const perRow = leftPerRow + rightPerRow;
    final rows = (total / perRow).ceil();

    Widget seat(int seatNo) {
      final taken = _reserved.contains(seatNo);
      final sel = _selected.contains(seatNo);
      Color bg;
      if (taken) {
        bg = Colors.red.withValues(alpha: 0.35);
      } else if (sel) {
        bg = Colors.green.withValues(alpha: 0.35);
      } else {
        bg = Colors.white.withValues(alpha: 0.08);
      }
      return GestureDetector(
        onTap: taken
            ? null
            : () {
                setState(() {
                  if (sel) {
                    _selected.remove(seatNo);
                  } else {
                    if (_selected.length < 6) _selected.add(seatNo);
                  }
                });
              },
        child: Container(
          width: 46,
          height: 38,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.white24),
          ),
          child: Text('$seatNo', style: const TextStyle(fontSize: 12)),
        ),
      );
    }

    final List<Widget> children = [];
    // Kein separates Symbol oberhalb — das Lenkrad wird in die erste Reihe integriert

    int current = 1;
    for (int r = 0; r < rows; r++) {
      final List<Widget> left = [];
      for (int i = 0; i < leftPerRow; i++) {
        if (current <= total) {
          left.add(seat(current));
          current++;
        } else {
          left.add(const SizedBox(width: 46, height: 38));
        }
      }
      final List<Widget> right = [];
      for (int i = 0; i < rightPerRow; i++) {
        if (current <= total) {
          right.add(seat(current));
          current++;
        } else {
          right.add(const SizedBox(width: 46, height: 38));
        }
      }
      children.add(Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Lenkrad vor der linken Sitzreihe (nur in der ersten Reihe)
            if (r == 0) ...[
              SteeringWheelIcon(size: 20, color: Colors.white.withValues(alpha: 0.9), strokeWidth: 2.0),
              const SizedBox(width: 6),
            ] else
              const SizedBox(width: 26),
            ...left,
            const SizedBox(width: 30), // Gang
            ...right,
          ],
        ),
      ));
    }

    // Legende
    children.add(const SizedBox(height: 8));
    children.add(Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _legendBox(color: Colors.white.withValues(alpha: 0.12), label: 'Free'),
        const SizedBox(width: 12),
        _legendBox(color: Colors.green.withValues(alpha: 0.35), label: 'Selected'),
        const SizedBox(width: 12),
        _legendBox(color: Colors.red.withValues(alpha: 0.35), label: 'Reserved'),
      ],
    ));

    return Column(children: children);
  }

  Widget _legendBox({required Color color, required String label}) {
    return Row(children: [
      Container(width: 16, height: 12, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3), border: Border.all(color: Colors.white24))),
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(fontSize: 12)),
    ]);
  }
}
// ignore_for_file: use_build_context_synchronously
