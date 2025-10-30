import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';
import '../services.dart';
import 'bus_ticket_screen.dart';
import 'package:shared_core/shared_core.dart';
import 'dart:convert';

import '../ui/errors.dart';

class BusBookingDetailScreen extends StatefulWidget {
  final String bookingId;
  const BusBookingDetailScreen({super.key, required this.bookingId});

  @override
  State<BusBookingDetailScreen> createState() => _BusBookingDetailScreenState();
}

class _BusBookingDetailScreenState extends State<BusBookingDetailScreen> {
  static const _service = 'bus';
  Map<String, dynamic>? _booking;
  bool _loading = false;
  bool _paying = false;
  bool _showSuccess = false;
  bool _ratingInFlight = false;
  bool _queuedConfirm = false;
  bool _queuedPayment = false;

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
    _checkQueued();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final booking = await serviceGetJson(
        _service,
        '/bookings/${widget.bookingId}',
        options: const RequestOptions(expectValidationErrors: true, cacheTtl: Duration(seconds: 30), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _booking = booking);
      // Auto-fetch ticket QR if confirmed
      if ((booking['status'] ?? '').toString().toLowerCase() == 'confirmed') {
        await _ticket();
      }
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Load failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _checkQueued() async {
    try {
      final busQ = await OfflineRequestQueue('bus').load();
      final payQ = await OfflineRequestQueue('payments').load();
      final hasConfirm = busQ.any((e) => e.method.toUpperCase() == 'POST' && e.path.contains('/bookings/${widget.bookingId}/confirm'));
      final hasPayment = payQ.any((e) => e.method.toUpperCase() == 'POST' && e.path.contains('/wallet/transfer'));
      if (mounted) setState(() { _queuedConfirm = hasConfirm; _queuedPayment = hasPayment; });
    } catch (_) {}
  }

  Future<void> _retryConfirm() async {
    try {
      final q = OfflineRequestQueue('bus');
      final items = await q.load();
      bool changed = false;
      for (int i = 0; i < items.length; i++) {
        final it = items[i];
        if (it.method.toUpperCase() != 'POST' || !it.path.contains('/bookings/${widget.bookingId}/confirm')) {
          continue;
        }
        final client = SharedHttpClient(
          service: 'bus',
          baseUrl: ServiceConfig.baseUrl('bus'),
          tokenProvider: (svc) => MultiTokenStore().get(svc),
          connectivity: ConnectivityService(),
        );
        try {
          await client.send(CoreHttpRequest(
            method: it.method,
            path: it.path,
            body: it.bodyText,
            options: RequestOptions(
              queryParameters: it.query,
              idempotent: true,
              idempotencyKey: it.idempotencyKey,
              attachAuthHeader: true,
              expectValidationErrors: it.expectValidationErrors,
              headers: it.contentType == null ? null : {'Content-Type': it.contentType!},
            ),
          ));
          await OfflineQueueHistoryStore().appendFromQueued('bus', it, 'sent');
          await q.removeAt(i);
          changed = true;
        } catch (e) {
          if (e is CoreError && !e.isRetriable) {
            await OfflineQueueHistoryStore().appendFromQueued('bus', it, 'removed');
            await q.removeAt(i);
            changed = true;
          } else {
            client.close();
            break;
          }
        } finally {
          client.close();
        }
      }
      if (changed) {
        await _checkQueued();
        await _load();
      }
    } catch (_) {}
  }

  Future<void> _retryPayment() async {
    final b = _booking;
    if (b == null) return;
    final toPhone = (b['merchant_phone'] ?? '').toString();
    final amount = (b['total_price_cents'] ?? 0) as int;
    try {
      final q = OfflineRequestQueue('payments');
      final items = await q.load();
      for (int i = 0; i < items.length; i++) {
        final it = items[i];
        if (it.method.toUpperCase() != 'POST' || !it.path.contains('/wallet/transfer')) continue;
        bool match = false;
        try {
          if (it.bodyText != null && it.bodyText!.isNotEmpty) {
            final m = jsonDecode(it.bodyText!) as Map<String, dynamic>;
            final amt = (m['amount_cents'] as num?)?.toInt();
            final tp = m['to_phone']?.toString();
            match = (amt == amount && tp == toPhone);
          }
        } catch (_) {}
        if (!match) continue;
        final client = SharedHttpClient(
          service: 'payments',
          baseUrl: ServiceConfig.baseUrl('payments'),
          tokenProvider: (svc) => MultiTokenStore().get(svc),
          connectivity: ConnectivityService(),
        );
        try {
          await client.send(CoreHttpRequest(
            method: it.method,
            path: it.path,
            body: it.bodyText,
            options: RequestOptions(
              queryParameters: it.query,
              idempotent: true,
              idempotencyKey: it.idempotencyKey,
              attachAuthHeader: true,
              expectValidationErrors: it.expectValidationErrors,
              headers: it.contentType == null ? null : {'Content-Type': it.contentType!},
            ),
          ));
          await OfflineQueueHistoryStore().appendFromQueued('payments', it, 'sent');
          await q.removeAt(i);
          // continue to flush any other duplicates
        } catch (e) {
          if (e is CoreError && !e.isRetriable) {
            await OfflineQueueHistoryStore().appendFromQueued('payments', it, 'removed');
            await q.removeAt(i);
          } else {
            client.close();
            break;
          }
        } finally {
          client.close();
        }
      }
      await _checkQueued();
      await _load();
    } catch (_) {}
  }

  Future<void> _ticket() async {
    try {
      // Only allow ticket retrieval if booking is confirmed
      final b = _booking;
      final confirmed =
          ((b?['status'] ?? '').toString().toLowerCase() == 'confirmed');
      if (!confirmed) {
        if (mounted) { MessageHost.showInfoBanner(context, 'Ticket available after payment'); }
        return;
      }
      final js = await serviceGetJson(
        _service,
        '/bookings/${widget.bookingId}/ticket',
        options: const RequestOptions(expectValidationErrors: true, cacheTtl: Duration(minutes: 5), staleIfOffline: true),
      );
      final qr = js['qr_text']?.toString() ?? '';
      if (!mounted) return;
      Navigator.push(
          context,
          MaterialPageRoute(
              builder: (_) =>
                  BusTicketScreen(bookingId: widget.bookingId, qrText: qr)));
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Ticket failed');
    }
  }

  Future<void> _payNow() async {
    final b = _booking;
    if (b == null) return;
    final toPhone = (b['merchant_phone'] ?? '').toString();
    final amount = (b['total_price_cents'] ?? 0) as int;
    if (toPhone.isEmpty || amount <= 0) {
      if (mounted) { MessageHost.showInfoBanner(context, 'Missing merchant or amount'); }
      return;
    }
    setState(() => _paying = true);
    try {
      final idempotencyKey =
          'bus-${widget.bookingId}-${DateTime.now().millisecondsSinceEpoch}';
      await servicePostJson(
        'payments',
        '/wallet/transfer',
        body: {'to_phone': toPhone, 'amount_cents': amount},
        options: RequestOptions(
          headers: {'Idempotency-Key': idempotencyKey},
          expectValidationErrors: true,
        ),
      );
      await servicePost(
        _service,
        '/bookings/${widget.bookingId}/confirm',
        options: const RequestOptions(idempotent: true),
      );
      // Show success checkmark before loading ticket
      await _showPaymentSuccess();
      await _load();
      await _ticket();
      if (mounted) { showToast(context, 'Paid and confirmed'); }
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Pay failed');
    } finally {
      if (mounted) setState(() => _paying = false);
    }
  }

  Future<void> _cancel() async {
    try {
      await servicePost(
        _service,
        '/bookings/${widget.bookingId}/cancel',
        options: const RequestOptions(idempotent: true),
      );
      await _load();
      if (mounted) { MessageHost.showInfoBanner(context, 'Canceled'); }
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Cancel failed');
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
                        await servicePost(
                          _service,
                          '/bookings/${widget.bookingId}/rate',
                          body: {
                            'rating': rating,
                            if (ctrl.text.trim().isNotEmpty)
                              'comment': ctrl.text.trim(),
                          },
                          options: const RequestOptions(
                            expectValidationErrors: true,
                            idempotent: true,
                          ),
                        );
                        if (ctx.mounted) Navigator.pop(ctx, true);
                      } catch (e) {
                        setDlg(() => saving = false);
                        if (ctx.mounted) {
                          presentError(ctx, e, message: 'Bewertung fehlgeschlagen');
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
      showToast(context, 'Danke für deine Bewertung');
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
                      if (_queuedPayment || _queuedConfirm)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  _queuedPayment && _queuedConfirm
                                      ? 'Hinweis: Zahlung und Bestätigung ausstehend.'
                                      : _queuedPayment
                                          ? 'Hinweis: Zahlung ausstehend.'
                                          : 'Hinweis: Bestätigung ausstehend.',
                                  style: const TextStyle(fontSize: 12),
                                ),
                              ),
                              if (_queuedPayment)
                                TextButton(onPressed: _retryPayment, child: const Text('Zahlung jetzt senden')),
                              if (_queuedConfirm)
                                TextButton(onPressed: _retryConfirm, child: const Text('Bestätigen')),
                            ],
                          ),
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
