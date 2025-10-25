import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';

class SearchScreen extends StatefulWidget {
  final ApiClient api;
  const SearchScreen({super.key, required this.api});
  @override
  State<SearchScreen> create() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _origin = TextEditingController(text: 'Damascus');
  final _destination = TextEditingController(text: 'Aleppo');
  DateTime _date = DateTime.now();
  final _seatsCtrl = TextEditingController(text: '1');
  final _seatNumsCtrl = TextEditingController();
  final _promoCtrl = TextEditingController();
  bool _loading = false;
  List<Map<String, dynamic>> _results = [];
  String? _lastPaymentId;

  Future<void> _pickDate() async {
    final picked = await showDatePicker(context: context, firstDate: DateTime.now().subtract(const Duration(days: 0)), lastDate: DateTime.now().add(const Duration(days: 30)), initialDate: _date);
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _search() async {
    if (_origin.text.trim().isEmpty || _destination.text.trim().isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please enter origin and destination.')));
      }
      return;
    }
    setState(() => _loading = true);
    try {
      final items = await widget.api.searchFlights(origin: _origin.text.trim(), destination: _destination.text.trim(), date: _date);
      setState(() => _results = items);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _book(String flightId) async {
    final seats = int.tryParse(_seatsCtrl.text.trim()) ?? 1;
    if (seats < 1 || seats > 6) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Seats must be between 1 and 6.')));
      }
      return;
    }
    List<int>? seatNums;
    if (_seatNumsCtrl.text.trim().isNotEmpty) {
      try {
        seatNums = _seatNumsCtrl.text.split(',').map((e) => int.parse(e.trim())).toList();
      } catch (_) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Invalid seat numbers format.')));
        return;
      }
    }
    setState(() => _loading = true);
    try {
      final res = await widget.api.createBooking(
        flightId: flightId,
        seatsCount: seats,
        seatNumbers: seatNums,
        promoCode: _promoCtrl.text.trim().isEmpty ? null : _promoCtrl.text.trim(),
      );
      _lastPaymentId = res['payment_request_id'] as String?;
      if (!mounted) return;
      await showModalBottomSheet(
        context: context,
        showDragHandle: true,
        builder: (_) => _BookingResultSheet(paymentId: _lastPaymentId),
      );
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (_loading) const LinearProgressIndicator(),
      Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Search Flights', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: TextField(controller: _origin, decoration: const InputDecoration(labelText: 'Origin'))),
            const SizedBox(width: 12),
            Expanded(child: TextField(controller: _destination, decoration: const InputDecoration(labelText: 'Destination'))),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: Text('Date: ${DateFormat('yyyy-MM-dd').format(_date)}')),
            const SizedBox(width: 8),
            OutlinedButton.icon(onPressed: _pickDate, icon: const Icon(Icons.calendar_today), label: const Text('Pick')),
            const Spacer(),
            FilledButton(onPressed: _search, child: const Text('Search')),
          ]),
        ]),
      ),
      const Divider(height: 1),
      Expanded(
        child: ListView.separated(
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemCount: _results.length,
          itemBuilder: (context, i) {
            final f = _results[i];
            return ListTile(
              title: Text('${f['origin']} → ${f['destination']} • ${f['airline_name']}'),
              subtitle: Text('Depart: ${f['depart_at']}\nPrice: ${f['price_cents']} SYP\nSeats available: ${f['seats_available']}'),
              trailing: Wrap(spacing: 8, children: [
                OutlinedButton.icon(onPressed: () => _seats(f['id'] as String), icon: const Icon(Icons.event_seat), label: const Text('Seats')),
                FilledButton(onPressed: () => _book(f['id'] as String), child: const Text('Book')),
              ]),
            );
          },
        ),
      ),
    ]);
  }

  Future<void> _seats(String flightId) async {
    setState(() => _loading = true);
    try {
      final s = await widget.api.flightSeats(flightId);
      if (!mounted) return;
      await showModalBottomSheet(
        context: context,
        showDragHandle: true,
        builder: (ctx) {
          final total = s['seats_total'] as int? ?? 0;
          final reserved = ((s['reserved'] as List?) ?? []).cast<dynamic>().map((e) => int.tryParse('$e') ?? 0).toList();
          return Padding(
            padding: const EdgeInsets.all(16),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Seat Map (total: $total)', style: const TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Text('Reserved: ${reserved.join(', ')}'),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _seatsCtrl, decoration: const InputDecoration(labelText: 'Seats count (1-6)'))),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: _seatNumsCtrl, decoration: const InputDecoration(labelText: 'Seat numbers (comma separated)'))),
              ]),
              const SizedBox(height: 8),
              TextField(controller: _promoCtrl, decoration: const InputDecoration(labelText: 'Promo code (optional)')),
              const SizedBox(height: 8),
              Row(children: [
                FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
              ])
            ]),
          );
        },
      );
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }
}

class _BookingResultSheet extends StatelessWidget {
  final String? paymentId;
  const _BookingResultSheet({required this.paymentId});
  @override
  Widget build(BuildContext context) {
    final hasPayment = paymentId != null && paymentId!.isNotEmpty;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Booking created', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Text(hasPayment ? 'A payment request was created.' : 'No payment required.'),
        const SizedBox(height: 8),
        Row(children: [
          if (hasPayment)
            FilledButton.icon(
              onPressed: () async {
                final uri = Uri.parse('payments://request/$paymentId');
                final ok = await canLaunchUrl(uri);
                if (ok) {
                  await launchUrl(uri, mode: LaunchMode.externalApplication);
                } else {
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed / cannot open link.')));
                }
              },
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open in Payments'),
            ),
          const SizedBox(width: 8),
          OutlinedButton.icon(onPressed: () async {
            await Clipboard.setData(ClipboardData(text: paymentId ?? ''));
            if (!context.mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied Payment Request ID')));
          }, icon: const Icon(Icons.copy), label: const Text('Copy ID')),
        ])
      ]),
    );
  }
}

