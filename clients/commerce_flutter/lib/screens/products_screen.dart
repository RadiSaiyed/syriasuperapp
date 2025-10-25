import 'package:flutter/material.dart';
import '../api.dart';

class ProductsScreen extends StatefulWidget {
  final ApiClient api;
  final String shopId;
  final String shopName;
  const ProductsScreen({super.key, required this.api, required this.shopId, required this.shopName});
  @override
  State<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends State<ProductsScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];
  final _qCtrl = TextEditingController();
  String? _category;

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.listProducts(widget.shopId, q: _qCtrl.text.trim().isEmpty ? null : _qCtrl.text.trim(), category: _category);
      setState(() => _items = rows);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _add(String productId) async {
    setState(() => _loading = true);
    try {
      await widget.api.addCartItem(productId: productId, qty: 1);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Added to cart')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addFav(String productId) async {
    setState(() => _loading = true);
    try {
      await widget.api.wishlistAdd(productId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Added to wishlist')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openReviews(String productId) async {
    final items = await widget.api.reviewsGet(productId);
    final ratingCtrl = TextEditingController(text: '5');
    final commentCtrl = TextEditingController();
    if (!mounted) return;
    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (ctx) {
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom).add(const EdgeInsets.all(16)),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Reviews', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            SizedBox(
              height: 200,
              child: ListView.separated(
                shrinkWrap: true,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemCount: items.length,
                itemBuilder: (c, i) { final r = items[i]; return ListTile(title: Text('${r['rating']} ★'), subtitle: Text(r['comment'] ?? '')); },
              ),
            ),
            const Divider(),
            const Text('Add review (1..5)'),
            Row(children: [
              SizedBox(width: 80, child: TextField(controller: ratingCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(hintText: '5'))),
              const SizedBox(width: 8),
              Expanded(child: TextField(controller: commentCtrl, decoration: const InputDecoration(hintText: 'Comment'))),
              const SizedBox(width: 8),
              FilledButton(onPressed: () async { try { final r = int.tryParse(ratingCtrl.text.trim()) ?? 5; await widget.api.reviewsAdd(productId, rating: r, comment: commentCtrl.text.trim()); if (Navigator.canPop(ctx)) Navigator.pop(ctx); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Review submitted')));} catch (e) { ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('$e')));} }, child: const Text('Send')),
            ])
          ]),
        );
      }
    );
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.shopName)),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(children: [
            Expanded(child: TextField(controller: _qCtrl, decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search'))),
            const SizedBox(width: 8),
            DropdownButton<String>(value: _category, hint: const Text('Category'), items: const [
              DropdownMenuItem(value: 'grocery', child: Text('grocery')),
              DropdownMenuItem(value: 'home', child: Text('home')),
              DropdownMenuItem(value: 'fashion', child: Text('fashion')),
            ], onChanged: (v) { setState(()=>_category=v); _load(); }),
            const SizedBox(width: 8),
            OutlinedButton.icon(onPressed: _loading ? null : _load, icon: const Icon(Icons.filter_alt), label: const Text('Apply')),
          ]),
        ),
        if (_loading) const LinearProgressIndicator(),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              itemCount: _items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final p = _items[i];
                return ListTile(
                  title: Text(p['name'] as String? ?? ''),
                  subtitle: Text('${p['price_cents']} SYP\nStock: ${p['stock_qty']}${(p['avg_rating']!=null)?' • ${p['avg_rating'].toStringAsFixed(1)}★ (${p['ratings_count']??0})':''}'),
                  isThreeLine: true,
                  trailing: Wrap(spacing: 8, children: [
                    IconButton(onPressed: _loading ? null : () => _openReviews(p['id'] as String), icon: const Icon(Icons.reviews)),
                    IconButton(onPressed: _loading ? null : () => _addFav(p['id'] as String), icon: const Icon(Icons.favorite_border)),
                    FilledButton(onPressed: _loading ? null : () => _add(p['id'] as String), child: const Text('Add')),
                  ]),
                );
              },
            ),
          ),
        ),
      ]),
    );
  }
}
