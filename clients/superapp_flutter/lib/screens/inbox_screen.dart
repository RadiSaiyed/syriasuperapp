import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../services.dart';
import 'package:http/http.dart' as http;
import '../push_history.dart';

class InboxScreen extends StatefulWidget {
  const InboxScreen({super.key});
  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  final _store = MultiTokenStore();
  WebSocketChannel? _ws;
  final List<Map<String, dynamic>> _events = [];
  bool _connecting = false;
  List<PushHistoryEntry> _pushes = const [];
  String _userId = '';

  Uri _chatUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('chat', path, query: query);

  Future<Map<String, String>> _chatHeaders() =>
      authHeaders('chat', store: _store);

  String _chatBase() => ServiceConfig.baseUrl('chat');

  @override
  void initState() {
    super.initState();
    _connectWs();
    _loadPush();
  }

  @override
  void dispose() {
    _ws?.sink.close();
    super.dispose();
  }

  Future<void> _connectWs() async {
    if (_connecting) return;
    setState(() => _connecting = true);
    try {
      final base = _chatBase();
      final t = await getTokenFor('chat', store: _store);
      if (t == null) {
        _append({'kind': 'text', 'text': 'Not logged in — please log in via Profile.'});
        return;
      }
      String wsBase = base
          .replaceFirst('https://', 'wss://')
          .replaceFirst('http://', 'ws://');
      final uri = Uri.parse('$wsBase/ws?token=$t');
      // Decode user id from token for filtering
      try {
        final parts = t.split('.');
        final map = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1])))) as Map<String, dynamic>;
        _userId = (map['sub'] ?? '').toString();
      } catch (_) {
        _userId = '';
      }
      final ch = WebSocketChannel.connect(uri);
      _ws = ch;
      _append({'kind': 'text', 'text': 'Verbunden mit Inbox'});
      ch.stream.listen((event) {
        try {
          if (event is String) {
            _handleIncoming(event);
          } else {
            _handleIncoming(event.toString());
          }
        } catch (_) {}
      }, onDone: () {
        _append({'kind': 'text', 'text': 'Verbindung geschlossen'});
      }, onError: (_) {
        _append({'kind': 'text', 'text': 'Verbindungsfehler'});
      });
    } catch (_) {
      _append({'kind': 'text', 'text': 'WS Connect fehlgeschlagen'});
    } finally {
      setState(() => _connecting = false);
    }
  }

  void _append(Map<String, dynamic> e) {
    setState(() => _events.insert(0, e));
  }

  Future<void> _loadPush() async {
    final items = await PushHistoryStore.load();
    if (!mounted) return;
    setState(() => _pushes = items);
  }

  Future<void> _fetchInbox() async {
    try {
      final headers = await _chatHeaders();
      if (!headers.containsKey('Authorization')) {
        _append({'kind': 'text', 'text': 'Not logged in'});
        return;
      }
      final res =
          await http.get(_chatUri('/messages/inbox'), headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final items = (js['messages'] as List?) ?? [];
      _append({'kind': 'text', 'text': items.isEmpty ? 'Inbox leer' : 'Inbox: ${items.length} Nachricht(en)'});
    } catch (e) {
      _append({'kind': 'text', 'text': 'Inbox fehlgeschlagen: $e'});
    }
  }

  void _handleIncoming(String raw) {
    try {
      final obj = jsonDecode(raw);
      if (obj is Map && obj['type'] == 'message') {
        final msg = obj['message'] as Map? ?? {};
        final text = msg['ciphertext']?.toString() ?? '';
        if (text.startsWith('[ACTION]')) {
          final p = text.indexOf('{');
          if (p > 0) {
            final j = jsonDecode(text.substring(p)) as Map<String, dynamic>;
            _append({'kind': 'action', 'title': (j['title'] ?? 'Aktion').toString(), 'action': (j['action'] ?? '').toString(), 'data': (j['data'] as Map?)?.cast<String, dynamic>() ?? {}});
            return;
          }
        }
        _append({'kind': 'text', 'text': text});
        try {
          // Increase unread only for messages addressed to me
          final rcpt = (msg['recipient_user_id'] ?? '').toString();
          if (_userId.isNotEmpty && rcpt == _userId) {
            final cur = ChatUnreadStore.count.value;
            ChatUnreadStore.set(cur + 1);
          }
        } catch (_) {}
        return;
      }
    } catch (_) {}
    _append({'kind': 'text', 'text': raw});
  }

  Future<void> _confirmAction(Map<String, dynamic> a) async {
    try {
      final tool = a['action']?.toString() ?? '';
      final args = (a['data'] as Map<String, dynamic>? ?? {});
      String? svc;
      switch (tool) {
        case 'pay_bill':
          svc = 'utilities';
          break;
        case 'start_parking_session':
          svc = 'parking';
          break;
        case 'create_car_listing':
          svc = 'carmarket';
          break;
        default:
          svc = 'payments';
      }
      final token = await getTokenFor(svc, store: _store);
      if (token == null) {
        _append({'kind': 'text', 'text': 'Bitte zuerst einloggen.'});
        return;
      }
      // decode sub
      String userId = '';
      try {
        final parts = token.split('.');
        final map = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1])))) as Map<String, dynamic>;
        userId = (map['sub'] ?? '').toString();
      } catch (_) {}
      final base = const String.fromEnvironment('AI_GATEWAY_BASE_URL', defaultValue: '');
      final gw = base.isNotEmpty ? base : 'http://localhost:8099';
      final res = await http.post(Uri.parse('$gw/v1/tools/execute'),
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
          body: jsonEncode({'tool': tool, 'args': args, 'user_id': userId}));
      if (res.statusCode >= 400) {
        _append({'kind': 'text', 'text': 'Aktion fehlgeschlagen: ${res.body}'});
      } else {
        _append({'kind': 'text', 'text': 'Aktion ausgeführt.'});
      }
    } catch (e) {
      _append({'kind': 'text', 'text': 'Aktion fehlgeschlagen: $e'});
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(title: const Text('Inbox'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero), bottom: const TabBar(tabs: [Tab(text: 'Chat'), Tab(text: 'Notifications')])) ,
        body: TabBarView(children: [
          Column(children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: Glass(
                child: Row(children: [
                  FilledButton.icon(onPressed: _connecting ? null : _connectWs, icon: const Icon(Icons.wifi), label: const Text('Verbinden')),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(onPressed: _fetchInbox, icon: const Icon(Icons.download), label: const Text('Fetch Inbox')),
                ]),
              ),
            ),
            Expanded(
              child: ListView.builder(
                reverse: true,
                itemCount: _events.length,
                itemBuilder: (_, i) {
                  final e = _events[i];
                  if (e['kind'] == 'action') {
                    return GlassCard(
                        child: ListTile(
                      title: Text(e['title']?.toString() ?? 'Aktion'),
                      subtitle: Text(const JsonEncoder.withIndent('  ').convert(e['data'] ?? {})),
                      trailing: FilledButton(onPressed: () => _confirmAction(e), child: const Text('Bestätigen')),
                    ));
                  }
                  return GlassCard(child: ListTile(title: Text(e['text']?.toString() ?? '')));
                },
              ),
            ),
          ]),
          RefreshIndicator(
            onRefresh: () async { await _loadPush(); await PushHistoryStore.setSeenNow(); },
            child: ListView.builder(
              itemCount: _pushes.length,
              itemBuilder: (_, i) {
                final it = _pushes[i];
                return GlassCard(child: ListTile(
                  title: Text(it.title.isEmpty ? 'Notification' : it.title),
                  subtitle: Text(it.body),
                  trailing: it.deeplink != null && it.deeplink!.isNotEmpty ? TextButton(onPressed: () {
                    try { DeepLinks.handleUri(context, Uri.parse(it.deeplink!)); } catch (_) {}
                  }, child: const Text('Open')) : null,
                ));
              },
            ),
          ),
        ]),
      ),
    );
  }
}
