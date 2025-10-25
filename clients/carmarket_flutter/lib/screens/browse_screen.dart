import 'package:flutter/material.dart';
import '../api.dart';
import '../ui/glass.dart';

class BrowseScreen extends StatefulWidget {
  final ApiClient api;
  const BrowseScreen({super.key, required this.api});
  @override
  State<BrowseScreen> createState() => _BrowseScreenState();
}

class _BrowseScreenState extends State<BrowseScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];
  final Set<String> _fav = {};
  final _qCtrl = TextEditingController();
  final _makeCtrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  final _cityCtrl = TextEditingController();
  late int _yearStart;
  late int _yearEnd;
  late RangeValues _yearRange;
  RangeValues _priceRange = const RangeValues(0, 10000000); // in SYP (not cents)

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.browseListings();
      setState(() => _items = rows);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _offer(Map<String, dynamic> listing) async {
    final ctrl = TextEditingController(text: (listing['price_cents'] as int? ?? 0).toString());
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: Colors.white.withOpacity(0.14),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Offer for ${listing['title']}'),
        content: TextField(controller: ctrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Amount (SYP cents)')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Offer')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _loading = true);
    try {
      await widget.api.createOffer(listingId: listing['id'] as String, amountCents: int.tryParse(ctrl.text.trim()) ?? 0);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Offer submitted')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _chat(Map<String, dynamic> listing) async {
    final id = listing['id'] as String?; if (id == null) return;
    final msgCtrl = TextEditingController();
    List<Map<String, dynamic>> messages = [];
    try { messages = await widget.api.chatMessages(id); } catch (_) {}
    if (!mounted) return;
    await showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setS) {
          Future<void> reload() async { try { final rows = await widget.api.chatMessages(id); setS(() => messages = rows);} catch (_) {} }
          return Padding(
            padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom).add(const EdgeInsets.all(16)),
            child: Material(
              color: Colors.transparent,
              child: Glass(
                child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Chat • ${listing['title']}', style: const TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  SizedBox(height: 220, child: ListView.separated(shrinkWrap: true, itemBuilder: (c, i){ final m=messages[i]; return ListTile(title: Text(m['content']??''), subtitle: Text(m['from_user_id']??'')); }, separatorBuilder: (_, __)=>const Divider(height:1), itemCount: messages.length)),
                  Row(children: [
                    Expanded(child: TextField(controller: msgCtrl, decoration: const InputDecoration(hintText: 'Message'))),
                    const SizedBox(width: 8),
                    FilledButton(onPressed: () async { final txt = msgCtrl.text.trim(); if (txt.isEmpty) return; try { await widget.api.chatSend(id, txt); msgCtrl.clear(); await reload(); } catch (e) { ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('$e')));} }, child: const Text('Send')),
                  ])
                ]),
              ),
            ),
          );
        });
      }
    );
  }

  Future<void> _toggleFavorite(String id) async {
    setState(() => _loading = true);
    try {
      if (_fav.contains(id)) {
        await widget.api.removeFavorite(id);
        _fav.remove(id);
      } else {
        await widget.api.addFavorite(id);
        _fav.add(id);
      }
      setState(() {});
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _applyFilters() async {
    setState(() => _loading = true);
    try {
      final minPriceCents = (_priceRange.start.round()) * 100;
      final maxPriceCents = (_priceRange.end.round()) * 100;
      final rows = await widget.api.searchListings(
        q: _qCtrl.text.trim().isEmpty ? null : _qCtrl.text.trim(),
        make: _makeCtrl.text.trim().isEmpty ? null : _makeCtrl.text.trim(),
        model: _modelCtrl.text.trim().isEmpty ? null : _modelCtrl.text.trim(),
        city: _cityCtrl.text.trim().isEmpty ? null : _cityCtrl.text.trim(),
        yearMin: _yearRange.start.round(),
        yearMax: _yearRange.end.round(),
        minPrice: minPriceCents,
        maxPrice: maxPriceCents,
      );
      setState(() => _items = rows);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally { if (mounted) setState(() => _loading = false); }
  }

  @override
  void initState() {
    super.initState();
    _yearStart = 1980;
    _yearEnd = DateTime.now().year;
    _yearRange = RangeValues(_yearStart.toDouble(), _yearEnd.toDouble());
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Padding(
        padding: const EdgeInsets.all(12),
        child: Glass(child: Column(children: [
          Row(children: [
            Expanded(child: TextField(controller: _qCtrl, decoration: const InputDecoration(labelText: 'Search (title/make/model/city)'))),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _makeCtrl, decoration: const InputDecoration(labelText: 'Make'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _modelCtrl, decoration: const InputDecoration(labelText: 'Model'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _cityCtrl, decoration: const InputDecoration(labelText: 'City'))),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            const Text('Year:'),
            Expanded(
              child: RangeSlider(
                min: _yearStart.toDouble(),
                max: _yearEnd.toDouble(),
                divisions: (_yearEnd - _yearStart),
                values: _yearRange,
                labels: RangeLabels(_yearRange.start.round().toString(), _yearRange.end.round().toString()),
                onChanged: (v) => setState(() => _yearRange = v),
              ),
            ),
          ]),
          Row(children: [
            const Text('Price (SYP):'),
            Expanded(
              child: RangeSlider(
                min: 0,
                max: 10000000,
                divisions: 100,
                values: _priceRange,
                labels: RangeLabels(_priceRange.start.round().toString(), _priceRange.end.round().toString()),
                onChanged: (v) => setState(() => _priceRange = v),
              ),
            ),
          ]),
          Row(children: [
            OutlinedButton(onPressed: _loading ? null : _load, child: const Text('Clear')),
            const SizedBox(width: 8),
            FilledButton(onPressed: _loading ? null : _applyFilters, child: const Text('Apply')),
          ]),
        ])),
      ),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.builder(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: _items.length,
            itemBuilder: (context, i) {
              final l = _items[i];
              final id = l['id'] as String? ?? '';
              final isFav = _fav.contains(id);
              return GlassCard(
                child: ListTile(
                  title: Text(l['title'] as String? ?? ''),
                  subtitle: Text('Make: ${l['make'] ?? ''} • Model: ${l['model'] ?? ''} • Year: ${l['year'] ?? ''}\nPrice: ${l['price_cents']} SYP'),
                  isThreeLine: true,
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: _loading ? null : () => _toggleFavorite(id), icon: Icon(isFav ? Icons.favorite : Icons.favorite_border, color: isFav ? Colors.red : null)),
                    IconButton(onPressed: _loading ? null : () => _chat(l), icon: const Icon(Icons.chat_bubble_outline)),
                    FilledButton(onPressed: _loading ? null : () => _offer(l), child: const Text('Offer')),
                  ]),
                ),
              );
            },
          ),
        ),
      ),
    ]);
  }
}
