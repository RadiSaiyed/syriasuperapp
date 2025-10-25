import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';

import '../api.dart';
import 'transfer_screen.dart';
import 'merchant_screen.dart';
import 'qr_scan_screen.dart';
import 'receive_qr_screen.dart';
import 'contacts_screen.dart';
import 'request_screen.dart';
import 'requests_inbox_screen.dart';
import 'security_screen.dart';
import '../security/auth_gate.dart';
import 'cash_screen.dart';
import 'cash_inbox_screen.dart';
import 'links_screen.dart';
import 'subscriptions_screen.dart';
import 'statement_screen.dart';
import '../ui/connectivity_banner.dart';
import '../ui/errors.dart';
import '../security/security_health.dart';

class WalletScreen extends StatefulWidget {
  final ApiClient api;
  final TokenStore tokenStore;
  final Uuid uuid;

  const WalletScreen({super.key, required this.api, required this.tokenStore, required this.uuid});

  @override
  State<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends State<WalletScreen> {
  Map<String, dynamic>? _wallet;
  bool _loading = true;
  final _topupCtrl = TextEditingController(text: '100000'); // 1,000.00 SYP if cents base 100
  int _pendingRequests = 0;
  final _numFmt = NumberFormat.decimalPattern();
  int _kycLevel = 0;
  String _kycStatus = 'none';
  int _pendingCashIncoming = 0;
  bool _rooted = false;

  @override
  void initState() {
    super.initState();
    _load();
    SecurityHealth.isCompromisedDevice().then((v) { if (mounted) setState(() => _rooted = v); });
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.getWallet();
      setState(() => _wallet = data);
      await _loadRequestsCount();
      await _loadCashIncomingCount();
      await _loadKyc();
    } catch (e) {
      if (mounted) showRetrySnack(context, '$e', _load);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadKyc() async {
    try {
      final r = await widget.api.getKyc();
      if (mounted) setState(() {
        _kycLevel = (r['kyc_level'] as int?) ?? 0;
        _kycStatus = (r['kyc_status'] as String?) ?? 'none';
      });
    } catch (_) {}
  }

  Future<Map<String, dynamic>?> _loadLimits() async {
    try {
      return await widget.api.limitsSummary();
    } catch (_) {
      return null;
    }
  }

  Future<void> _loadRequestsCount() async {
    try {
      final res = await widget.api.listRequests();
      final inc = (res['incoming'] as List?) ?? [];
      int c = 0;
      for (final r in inc) {
        if ((r as Map)['status'] == 'pending') c++;
      }
      if (mounted) setState(() => _pendingRequests = c);
    } catch (_) {}
  }

  Future<void> _loadCashIncomingCount() async {
    try {
      final res = await widget.api.listCashRequests();
      final inc = (res['incoming'] as List?) ?? [];
      int c = 0;
      for (final r in inc) {
        if ((r as Map)['status'] == 'pending') c++;
      }
      if (mounted) setState(() => _pendingCashIncoming = c);
    } catch (_) {}
  }

  String _fmtAmount(int cents, String currency) {
    // assume cents base 100
    final major = cents / 100.0;
    return '${_numFmt.format(major)} $currency';
  }

  Future<void> _topup() async {
    final amountText = _topupCtrl.text.trim();
    final amount = int.tryParse(amountText) ?? 0;
    if (amount <= 0) return;
    try {
      await widget.api.topup(amountCents: amount, idempotencyKey: 'topup-${widget.uuid.v4()}');
      unawaited(widget.api.audit('wallet_topup', {'amount_cents': amount}));
      await _load();
    } catch (e) {
      if (mounted) showRetrySnack(context, '$e', _topup);
    }
  }

  Future<void> _logout() async {
    await widget.tokenStore.clear();
    if (mounted) Navigator.of(context).pushAndRemoveUntil(MaterialPageRoute(builder: (_) => const _LoggedOut()), (_) => false);
  }

  Future<void> _scanToPay() async {
    final code = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScanScreen()),
    );
    if (code == null || code.isEmpty) return;
    await _handleScannedCode(code);
  }

