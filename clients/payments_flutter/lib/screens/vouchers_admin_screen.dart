import 'package:flutter/material.dart';
import '../api.dart';

class VouchersAdminScreen extends StatefulWidget {
  final ApiClient api;
  const VouchersAdminScreen({super.key, required this.api});
  @override
  State<VouchersAdminScreen> createState() => _VouchersAdminScreenState();
}

class _VouchersAdminScreenState extends State<VouchersAdminScreen> {
  final _adminCtrl = TextEditingController();
  final _amountCtrl = TextEditingController(text: '100');
  final _countCtrl = TextEditingController(text: '10');
  final _prefixCtrl = TextEditingController();
  final _status = ValueNotifier<String>('');
  final _prefixFilterCtrl = TextEditingController();
  bool _loading = false;
  Map<String, dynamic>? _summary;
  List<Map<String, dynamic>> _items = [];
  List<Map<String, dynamic>> _fees = [];
  final _exportStatus = ValueNotifier<String>('');
  final _exportPrefixCtrl = TextEditingController();

  Future<void> _loadAdminToken() async {
    final t = await widget.api.getAdminToken();
    _adminCtrl.text = t ?? '';
  }

  Future<void> _saveAdmin() async {
    await widget.api.setAdminToken(_adminCtrl.text.trim());
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Admin token saved')));
  }

