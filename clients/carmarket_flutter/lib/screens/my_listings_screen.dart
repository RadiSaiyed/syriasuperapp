import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';
import '../ui/glass.dart';

class MyListingsScreen extends StatefulWidget {
  final ApiClient api;
  const MyListingsScreen({super.key, required this.api});
  @override
  State<MyListingsScreen> createState() => _MyListingsScreenState();
}

class _MyListingsScreenState extends State<MyListingsScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];
  String? _selectedListingId;
  List<Map<String, dynamic>> _offers = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.myListings();
      setState(() { _items = rows; if (_items.isNotEmpty) _selectedListingId ??= _items.first['id'] as String?; });
      await _loadOffers();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _loadOffers() async {
    final id = _selectedListingId; if (id == null) { setState(() => _offers = []); return; }
    try { final rows = await widget.api.offersForListing(id); setState(() => _offers = rows); } catch (_) {}
  }

  Future<void> _accept(String offerId) async {
    setState(() => _loading = true);
    try {
      final res = await widget.api.acceptOffer(offerId);
      final req = res['payment_request_id'] as String?;
      await _loadOffers();
      if (req != null) await _showPaymentCta(req);
    } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }

  Future<void> _reject(String offerId) async { setState(() => _loading = true); try { await widget.api.rejectOffer(offerId); await _loadOffers(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      await Clipboard.setData(ClipboardData(text: requestId));
      if (mounted) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed. Copied request ID.'))); }
    }
  }

  Future<void> _showPaymentCta(String requestId) async {
    await showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(16),
        child: Material(
          color: Colors.transparent,
          child: Glass(
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: const [Icon(Icons.directions_car_outlined, size: 28), SizedBox(width: 8), Text('Offer accepted', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))]),
              const SizedBox(height: 8),
              const Text('Open the Payments app to request payment from the buyer.'),
              const SizedBox(height: 16),
              Row(children: [Expanded(child: FilledButton.icon(onPressed: () { Navigator.pop(ctx); _openPayment(requestId); }, icon: Icon(Icons.open_in_new), label: Text('Open in Payments')))]),
              const SizedBox(height: 8),
              TextButton.icon(onPressed: () async { await Clipboard.setData(ClipboardData(text: requestId)); if (!mounted) return; ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied payment request ID'))); }, icon: const Icon(Icons.copy_outlined), label: const Text('Copy request ID')),
            ]),
          ),
        ),
      ),
    );
  }

  @override
  void initState() { super.initState(); _load(); }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Padding(
        padding: const EdgeInsets.all(8),
        child: Glass(
          child: Row(children: [
            const Text('Listing:'), const SizedBox(width: 8),
            DropdownButton<String>(
              value: _selectedListingId,
              hint: const Text('Select'),
              items: _items.map((l) => DropdownMenuItem<String>(value: l['id'] as String?, child: Text(l['title'] as String? ?? ''))).toList(),
              onChanged: (v) async { setState(() => _selectedListingId = v); await _loadOffers(); },
            ),
            const Spacer(),
            IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          ]),
        ),
      ),
      Expanded(
        child: ListView.builder(
          itemCount: _offers.length,
          itemBuilder: (context, i) {
            final o = _offers[i];
            final status = o['status'] as String? ?? 'pending';
            final req = o['payment_request_id'] as String?;
            return GlassCard(
              child: ListTile(
                title: Text('Offer ${o['amount_cents']} SYP'),
                subtitle: Text('Status: $status'),
                trailing: status == 'pending'
                    ? Wrap(spacing: 8, children: [
                        FilledButton(onPressed: _loading ? null : () => _accept(o['id'] as String), child: const Text('Accept')),
                        OutlinedButton(onPressed: _loading ? null : () => _reject(o['id'] as String), child: const Text('Reject')),
                      ])
                    : (req != null ? FilledButton.icon(onPressed: _loading ? null : () => _openPayment(req), icon: const Icon(Icons.open_in_new), label: const Text('Open Payment')) : null),
              ),
            );
          },
        ),
      ),
    ]);
  }
}
