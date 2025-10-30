import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import '../push_history.dart';
import '../deeplinks.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _loading = true;
  List<PushHistoryEntry> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final list = await PushHistoryStore.load();
    if (!mounted) return;
    setState(() { _items = list; _loading = false; });
    await PushHistoryStore.setSeenNow();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero), actions: [
        IconButton(onPressed: _loading ? null : () async { await PushHistoryStore.clear(); await _load(); }, icon: const Icon(Icons.clear_all))
      ]),
      body: _loading ? const Center(child: CircularProgressIndicator()) : ListView.builder(
        itemCount: _items.length,
        itemBuilder: (_, i) {
          final it = _items[i];
          return GlassCard(child: ListTile(
            title: Text(it.title.isEmpty ? 'Notification' : it.title),
            subtitle: Text(it.body),
            trailing: it.deeplink != null && it.deeplink!.isNotEmpty ? TextButton(onPressed: () {
              try { DeepLinks.handleUri(context, Uri.parse(it.deeplink!)); } catch (_) {}
            }, child: const Text('Open')) : null,
          ));
        },
      ),
    );
  }
}
