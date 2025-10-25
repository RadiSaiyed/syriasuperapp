import 'package:flutter/material.dart';
import '../api.dart';
import '../utils/currency.dart';
import 'ride_detail_screen.dart';

class HistoryScreen extends StatefulWidget {
  final ApiClient api;
  const HistoryScreen({super.key, required this.api});
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      _items = await widget.api.listRides(limit: 100);
    } catch (_) {
      _items = [];
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _rate(String id) async {
    int rating = 5;
    final ctrl = TextEditingController();
    bool saving = false;
    final res = await showDialog<bool>(
      context: context,
      barrierDismissible: !saving,
      builder: (_) => StatefulBuilder(builder: (ctx, setDlg) {
        return AlertDialog(
          title: const Text('Rate ride'),
          content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: List.generate(5, (i) {
              final idx = i + 1;
              final on = idx <= rating;
              return IconButton(onPressed: saving? null : () => setDlg(() => rating = idx), icon: Icon(on ? Icons.star : Icons.star_border));
            })),
            TextField(controller: ctrl, enabled: !saving, decoration: const InputDecoration(labelText: 'Comment (optional)')),
          ]),
          actions: [
            TextButton(onPressed: saving ? null : () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(
              onPressed: saving ? null : () async {
                setDlg(() => saving = true);
                try {
                  await widget.api.rateRide(id, rating: rating, comment: ctrl.text.trim().isEmpty ? null : ctrl.text.trim());
                  if (ctx.mounted) Navigator.pop(ctx, true);
                } catch (e) {
                  setDlg(() => saving = false);
                  if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('Rating failed: $e')));
                }
              },
              child: saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Save'),
            ),
          ],
        );
      }),
    );
    if (res == true) {
      await _load();
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ride history'), actions: [
        IconButton(onPressed: _loading ? null : _load, icon: _loading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.refresh))
      ]),
      body: _items.isEmpty && !_loading
          ? const Center(child: Text('No rides'))
          : ListView.builder(
              itemCount: _items.length,
              itemBuilder: (ctx, i) {
                final it = _items[i];
                final id = (it['id'] ?? '').toString();
                final status = (it['status'] ?? '').toString();
                final priceValue = it['final_fare_cents'] ?? it['quoted_fare_cents'];
                final price = formatSyp(priceValue);
                final created = (it['created_at'] ?? '').toString();
                return ListTile(
                  title: Text('Ride $id', maxLines: 1, overflow: TextOverflow.ellipsis),
                  subtitle: Text('Status: $status  •  Price: $price\n$created'),
                  isThreeLine: true,
                  trailing: status == 'completed'
                      ? TextButton(onPressed: () => _rate(id), child: const Text('Rate'))
                      : null,
                  onTap: () {
                    Navigator.of(context).push(MaterialPageRoute(builder: (_) => RideDetailScreen(api: widget.api, rideId: id)));
                  },
                );
              },
            ),
    );
  }
}
