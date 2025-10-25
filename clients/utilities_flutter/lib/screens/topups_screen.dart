import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';

class TopupsScreen extends StatefulWidget {
  final ApiClient api;
  const TopupsScreen({super.key, required this.api});
  @override
  State<TopupsScreen> createState() => _TopupsScreenState();
}

class _TopupsScreenState extends State<TopupsScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.listTopups();
      setState(() => _items = rows);
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
              final t = _items[i];
              final req = t['payment_request_id'] as String?;
              return ListTile(
                title: Text('Top-up ${t['target_phone']}'),
                subtitle: Text('Amount: ${t['amount_cents']} SYP  •  Status: ${t['status']}'),
                trailing: req != null
                    ? FilledButton.icon(onPressed: _loading ? null : () => _openPayment(req), icon: const Icon(Icons.open_in_new), label: const Text('Open Payment'))
                    : const SizedBox.shrink(),
              );
            },
          ),
        ),
      ),
    ]);
  }
}

