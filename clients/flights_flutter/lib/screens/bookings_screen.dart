import 'package:flutter/material.dart';
import '../api.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';

class BookingsScreen extends StatefulWidget {
  final ApiClient api;
  const BookingsScreen({super.key, required this.api});
  @override
  State<BookingsScreen> createState() => _BookingsScreenState();
}

class _BookingsScreenState extends State<BookingsScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.listBookings();
      setState(() => _items = rows);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _cancel(String id) async {
    setState(() => _loading = true);
    try {
      await widget.api.cancelBooking(id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _ticket(String id) async {
    setState(() => _loading = true);
    try {
      final t = await widget.api.bookingTicket(id);
      final ticketText = (t['qr_text'] as String?);
      if (!mounted) return;
      await showModalBottomSheet(
        context: context,
        showDragHandle: true,
        builder: (ctx) => Padding(
          padding: const EdgeInsets.all(16),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Ticket QR Text', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            SelectableText(ticketText ?? ''),
            const SizedBox(height: 8),
            Row(children: [
              TextButton.icon(
                onPressed: () async {
                  if (ticketText != null) {
                    await Clipboard.setData(ClipboardData(text: ticketText));
                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied ticket text')));
                  }
                },
                icon: const Icon(Icons.copy),
                label: const Text('Copy'),
              ),
            ])
          ]),
        ),
      );
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemCount: _items.length,
            itemBuilder: (context, i) {
              final b = _items[i];
              return ListTile(
                title: Text('${b['origin']} → ${b['destination']} • ${b['airline_name']}'),
                subtitle: Text('Depart: ${b['depart_at']}\nSeats: ${b['seats_count']} • Total: ${b['total_price_cents']} SYP\nStatus: ${b['status']}'),
                trailing: _buildActions(b),
              );
            },
          ),
        ),
      ),
    ]);
  }

  Widget _buildActions(Map<String, dynamic> b) {
    final status = (b['status'] as String?) ?? '';
    final paymentId = b['payment_request_id'] as String?;
    final canCancel = status != 'canceled';
    final canOpenPayment = paymentId != null && paymentId.isNotEmpty;
    if (!canCancel && !canOpenPayment) return const Text('Canceled');
    return Wrap(spacing: 8, children: [
      if (canOpenPayment)
        FilledButton.icon(
          onPressed: _loading ? null : () => _openPayment(paymentId!),
          icon: const Icon(Icons.open_in_new),
          label: const Text('Open Payment'),
        ),
      if (canCancel)
        OutlinedButton(
          onPressed: _loading ? null : () => _cancel(b['id'] as String),
          child: const Text('Cancel'),
        ),
      OutlinedButton.icon(onPressed: _loading ? null : () => _ticket(b['id'] as String), icon: const Icon(Icons.qr_code_2), label: const Text('Ticket')),
    ]);
  }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    final ok = await canLaunchUrl(uri);
    if (ok) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed / cannot open link.')));
      }
    }
  }
}

