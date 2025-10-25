import 'dart:convert';
import 'package:flutter/material.dart';
import '../ui/glass.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import '../main.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _tokens = MultiTokenStore();
  Map<String, dynamic>? _wallet;
  Map<String, dynamic>? _kyc;
  bool _loading = false;

  Future<Map<String, String>> _paymentsHeaders() =>
      authHeaders('payments', store: _tokens);

  Uri _paymentsUri(String path) => ServiceConfig.endpoint('payments', path);
  

  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _loadWalletKyc() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final w = await http.get(_paymentsUri('/wallet'), headers: headers);
      final k = await http.get(_paymentsUri('/kyc'), headers: headers);
      if (w.statusCode >= 400) throw Exception('wallet ${w.body}');
      if (k.statusCode >= 400) throw Exception('kyc ${k.body}');
      setState(() {
        _wallet = jsonDecode(w.body) as Map<String, dynamic>;
        _kyc = jsonDecode(k.body) as Map<String, dynamic>;
      });
    } catch (e) {
      _toast('$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _logoutAll() async {
    await _tokens.clearAll();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const HomeScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final u = _wallet?['user'];
    final w = _wallet?['wallet'];
    return Scaffold(
      appBar: AppBar(title: const Text('Profile'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Glass(child: FilledButton(onPressed: _loading ? null : _loadWalletKyc, child: const Text('Load Wallet & KYC'))),
        const SizedBox(height: 8),
        if (u != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('User: ${u['phone']}  name: ${u['name'] ?? ''}'))) else const SizedBox.shrink(),
        if (w != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('Wallet: ${w['balance_cents']} ${w['currency_code']}'))) else const SizedBox.shrink(),
        const SizedBox(height: 8),
        if (_kyc != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('KYC: ${_kyc!['status']} (level ${_kyc!['level']})'))) else const SizedBox.shrink(),
        const SizedBox(height: 16),
        FilledButton.tonal(onPressed: _loading ? null : _logoutAll, child: const Text('Logout')),
      ]),
    );
  }

  // PIN management removed
}
