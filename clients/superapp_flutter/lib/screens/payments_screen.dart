import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:http/http.dart' as http;
import 'package:qr_flutter/qr_flutter.dart';
import 'package:share_plus/share_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:printing/printing.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:flutter_contacts/flutter_contacts.dart';
import 'package:local_auth/local_auth.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services.dart';
import 'qr_scan_screen.dart';
import '../ui/glass.dart';
import 'ai_gateway_screen.dart';

class PaymentsScreen extends StatefulWidget {
  final String? initialAction; // 'scan' | 'topup'
  final String? view; // 'p2p' to show only P2P section
  const PaymentsScreen({super.key, this.initialAction, this.view});

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  final _tokens = MultiTokenStore();
  String? _balance;
  bool _loading = false;
  String? _viewMode; // if 'p2p', render only P2P section
  // Data
  List<Map<String, dynamic>> _tx = [];
  // Paging/filters
  int _txPage = 1;
  int _txPageSize = 50;
  int _txTotal = 0;
  String _txFilter = 'all'; // all|in|out
  // Requests
  List<Map<String, dynamic>> _reqIncoming = [];
  List<Map<String, dynamic>> _reqOutgoing = [];
  // P2P
  final _p2pPhoneCtrl = TextEditingController(text: '+963900000002');
  final _p2pAmountCtrl = TextEditingController(text: '1000'); // SYP
  // Payment Request (Create)
  final _reqPhoneCtrl = TextEditingController(text: '+963900000002');
  final _reqAmountCtrl = TextEditingController(text: '2500');
  final _reqExpiryCtrl = TextEditingController(text: '60');
  final _reqMetaCtrl = TextEditingController();
  // Split Bill
  final _splitTotalCtrl = TextEditingController(text: '10000');
  final List<TextEditingController> _splitPhones = [
    TextEditingController(text: '+963900000002'),
    TextEditingController(text: '+963900000003'),
  ];
  bool _splitEqual = true;
  // Links
  final _linkAmountCtrl = TextEditingController(text: '1500'); // SYP (dynamic)
  final _linkCodeCtrl = TextEditingController();
  final _linkPayAmountCtrl = TextEditingController(text: '1500'); // for static
  String? _lastLinkCode;
  // QR
  final _qrAmountCtrl = TextEditingController(text: '10000'); // SYP (dynamic)
  // Vouchers UI is admin-only (see ops_admin_flutter)

  Future<Map<String, String>> _paymentsHeaders() =>
      authHeaders('payments', store: _tokens);

