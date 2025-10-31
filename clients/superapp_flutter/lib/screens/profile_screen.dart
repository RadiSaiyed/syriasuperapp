import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import '../services.dart';
import '../main.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';
import '../push_register.dart';
import '../push_history.dart';
import 'package:shared_core/shared_core.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _tokens = MultiTokenStore();
  Map<String, dynamic>? _me;
  bool _loading = false;
  // Push topics
  List<String> _topics = const [];
  final TextEditingController _topicCtrl = TextEditingController(text: 'offers');
  // Dev push (optional)
  final TextEditingController _pushTitleCtrl = TextEditingController(text: 'Hello');
  final TextEditingController _pushBodyCtrl = TextEditingController(text: 'Tap to open');
  final TextEditingController _pushLinkCtrl = TextEditingController(text: 'superapp://payments');

  void _toast(String m) { showToast(context, m); }

  @override
  void dispose() {
    _topicCtrl.dispose();
    _pushTitleCtrl.dispose();
    _pushBodyCtrl.dispose();
    _pushLinkCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadMe() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson('superapp', '/v1/me', options: const RequestOptions(idempotent: true));
      if (!mounted) return;
      setState(() => _me = js);
      await _loadTopics();
    } catch (e) {
      MessageHost.showErrorBanner(context, '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadTopics() async {
    try {
      final js = await serviceGetJson('superapp', '/v1/push/topic/list', options: const RequestOptions(idempotent: true));
      final list = (js['topics'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
      if (!mounted) return;
      setState(() => _topics = list);
    } catch (_) {}
  }

  Future<void> _logoutAll() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Logout from all services?'),
        content: const Text('This clears tokens for Payments, Chat, Taxi, and all other services.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Logout All')),
        ],
      ),
    );
    if (ok == true) {
      await _tokens.clearAll();
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const HomeScreen()),
        (_) => false,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = _me?['user'] as Map<String, dynamic>?;
    final wallet = user?['wallet'] as Map<String, dynamic>?;
    final kyc = user?['kyc'] as Map<String, dynamic>?;
    final merch = user?['merchant'] as Map<String, dynamic>?;
    final services = _me?['services'] as Map<String, dynamic>?;
    int unread = 0;
    try {
      final chat = services?['chat'] as Map<String, dynamic>?;
      final convs = (chat?['conversations'] as List<dynamic>? ?? const []);
      for (final c in convs) { unread += int.tryParse((c['unread_count'] ?? '0').toString()) ?? 0; }
    } catch (_) {}
    return Scaffold(
      appBar: AppBar(title: const Text('Profile'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Glass(child: Wrap(spacing: 8, children: [
          FilledButton(onPressed: _loading ? null : _loadMe, child: const Text('Aktualisieren')),
          OutlinedButton(onPressed: () async { await PushHistoryStore.refreshUnread(); }, child: const Text('Refresh Badge')),
        ])),
        const SizedBox(height: 8),
        if (user != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
          const Icon(Icons.person, size: 18), const SizedBox(width: 8),
          Expanded(child: Text('User: ${user['wallet']?['user']?['phone'] ?? ''}')),
        ]))) else const SizedBox.shrink(),
        if (wallet != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
          const Icon(Icons.account_balance_wallet_outlined, size: 18), const SizedBox(width: 8),
          // Robust display: support both flattened and nested wallet without double-indexing
          Expanded(child: Builder(builder: (ctx) {
            dynamic nested = wallet['wallet'];
            final bal = (wallet['balance_cents'] ?? (nested is Map ? nested['balance_cents'] : null))?.toString() ?? '';
            final cur = (wallet['currency_code'] ?? (nested is Map ? nested['currency_code'] : null))?.toString() ?? '';
            return Text('Wallet: $bal $cur');
          })),
        ]))) else const SizedBox.shrink(),
        const SizedBox(height: 8),
        if (kyc != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
          const Icon(Icons.verified_user_outlined, size: 18), const SizedBox(width: 8),
          Expanded(child: Text('KYC: ${kyc['kyc_status']} (level ${kyc['kyc_level']})')),
        ]))) else const SizedBox.shrink(),
        if (merch != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
          const Icon(Icons.storefront_outlined, size: 18), const SizedBox(width: 8),
          Expanded(child: Text('Merchant: ${merch['merchant_status'] ?? (merch['is_merchant'] == true ? 'approved' : 'not set')}')),
        ]))) else const SizedBox.shrink(),
        if (unread > 0) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
          const Icon(Icons.mark_unread_chat_alt_outlined, size: 18), const SizedBox(width: 8),
          Expanded(child: Text('Chat: $unread ungelesen')),
        ]))) else const SizedBox.shrink(),
        const SizedBox(height: 12),
        Glass(child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Push Topics', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final t in _topics)
                InputChip(label: Text(t), onDeleted: _loading ? null : () async { await PushRegister.unsubscribeTopic(t); await _loadTopics(); }, deleteIcon: const Icon(Icons.close)),
              if (_topics.isEmpty) const Text('Keine Topics abonniert'),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(child: TextField(controller: _topicCtrl, decoration: const InputDecoration(labelText: 'Topic', hintText: 'offers'))),
              const SizedBox(width: 8),
              FilledButton.tonal(onPressed: _loading ? null : () async { final t=_topicCtrl.text.trim(); if (t.isEmpty) return; await PushRegister.subscribeTopic(t); await _loadTopics(); _toast('Subscribed: $t'); }, child: const Text('Subscribe')),
            ])
          ]),
        )),
        const SizedBox(height: 12),
        Glass(child: Padding(padding: const EdgeInsets.all(12), child: Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.tonal(onPressed: _loading ? null : _submitKyc, child: const Text('KYC einreichen')),
          FilledButton.tonal(onPressed: _loading ? null : _devApproveKyc, child: const Text('DEV: KYC Approve')),
          FilledButton.tonal(onPressed: _loading ? null : _applyMerchant, child: const Text('Händler‑Antrag')),
          OutlinedButton(onPressed: _loading ? null : _devSendPush, child: const Text('Dev: Send to me')),
          OutlinedButton(onPressed: _loading ? null : _devBroadcastTopic, child: const Text('Dev: Broadcast Topic')),
        ]))),
        const SizedBox(height: 8),
        Glass(child: Padding(padding: const EdgeInsets.all(12), child: Column(children: [
          Row(children: [
            Expanded(child: TextField(controller: _pushTitleCtrl, decoration: const InputDecoration(labelText: 'Title'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _pushBodyCtrl, decoration: const InputDecoration(labelText: 'Body'))),
          ]),
          const SizedBox(height: 8),
          TextField(controller: _pushLinkCtrl, decoration: const InputDecoration(labelText: 'Deeplink', hintText: 'superapp://...')),
        ]))),
        const SizedBox(height: 16),
        FilledButton.tonal(onPressed: _loading ? null : _logoutAll, child: const Text('Logout All')),
      ]),
    );
  }

  Future<void> _submitKyc() async { try { await servicePost('payments', '/kyc/submit'); _toast('KYC eingereicht'); } catch (_) { _toast('KYC Fehler'); } }

  Future<void> _devApproveKyc() async { try { await servicePost('payments', '/kyc/dev/approve'); _toast('KYC approved'); } catch (_) { _toast('Approve Fehler'); } }

  Future<void> _applyMerchant() async { try { await servicePost('payments', '/payments/merchant/apply'); _toast('Antrag gesendet'); } catch (_) { _toast('Antrag Fehler'); } }

  Future<void> _devSendPush() async {
    setState(() => _loading = true);
    try {
      await servicePostJson('superapp', '/v1/push/dev/send', body: {
        'title': _pushTitleCtrl.text.trim(),
        'body': _pushBodyCtrl.text.trim(),
        'deeplink': _pushLinkCtrl.text.trim(),
      });
      _toast('Gesendet');
    } catch (e) { _toast('Send Fehler: $e'); } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _devBroadcastTopic() async {
    final topic = _topicCtrl.text.trim();
    if (topic.isEmpty) { _toast('Topic fehlt'); return; }
    setState(() => _loading = true);
    try {
      await servicePostJson('superapp', '/v1/push/dev/broadcast_topic', body: {
        'topic': topic,
        'title': _pushTitleCtrl.text.trim(),
        'body': _pushBodyCtrl.text.trim(),
        'deeplink': _pushLinkCtrl.text.trim(),
      });
      _toast('Broadcast gesendet');
    } catch (e) { _toast('Broadcast Fehler: $e'); } finally { if (mounted) setState(() => _loading = false); }
  }

  // PIN management removed
}
