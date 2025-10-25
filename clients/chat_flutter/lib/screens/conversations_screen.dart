import 'package:flutter/material.dart';

import '../api.dart';
import 'chat_screen.dart';

class ConversationsScreen extends StatefulWidget {
  final ApiClient api;
  const ConversationsScreen({super.key, required this.api});

  @override
  State<ConversationsScreen> createState() => _ConversationsScreenState();
}

class _ConversationsScreenState extends State<ConversationsScreen> {
  late Future<List<Map<String, dynamic>>> _future = widget.api.conversationsSummary();
  final TextEditingController _searchCtrl = TextEditingController();
  List<Map<String, dynamic>> _items = [];

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => setState(() => _future = widget.api.conversationsSummary()),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          _items = snap.data!;
          final q = _searchCtrl.text.trim().toLowerCase();
          final convos = q.isEmpty
              ? _items
              : _items.where((c) =>
                    (c['user_a'] ?? '').toString().toLowerCase().contains(q) ||
                    (c['user_b'] ?? '').toString().toLowerCase().contains(q)).toList();
          if (convos.isEmpty) {
            return Column(children: [
              _buildSearchBar(),
              const Expanded(child: Center(child: Text('No conversations'))),
            ]);
          }
          return ListView.separated(
            itemCount: convos.length + 1,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              if (i == 0) return _buildSearchBar();
              final c = convos[i - 1];
              final other = _otherUserId(c);
              final unread = (c['unread_count'] as int?) ?? 0;
              return ListTile(
                title: Text('Chat with ${other.substring(0, 8)}'),
                subtitle: Text('Last: ${c['last_message_at']}'),
                trailing: unread > 0
                    ? CircleAvatar(radius: 12, backgroundColor: Colors.redAccent, child: Text('$unread', style: const TextStyle(fontSize: 12)))
                    : null,
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => ChatScreen(
                      api: widget.api,
                      contact: {
                        'user_id': other,
                        if (c['id'] != null) 'conversation_id': c['id'].toString(),
                      },
                    ),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: TextField(
        controller: _searchCtrl,
        decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search by user id…'),
        onChanged: (_) => setState(() {}),
      ),
    );
  }

  String _otherUserId(Map<String, dynamic> convo) {
    final a = (convo['user_a'] ?? '').toString();
    final b = (convo['user_b'] ?? '').toString();
    // We don't know current user id here; fallback: pick the lexicographically larger as "other" for demo
    return a.compareTo(b) < 0 ? b : a;
  }
}