  Future<void> _refreshSummaryAndList() async {
    setState(() => _loading = true);
    try {
      final s = await widget.api.adminVouchersSummary(createdByMe: true);
      final items = await widget.api.adminVouchersList(status: _status.value.isEmpty ? null : _status.value, prefix: _prefixFilterCtrl.text.trim(), createdByMe: true);
      setState(() { _summary = s; _items = items; });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadFees() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.adminFeesEntries(limit: 200);
      setState(() => _fees = rows);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _copyCsv() async {
    setState(() => _loading = true);
    try {
      final csv = await widget.api.adminVouchersExport(status: _exportStatus.value.isEmpty ? null : _exportStatus.value, prefix: _exportPrefixCtrl.text.trim(), createdByMe: true);
      // Show in dialog for copy
      if (!mounted) return;
      await showDialog(context: context, builder: (_) => AlertDialog(
        title: const Text('CSV (copy)'),
        content: SizedBox(width: 600, child: SingleChildScrollView(child: SelectableText(csv))),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
      ));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _bulkCreate() async {
    final amt = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    final cnt = int.tryParse(_countCtrl.text.trim()) ?? 0;
    if (amt <= 0 || cnt <= 0) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Invalid amount or count')));
      return;
    }
    setState(() => _loading = true);
    try {
      final created = await widget.api.adminVouchersBulk(amountSyp: amt, count: cnt, prefix: _prefixCtrl.text.trim().isEmpty ? null : _prefixCtrl.text.trim());
      await _refreshSummaryAndList();
      if (!mounted) return;
      await showDialog(context: context, builder: (_) => AlertDialog(
        title: const Text('Created Vouchers'),
        content: SizedBox(
          width: 480,
          child: SingleChildScrollView(child: SelectableText(created.map((v) => '${v['code']},${v['amount_syp'] ?? ((v['amount_cents']??0)/100).round()},${v['qr_text'] ?? ''}').join('\n'))),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
      ));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _revoke(String code) async {
    setState(() => _loading = true);
    try {
      await widget.api.adminVoucherRevoke(code);
      await _refreshSummaryAndList();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _loadAdminToken();
    _refreshSummaryAndList();
  }

  @override
  Widget build(BuildContext context) {
    final s = _summary;
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Expanded(child: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Admin — Vouchers', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Admin Token'),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _adminCtrl, decoration: const InputDecoration(labelText: 'X-Admin-Token'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _saveAdmin, child: const Text('Save')),
          ])
        ]))),
        const SizedBox(height: 12),
        if (s != null) Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Summary (mine)'),
          const SizedBox(height: 8),
          Wrap(spacing: 24, runSpacing: 8, children: [
            Text('Total: ${s['total_count']}'),
            Text('Active: ${s['active_count']}'),
            Text('Redeemed: ${s['redeemed_count']}'),
            Text('Revoked: ${s['revoked_count']}'),
            Text('Sum SYP: ${s['total_syp']}'),
            Text('Redeemed SYP: ${s['redeemed_total_syp']}'),
            Text('Fees SYP: ${s['fees_syp']}'),
            Text('Net SYP: ${s['net_syp']}'),
          ])
        ]))),
        const SizedBox(height: 12),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Bulk Create'),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (SYP)'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _countCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Count (1..1000)'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _prefixCtrl, decoration: const InputDecoration(labelText: 'Prefix (optional)'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _bulkCreate, child: const Text('Create')),
          ])
        ]))),
        const SizedBox(height: 12),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Vouchers (mine)'),
          const SizedBox(height: 8),
          Row(children: [
            DropdownMenu<String>(label: const Text('Status'), initialSelection: _status.value, dropdownMenuEntries: const [
              DropdownMenuEntry(value: '', label: 'All'),
              DropdownMenuEntry(value: 'active', label: 'Active'),
              DropdownMenuEntry(value: 'redeemed', label: 'Redeemed'),
              DropdownMenuEntry(value: 'revoked', label: 'Revoked'),
            ], onSelected: (v) { _status.value = v ?? ''; _refreshSummaryAndList(); }),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _prefixFilterCtrl, decoration: const InputDecoration(labelText: 'Prefix filter'))),
            const SizedBox(width: 8),
            OutlinedButton(onPressed: _refreshSummaryAndList, child: const Text('Refresh')),
          ]),
          const SizedBox(height: 12),
          SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(columns: const [
            DataColumn(label: Text('Code')),
            DataColumn(label: Text('Amount (SYP')),
            DataColumn(label: Text('Status')),
            DataColumn(label: Text('Created')),
            DataColumn(label: Text('Redeemed')),
            DataColumn(label: Text('Redeemer')),
            DataColumn(label: Text('Actions')),
          ], rows: [
            for (final v in _items) DataRow(cells: [
              DataCell(SelectableText('${v['code']}')),
              DataCell(Text('${v['amount_syp']}')),
              DataCell(Text('${v['status']}')),
              DataCell(Text('${v['created_at'] ?? ''}')),
              DataCell(Text('${v['redeemed_at'] ?? ''}')),
              DataCell(Text('${v['redeemed_by_phone'] ?? ''}')),
              DataCell(Row(children: [
                if (v['status'] == 'active') OutlinedButton(onPressed: () => _revoke(v['code'] as String), child: const Text('Revoke')),
              ])),
            ])
          ]))
        ]))),
        const SizedBox(height: 12),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Export CSV (mine)'),
          const SizedBox(height: 8),
          Row(children: [
            DropdownMenu<String>(label: const Text('Status'), initialSelection: _exportStatus.value, dropdownMenuEntries: const [
              DropdownMenuEntry(value: '', label: 'All'),
              DropdownMenuEntry(value: 'active', label: 'Active'),
              DropdownMenuEntry(value: 'redeemed', label: 'Redeemed'),
              DropdownMenuEntry(value: 'revoked', label: 'Revoked'),
            ], onSelected: (v) { _exportStatus.value = v ?? ''; }),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _exportPrefixCtrl, decoration: const InputDecoration(labelText: 'Prefix filter'))),
            const SizedBox(width: 8),
            FilledButton(onPressed: _copyCsv, child: const Text('Copy CSV')),
          ])
        ]))),
        const SizedBox(height: 12),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Fee Entries (1% from voucher redeems)'),
          const SizedBox(height: 8),
          Row(children: [
            OutlinedButton(onPressed: _loadFees, child: const Text('Refresh')),
          ]),
          const SizedBox(height: 12),
          SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(columns: const [
            DataColumn(label: Text('Created')),
            DataColumn(label: Text('Code')),
            DataColumn(label: Text('Amount (SYP)')),
            DataColumn(label: Text('Transfer ID')),
          ], rows: [
            for (final f in _fees) DataRow(cells: [
              DataCell(Text('${f['created_at'] ?? ''}')),
              DataCell(SelectableText('${f['code'] ?? ''}')),
              DataCell(Text('${f['amount_syp'] ?? ''}')),
              DataCell(SelectableText('${f['transfer_id'] ?? ''}')),
            ])
          ]))
        ]))),
      ]))
    ]);
  }
}
