import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';
import '../ui/glass.dart';

class MyOffersScreen extends StatefulWidget {
  final ApiClient api;
  const MyOffersScreen({super.key, required this.api});
  @override
  State<MyOffersScreen> createState() => _MyOffersScreenState();
}

class _MyOffersScreenState extends State<MyOffersScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];
  final _rateCtrl = TextEditingController(text: '5');
  final _commentCtrl = TextEditingController();

  Future<void> _load() async {
    setState(() => _loading = true);
    try { final rows = await widget.api.myOffers(); setState(() => _items = rows); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      await Clipboard.setData(ClipboardData(text: requestId));
      if (mounted) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed. Copied request ID.'))); }
    }
  }

  @override
  void initState() { super.initState(); _load(); }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.builder(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: _items.length,
            itemBuilder: (context, i) {
              final o = _items[i];
              final req = o['payment_request_id'] as String?;
              return GlassCard(
                child: ListTile(
                  title: Text('Offer ${o['amount_cents']} SYP'),
                  subtitle: Text('Status: ${o['status']}'),
                  trailing: Wrap(spacing: 8, children: [
                    if (req != null) FilledButton.icon(onPressed: _loading ? null : () => _openPayment(req), icon: const Icon(Icons.open_in_new), label: const Text('Payment')),
                    if (o['status'] == 'pending') OutlinedButton(onPressed: _loading ? null : () async { setState(()=>_loading=true); try { await widget.api.cancelOffer(o['id'] as String); await _load(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(()=>_loading=false);} }, child: const Text('Cancel')),
                    if (o['status'] == 'accepted') OutlinedButton(onPressed: _loading ? null : () async { final ok = await showDialog<bool>(context: context, builder: (_) => AlertDialog(backgroundColor: Colors.white.withOpacity(0.14), surfaceTintColor: Colors.transparent, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)), title: const Text('Rate seller'), content: Column(mainAxisSize: MainAxisSize.min, children: [TextField(controller: _rateCtrl, decoration: const InputDecoration(labelText: 'Rating 1..5'), keyboardType: TextInputType.number), TextField(controller: _commentCtrl, decoration: const InputDecoration(labelText: 'Comment'))]), actions: [TextButton(onPressed: ()=>Navigator.pop(context,false), child: const Text('Cancel')), FilledButton(onPressed: ()=>Navigator.pop(context,true), child: const Text('Send'))],)); if (ok==true) { try { final r = int.tryParse(_rateCtrl.text.trim()) ?? 5; await widget.api.rateOffer(o['id'] as String, rating: r, comment: _commentCtrl.text.trim()); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Review submitted')));} catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} } }, child: const Text('Rate')),
                  ]),
                ),
              );
            },
          ),
        ),
      ),
    ]);
  }
}
