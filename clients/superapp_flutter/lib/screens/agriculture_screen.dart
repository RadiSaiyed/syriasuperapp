import 'package:flutter/material.dart';
import 'package:shared_core/shared_core.dart';
import '../services.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';
import '../ui/errors.dart';

class AgricultureScreen extends StatefulWidget {
  const AgricultureScreen({super.key});
  @override
  State<AgricultureScreen> createState() => _AgricultureScreenState();
}

class _AgricultureScreenState extends State<AgricultureScreen>
    with SingleTickerProviderStateMixin {
  String _health = '?';
  // removed unused _loading field
  late TabController _tab;

  List<dynamic> _listings = [];
  List<dynamic> _jobs = [];
  List<dynamic> _myOrders = [];

  static const _service = 'agriculture';

  Future<bool> _ensureAuth() async {
    final authed = await hasTokenFor(_service);
    if (!authed && mounted) {
      MessageHost.showInfoBanner(context, 'Please log in');
    }
    return authed;
  }

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 3, vsync: this);
    _healthCheck();
    _loadMarket();
    _loadJobs();
  }

  Future<void> _healthCheck() async {
    try {
      final js = await serviceGetJson(
        _service,
        '/health',
        options: const RequestOptions(cacheTtl: Duration(minutes: 5), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      if (!mounted) return;
      setState(() => _health = 'error');
    }
  }

  Future<void> _loadMarket() async {
    try {
      final js = await serviceGetJson(
        _service,
        '/market/listings',
        options: const RequestOptions(cacheTtl: Duration(minutes: 10), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _listings = js['listings'] as List<dynamic>? ?? const []);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Failed to load listings');
    }
  }

  Future<void> _loadJobs() async {
    try {
      final js = await serviceGetJson(
        _service,
        '/jobs',
        options: const RequestOptions(cacheTtl: Duration(minutes: 10), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _jobs = js['jobs'] as List<dynamic>? ?? const []);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Failed to load jobs');
    }
  }

  Future<void> _loadMyOrders() async {
    try {
      final js = await serviceGetJson(
        _service,
        '/market/orders',
        options: const RequestOptions(expectValidationErrors: true),
      );
      if (!mounted) return;
      setState(() => _myOrders = js['orders'] as List<dynamic>? ?? const []);
    } on ApiError catch (e) {
      if (!mounted) return;
      if (e.kind == CoreErrorKind.unauthorized || e.kind == CoreErrorKind.forbidden) {
        MessageHost.showInfoBanner(context, 'Please log in');
        return;
      }
      presentError(context, e, message: 'Failed to load orders');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Failed to load orders');
    }
  }

  Future<void> _placeOrder(Map<String, dynamic> listing) async {
    final qtyCtrl = TextEditingController(text: '1');
    final qty = await showDialog<int>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Order quantity (kg)'),
        content: TextField(
          controller: qtyCtrl,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(hintText: 'z. B. 5'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
              onPressed: () {
                final v = int.tryParse(qtyCtrl.text.trim());
                if (v == null || v <= 0) return;
                Navigator.pop(context, v);
              },
              child: const Text('OK')),
        ],
      ),
    );
    if (qty == null) return;
    if (!await _ensureAuth()) return;
    try {
      final id = listing['id'];
      await servicePost(
        _service,
        '/market/listings/$id/order',
        body: {'qty_kg': qty},
        options: const RequestOptions(expectValidationErrors: true),
      );
      if (!mounted) return;
      _toast('Order created');
      await _loadMarket();
      await _loadMyOrders();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Order failed');
    }
  }

  Future<void> _applyJob(Map<String, dynamic> job) async {
    final msgCtrl = TextEditingController();
    final message = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Application (optional message)'),
        content: TextField(controller: msgCtrl, decoration: const InputDecoration(hintText: 'Message')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, msgCtrl.text), child: const Text('Send')),
        ],
      ),
    );
    if (message == null) return;
    if (!await _ensureAuth()) return;
    try {
      final id = job['id'];
      await servicePost(
        _service,
        '/jobs/$id/apply',
        body: {'message': message},
        options: const RequestOptions(expectValidationErrors: true),
      );
      if (!mounted) return;
      _toast('Application sent');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Application failed');
    }
  }

  // Per-app OTP login removed: use central login

  void _toast(String m) {
    if (!mounted) return;
    showToast(context, m);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Agriculture'),
        bottom: TabBar(
          controller: _tab,
          tabs: const [
            Tab(text: 'Markt'),
            Tab(text: 'Jobs'),
            Tab(text: 'Farmer'),
          ],
        ),
        actions: [
          Center(child: Text(_health, style: const TextStyle(fontSize: 12))),
          const SizedBox(width: 8),
        ],
      ),
      body: TabBarView(
        controller: _tab,
        children: [
          _buildMarket(),
          _buildJobs(),
          _buildFarmer(),
        ],
      ),
    );
  }

  Widget _buildMarket() {
    return RefreshIndicator(
      onRefresh: () async {
        await _loadMarket();
        await _loadMyOrders();
      },
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          const Text('Aktive Listings', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ..._listings.map((l) => Card(
                child: ListTile(
                  title: Text(l['produce_name']),
                  subtitle: Text('${l['category'] ?? ''}  •  ${l['quantity_kg']} kg  •  ${(l['price_per_kg_cents'] / 100).toStringAsFixed(2)}'),
                  trailing: ElevatedButton(
                      onPressed: () => _placeOrder(l), child: const Text('Bestellen')),
                ),
              )),
          const Divider(),
          const Text('My Orders', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ..._myOrders.map((o) => ListTile(
                title: Text('Order ${o['id']}'),
                subtitle: Text('Qty ${o['qty_kg']} • Total ${(o['total_cents'] / 100).toStringAsFixed(2)} • ${o['status']}'),
              )),
        ],
      ),
    );
  }

  Widget _buildJobs() {
    return RefreshIndicator(
      onRefresh: _loadJobs,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          const SizedBox(height: 8),
          ..._jobs.map((j) => Card(
                child: ListTile(
                  title: Text(j['title']),
                  subtitle: Text('${j['location'] ?? ''} • ${(j['wage_per_day_cents'] ?? 0) / 100}/Tag'),
                  trailing: ElevatedButton(
                      onPressed: () => _applyJob(j), child: const Text('Bewerben')),
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildFarmer() {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        const Text('Farmer‑Aktionen', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          ElevatedButton(onPressed: _seed, child: const Text('Seed Demo‑Daten')),
          ElevatedButton(onPressed: _createFarm, child: const Text('Farm anlegen')),
          ElevatedButton(onPressed: _createListing, child: const Text('Listing erstellen')),
          ElevatedButton(onPressed: _createJob, child: const Text('Job erstellen')),
          ElevatedButton(onPressed: _loadMyOrders, child: const Text('Farmer‑Bestellungen')),
        ]),
      ],
    );
  }

  Future<void> _createFarm() async {
    final nameCtrl = TextEditingController();
    final locCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final data = await showDialog<Map<String, String>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Farm anlegen'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
            TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Ort')),
            TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Beschreibung')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'name': nameCtrl.text,
            'location': locCtrl.text,
            'description': descCtrl.text,
          }), child: const Text('Anlegen')),
        ],
      ),
    );
    if (data == null) return;
    if (!await _ensureAuth()) return;
    try {
      await servicePost(
        _service,
        '/farmer/farm',
        body: data,
        options: const RequestOptions(expectValidationErrors: true),
      );
      if (!mounted) return;
      _toast('Farm erstellt');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Farm erstellen fehlgeschlagen');
    }
  }

  Future<void> _seed() async {
    try {
      await servicePost(_service, '/admin/seed');
      if (!mounted) return;
      _toast('Seed ok');
      await _loadMarket();
      await _loadJobs();
      await _loadMyOrders();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Seed fehlgeschlagen');
    }
  }

  Future<void> _createListing() async {
    final nameCtrl = TextEditingController();
    final catCtrl = TextEditingController();
    final qtyCtrl = TextEditingController(text: '10');
    final priceCtrl = TextEditingController(text: '1000');
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Listing erstellen'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Produkt')),
            TextField(controller: catCtrl, decoration: const InputDecoration(labelText: 'Kategorie')),
            TextField(controller: qtyCtrl, decoration: const InputDecoration(labelText: 'Quantity (kg)'), keyboardType: TextInputType.number),
            TextField(controller: priceCtrl, decoration: const InputDecoration(labelText: 'Price/kg (cents)'), keyboardType: TextInputType.number),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'produce_name': nameCtrl.text,
            'category': catCtrl.text,
            'quantity_kg': int.tryParse(qtyCtrl.text) ?? 0,
            'price_per_kg_cents': int.tryParse(priceCtrl.text) ?? 0,
          }), child: const Text('Create')),
        ],
      ),
    );
    if (data == null) return;
    if (!await _ensureAuth()) return;
    try {
      await servicePost(
        _service,
        '/farmer/listings',
        body: data,
        options: const RequestOptions(expectValidationErrors: true),
      );
      if (!mounted) return;
      _toast('Listing erstellt');
      await _loadMarket();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Listing erstellen fehlgeschlagen');
    }
  }

  Future<void> _createJob() async {
    final titleCtrl = TextEditingController();
    final locCtrl = TextEditingController();
    final wageCtrl = TextEditingController(text: '0');
    final startCtrl = TextEditingController();
    final endCtrl = TextEditingController();
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Job erstellen'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: titleCtrl, decoration: const InputDecoration(labelText: 'Titel')),
            TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Location (optional)')),
            TextField(controller: wageCtrl, decoration: const InputDecoration(labelText: 'Lohn/Tag (Cent)'), keyboardType: TextInputType.number),
            TextField(controller: startCtrl, decoration: const InputDecoration(labelText: 'Start (YYYY-MM-DD)')),
            TextField(controller: endCtrl, decoration: const InputDecoration(labelText: 'Ende (YYYY-MM-DD)')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, {
            'title': titleCtrl.text,
            'location': locCtrl.text,
            'wage_per_day_cents': int.tryParse(wageCtrl.text) ?? 0,
            'start_date': startCtrl.text,
            'end_date': endCtrl.text,
          }), child: const Text('Create')),
        ],
      ),
    );
    if (data == null) return;
    if (!await _ensureAuth()) return;
    try {
      await servicePost(
        _service,
        '/farmer/jobs',
        body: data,
        options: const RequestOptions(expectValidationErrors: true),
      );
      if (!mounted) return;
      _toast('Job erstellt');
      await _loadJobs();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Job erstellen fehlgeschlagen');
    }
  }
}
