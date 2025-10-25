import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';

class SearchScreen extends StatefulWidget {
  final ApiClient api;
  const SearchScreen({super.key, required this.api});
  @override
  State<SearchScreen> createState() => _SearchScreenState();
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
      final trips = await widget.api.searchTrips(origin: _origin.text.trim(), destination: _destination.text.trim(), date: _date);
      setState(() => _results = trips);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _book(String tripId) async {
    final seats = int.tryParse(_seatsCtrl.text.trim()) ?? 1;
    if (seats < 1 || seats > 6) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Seats must be between 1 and 6.')));
      }
      return;
    }
    setState(() => _loading = true);
    try {
      List<int>? seatNumbers;
      if (_seatNumsCtrl.text.trim().isNotEmpty) {
        seatNumbers = _seatNumsCtrl.text.split(',').map((e) => int.tryParse(e.trim())).whereType<int>().toList();
      }
      final promo = _promoCtrl.text.trim().isEmpty ? null : _promoCtrl.text.trim();
      final res = await widget.api.createBooking(tripId: tripId, seatsCount: seats, seatNumbers: seatNumbers, promoCode: promo);
      if (!mounted) return;
      _lastPaymentId = (res['payment_request_id'] as String?);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Booking ${res['id']} (${res['status']})')));
      if (_lastPaymentId != null) {
        await _showPaymentCta(_lastPaymentId!);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    final ok = await canLaunchUrl(uri);
    if (ok) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        await Clipboard.setData(ClipboardData(text: requestId));
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed. Copied request ID.')));
      }
    }
  }

  Future<void> _showPaymentCta(String requestId) async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: false,
      showDragHandle: true,
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: const [
                Icon(Icons.account_balance_wallet_outlined, size: 28),
                SizedBox(width: 8),
                Text('Complete your payment', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ]),
              const SizedBox(height: 8),
              const Text('Open the Payments app to review and authorize this booking.'),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () { Navigator.pop(ctx); _openPayment(requestId); },
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('Open in Payments'),
                  ),
                ),
              ]),
              const SizedBox(height: 8),
              TextButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: requestId));
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied payment request ID')));
                },
                icon: const Icon(Icons.copy_outlined),
                label: const Text('Copy request ID'),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final fmt = DateFormat('yyyy-MM-dd HH:mm');
    return Column(children: [
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
            Expanded(child: OutlinedButton.icon(onPressed: _pickDate, icon: const Icon(Icons.calendar_today), label: Text(DateFormat('yyyy-MM-dd').format(_date)))),
            const SizedBox(width: 8),
            SizedBox(width: 120, child: TextField(controller: _seatsCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Seats'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading ? null : _search, child: const Text('Search')),
          ]),
          if (_loading) const Padding(padding: EdgeInsets.only(top: 8), child: LinearProgressIndicator()),
          const SizedBox(height: 8),
          const Text('Seat numbers (optional, comma-separated) and Promo code'),
          Row(children: [
            Expanded(child: TextField(controller: _seatNumsCtrl, decoration: const InputDecoration(hintText: 'e.g. 5,6'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _promoCtrl, decoration: const InputDecoration(hintText: 'PROMO10'))),
          ]),
        ]),
      ),
      const Divider(height: 1),
      Expanded(
        child: _results.isEmpty
            ? const Center(child: Text('No results'))
            : ListView.separated(
                itemCount: _results.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, i) {
                  final t = _results[i];
                  return FutureBuilder<Map<String, dynamic>>(
                    future: widget.api.tripSeats(t['id'] as String),
                    builder: (context, snap) {
                      final reserved = (snap.data?['reserved'] as List?)?.length ?? 0;
                      final total = (snap.data?['seats_total'] as int?) ?? (t['seats_available'] as int? ?? 40);
                      return ListTile(
                        title: Text('${t['origin']} → ${t['destination']} • ${t['operator_name']}'),
                        subtitle: Text('${fmt.format(DateTime.parse(t['depart_at']))}${t['arrive_at'] != null ? ' → ${fmt.format(DateTime.parse(t['arrive_at']))}' : ''}\n$reserved/$total seats taken • ${t['price_cents']} SYP'),
                        trailing: FilledButton(onPressed: _loading ? null : () => _book(t['id'] as String), child: const Text('Book')),
                      );
                    },
                  );
                },
              ),
      )
    ]);
  }
}
