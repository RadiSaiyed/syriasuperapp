import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';
import '../auth.dart';
import 'profile_screen.dart';
import 'ai_gateway_screen.dart';

class UtilitiesScreen extends StatefulWidget {
  const UtilitiesScreen({super.key});
  @override
  State<UtilitiesScreen> createState() => _UtilitiesScreenState();
}

class _UtilitiesScreenState extends State<UtilitiesScreen> {
  final _tokens = MultiTokenStore();
  List<dynamic> _billers = [];
  String? _linkedAccountId;
  List<dynamic> _bills = [];
  bool _loading = false;
  // SuperSearch & OCR (MVP)
  final TextEditingController _searchCtrl = TextEditingController();
  List<Map<String, dynamic>> _helpItems = [];
  final TextEditingController _ocrCtrl = TextEditingController();
  List<Map<String, String>> _ocrFields = [];
  // AutoPay (MVP)
  final TextEditingController _ruleAccountCtrl = TextEditingController();
  final TextEditingController _ruleDayCtrl = TextEditingController();
  final TextEditingController _ruleMaxCtrl = TextEditingController();
  bool _ruleEnabled = true;
  List<Map<String, dynamic>> _rules = [];

  Uri _utilitiesUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('utilities', path, query: query);

  Map<String, String> _bearer(String token,
          {Map<String, String>? headers}) =>
      {
        'Authorization': 'Bearer $token',
        if (headers != null) ...headers,
      };

  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _listBillers() async {
    final t = await getTokenFor('utilities', store: _tokens);
    if (t == null) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res =
          await http.get(_utilitiesUri('/billers'), headers: _bearer(t));
      if (res.statusCode >= 400) throw Exception(res.body);
      final arr = jsonDecode(res.body) as List<dynamic>;
      setState(() => _billers = arr);
    } catch (e) {
      _toast('Billers failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Utilities'), actions: [
        IconButton(
            tooltip: 'AI Assistant',
            onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) => const AIGatewayScreen())),
            icon: const Icon(Icons.smart_toy_outlined)),
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        // Natural Language Help Search (SuperSearch)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Hilfe & Suche', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: TextField(
                  controller: _searchCtrl,
                  decoration: const InputDecoration(
                      labelText: 'Frage oder Stichwort',
                      hintText: 'z. B. Stromrechnung verknüpfen'),
                )),
                const SizedBox(width: 8),
                FilledButton(onPressed: _loading ? null : _doSearch, child: const Text('Suchen')),
              ]),
              if (_helpItems.isNotEmpty) const SizedBox(height: 8),
              for (final it in _helpItems)
                ListTile(
                  dense: true,
                  title: Text(it['text']?.toString() ?? ''),
                  subtitle: Text('Score: ${(it['score'] ?? 0).toStringAsFixed(3)}'),
                ),
            ]),
          ),
        ),
        const SizedBox(height: 8),
        // OCR Autofill (MVP)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('OCR (MVP)', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextField(
                controller: _ocrCtrl,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(
                    labelText: 'Text Hinweis',
                    hintText: 'z. B. Invoice #123 Total: 25000 Due 2025-11-01'),
              ),
              const SizedBox(height: 8),
              Row(children: [
                FilledButton(onPressed: _loading ? null : _doOcr, child: const Text('Extrahieren')),
              ]),
              if (_ocrFields.isNotEmpty) const SizedBox(height: 8),
              for (final f in _ocrFields)
                ListTile(dense: true, title: Text(f['key'] ?? ''), subtitle: Text(f['value'] ?? '')),
            ]),
          ),
        ),
        const Divider(height: 16),
        // AutoPay Rules (MVP)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Auto‑Pay Regeln', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: TextField(
                  controller: _ruleAccountCtrl,
                  decoration: const InputDecoration(labelText: 'Account ID (verknüpft)'),
                )),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: TextField(
                  controller: _ruleDayCtrl,
                  decoration: const InputDecoration(labelText: 'Tag im Monat (1..28, leer = Fälligkeitsdatum)'),
                  keyboardType: TextInputType.number,
                )),
                const SizedBox(width: 8),
                Expanded(
                    child: TextField(
                  controller: _ruleMaxCtrl,
                  decoration: const InputDecoration(labelText: 'Max Betrag (Cent, leer = unbegrenzt)'),
                  keyboardType: TextInputType.number,
                )),
              ]),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Aktiviert'),
                value: _ruleEnabled,
                onChanged: (v) => setState(() => _ruleEnabled = v),
              ),
              Row(children: [
                FilledButton(onPressed: _loading ? null : _saveRule, child: const Text('Speichern')),
                const SizedBox(width: 8),
                OutlinedButton(onPressed: _loading ? null : _loadRules, child: const Text('Regeln laden')),
                const SizedBox(width: 8),
                OutlinedButton(onPressed: _loading ? null : _runAutopay, child: const Text('Jetzt ausführen')),
              ]),
              if (_rules.isNotEmpty) const SizedBox(height: 8),
              for (final r in _rules)
                ListTile(
                  dense: true,
                  title: Text('Account: ${r['account_id']}'),
                  subtitle: Text('Tag: ${r['day_of_month'] ?? '-'}  Max: ${r['max_amount_cents'] ?? '-'}  Enabled: ${r['enabled']}'),
                ),
            ]),
          ),
        ),
        const SizedBox(height: 8),
        const Text('Use single‑login via Profile/Payments.'),
        TextButton(
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const ProfileScreen())),
            child: const Text('Open Profile (Login)')),
        const Divider(height: 16),
        Wrap(spacing: 8, children: [
          ElevatedButton(
              onPressed: _loading ? null : _listBillers,
              child: const Text('List Billers')),
          ElevatedButton(
              onPressed: _loading ? null : _refreshBills,
              child: const Text('Refresh Bills')),
          ElevatedButton(
              onPressed: _loading ? null : _listBills,
              child: const Text('List Bills')),
          ElevatedButton(
              onPressed: _loading ? null : _payFirstPending,
              child: const Text('Pay First Pending')),
        ]),
        const SizedBox(height: 8),
        for (final b in _billers)
          ListTile(
              title: Text(b['name'] ?? ''),
              subtitle: Text('Category: ${b['category']}'),
              trailing: TextButton(
                  onPressed: () => _linkAccount(b['id'] as String, 'METER-123'),
                  child: const Text('Link METER-123'))),
        if (_linkedAccountId != null) Text('Linked account: $_linkedAccountId'),
        if (_bills.isNotEmpty) const Divider(),
        for (final b in _bills)
          ListTile(
              title: Text('Bill ${b['id']}'),
              subtitle:
                  Text('Status: ${b['status']} Amount: ${b['amount_cents']}')),
      ]),
    );
  }

  Future<void> _linkAccount(String billerId, String accountRef) async {
    final t = await _tokens.get('utilities');
    if (t == null) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.post(
        _utilitiesUri('/accounts/link'),
        headers: _bearer(t, headers: {'Content-Type': 'application/json'}),
        body: jsonEncode({'biller_id': billerId, 'account_ref': accountRef}),
      );
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _linkedAccountId = js['id'] as String?);
    } catch (e) {
      _toast('Link failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _refreshBills() async {
    final t = await getTokenFor('utilities', store: _tokens);
    if (t == null) {
      _toast('Login first');
      return;
    }
    if (_linkedAccountId == null) {
      _toast('Link account first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.post(
          _utilitiesUri('/bills/refresh',
              query: {'account_id': _linkedAccountId!}),
          headers: _bearer(t));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _bills = js['bills'] as List? ?? []);
    } catch (e) {
      _toast('Refresh failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _listBills() async {
    final t = await getTokenFor('utilities', store: _tokens);
    if (t == null) {
      _toast('Login first');
      return;
    }
    setState(() => _loading = true);
    try {
      final res =
          await http.get(_utilitiesUri('/bills'), headers: _bearer(t));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _bills = js['bills'] as List? ?? []);
    } catch (e) {
      _toast('List bills failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _payFirstPending() async {
    final t = await getTokenFor('utilities', store: _tokens);
    if (t == null) {
      _toast('Login first');
      return;
    }
    final pending = _bills.where((b) => b['status'] == 'pending').toList();
    if (pending.isEmpty) {
      _toast('No pending bills');
      return;
    }
    // Request biometric confirmation if enabled
    final ok = await requireBiometricIfEnabled(context, reason: 'Confirm bill payment');
    if (!ok) return;
    setState(() => _loading = true);
    try {
      final id = pending.first['id'];
      final res = await http.post(_utilitiesUri('/bills/$id/pay'),
          headers: _bearer(t));
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Bill pay initiated');
    } catch (e) {
      _toast('Pay failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _doSearch() async {
    setState(() => _loading = true);
    try {
      final t = await getTokenFor('utilities', store: _tokens);
      final uri = _utilitiesUri('/help/search', query: {'q': _searchCtrl.text.trim()});
      final r = await http.get(uri, headers: t != null ? _bearer(t) : {});
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final items = ((js['items'] as List?) ?? [])
          .map<Map<String, dynamic>>((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      setState(() => _helpItems = items);
    } catch (e) {
      _toast('Search failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _doOcr() async {
    setState(() => _loading = true);
    try {
      final t = await getTokenFor('utilities', store: _tokens);
      if (t == null) {
        _toast('Login first');
        return;
      }
      final r = await http.post(
        _utilitiesUri('/ocr/invoice'),
        headers: _bearer(t, headers: {'Content-Type': 'application/json'}),
        body: jsonEncode({'text_hint': _ocrCtrl.text.trim()}),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      final fields = ((js['fields'] as List?) ?? [])
          .map<Map<String, String>>((e) => (e as Map).map((k, v) => MapEntry(k.toString(), v.toString())))
          .toList();
      setState(() => _ocrFields = fields);
    } catch (e) {
      _toast('OCR failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _saveRule() async {
    setState(() => _loading = true);
    try {
      final t = await getTokenFor('utilities', store: _tokens);
      if (t == null) {
        _toast('Login first');
        return;
      }
      final body = <String, dynamic>{
        'account_id': _ruleAccountCtrl.text.trim(),
        'enabled': _ruleEnabled,
      };
      final d = int.tryParse(_ruleDayCtrl.text.trim());
      if (d != null) body['day_of_month'] = d;
      final m = int.tryParse(_ruleMaxCtrl.text.trim());
      if (m != null) body['max_amount_cents'] = m;
      final r = await http.post(
        _utilitiesUri('/autopay/rules'),
        headers: _bearer(t, headers: {'Content-Type': 'application/json'}),
        body: jsonEncode(body),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Regel gespeichert');
      await _loadRules();
    } catch (e) {
      _toast('Save rule failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _loadRules() async {
    try {
      final t = await getTokenFor('utilities', store: _tokens);
      if (t == null) {
        _toast('Login first');
        return;
      }
      final r = await http.get(_utilitiesUri('/autopay/rules'), headers: _bearer(t));
      if (r.statusCode >= 400) throw Exception(r.body);
      final arr = jsonDecode(r.body) as List<dynamic>;
      setState(() => _rules = arr.map<Map<String, dynamic>>((e) => Map<String, dynamic>.from(e as Map)).toList());
    } catch (e) {
      _toast('Load rules failed: $e');
    }
  }

  Future<void> _runAutopay() async {
    setState(() => _loading = true);
    try {
      final t = await getTokenFor('utilities', store: _tokens);
      if (t == null) {
        _toast('Login first');
        return;
      }
      final r = await http.post(_utilitiesUri('/autopay/run'), headers: _bearer(t));
      if (r.statusCode >= 400) throw Exception(r.body);
      _toast('Auto‑Pay ausgelöst');
    } catch (e) {
      _toast('Run Auto‑Pay failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }
}
// ignore_for_file: use_build_context_synchronously
