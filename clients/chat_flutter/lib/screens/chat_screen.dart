import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:file_selector/file_selector.dart';
import '../crypto.dart';

import '../api.dart';

class ChatScreen extends StatefulWidget {
  final ApiClient api;
  final Map<String, dynamic> contact;
  const ChatScreen({super.key, required this.api, required this.contact});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _msgCtrl = TextEditingController();
  final List<Map<String, dynamic>> _messages = [];
  bool _sending = false;
  WebSocketChannel? _ws;
  StreamSubscription? _wsSub;
  String? _conversationId;
  String? _beforeIso;
  final _attCtrl = TextEditingController();
  final ScrollController _scroll = ScrollController();
  bool _peerTyping = false;
  String _presenceLabel = '';
  Timer? _presenceTimer;
  Timer? _typingDebounce;
  final Map<String, List<Map<String, dynamic>>> _reactions = {};
  bool _attaching = false;

  Future<void> _send() async {
    final txt = _msgCtrl.text.trim();
    if (txt.isEmpty) return;
    setState(() { _sending = true; });
    try {
      // Encrypt plaintext for recipient using first device key
      final keys = await widget.api.userKeys(widget.contact['user_id'] as String);
      if (keys.isEmpty) { throw Exception('No recipient keys'); }
      final pub = keys.first['public_key'] as String;
      final box = CryptoBox();
      final payload = await box.encryptFor(recipientPubB64: pub, plaintext: txt);
      final sent = await widget.api.sendMessage(recipientUserId: widget.contact['user_id'] as String, ciphertext: payload);
      setState(() { _messages.add(sent); _msgCtrl.clear(); });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() { _sending = false; });
    }
  }

  Future<void> _loadHistory() async {
    if (_conversationId == null) return;
    try {
      final list = await widget.api.history(conversationId: _conversationId!, beforeIso: _beforeIso, limit: 20);
      if (list.isNotEmpty) {
        setState(() {
          _messages.insertAll(0, list);
          _beforeIso = list.first['sent_at']?.toString();
        });
      }
    } catch (_) {}
  }

  Future<void> _loadInitial() async {
    // If conversation id known, load latest page; otherwise, try infer from inbox
    if (_conversationId != null) {
      _beforeIso = null;
      await _loadHistory();
      return;
    }
    try {
      final inbox = await widget.api.inbox();
      final uid = widget.contact['user_id']?.toString();
      final withContact = inbox.where((m) =>
          m['recipient_user_id']?.toString() == uid || m['sender_user_id']?.toString() == uid).toList();
      withContact.sort((a, b) => (a['sent_at'] ?? '').toString().compareTo((b['sent_at'] ?? '').toString()));
      if (withContact.isNotEmpty) {
        setState(() {
          _messages.clear();
          _messages.addAll(withContact);
          _conversationId = withContact.last['conversation_id']?.toString();
          _beforeIso = withContact.first['sent_at']?.toString();
        });
      }
    } catch (_) {}
  }

  Future<void> _connectWs() async {
    try {
      _ws = await widget.api.connectWs();
      _wsSub = _ws!.stream.listen((evt) async {
        try {
          final data = jsonDecode(evt as String) as Map<String, dynamic>;
          if (data['type'] == 'message') {
            final msg = (data['message'] as Map).cast<String, dynamic>();
            // Always decrypt and show if message belongs to this conversation
            final uid = widget.contact['user_id']?.toString();
            final isOutbound = msg['recipient_user_id']?.toString() == uid;
            if (!isOutbound && msg['sender_user_id']?.toString() != uid) {
              return; // not this chat
            }
            final pt = await CryptoBox().decryptIncoming(ciphertextJson: msg['ciphertext'] as String);
            final dec = Map<String, dynamic>.from(msg);
            dec['ciphertext'] = pt;
            setState(() { _messages.add(dec); });
            // ACK only for inbound (delivered to us)
            if (!isOutbound) {
              await widget.api.ackDelivered(msg['id'] as String);
            }
          } else if (data['type'] == 'delivered' || data['type'] == 'read') {
            final id = (data['message_id'] ?? '').toString();
            final isRead = data['type'] == 'read';
            setState(() {
              for (final m in _messages) {
                if ((m['id'] ?? '') == id) {
                  if (isRead) {
                    m['read'] = true;
                    m['delivered'] = true;
                  } else {
                    m['delivered'] = true;
                  }
                }
              }
            });
          } else if (data['type'] == 'typing') {
            final from = (data['from'] ?? '').toString();
            final uid = widget.contact['user_id']?.toString();
            if (uid == from) {
              setState(() => _peerTyping = (data['is_typing'] == true));
              if (_peerTyping) {
                // auto clear after a few seconds
                Future.delayed(const Duration(seconds: 4), () {
                  if (mounted) setState(() => _peerTyping = false);
                });
              }
            }
          } else if (data['type'] == 'reaction' || data['type'] == 'reaction_removed') {
            final id = (data['message_id'] ?? '').toString();
            final emoji = (data['emoji'] ?? '').toString();
            setState(() {
              final list = _reactions[id] ?? <Map<String, dynamic>>[];
              if (data['type'] == 'reaction') {
                list.add({'emoji': emoji, 'user_id': data['user_id']});
              } else {
                list.removeWhere((e) => e['emoji'] == emoji && e['user_id'] == data['user_id']);
              }
              _reactions[id] = list;
            });
          }
        } catch (_) {}
      });
    } catch (_) {}
  }

  @override
  void initState() {
    super.initState();
    _conversationId = widget.contact['conversation_id']?.toString();
    _connectWs();
    _loadInitial();
    _startPresenceTimer();
    _scroll.addListener(() {
      if (_scroll.position.pixels <= 120) {
        _loadHistory();
      }
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 48) {
        _markLatestInboundRead();
      }
    });
  }

  @override
  void dispose() {
    _wsSub?.cancel();
    _ws?.sink.close();
    _presenceTimer?.cancel();
    _typingDebounce?.cancel();
    super.dispose();
  }

  void _startPresenceTimer() {
    _presenceTimer?.cancel();
    _presenceTimer = Timer.periodic(const Duration(seconds: 20), (_) async {
      try {
        await widget.api.pingPresence();
      } catch (_) {}
      final uid = widget.contact['user_id']?.toString();
      if (uid != null) {
        try {
          final p = await widget.api.presence(uid);
          final online = p['online'] == true;
          final last = (p['last_seen'] ?? '').toString();
          setState(() => _presenceLabel = online ? 'Online' : (last.isNotEmpty ? 'Last seen: $last' : 'Offline'));
        } catch (_) {}
      }
    });
  }

  void _markLatestInboundRead() {
    final uid = widget.contact['user_id']?.toString();
    if (uid == null) return;
    String? lastInboundId;
    for (final m in _messages.reversed) {
      final inbound = (m['sender_user_id']?.toString() == uid);
      if (inbound) { lastInboundId = (m['id'] ?? '').toString(); break; }
    }
    if (lastInboundId != null && lastInboundId.isNotEmpty) {
      widget.api.ackRead(lastInboundId).catchError((_){});
    }
  }

  @override
  Widget build(BuildContext context) {
    final name = widget.contact['name'] ?? widget.contact['phone'] ?? 'Chat';
    return Scaffold(
      appBar: AppBar(title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(name.toString()),
        if (_peerTyping) const Text('typing…', style: TextStyle(fontSize: 12)),
        if (!_peerTyping && _presenceLabel.isNotEmpty) Text(_presenceLabel, style: const TextStyle(fontSize: 12)),
      ])),
      body: Column(children: [
        Expanded(
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(8),
            itemCount: _messages.length,
            separatorBuilder: (_, __) => const SizedBox(height: 6),
            itemBuilder: (context, i) {
              final m = _messages[i];
              final uid = widget.contact['user_id']?.toString();
              final isOutbound = m['recipient_user_id']?.toString() == uid;
              final time = (m['sent_at'] ?? '')
                  .toString()
                  .replaceFirst('T', ' ')
                  .replaceFirst('Z', '');
              final bubbleColor = isOutbound
                  ? Colors.blue.shade400.withOpacity(0.25)
                  : Colors.grey.shade500.withOpacity(0.18);
              final align = isOutbound ? Alignment.centerRight : Alignment.centerLeft;
              final delivered = (m['delivered'] == true);
              final read = (m['read'] == true);
              final msgId = (m['id'] ?? '').toString();
              return Align(
                alignment: align,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: bubbleColor,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white.withOpacity(0.12)),
                  ),
                  child: Column(
                    crossAxisAlignment: isOutbound ? CrossAxisAlignment.end : CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(m['ciphertext'] ?? ''),
                      if ((_reactions[msgId] ?? const []).isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2, bottom: 2),
                          child: Wrap(spacing: 4, children: (_reactions[msgId] ?? const []).map((r) => Text(r['emoji'] ?? '👍')).toList()),
                        ),
                      const SizedBox(height: 4),
                      Row(mainAxisSize: MainAxisSize.min, children: [
                        Text(time, style: Theme.of(context).textTheme.bodySmall),
                        if (isOutbound) ...[
                          const SizedBox(width: 6),
                          Icon(read ? Icons.done_all : (delivered ? Icons.done_all : Icons.check), size: 16, color: read ? Colors.lightBlueAccent : Colors.white70),
                        ]
                      ]),
                    ],
                  ),
                ),
              )._withMessageGestures(onReact: () => _pickReaction(msgId));
            },
          ),
        ),
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Row(children: [
            Expanded(child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextField(controller: _msgCtrl, decoration: const InputDecoration(hintText: 'Type encrypted text...'), onChanged: (_) {
                _typingDebounce?.cancel();
                _typingDebounce = Timer(const Duration(milliseconds: 400), () {
                  widget.api.typing(peerUserId: widget.contact['user_id']?.toString(), isTyping: true).catchError((_){});
                });
              }),
              TextField(controller: _attCtrl, decoration: const InputDecoration(hintText: 'Attachment (ciphertext base64, optional)')),
            ])),
            const SizedBox(width: 8),
            IconButton(
              tooltip: 'React',
              onPressed: _messages.isEmpty ? null : () => _pickReaction((_messages.last['id'] ?? '').toString()),
              icon: const Icon(Icons.emoji_emotions_outlined),
            ),
            IconButton(
              tooltip: 'Attach file',
              onPressed: _attaching ? null : _attachFile,
              icon: _attaching ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.attach_file),
            ),
            FilledButton(onPressed: _sending ? null : () async {
              await _send();
              final last = _messages.isNotEmpty ? _messages.last : null;
              final att = _attCtrl.text.trim();
              if (last != null && att.isNotEmpty) {
                try { await widget.api.addAttachment(messageId: last['id'] as String, contentType: 'text/plain', ciphertextB64: att); _attCtrl.clear(); } catch (_) {}
              }
            }, child: const Text('Send')),
          ]),
        )
      ]),
    );
  }

  Future<void> _pickReaction(String messageId) async {
    final emoji = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (_) => Padding(
        padding: const EdgeInsets.all(12),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          for (final e in ['👍','❤️','😂','🎉','😮','😢'])
            IconButton(onPressed: () => Navigator.pop(context, e), icon: Text(e, style: const TextStyle(fontSize: 22)))
        ]),
      ),
    );
    if (emoji == null || emoji.isEmpty) return;
    try {
      await widget.api.addReaction(messageId: messageId, emoji: emoji);
      setState(() {
        final list = _reactions[messageId] ?? <Map<String, dynamic>>[];
        list.add({'emoji': emoji, 'user_id': 'me'});
        _reactions[messageId] = list;
      });
    } catch (_) {}
  }

  Future<void> _attachFile() async {
    try {
      setState(() => _attaching = true);
      // Lazy import to avoid platform issues
      // ignore: avoid_dynamic_calls
      final picker = await _selectFile();
      if (picker == null) { setState(() => _attaching = false); return; }
      final bytes = picker.bytes as List<int>;
      final name = (picker.name as String?) ?? 'file.bin';
      // Encrypt bytes by wrapping as base64 string and using CryptoBox
      final base64Content = base64Encode(bytes);
      final keys = await widget.api.userKeys(widget.contact['user_id'] as String);
      if (keys.isEmpty) throw Exception('No recipient keys');
      final pub = keys.first['public_key'] as String;
      final payload = await CryptoBox().encryptFor(recipientPubB64: pub, plaintext: base64Content);
      if (_messages.isEmpty) {
        // ensure a message exists (send empty text)
        _msgCtrl.text = '[attachment]';
        await _send();
      }
      final last = _messages.isNotEmpty ? _messages.last : null;
      if (last != null) {
        final b64Cipher = base64Encode(utf8.encode(payload));
        await widget.api.addAttachment(messageId: last['id'] as String, contentType: 'application/octet-stream', ciphertextB64: b64Cipher);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Attached $name')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Attach failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _attaching = false);
    }
  }

  Future<dynamic> _selectFile() async {
    final type = const XTypeGroup(label: 'Any', extensions: <String>['png','jpg','jpeg','pdf','txt','bin']);
    final XFile? file = await openFile(acceptedTypeGroups: [type]);
    if (file == null) return null;
    final bytes = await file.readAsBytes();
    return {'bytes': bytes, 'name': file.name};
  }
}

extension _MsgGesture on Widget {
  Widget _withMessageGestures({required VoidCallback onReact}) {
    return GestureDetector(onLongPress: onReact, child: this);
  }
}