  Uri _paymentsUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('payments', path, query: query);

  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }
  // Webhooks removed
  @override
  void initState() {
    super.initState();
    _viewMode = widget.view;
    // Defer actions until first frame
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      if (widget.initialAction == 'scan') {
        await _scanAndPay();
      } else if (widget.initialAction == 'topup') {
        await _scanTopUp();
      }
    });
  }

  // Per-app OTP login removed: use central login

  Future<void> _fetchWallet() async {
    final t = await getTokenFor('payments', store: _tokens);
    if (t == null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final headers = await _paymentsHeaders();
      final res = await http.get(_paymentsUri('/wallet'), headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => _balance =
          '${js['wallet']['balance_cents']} ${js['wallet']['currency_code']}');
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Wallet failed: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  // Dev topup removed

  String _fmtCents(int? cents, {String currency = 'SYP'}) {
    if (cents == null) return '0 $currency';
    return '$cents $currency';
  }

  Future<void> _p2pTransfer() async {
    // Require biometric confirmation for payments
    final bioOk = await _confirmBiometric();
    if (!bioOk) return;
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    final to = _p2pPhoneCtrl.text.trim();
    final amtStr = _p2pAmountCtrl.text.trim();
    final amt = int.tryParse(amtStr);
    if (to.isEmpty || amt == null || amt <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter phone and amount')));
      return;
    }
    setState(() => _loading = true);
    try {
      headers['Idempotency-Key'] =
          'p2p-${DateTime.now().millisecondsSinceEpoch}';
      final res = await http.post(_paymentsUri('/wallet/transfer'),
          headers: headers,
          body: jsonEncode({
            'to_phone': to,
            'amount_cents': amt * 100,
            'idempotency_key': headers['Idempotency-Key'],
          }));
      if (res.statusCode >= 400) throw Exception(res.body);
      await _fetchWallet();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('P2P transfer OK')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('P2P failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickContactInto(TextEditingController ctrl) async {
    try {
      final granted = await FlutterContacts.requestPermission();
      if (!granted) { _toast('No contacts permission'); return; }
      final c = await FlutterContacts.openExternalPick();
      if (c == null) return;
      final phones = c.phones;
      if (phones.isEmpty) { _toast('Contact has no phone number'); return; }
      final num = phones.first.number.trim();
      ctrl.text = num;
    } catch (e) { _toast('Contact pick failed: $e'); }
  }

  Future<void> _createRequest() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      _toast('Login first');
      return;
    }
    final to = _reqPhoneCtrl.text.trim();
    final amt = int.tryParse(_reqAmountCtrl.text.trim());
    final exp = int.tryParse(_reqExpiryCtrl.text.trim());
    if (to.isEmpty || amt == null || amt <= 0) { _toast('Phone/Amount fehlen'); return; }
    setState(() => _loading = true);
    try {
      final body = {
        'to_phone': to,
        'amount_cents': amt * 100,
      if (exp != null && exp > 0) 'expires_in_minutes': exp,
      if (_reqMetaCtrl.text.trim().isNotEmpty) 'metadata': { 'note': _reqMetaCtrl.text.trim() },
      };
      final idk = 'pr-${DateTime.now().millisecondsSinceEpoch}-${to.hashCode}';
      final reqHeaders = Map<String, String>.from(headers)
        ..['Idempotency-Key'] = idk;
      final res = await http.post(_paymentsUri('/requests'),
          headers: reqHeaders,
          body: jsonEncode(body));
      if (res.statusCode >= 400) throw Exception(res.body);
      _toast('Request erstellt');
      await _loadRequests();
    } catch (e) { _toast('Create failed: $e'); }
    finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _createSplitRequests() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) { _toast('Login first'); return; }
    final total = int.tryParse(_splitTotalCtrl.text.trim());
    if (total == null || total <= 0) { _toast('Enter total amount'); return; }
    final phones = _splitPhones.map((c) => c.text.trim()).where((p) => p.isNotEmpty).toList();
    if (phones.isEmpty) { _toast('Add at least one participant'); return; }
    // Even split
    final n = phones.length;
    final share = total ~/ n;
    int rem = total % n;
    setState(() => _loading = true);
    try {
      for (int i = 0; i < n; i++) {
        final syp = share + (rem > 0 ? 1 : 0);
        if (rem > 0) rem -= 1;
        final body = {
          'to_phone': phones[i],
          'amount_cents': syp * 100,
          'metadata': { 'split_total_syp': total, 'participants': phones },
        };
        final idk = 'split-${DateTime.now().millisecondsSinceEpoch}-$i-${phones[i].hashCode}';
        final res = await http.post(_paymentsUri('/requests'),
            headers: (Map<String, String>.from(headers)
              ..['Idempotency-Key'] = idk),
            body: jsonEncode(body));
        if (res.statusCode >= 400) throw Exception('req ${i+1}/$n: ${res.body}');
      }
      _toast('Split created: $n requests');
      await _loadRequests();
    } catch (e) { _toast('Split failed: $e'); }
    finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _createLinkDynamic() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    final amt = int.tryParse(_linkAmountCtrl.text.trim());
    if (amt == null || amt <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter amount')));
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.post(_paymentsUri('/payments/links'),
          headers: headers,
          body: jsonEncode({'amount_cents': amt * 100}));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _lastLinkCode = js['code'] as String?;
        if (_lastLinkCode != null) _linkCodeCtrl.text = _lastLinkCode!;
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Link created')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create link failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _createLinkStatic() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.post(_paymentsUri('/payments/links'),
          headers: headers,
          body: jsonEncode({}));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _lastLinkCode = js['code'] as String?;
        if (_lastLinkCode != null) _linkCodeCtrl.text = _lastLinkCode!;
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Static link created')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create link failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _payLink() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    final code = _linkCodeCtrl.text.trim();
    if (code.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter link code')));
      return;
    }
    final amt = int.tryParse(_linkPayAmountCtrl.text.trim());
    setState(() => _loading = true);
    try {
      final body = <String, dynamic>{
        'code': code,
        'idempotency_key': 'link-pay-${DateTime.now().millisecondsSinceEpoch}',
      };
      if (amt != null && amt > 0) body['amount_cents'] = amt * 100;
      final res = await http.post(_paymentsUri('/payments/links/pay'),
          headers: headers,
          body: jsonEncode(body));
      if (res.statusCode >= 400) throw Exception(res.body);
      await _fetchWallet();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Link paid')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Pay link failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _createMerchantQr() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    final amt = int.tryParse(_qrAmountCtrl.text.trim());
    if (amt == null || amt <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter amount')));
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.post(_paymentsUri('/payments/merchant/qr'),
          headers: headers,
          body: jsonEncode({'amount_cents': amt * 100, 'currency_code': 'SYP', 'mode': 'dynamic'}));
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final code = (js['code'] as String?) ?? '';
      if (!mounted) return;
      await _showQrDialog(title: 'Receiving QR', code: code.isNotEmpty ? code : res.body, amountSyp: amt);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create QR failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _createStaticQr() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      // Consumer-presented QR containing user's phone for P2P style payments
      final res = await http.get(
          _paymentsUri('/payments/cpm_qr', query: {'format': 'phone'}),
          headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final code = (js['qr_text'] as String?) ?? '';
      if (!mounted) return;
      await _showQrDialog(title: 'Receiving QR', code: code.isNotEmpty ? code : res.body);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create static QR failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }


  int? _parseSypFromQr(String s) {
    final t = s.trim();
    final onlyDigits = RegExp(r'^\d{1,9}$');
    if (onlyDigits.hasMatch(t)) return int.tryParse(t);
    final amt = RegExp(r'(?:amount(?:_syp)?\s*=\s*)(\d{1,9})', caseSensitive: false).firstMatch(t);
    if (amt != null) return int.tryParse(amt.group(1)!);
    final centsM = RegExp(r'(?:amount_cents\s*=\s*)(\d{1,12})', caseSensitive: false).firstMatch(t);
    if (centsM != null) {
      final cents = int.tryParse(centsM.group(1)!);
      if (cents != null && cents > 0) return (cents / 100).floor();
    }
    final sypPat = RegExp(r'SYP[:\s]*(\d{1,9})', caseSensitive: false).firstMatch(t);
    if (sypPat != null) return int.tryParse(sypPat.group(1)!);
    return null;
  }

  Future<void> _scanAndPay() async {
    final code = await Navigator.push<String?>(context, MaterialPageRoute(builder: (_) => const QrScanScreen()));
    if (code == null || code.isEmpty) return;
    // P2P static CPM QR
    if (code.startsWith('CPM:v1;phone=')) {
      final phone = code.substring('CPM:v1;phone='.length).trim();
      final amtCtrl = TextEditingController();
      final ok = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Scan & Pay (P2P)'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('To: $phone'),
            const SizedBox(height: 6),
            TextField(controller: amtCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (SYP)')),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(_, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(_, true), child: const Text('Pay')),
          ],
        ),
      );
      if (ok == true) {
        final v = int.tryParse(amtCtrl.text.trim());
        if (v != null && v > 0) {
          await _p2pPayPhone(phone, v);
        }
      }
      return;
    }

    // Merchant PAY QR (dynamic or static); ask for amount if needed
    final parsedAmt = _parseSypFromQr(code);
    int? toPaySyp = parsedAmt;
    final amtCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Scan & Pay (Merchant)'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (parsedAmt != null)
            Text('You will pay $parsedAmt SYP (dynamic QR).')
          else ...[
            const Text('Static QR – enter amount:'),
            const SizedBox(height: 6),
            TextField(controller: amtCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (SYP)')),
          ],
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(_, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(_, true), child: const Text('Pay')),
        ],
      ),
    );
    if (ok == true) {
      if (parsedAmt == null) {
        final v = int.tryParse(amtCtrl.text.trim());
        if (v == null || v <= 0) return;
        toPaySyp = v;
      }
      await _payMerchantCode(code, amountSyp: toPaySyp);
    }
  }

  Future<void> _p2pPayPhone(String phone, int syp) async {
    final bioOk = await _confirmBiometric();
    if (!bioOk) return;
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      headers['Idempotency-Key'] =
          'p2p-qr-${DateTime.now().millisecondsSinceEpoch}';
      final res = await http.post(_paymentsUri('/wallet/transfer'),
          headers: headers,
          body: jsonEncode({
            'to_phone': phone,
            'amount_cents': syp * 100,
            'idempotency_key': headers['Idempotency-Key'],
          }));
      if (res.statusCode >= 400) throw Exception(res.body);
      await _fetchWallet();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('P2P paid')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('P2P failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _scanTopUp() async {
    final code = await Navigator.push<String?>(context, MaterialPageRoute(builder: (_) => const QrScanScreen()));
    if (code == null || code.isEmpty) return;
    // Try to parse amount from QR/text
    final amt = _parseSypFromQr(code);
    if (amt == null || amt <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No amount detected in QR')));
      return;
    }
    // Offer to open Payments app via deep link if available
    final uri = Uri.parse('payments://topup?amount=$amt');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Top Up'),
          content: Text('Top up SYP $amt in the Payments app.'),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
        ),
      );
    }
  }

  Future<void> _payMerchantCode(String code, {int? amountSyp}) async {
    final bioOk = await _confirmBiometric();
    if (!bioOk) return;
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final body = <String, dynamic>{
        'code': code,
        'idempotency_key': 'qr-pay-${DateTime.now().millisecondsSinceEpoch}',
      };
      if (amountSyp != null && amountSyp > 0) body['amount_cents'] = amountSyp * 100;
      final res = await http.post(_paymentsUri('/payments/merchant/pay'),
          headers: headers,
          body: jsonEncode(body));
      if (res.statusCode >= 400) throw Exception(res.body);
      await _fetchWallet();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Paid successfully')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Pay failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _showQrDialog({required String title, required String code, int? amountSyp}) async {
    if (!mounted) return;
    final png = await _buildQrPng(code);
    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(title),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (png != null)
              Container(
                color: Colors.white,
                padding: const EdgeInsets.all(8),
                child: Image.memory(png, width: 220, height: 220, fit: BoxFit.contain, filterQuality: FilterQuality.high),
              )
            else
              Container(
                color: Colors.white,
                padding: const EdgeInsets.all(8),
                child: QrImageView(data: code, version: QrVersions.auto, size: 220, backgroundColor: Colors.white),
              ),
            const SizedBox(height: 8),
            if (amountSyp != null)
              Text('Amount: $amountSyp SYP', style: const TextStyle(fontWeight: FontWeight.w600)),
            if (amountSyp != null) const SizedBox(height: 10),
            // Row(s) of actions for QR asset
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 8,
              runSpacing: 8,
              children: [
                if (png != null) OutlinedButton(onPressed: () => _savePng(png), child: const Text('Save QR')),
                if (png != null) OutlinedButton(onPressed: () => _sharePng(png), child: const Text('Share QR')),
                if (png != null) OutlinedButton(onPressed: () => _printPng(png), child: const Text('Print QR')),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () {
                Clipboard.setData(ClipboardData(text: code));
                Navigator.pop(context);
              },
              child: const Text('Copy')),
          FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close')),
        ],
      ),
    );
  }

  Future<Uint8List?> _buildQrPng(String code, {double size = 512}) async {
    try {
      final painter = QrPainter(
        data: code,
        version: QrVersions.auto,
        gapless: true,
        eyeStyle: const QrEyeStyle(eyeShape: QrEyeShape.square, color: Colors.black),
        dataModuleStyle: const QrDataModuleStyle(dataModuleShape: QrDataModuleShape.square, color: Colors.black),
      );
      final bd = await painter.toImageData(size, format: ui.ImageByteFormat.png);
      if (bd == null) return null;
      return bd.buffer.asUint8List();
    } catch (_) {
      return null;
    }
  }

  Future<void> _savePng(Uint8List png) async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      final ts = DateTime.now().toIso8601String().replaceAll(':', '-');
      final file = File('${dir.path}/qr_$ts.png');
      await file.writeAsBytes(png);
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Saved: ${file.path}')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Save failed: $e')));
    }
  }

  Future<void> _sharePng(Uint8List png) async {
    try {
      final xf = XFile.fromData(png, name: 'qr.png', mimeType: 'image/png');
      await Share.shareXFiles([xf], text: 'QR Code');
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Share failed: $e')));
    }
  }

  Future<void> _printPng(Uint8List png) async {
    try {
      final doc = pw.Document();
      final img = pw.MemoryImage(png);
      doc.addPage(pw.Page(build: (context) => pw.Center(child: pw.Image(img))));
      await Printing.layoutPdf(onLayout: (_) async => doc.save());
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Print failed: $e')));
    }
  }

  // Webhook helpers removed

  Future<void> _loadTransactions() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final uri = _paymentsUri('/wallet/transactions/page',
          query: {
            'page': '$_txPage',
            'page_size': '$_txPageSize'
          });
      final res = await http.get(uri, headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final entries = (js['entries'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      // Apply simple client-side filter by sign
      final filtered = entries.where((e) {
        final v = (e['amount_cents_signed'] as int?) ?? 0;
        if (_txFilter == 'in') return v > 0;
        if (_txFilter == 'out') return v < 0;
        return true;
      }).toList();
      setState(() {
        _tx = filtered;
        _txTotal = (js['total'] as int?) ?? entries.length;
        _txPage = (js['page'] as int?) ?? _txPage;
        _txPageSize = (js['page_size'] as int?) ?? _txPageSize;
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Transactions failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  // Merchant Statement removed

  Future<void> _loadRequests() async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await http.get(_paymentsUri('/requests'), headers: headers);
      if (res.statusCode >= 400) throw Exception(res.body);
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _reqIncoming = ((js['incoming'] as List?) ?? []).cast<Map<String, dynamic>>();
        _reqOutgoing = ((js['outgoing'] as List?) ?? []).cast<Map<String, dynamic>>();
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Requests failed: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _acceptRequest(String id) async {
    final bioOk = await _confirmBiometric();
    if (!bioOk) return;
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Login first')));
      return;
    }
    setState(() => _loading = true);
    try {
      final r = await http.post(
          _paymentsUri('/requests/$id/accept'),
          headers: headers);
      if (r.statusCode >= 400) throw Exception(r.body);
      await _fetchWallet();
      await _loadRequests();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Request accepted')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Accept failed: $e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<bool> _confirmBiometric() async {
    try {
      final auth = LocalAuthentication();
      final supp = await auth.isDeviceSupported();
      final can = await auth.canCheckBiometrics;
      if (!supp || !can) { _toast('Biometrics not available'); return false; }
      final lang = WidgetsBinding.instance.platformDispatcher.locale.languageCode.toLowerCase();
      final reason = lang == 'ar' ? 'تأكيد الدفع باستخدام Face ID / Touch ID' : 'Confirm payment with Face ID / Touch ID';
      final rs = await auth.authenticate(localizedReason: reason, options: const AuthenticationOptions(biometricOnly: true, stickyAuth: true));
      if (!rs) _toast('Payment canceled');
      return rs;
    } catch (e) { _toast('Biometric error: $e'); return false; }
  }

  Future<void> _rejectRequest(String id) async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Login first'))); return; }
    setState(() => _loading = true);
    try {
      final r = await http.post(_paymentsUri('/requests/$id/reject'), headers: headers);
      if (r.statusCode >= 400) throw Exception(r.body);
      await _loadRequests();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Reject failed: $e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _cancelRequest(String id) async {
    final headers = await _paymentsHeaders();
    if (!headers.containsKey('Authorization')) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Login first'))); return; }
    setState(() => _loading = true);
    try {
      final r = await http.post(_paymentsUri('/requests/$id/cancel'), headers: headers);
      if (r.statusCode >= 400) throw Exception(r.body);
      await _loadRequests();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Cancel failed: $e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  // Merchant Statement export removed

  @override
  Widget build(BuildContext context) {
    // When in P2P view mode, render a minimal page: wallet + P2P only
    if (_viewMode == 'p2p') {
      return Scaffold(
        appBar: AppBar(title: const Text('Payments'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
        body: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 16), children: [
          Row(children: [
            Expanded(child: ElevatedButton(onPressed: _loading ? null : _fetchWallet, child: const Text('Check Wallet'))),
          ]),
          if (_balance != null)
            Padding(padding: const EdgeInsets.only(top: 8), child: Text('Balance: $_balance')),
          const SizedBox(height: 16),
          Glass(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('P2P Transfer', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: TextField(controller: _p2pPhoneCtrl, decoration: const InputDecoration(labelText: 'To phone (+963...)'))),
                  const SizedBox(width: 8),
                  IconButton(onPressed: _loading ? null : () => _pickContactInto(_p2pPhoneCtrl), icon: const Icon(Icons.contacts_outlined))
                ]),
                const SizedBox(height: 8),
                TextField(controller: _p2pAmountCtrl, decoration: const InputDecoration(labelText: 'Amount (SYP)'), keyboardType: TextInputType.number),
                const SizedBox(height: 8),
                FilledButton(onPressed: _loading ? null : _p2pTransfer, child: const Text('Send')),
              ]),
            ),
          ),
        ]),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Payments'), actions: [
        IconButton(
            tooltip: 'AI Assistant',
            onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) => const AIGatewayScreen())),
            icon: const Icon(Icons.smart_toy_outlined)),
      ], flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 16), children: [
        // Wallet
        Row(children: [
          Expanded(child: ElevatedButton(onPressed: _loading ? null : _fetchWallet, child: const Text('Check Wallet'))),
        ]),
        if (_balance != null)
          Padding(padding: const EdgeInsets.only(top: 8), child: Text('Balance: $_balance')),

        

        const SizedBox(height: 16),
        // P2P Transfer
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('P2P Transfer', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _p2pPhoneCtrl, decoration: const InputDecoration(labelText: 'To phone (+963...)'))),
                const SizedBox(width: 8),
                IconButton(onPressed: _loading ? null : () => _pickContactInto(_p2pPhoneCtrl), icon: const Icon(Icons.contacts_outlined))
              ]),
              const SizedBox(height: 8),
              TextField(controller: _p2pAmountCtrl, decoration: const InputDecoration(labelText: 'Amount (SYP)'), keyboardType: TextInputType.number),
              const SizedBox(height: 8),
              FilledButton(onPressed: _loading ? null : _p2pTransfer, child: const Text('Send')),
            ]),
          ),
        ),

        // Payment Links section removed on request

        const SizedBox(height: 16),
        // Payment Request (Create)
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Payment Request', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _reqPhoneCtrl, decoration: const InputDecoration(labelText: 'To phone (+963...)'))),
                const SizedBox(width: 8),
                IconButton(onPressed: _loading ? null : () => _pickContactInto(_reqPhoneCtrl), icon: const Icon(Icons.contacts_outlined))
              ]),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _reqAmountCtrl, decoration: const InputDecoration(labelText: 'Amount (SYP)'), keyboardType: TextInputType.number)),
                const SizedBox(width: 8),
                Expanded(child: TextField(controller: _reqExpiryCtrl, decoration: const InputDecoration(labelText: 'Expiry (min, optional)'), keyboardType: TextInputType.number)),
              ]),
              const SizedBox(height: 8),
              TextField(controller: _reqMetaCtrl, decoration: const InputDecoration(labelText: 'Note (optional)')),
              const SizedBox(height: 8),
              FilledButton(onPressed: _loading ? null : _createRequest, child: const Text('Create Request')),
            ]),
          ),
        ),

        const SizedBox(height: 16),
        // Split Bill
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Split Bill', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _splitTotalCtrl, decoration: const InputDecoration(labelText: 'Total (SYP)'), keyboardType: TextInputType.number)),
                const SizedBox(width: 8),
                Row(children: [ const Text('Equal'), Switch(value: _splitEqual, onChanged: (v) { setState(() => _splitEqual = v); }) ]),
              ]),
              const SizedBox(height: 8),
              const Text('Participants (phone numbers):'),
              const SizedBox(height: 6),
              ..._splitPhones.asMap().entries.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(children: [
                  Expanded(child: TextField(controller: e.value, decoration: InputDecoration(labelText: 'Phone #${e.key+1}'))),
                  const SizedBox(width: 8),
                  IconButton(onPressed: _loading ? null : () => _pickContactInto(e.value), icon: const Icon(Icons.contacts_outlined)),
                  IconButton(onPressed: () { setState(() { _splitPhones.removeAt(e.key); }); }, icon: const Icon(Icons.remove_circle_outline))
                ]),
              )),
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton.icon(onPressed: () { setState(() { _splitPhones.add(TextEditingController()); }); }, icon: const Icon(Icons.add), label: const Text('Add Participant')),
              ),
              const SizedBox(height: 8),
              FilledButton(onPressed: _loading ? null : _createSplitRequests, child: const Text('Create Split Requests')),
            ]),
          ),
        ),

        const SizedBox(height: 16),
        // QR Payments (only create dynamic / static)
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('QR Payments', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextField(controller: _qrAmountCtrl, decoration: const InputDecoration(labelText: 'Amount for dynamic QR (SYP)'), keyboardType: TextInputType.number),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: FilledButton(onPressed: _loading ? null : _createMerchantQr, child: const Text('Create Dynamic QR'))),
                const SizedBox(width: 8),
                Expanded(child: FilledButton.tonal(onPressed: _loading ? null : _createStaticQr, child: const Text('Create Static QR'))),
              ]),
              const SizedBox(height: 8),
              OutlinedButton.icon(onPressed: _loading ? null : _scanAndPay, icon: const Icon(Icons.qr_code_scanner), label: const Text('Scan & Pay')),
            ]),
          ),
        ),

        // Top-up voucher creation/printing is available in the Ops Admin app only

        // Webhooks section removed

        const SizedBox(height: 16),
        // Transactions
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                const Expanded(child: Text('Transactions', style: TextStyle(fontWeight: FontWeight.w600))),
                DropdownButton<String>(
                  value: _txFilter,
                  items: const [
                    DropdownMenuItem(value: 'all', child: Text('All')),
                    DropdownMenuItem(value: 'in', child: Text('Incoming')),
                    DropdownMenuItem(value: 'out', child: Text('Outgoing')),
                  ],
                  onChanged: (v) => setState(() => _txFilter = v ?? 'all'),
                ),
                const SizedBox(width: 8),
                FilledButton.tonal(onPressed: _loading ? null : _loadTransactions, child: const Text('Load')),
              ]),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: 100,
                    child: TextField(
                      decoration: const InputDecoration(labelText: 'Page'),
                      keyboardType: TextInputType.number,
                      controller: TextEditingController(text: _txPage.toString()),
                      onSubmitted: (v) {
                        final p = int.tryParse(v) ?? 1;
                        setState(() => _txPage = p.clamp(1, 100000));
                        _loadTransactions();
                      },
                    ),
                  ),
                  SizedBox(
                    width: 140,
                    child: TextField(
                      decoration: const InputDecoration(labelText: 'Page size'),
                      keyboardType: TextInputType.number,
                      controller: TextEditingController(text: _txPageSize.toString()),
                      onSubmitted: (v) {
                        final s = int.tryParse(v) ?? 50;
                        setState(() => _txPageSize = s.clamp(1, 500));
                        _loadTransactions();
                      },
                    ),
                  ),
                  OutlinedButton(
                    onPressed: _loading || _txPage <= 1
                        ? null
                        : () {
                            setState(() => _txPage -= 1);
                            _loadTransactions();
                          },
                    child: const Text('Prev'),
                  ),
                  OutlinedButton(
                    onPressed: _loading || (_txPage * _txPageSize >= _txTotal && _txTotal > 0)
                        ? null
                        : () {
                            setState(() => _txPage += 1);
                            _loadTransactions();
                          },
                    child: const Text('Next'),
                  ),
                  if (_txTotal > 0) Text('Total: $_txTotal'),
                ],
              ),
              const SizedBox(height: 8),
              if (_tx.isEmpty) const Text('No entries loaded.'),
              for (final e in _tx.take(50))
                ListTile(
                  dense: true,
                  title: Text(_fmtCents(e['amount_cents_signed'] as int?)),
                  subtitle: Text((e['created_at'] as String?) ?? ''),
                  trailing: Text((e['transfer_id'] as String?)?.substring(0, 8) ?? ''),
                ),
            ]),
          ),
        ),

        // Merchant Statement section removed on request

        const SizedBox(height: 16),
        // Payment Requests (Incoming/Outgoing)
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                const Expanded(child: Text('Payment Requests', style: TextStyle(fontWeight: FontWeight.w600))),
                FilledButton.tonal(onPressed: _loading ? null : _loadRequests, child: const Text('Load')),
              ]),
              const SizedBox(height: 8),
              const Text('Incoming (you pay):'),
              if (_reqIncoming.isEmpty) const Text('—'),
              for (final r in _reqIncoming.take(20))
                ListTile(
                  dense: true,
                  title: Text('${r['requester_phone']} ← ${_fmtCents(r['amount_cents'] as int?)}'),
                  subtitle: Text('id: ${r['id']}  •  status: ${r['status']}'),
                  trailing: Wrap(spacing: 8, children: [
                    FilledButton(onPressed: _loading ? null : () => _acceptRequest(r['id'] as String), child: const Text('Accept')),
                    OutlinedButton(onPressed: _loading ? null : () => _rejectRequest(r['id'] as String), child: const Text('Reject')),
                  ]),
                ),
              const Divider(height: 16),
              const Text('Outgoing (request others to pay you):'),
              if (_reqOutgoing.isEmpty) const Text('—'),
              for (final r in _reqOutgoing.take(20))
                ListTile(
                  dense: true,
                  title: Text('${r['target_phone']} → ${_fmtCents(r['amount_cents'] as int?)}'),
                  subtitle: Text('id: ${r['id']}  •  status: ${r['status']}'),
                  trailing: OutlinedButton(onPressed: _loading ? null : () => _cancelRequest(r['id'] as String), child: const Text('Cancel')),
                ),
            ]),
          ),
        ),
      ]),
    );
  }
}
// ignore_for_file: use_build_context_synchronously, unused_element, no_wildcard_variable_uses
