import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import '../api.dart';

class CarrierScreen extends StatefulWidget {
  final ApiClient api;
  const CarrierScreen({super.key, required this.api});
  @override
  State<CarrierScreen> createState() => _CarrierScreenState();
}

class _CarrierScreenState extends State<CarrierScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _available = [];
  Map<String, dynamic>? _current;
  String? _paymentId;
  final _latCtrl = TextEditingController(text: '33.5138');
  final _lonCtrl = TextEditingController(text: '36.2765');
  final _podCtrl = TextEditingController();

  Future<void> _apply() async {
    setState(() => _loading = true);
    try {
      await widget.api.carrierApply(companyName: 'Carrier Co');
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Carrier approved (dev)')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _loadAvailable() async {
    setState(() => _loading = true);
    try { final rows = await widget.api.availableLoads(); setState(() => _available = rows); } catch (_) {} finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _accept(String id) async { setState(() => _loading = true); try { final l = await widget.api.acceptLoad(id); setState(() => _current = l); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }
  Future<void> _pickup() async { if (_current==null) return; setState(() => _loading = true); try { final l = await widget.api.pickupLoad(_current!['id'] as String); setState(() => _current = l);} catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }
  Future<void> _inTransit() async { if (_current==null) return; setState(() => _loading = true); try { final l = await widget.api.inTransitLoad(_current!['id'] as String); setState(() => _current = l);} catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }
  Future<void> _deliver() async { if (_current==null) return; setState(() => _loading = true); try { final l = await widget.api.deliverLoad(_current!['id'] as String); setState(() { _current = l; _paymentId = l['payment_request_id'] as String?; }); if (_paymentId!=null) await _showPaymentCta(_paymentId!);} catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }

  Future<void> _updateLocation() async {
    final lat = double.tryParse(_latCtrl.text.trim());
    final lon = double.tryParse(_lonCtrl.text.trim());
    if (lat == null || lon == null) return;
    setState(() => _loading = true);
    try { await widget.api.updateCarrierLocation(lat: lat, lon: lon); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Location updated')));} catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);}  
  }

  Future<void> _addPod() async { if (_current==null) return; final url = _podCtrl.text.trim(); if (url.isEmpty) return; setState(()=>_loading=true); try { await widget.api.addPod(_current!['id'] as String, url); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('POD added')));} catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(()=>_loading=false);} }

  Future<void> _openChat() async {
    final id = _current?['id'] as String?; if (id == null) return;
    final msgCtrl = TextEditingController();
    List<Map<String, dynamic>> msgs = [];
    try { msgs = await widget.api.chatList(id); } catch (_) {}
    if (!mounted) return;
    await showModalBottomSheet(context: context, showDragHandle: true, isScrollControlled: true, builder: (ctx) {
      return StatefulBuilder(builder: (ctx, setS){
        Future<void> reload() async { try { final rows = await widget.api.chatList(id); setS(()=>msgs=rows);} catch(_){} }
        return Padding(padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom).add(const EdgeInsets.all(16)), child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Load chat', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          SizedBox(height: 220, child: ListView.separated(shrinkWrap: true, itemBuilder: (c,i){ final m=msgs[i]; return ListTile(title: Text(m['content']??''), subtitle: Text(m['from_user_id']??'')); }, separatorBuilder: (_, __)=>const Divider(height:1), itemCount: msgs.length)),
          Row(children: [ Expanded(child: TextField(controller: msgCtrl, decoration: const InputDecoration(hintText: 'Message'))), const SizedBox(width: 8), FilledButton(onPressed: () async { final t=msgCtrl.text.trim(); if (t.isEmpty) return; try { await widget.api.chatSend(id, t); msgCtrl.clear(); await reload(); } catch (e) { ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('$e')));} }, child: const Text('Send')) ])
        ]));
      });
    });
  }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      await Clipboard.setData(ClipboardData(text: requestId));
      if (mounted) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payments app not installed. Copied request ID.'))); }
    }
  }

  Future<void> _showPaymentCta(String requestId) async {
    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: const [Icon(Icons.local_shipping_outlined, size: 28), SizedBox(width: 8), Text('Load delivered', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))]),
          const SizedBox(height: 8),
          const Text('Open the Payments app to receive your payout.'),
          const SizedBox(height: 16),
          Row(children: [Expanded(child: FilledButton.icon(onPressed: () { Navigator.pop(ctx); _openPayment(requestId); }, icon: Icon(Icons.open_in_new), label: Text('Open in Payments')))]),
          const SizedBox(height: 8),
          TextButton.icon(onPressed: () async { await Clipboard.setData(ClipboardData(text: requestId)); if (!mounted) return; ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied payment request ID'))); }, icon: const Icon(Icons.copy_outlined), label: const Text('Copy request ID')),
        ]),
      ),
    );
  }

  @override
  void initState() { super.initState(); _loadAvailable(); }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (_loading) const LinearProgressIndicator(),
        Row(children: [
          FilledButton(onPressed: _loading ? null : _apply, child: const Text('Apply (dev)')),
          const SizedBox(width: 8),
          OutlinedButton(onPressed: _loading ? null : _loadAvailable, child: const Text('Refresh available')),
        ]),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: TextField(controller: _latCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Lat'))),
          const SizedBox(width: 8),
          Expanded(child: TextField(controller: _lonCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Lon'))),
          const SizedBox(width: 8),
          OutlinedButton(onPressed: _loading ? null : _updateLocation, child: const Text('Send loc')),
        ]),
        const SizedBox(height: 8),
        const Text('Available Loads', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        for (final l in _available)
          Card(child: ListTile(title: Text('${l['origin']} → ${l['destination']}'), subtitle: Text('Weight: ${l['weight_kg']} kg • Price: ${l['price_cents']} SYP'), trailing: FilledButton(onPressed: _loading ? null : () => _accept(l['id'] as String), child: const Text('Accept')))),
        const SizedBox(height: 12),
        const Divider(),
        const Text('Current Load', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        if (_current != null) ...[
          ListTile(title: Text('${_current!['origin']} → ${_current!['destination']}'), subtitle: Text('Status: ${_current!['status']} • Price: ${_current!['price_cents']} SYP')),
          Wrap(spacing: 8, children: [
            FilledButton(onPressed: _loading ? null : _pickup, child: const Text('Pickup')),
            FilledButton(onPressed: _loading ? null : _inTransit, child: const Text('In transit')),
            FilledButton(onPressed: _loading ? null : _deliver, child: const Text('Deliver')),
            OutlinedButton(onPressed: _loading ? null : _openChat, child: const Text('Chat')),
          ]),
          Row(children: [ Expanded(child: TextField(controller: _podCtrl, decoration: const InputDecoration(hintText: 'POD URL (optional)'))), const SizedBox(width: 8), OutlinedButton(onPressed: _loading ? null : _addPod, child: const Text('Save POD')) ]),
        ] else const Text('No current load'),
      ]),
    );
  }
}
