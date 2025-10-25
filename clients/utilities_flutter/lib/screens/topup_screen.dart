import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';

class TopupScreen extends StatefulWidget {
  final ApiClient api;
  const TopupScreen({super.key, required this.api});
  @override
  State<TopupScreen> createState() => _TopupScreenState();
}

class _TopupScreenState extends State<TopupScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _operators = [];
  String? _opId;
  final _phoneCtrl = TextEditingController(text: '+963');
  final _amountCtrl = TextEditingController(text: '5000');
  final _promoCtrl = TextEditingController();

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final billers = await widget.api.listBillers(category: 'mobile');
      final ops = billers.where((b) => (b['category'] as String?) == 'mobile').toList();
      setState(() { _operators = ops; if (ops.isNotEmpty) _opId = ops.first['id'] as String?; });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _submit() async {
    final op = _opId; final phone = _phoneCtrl.text.trim(); final amount = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    if (op == null || phone.isEmpty || amount <= 0) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Select operator, enter phone and amount')));
      return;
    }
    setState(() => _loading = true);
    try {
      final promo = _promoCtrl.text.trim().isEmpty ? null : _promoCtrl.text.trim();
      final res = await widget.api.createTopup(operatorBillerId: op, targetPhone: phone, amountCents: amount, promoCode: promo);
      final req = res['payment_request_id'] as String?;
      if (req != null) await _showPaymentCta(req);
      if (mounted) {
        final fin = res['final_amount_cents'] ?? res['amount_cents'];
        final disc = res['discount_cents'];
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Top-up created • ${fin ?? '-'} SYP${disc!=null?' (discount $disc)':''}')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      await Clipboard.setData(ClipboardData(text: requestId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed. Copied request ID.')));
      }
    }
  }

  Future<void> _showPaymentCta(String requestId) async {
    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: const [Icon(Icons.phone_android_outlined, size: 28), SizedBox(width: 8), Text('Mobile top-up', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))]),
          const SizedBox(height: 8),
          const Text('Open the Payments app to approve this top-up.'),
          const SizedBox(height: 16),
          Row(children: [Expanded(child: FilledButton.icon(onPressed: () { Navigator.pop(ctx); _openPayment(requestId); }, icon: Icon(Icons.open_in_new), label: Text('Open in Payments')))]),
          const SizedBox(height: 8),
          TextButton.icon(onPressed: () async { await Clipboard.setData(ClipboardData(text: requestId)); if (!mounted) return; ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied payment request ID'))); }, icon: const Icon(Icons.copy_outlined), label: const Text('Copy request ID')),
        ]),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Text('Operator:'), const SizedBox(width: 8),
          DropdownButton<String>(
            value: _opId,
            items: _operators.map((o) => DropdownMenuItem<String>(value: o['id'] as String?, child: Text(o['name'] as String? ?? ''))).toList(),
            onChanged: (v) => setState(() => _opId = v),
          ),
        ]),
        const SizedBox(height: 8),
        TextField(controller: _phoneCtrl, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Target phone (+963...)')),
        const SizedBox(height: 8),
        TextField(controller: _amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (SYP cents)')),
        const SizedBox(height: 8),
        TextField(controller: _promoCtrl, decoration: const InputDecoration(labelText: 'Promo code (optional)')),
        const SizedBox(height: 12),
        FilledButton(onPressed: _loading ? null : _submit, child: const Text('Create Top-up')),
        if (_loading) const Padding(padding: EdgeInsets.only(top: 8), child: LinearProgressIndicator()),
      ]),
    );
  }
}
