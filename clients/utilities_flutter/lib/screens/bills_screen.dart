import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';

class BillsScreen extends StatefulWidget {
  final ApiClient api;
  const BillsScreen({super.key, required this.api});
  @override
  State<BillsScreen> createState() => _BillsScreenState();
}

class _BillsScreenState extends State<BillsScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _accounts = [];
  String? _selectedAccountId;
  List<Map<String, dynamic>> _bills = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final accs = await widget.api.listAccounts();
      String? sel = _selectedAccountId;
      if (sel == null && accs.isNotEmpty) sel = accs.first['id'] as String?;
      List<Map<String, dynamic>> bills = [];
      if (sel != null) {
        bills = await widget.api.refreshBills(sel);
      }
      setState(() { _accounts = accs; _selectedAccountId = sel; _bills = bills; });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pay(String billId) async {
    setState(() => _loading = true);
    try {
      final res = await widget.api.payBill(billId);
      if (!mounted) return;
      final req = res['payment_request_id'] as String?;
      if (req != null) await _showPaymentCta(req);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
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
          Row(children: const [Icon(Icons.receipt_long, size: 28), SizedBox(width: 8), Text('Bill payment', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))]),
          const SizedBox(height: 8),
          const Text('Open the Payments app to approve this payment.'),
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
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Padding(
        padding: const EdgeInsets.all(8),
        child: Row(children: [
          const Text('Account:'), const SizedBox(width: 8),
          DropdownButton<String>(
            value: _selectedAccountId,
            hint: const Text('Select'),
            items: _accounts.map((a) => DropdownMenuItem<String>(value: a['id'] as String?, child: Text(a['alias'] as String? ?? a['account_ref'] as String? ?? ''))).toList(),
            onChanged: (v) async { setState(() => _selectedAccountId = v); if (v != null) { setState(() => _loading = true); try { final b = await widget.api.refreshBills(v); setState(() => _bills = b); } catch (_) {} finally { if (mounted) setState(() => _loading = false); } } },
          ),
          const Spacer(),
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ]),
      ),
      Expanded(
        child: ListView.separated(
          itemCount: _bills.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final b = _bills[i];
            return ListTile(
              title: Text('Bill ${b['id']}'),
              subtitle: Text('Amount: ${b['amount_cents']} SYP  •  Status: ${b['status']}'),
              trailing: FilledButton(onPressed: _loading ? null : () => _pay(b['id'] as String), child: const Text('Pay')),
            );
          },
        ),
      ),
    ]);
  }
}

