import 'package:flutter/material.dart';
import '../api.dart';

class BillersScreen extends StatefulWidget {
  final ApiClient api;
  const BillersScreen({super.key, required this.api});
  @override
  State<BillersScreen> createState() => _BillersScreenState();
}

class _BillersScreenState extends State<BillersScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _billers = [];
  List<Map<String, dynamic>> _accounts = [];
  String? _category;

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final b = await widget.api.listBillers(category: _category);
      final a = await widget.api.listAccounts();
      setState(() { _billers = b; _accounts = a; });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _link(Map<String, dynamic> biller) async {
    final refCtrl = TextEditingController();
    final aliasCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('Link ${biller['name']}'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: refCtrl, decoration: const InputDecoration(labelText: 'Account ref (meter/phone)')),
          TextField(controller: aliasCtrl, decoration: const InputDecoration(labelText: 'Alias (optional)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Link')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _loading = true);
    try {
      await widget.api.linkAccount(billerId: biller['id'] as String, accountRef: refCtrl.text.trim(), alias: aliasCtrl.text.trim().isEmpty ? null : aliasCtrl.text.trim());
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Account linked')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Padding(
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
        child: Row(children: [
          const Text('Filter:'), const SizedBox(width: 8),
          DropdownButton<String>(
            value: _category,
            hint: const Text('All'),
            items: const [
              DropdownMenuItem(value: 'electricity', child: Text('electricity')),
              DropdownMenuItem(value: 'water', child: Text('water')),
              DropdownMenuItem(value: 'mobile', child: Text('mobile')),
            ],
            onChanged: (v) async { setState(()=>_category=v); await _load(); },
          ),
          const Spacer(),
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ]),
      ),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            children: [
              const ListTile(title: Text('Linked Accounts', style: TextStyle(fontWeight: FontWeight.bold))),
              ..._accounts.map((a) => ListTile(
                title: Text('${a['account_ref']}'),
                subtitle: Text('Biller: ${a['biller_id']}  •  Alias: ${a['alias'] ?? ''}'),
                trailing: Wrap(spacing: 8, children: [
                  IconButton(onPressed: _loading ? null : () async { final ctrl = TextEditingController(text: a['alias'] as String? ?? ''); final ok = await showDialog<bool>(context: context, builder: (_) => AlertDialog(title: const Text('Rename alias'), content: TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'Alias')), actions: [TextButton(onPressed: ()=>Navigator.pop(context,false), child: const Text('Cancel')), FilledButton(onPressed: ()=>Navigator.pop(context,true), child: const Text('Save'))])); if (ok==true) { setState(()=>_loading=true); try { await widget.api.updateAccountAlias(accountId: a['id'] as String, alias: ctrl.text.trim()); await _load(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(()=>_loading=false);} } }, icon: const Icon(Icons.edit)),
                  IconButton(onPressed: _loading ? null : () async { setState(()=>_loading=true); try { await widget.api.deleteAccount(a['id'] as String); await _load(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(()=>_loading=false);} }, icon: const Icon(Icons.delete_outline)),
                ]),
              )),
              const Divider(),
              const ListTile(title: Text('Billers', style: TextStyle(fontWeight: FontWeight.bold))),
              ..._billers.map((b) => ListTile(
                title: Text(b['name'] as String? ?? ''),
                subtitle: Text(b['category'] as String? ?? ''),
                trailing: FilledButton(onPressed: _loading ? null : () => _link(b), child: const Text('Link')),
              )),
            ],
          ),
        ),
      ),
    ]);
  }
}
