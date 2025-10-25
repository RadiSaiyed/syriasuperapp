import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../api.dart';
import 'chat_screen.dart';

class ContactsScreen extends StatefulWidget {
  final ApiClient api;
  const ContactsScreen({super.key, required this.api});

  @override
  State<ContactsScreen> createState() => _ContactsScreenState();
}

class _ContactsScreenState extends State<ContactsScreen> {
  late Future<List<Map<String, dynamic>>> _future = widget.api.listContacts();
  final _phoneCtrl = TextEditingController(text: '+963');
  WebSocketChannel? _ws;
  StreamSubscription? _wsSub;
  final List<Map<String, dynamic>> _incoming = [];

  @override
  void initState() {
    super.initState();
    _connectWs();
  }

  Future<void> _connectWs() async {
    try {
      _ws = await widget.api.connectWs();
      _wsSub = _ws!.stream.listen((evt) {
        try {
          final data = jsonDecode(evt as String) as Map<String, dynamic>;
          if (data['type'] == 'message') {
            setState(() { _incoming.add((data['message'] as Map).cast<String, dynamic>()); });
          }
        } catch (_) {}
      }, onError: (_) {}, onDone: () {});
    } catch (_) {}
  }

  @override
  void dispose() {
    _wsSub?.cancel();
    _ws?.sink.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(8),
        child: Row(children: [
          Expanded(child: TextField(controller: _phoneCtrl, decoration: const InputDecoration(labelText: 'Add contact by phone'))),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: () async {
              try { await widget.api.addContactByPhone(_phoneCtrl.text.trim()); if (mounted) setState(() { _future = widget.api.listContacts(); }); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()))); }
            },
            child: const Text('Add'),
          )
        ]),
      ),
      const Divider(height: 1),
      Expanded(
        child: FutureBuilder<List<Map<String, dynamic>>>(
          future: _future,
          builder: (context, snap) {
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final cs = snap.data!;
            return ListView.separated(
              itemCount: cs.length + (_incoming.isEmpty ? 0 : 1),
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                if (i == 0 && _incoming.isNotEmpty) {
                  final m = _incoming.last;
                  return ListTile(
                    tileColor: Colors.yellow.withOpacity(0.2),
                    title: const Text('New message'),
                    subtitle: Text(m['ciphertext'] ?? ''),
                  );
                }
                final idx = _incoming.isEmpty ? i : i - 1;
                final c = cs[idx];
                return ListTile(
                  title: Text(c['name'] ?? c['phone'] ?? ''),
                  subtitle: Text(c['phone'] ?? ''),
                  trailing: PopupMenuButton<String>(
                    onSelected: (v) async {
                      if (v == 'block') {
                        try { await widget.api.blockUser(c['user_id'] as String); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Blocked'))); } catch (e) {}
                      } else if (v == 'unblock') {
                        try { await widget.api.unblockUser(c['user_id'] as String); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Unblocked'))); } catch (e) {}
                      }
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'block', child: Text('Block')),
                      PopupMenuItem(value: 'unblock', child: Text('Unblock')),
                    ],
                  ),
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api, contact: c))),
                );
              },
            );
          },
        ),
      ),
    ]);
  }
}
