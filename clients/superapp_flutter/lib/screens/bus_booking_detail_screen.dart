import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../ui/glass.dart';
import '../services.dart';
import 'bus_ticket_screen.dart';

class BusBookingDetailScreen extends StatefulWidget {
  final String bookingId;
  const BusBookingDetailScreen({super.key, required this.bookingId});

  @override
  State<BusBookingDetailScreen> createState() => _BusBookingDetailScreenState();
}

class _BusBookingDetailScreenState extends State<BusBookingDetailScreen> {
  final _tokens = MultiTokenStore();
  Map<String, dynamic>? _booking;
  bool _loading = false;
  bool _paying = false;
  bool _showSuccess = false;
  bool _ratingInFlight = false;

  Future<Map<String, String>> _busHeaders() =>
      authHeaders('bus', store: _tokens);

  Uri _busUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('bus', path, query: query);

  Uri _paymentsUri(String path) => ServiceConfig.endpoint('payments', path);

  Future<void> _showPaymentSuccess() async {
    if (!mounted) return;
    setState(() => _showSuccess = true);
    await Future.delayed(const Duration(milliseconds: 900));
    if (!mounted) return;
    setState(() => _showSuccess = false);
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final headers = await _busHeaders();
      final r = await http.get(
        _busUri('/bookings/${widget.bookingId}'),
        headers: headers,
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _booking = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() {});
      // Auto-fetch ticket QR if confirmed
      if ((_booking?['status'] ?? '').toString().toLowerCase() == 'confirmed') {
        await _ticket();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Load failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _ticket() async {
    try {
      // Only allow ticket retrieval if booking is confirmed
      final b = _booking;
      final confirmed =
          ((b?['status'] ?? '').toString().toLowerCase() == 'confirmed');
      if (!confirmed) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Ticket available after payment')));
        }
        return;
      }
      final headers = await _busHeaders();
      final r = await http.get(
        _busUri('/bookings/${widget.bookingId}/ticket'),
        headers: headers,
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final qr = js['qr_text']?.toString() ?? '';
      if (!mounted) return;
      Navigator.push(
          context,
          MaterialPageRoute(
              builder: (_) =>
                  BusTicketScreen(bookingId: widget.bookingId, qrText: qr)));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Ticket failed: $e')));
      }
    }
  }