  Map<String, String> _parseParams(String s) {
    // Expects key=value pairs separated by ';'
    final map = <String, String>{};
    for (final part in s.split(';')) {
      final idx = part.indexOf('=');
      if (idx <= 0) continue;
      final k = part.substring(0, idx).trim().toLowerCase();
      final v = part.substring(idx + 1).trim();
      if (k.isNotEmpty) map[k] = v;
    }
    return map;
  }

  Future<void> _handleScannedCode(String code) async {
    if (code.startsWith('PAY:v1;code=')) {
      // Merchant QR
      final ok = await AuthGate.verifyForAction(context, reason: 'Pay merchant');
      if (!ok) return;
      bool cancelled = false;
      await showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => StatefulBuilder(builder: (ctx, setState) {
          () async {
            try {
              final res = await widget.api.payQr(code: code, idempotencyKey: 'qr-${widget.uuid.v4()}');
              if (!mounted || cancelled) return;
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Paid ${res['amount_cents']}')));
              unawaited(widget.api.audit('payment_qr', {'amount_cents': res['amount_cents'] ?? 0}));
              await _load();
            } catch (e) {
              if (!mounted || cancelled) return;
              Navigator.pop(ctx);
              showRetrySnack(context, '$e', () => _handleScannedCode(code));
            }
          }();
          return AlertDialog(
            content: Row(children: const [CircularProgressIndicator(), SizedBox(width: 12), Text('Processing payment…')]),
            actions: [
              TextButton(onPressed: () { cancelled = true; Navigator.pop(ctx); }, child: const Text('Cancel')),
            ],
          );
        }),
      );
      return;
    }
    if (code.startsWith('VCHR|')) {
      final parts = code.split('|');
      final voucher = parts.length == 2 ? parts[1] : code.substring(5);
      try {
        final ok = await AuthGate.verifyForAction(context, reason: 'Redeem voucher');
        if (!ok) return;
        await widget.api.redeemVoucher(code: voucher);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Voucher redeemed')));
          unawaited(widget.api.audit('voucher_redeem', {'code_len': voucher.length}));
          await _load();
        }
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
      return;
    }
    if (code.startsWith('P2P:v1;')) {
      // P2P QR -> parse params
      final rest = code.substring('P2P:v1;'.length);
      final params = _parseParams(rest);
      final to = params['to'] ?? params['to_phone'];
      if (to == null || to.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context)
              .showSnackBar(const SnackBar(content: Text('Invalid P2P QR: missing destination phone')));
        }
        return;
      }
      int amount = 0;
      if (params.containsKey('amount_cents')) {
        amount = int.tryParse(params['amount_cents'] ?? '') ?? 0;
      }
      if (amount <= 0) {
        // prompt for amount
        final ctrl = TextEditingController();
        final entered = await showDialog<String>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Enter amount (cents)'),
            content: TextField(controller: ctrl, keyboardType: TextInputType.number),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('OK')),
            ],
          ),
        );
        if (entered == null || entered.isEmpty) return;
        amount = int.tryParse(entered) ?? 0;
      }
      if (amount <= 0) {
        if (mounted) {
          ScaffoldMessenger.of(context)
              .showSnackBar(const SnackBar(content: Text('Invalid amount')));
        }
        return;
      }
      bool cancelled = false;
      await showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => StatefulBuilder(builder: (ctx, setState) {
          () async {
            try {
              final res = await widget.api.transfer(
                toPhone: to,
                amountCents: amount,
                idempotencyKey: 'p2p-${widget.uuid.v4()}',
              );
              if (!mounted || cancelled) return;
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context)
                  .showSnackBar(SnackBar(content: Text('Sent ${res['amount_cents']} to $to')));
              final masked = to.replaceRange(4, to.length - 2, '****');
              unawaited(widget.api.audit('payment_p2p', {'amount_cents': res['amount_cents'] ?? amount, 'to_masked': masked}));
              await _load();
            } catch (e) {
              if (!mounted || cancelled) return;
              Navigator.pop(ctx);
              showRetrySnack(context, '$e', () => _handleScannedCode(code));
            }
          }();
          return AlertDialog(
            content: Row(children: const [CircularProgressIndicator(), SizedBox(width: 12), Text('Sending transfer…')]),
            actions: [
              TextButton(onPressed: () { cancelled = true; Navigator.pop(ctx); }, child: const Text('Cancel')),
            ],
          );
        }),
      );
      return;
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Unrecognized QR')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = _wallet != null ? _wallet!['user'] as Map<String, dynamic>? : null;
    final w = _wallet != null ? _wallet!['wallet'] as Map<String, dynamic>? : null;
    return _loading
        ? const Center(child: CircularProgressIndicator())
        : SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const ConnectivityBanner(),
              if (_rooted)
                Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(color: Colors.orange.shade700, borderRadius: BorderRadius.circular(8)),
                  child: const Text('Security warning: Device may be rooted / jailbroken.', style: TextStyle(color: Colors.white)),
                ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Wallet', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                  IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
                ],
              ),
              const SizedBox(height: 8),
              if (user != null)
                Text('User: ${user['phone']}  ${user['name'] ?? ''}', style: const TextStyle(fontSize: 14)),
              const SizedBox(height: 12),
              if (w != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('KYC: level $_kycLevel — $_kycStatus'),
                          Row(children: [
                            TextButton(onPressed: () async { await widget.api.submitKyc(); unawaited(widget.api.audit('kyc_submit', {})); await _loadKyc(); }, child: const Text('Submit')),
                            const SizedBox(width: 8),
                            TextButton(onPressed: () async { await widget.api.devApproveKyc(); unawaited(widget.api.audit('kyc_approve_dev', {})); await _loadKyc(); }, child: const Text('Dev Approve')),
                          ]),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text('Balance: ${_fmtAmount((w['balance_cents'] ?? 0) as int, w['currency_code'] as String)}',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 12),
                      FutureBuilder<Map<String, dynamic>?>(
                        future: _loadLimits(),
                        builder: (context, snap) {
                          final m = snap.data;
                          return Card(
                            child: Padding(
                              padding: const EdgeInsets.all(12),
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                const Text('Compliance & Limits', style: TextStyle(fontWeight: FontWeight.w600)),
                                const SizedBox(height: 6),
                                Text('KYC: level \\$_kycLevel — \\$_kycStatus'),
                                const SizedBox(height: 4),
                                Text('Per‑Tx Max: \\${m?['per_txn_max_cents'] ?? 'N/A'}'),
                                Text('Daily Outgoing: \\${m?['daily_outgoing_cents'] ?? 'N/A'}'),
                                Text('Daily Incoming: \\${m?['daily_incoming_cents'] ?? 'N/A'}'),
                              ]),
                            ),
                          );
                        },
                      ),
                      const SizedBox(height: 12),
                      Row(children: [
                        Expanded(
                          child: TextField(
                            controller: _topupCtrl,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(labelText: 'Topup amount (cents)'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton(onPressed: _topup, child: const Text('Dev Topup')),
                      ]),
                    ]),
                  ),
                ),
              const SizedBox(height: 12),
              Wrap(spacing: 8, runSpacing: 8, children: [
                FilledButton.icon(
                  onPressed: () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => TransferScreen(api: widget.api, onDone: _load)));
                  },
                  icon: const Icon(Icons.send),
                  label: const Text('Transfer'),
                ),
                FilledButton.icon(
                  onPressed: _scanToPay,
                  icon: const Icon(Icons.qr_code_scanner),
                  label: const Text('Scan to Pay'),
                ),
                OutlinedButton.icon(
                  onPressed: () async {
                    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SecurityScreen()));
                  },
                  icon: const Icon(Icons.lock),
                  label: const Text('Security'),
                ),
                OutlinedButton.icon(
                  onPressed: () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => CashScreen(api: widget.api, onChanged: _load),
                    ));
                  },
                  icon: const Icon(Icons.account_balance_wallet),
                  label: const Text('Cash In/Out'),
                ),
                FilledButton.icon(
                  onPressed: () {
                    final phone = _wallet?['user']?['phone'] as String?;
                    if (phone == null || phone.isEmpty) return;
                    Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => ReceiveQrScreen(phone: phone)),
                    );
                  },
                  icon: const Icon(Icons.qr_code_2),
                  label: const Text('Receive QR'),
                ),
                OutlinedButton.icon(
                  onPressed: () {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => ContactsScreen(
                        onTransfer: (p) {
                          Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) => TransferScreen(api: widget.api, initialPhone: p, onDone: _load),
                          ));
                        },
                        onRequest: (p) {
                          Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) => RequestScreen(api: widget.api, initialPhone: p),
                          ));
                        },
                      ),
                    ));
                  },
                  icon: const Icon(Icons.contacts),
                  label: const Text('Contacts'),
                ),
                Stack(
                  clipBehavior: Clip.none,
                  children: [
                    OutlinedButton.icon(
                      onPressed: () {
                        Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => RequestsInboxScreen(api: widget.api),
                        ));
                      },
                      icon: const Icon(Icons.request_page),
                      label: const Text('Requests'),
                    ),
                    if (_pendingRequests > 0)
                      Positioned(
                        right: -4,
                        top: -4,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(color: Colors.red, borderRadius: BorderRadius.circular(12)),
                          child: Text('$_pendingRequests', style: const TextStyle(color: Colors.white, fontSize: 12)),
                        ),
                      ),
                  ],
                ),
                Stack(
                  clipBehavior: Clip.none,
                  children: [
                    OutlinedButton.icon(
                      onPressed: () async {
                        await Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => CashInboxScreen(api: widget.api),
                        ));
                        await _loadCashIncomingCount();
                      },
                      icon: const Icon(Icons.store),
                      label: const Text('Agent Inbox'),
                    ),
                    if (_pendingCashIncoming > 0)
                      Positioned(
                        right: -4,
                        top: -4,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(color: Colors.red, borderRadius: BorderRadius.circular(12)),
                          child: Text('$_pendingCashIncoming', style: const TextStyle(color: Colors.white, fontSize: 12)),
                        ),
                      ),
                  ],
                ),
                FilledButton.icon(
                  onPressed: () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => MerchantScreen(api: widget.api, onChanged: _load)));
                  },
                  icon: const Icon(Icons.qr_code),
                  label: const Text('Merchant / QR'),
                ),
                OutlinedButton.icon(
                  onPressed: () async { await Navigator.of(context).push(MaterialPageRoute(builder: (_) => LinksScreen(api: widget.api))); },
                  icon: const Icon(Icons.link),
                  label: const Text('Links'),
                ),
                OutlinedButton.icon(
                  onPressed: () async { await Navigator.of(context).push(MaterialPageRoute(builder: (_) => SubscriptionsScreen(api: widget.api))); },
                  icon: const Icon(Icons.repeat),
                  label: const Text('Subscriptions'),
                ),
                OutlinedButton.icon(
                  onPressed: () async { await Navigator.of(context).push(MaterialPageRoute(builder: (_) => StatementScreen(api: widget.api))); },
                  icon: const Icon(Icons.summarize),
                  label: const Text('Statement'),
                ),
                OutlinedButton.icon(onPressed: _logout, icon: const Icon(Icons.logout), label: const Text('Logout')),
              ]),
              const SizedBox(height: 16),
              const Text('Transactions', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              _TransactionsList(api: widget.api),
            ]),
          );
  }
}

class _TransactionsList extends StatefulWidget {
  final ApiClient api;
  const _TransactionsList({required this.api});
  @override
  State<_TransactionsList> createState() => _TransactionsListState();
}

class _TransactionsListState extends State<_TransactionsList> {
  bool _loading = true;
  List<dynamic> _entries = [];
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final e = await widget.api.transactions();
      setState(() => _entries = e);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_entries.isEmpty) return const Text('No transactions');
    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _entries.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, i) {
        final e = _entries[i] as Map<String, dynamic>;
        final amt = e['amount_cents_signed'] as int? ?? 0;
        final sign = amt >= 0 ? '+' : '-';
        return ListTile(
          dense: true,
          title: Text('Transfer ${e['transfer_id']}'),
          subtitle: Text(e['created_at'] ?? ''),
          trailing: Text('$sign${amt.abs()}', style: TextStyle(color: amt >= 0 ? Colors.green : Colors.red)),
        );
      },
    );
  }
}

class _LoggedOut extends StatelessWidget {
  const _LoggedOut();
  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('Logged out. Restart the app.')));
  }
}
