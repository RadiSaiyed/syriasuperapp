import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api.dart';

class OrdersScreen extends StatefulWidget {
  final ApiClient api;
  const OrdersScreen({super.key, required this.api});
  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _orders = [];
  String? _cancelingId;

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.listOrders();
      setState(() => _orders = rows);
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed / cannot open link.')));
      }
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
            itemCount: _orders.length,
            itemBuilder: (context, i) {
              final o = _orders[i];
              final status = (o['status'] as String?) ?? 'created';
              final paymentId = o['payment_request_id'] as String?;
              return ListTile(
                title: Text('Order ${o['id']}'),
                subtitle: Text('Total: ${o['total_cents']} SYP\nStatus: $status'),
                trailing: Wrap(spacing: 8, children: [
                  if (paymentId != null)
                    FilledButton.icon(
                      onPressed: _loading ? null : () => _openPayment(paymentId),
                      icon: const Icon(Icons.open_in_new),
                      label: const Text('Payment'),
                    ),
                  if (status != 'canceled' && status != 'shipped')
                    OutlinedButton.icon(
                      onPressed: _loading ? null : () async { setState(()=>_cancelingId=o['id'] as String?); try { await widget.api.cancelOrder(o['id'] as String); await _load(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(()=>_cancelingId=null);} },
                      icon: const Icon(Icons.cancel),
                      label: const Text('Cancel'),
                    ),
                ]),
              );
            },
          ),
        ),
      ),
    ]);
  }
}