  Future<void> _payNow() async {
    final b = _booking;
    if (b == null) return;
    final toPhone = (b['merchant_phone'] ?? '').toString();
    final amount = (b['total_price_cents'] ?? 0) as int;
    if (toPhone.isEmpty || amount <= 0) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Missing merchant or amount')));
      }
      return;
    }
    setState(() => _paying = true);
    try {
      final headers = await authHeaders('payments');
      headers['Idempotency-Key'] =
          'bus-${widget.bookingId}-${DateTime.now().millisecondsSinceEpoch}';
      final body = jsonEncode({'to_phone': toPhone, 'amount_cents': amount});
      final r = await http.post(_paymentsUri('/wallet/transfer'),
          headers: headers, body: body);
      if (r.statusCode >= 400) {
        throw Exception(r.body);
      }
      // Confirm booking in Bus backend
      final busHeaders = await _busHeaders();
      await http.post(_busUri('/bookings/${widget.bookingId}/confirm'),
          headers: busHeaders);
      // Show success checkmark before loading ticket
      await _showPaymentSuccess();
      await _load();
      await _ticket();
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Paid and confirmed')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Pay failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _paying = false);
    }
  }

  Future<void> _cancel() async {
    try {
      final headers = await _busHeaders();
      final r = await http.post(
          _busUri('/bookings/${widget.bookingId}/cancel'),
          headers: headers);
      if (r.statusCode >= 400) throw Exception(r.body);
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Canceled')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Cancel failed: $e')));
      }
    }
  }

  DateTime? _parseDateTime(dynamic value) {
    if (value == null) return null;
    if (value is DateTime) return value.toLocal();
    try {
      return DateTime.parse(value.toString()).toLocal();
    } catch (_) {
      return null;
    }
  }

  bool _canRateBooking(Map<String, dynamic> b) {
    final status = (b['status'] ?? '').toString().toLowerCase();
    final ratingExists = b['my_rating'] != null;
    if (ratingExists) return true;
    if (status == 'canceled') {
      final departAt = _parseDateTime(b['depart_at']);
      return departAt == null || departAt.isBefore(DateTime.now());
    }
    if (status != 'confirmed' && status != 'reserved') {
      return false;
    }
    final departAt = _parseDateTime(b['depart_at']);
    if (departAt == null) return true;
    return departAt.isBefore(DateTime.now());
  }

  Future<void> _rateBooking() async {
    final b = _booking;
    if (b == null || _ratingInFlight) return;
    int rating = (b['my_rating'] as num?)?.toInt() ?? 5;
    final ctrl =
        TextEditingController(text: (b['my_rating_comment'] ?? '').toString());
    bool saving = false;
    final ok = await showDialog<bool>(
      context: context,
      barrierDismissible: !saving,
      builder: (_) => StatefulBuilder(builder: (ctx, setDlg) {
        return AlertDialog(
          title: const Text('Bewertung'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(5, (i) {
                  final idx = i + 1;
                  final active = idx <= rating;
                  return IconButton(
                    visualDensity: VisualDensity.compact,
                    onPressed: saving ? null : () => setDlg(() => rating = idx),
                    icon: Icon(active ? Icons.star : Icons.star_border),
                  );
                }),
              ),
              TextField(
                controller: ctrl,
                enabled: !saving,
                decoration:
                    const InputDecoration(labelText: 'Kommentar (optional)'),
                maxLines: 3,
              ),
            ],
          ),
          actions: [
            TextButton(
                onPressed: saving ? null : () => Navigator.pop(ctx, false),
                child: const Text('Abbrechen')),
            FilledButton(
              onPressed: saving
                  ? null
                  : () async {
                      setDlg(() => saving = true);
                      try {
                        if (mounted) {
                          setState(() => _ratingInFlight = true);
                        }
                        final headers = await _busHeaders();
                        final body = jsonEncode({
                          'rating': rating,
                          if (ctrl.text.trim().isNotEmpty)
                            'comment': ctrl.text.trim(),
                        });
                        final res = await http.post(
                            _busUri('/bookings/${widget.bookingId}/rate'),
                            headers: headers,
                            body: body);
                        if (res.statusCode >= 400) {
                          throw Exception(res.body);
                        }
                        if (ctx.mounted) Navigator.pop(ctx, true);
                      } catch (e) {
                        setDlg(() => saving = false);
                        if (ctx.mounted) {
                          ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
                              content: Text('Bewertung fehlgeschlagen: $e')));
                        }
                      } finally {
                        if (mounted) {
                          setState(() => _ratingInFlight = false);
                        }
                      }
                    },
              child: saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Speichern'),
            ),
          ],
        );
      }),
    );
    if (ok == true) {
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Danke für deine Bewertung')));
    }
  }

  Widget _ratingSummary(Map<String, dynamic> b) {
    final rating = (b['my_rating'] as num?)?.toInt();
    final comment = (b['my_rating_comment'] ?? '').toString();
    if (rating == null) {
      return const Text('Noch keine Bewertung abgegeben.');
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(
              5,
              (i) => Icon(
                    i < rating ? Icons.star : Icons.star_border,
                    size: 20,
                    color: Colors.amber,
                  )),
        ),
        if (comment.isNotEmpty)
          Padding(padding: const EdgeInsets.only(top: 4), child: Text(comment)),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final b = _booking;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Booking'),
        flexibleSpace: const Glass(
            padding: EdgeInsets.zero,
            blur: 24,
            opacity: 0.16,
            borderRadius: BorderRadius.zero),
      ),
      body: Stack(children: [
        if (_loading) const LinearProgressIndicator(),
        if (b == null)
          const Center(child: CircularProgressIndicator())
        else
          ListView(padding: const EdgeInsets.all(16), children: [
            Glass(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${b['origin']} → ${b['destination']}',
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      Text('Depart: ${b['depart_at']}'),
                      Text('Seats: ${b['seats_count']}'),
                      Text('Total: ${b['total_price_cents']} SYP'),
                      Text('Status: ${b['status']}'),
                      if (b['payment_request_id'] != null)
                        Text('Payment Request: ${b['payment_request_id']}'),
                    ]),
              ),
            ),
            const SizedBox(height: 12),
            Glass(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          FilledButton(
                            onPressed:
                                ((b['status'] ?? '').toString().toLowerCase() ==
                                        'confirmed')
                                    ? _ticket
                                    : null,
                            child: const Text('Show Ticket'),
                          ),
                          FilledButton.tonal(
                              onPressed: _cancel, child: const Text('Cancel')),
                          OutlinedButton(
                              onPressed: _paying ? null : _payNow,
                              child: const Text('Pay Now')),
                        ],
                      ),
                      const SizedBox(height: 12),
                      const Text(
                          'Pay and confirm to receive your ticket (QR check‑in).'),
                      const SizedBox(height: 12),
                      Text(
                        b['my_rating'] != null
                            ? 'Deine Bewertung'
                            : 'Noch keine Bewertung',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 4),
                      _ratingSummary(b),
                      const SizedBox(height: 12),
                      FilledButton.tonal(
                        onPressed: _canRateBooking(b) ? _rateBooking : null,
                        child: Text(b['my_rating'] != null
                            ? 'Bewertung bearbeiten'
                            : 'Bewerten'),
                      ),
                      if (!_canRateBooking(b) && b['my_rating'] == null)
                        const Padding(
                          padding: EdgeInsets.only(top: 8),
                          child: Text(
                            'Bewertung nach Abfahrtszeit möglich.',
                            style: TextStyle(fontSize: 12),
                          ),
                        ),
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
                builder: (_, s, child) =>
                    Transform.scale(scale: s, child: child),
                child: const Icon(Icons.check_circle,
                    color: Colors.greenAccent, size: 120),
              ),
            ),
          ),
      ]),
    );
  }
}
