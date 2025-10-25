import 'package:flutter/material.dart';

import '../api.dart';
import 'menu_screen.dart';

class RestaurantsScreen extends StatefulWidget {
  final ApiClient api;
  const RestaurantsScreen({super.key, required this.api});

  @override
  State<RestaurantsScreen> createState() => _RestaurantsScreenState();
}

class _RestaurantsScreenState extends State<RestaurantsScreen> {
  late Future<List<Map<String, dynamic>>> _future = widget.api.listRestaurants();
  List<Map<String, dynamic>> _favorites = const [];
  bool _favoritesFetched = false;
  bool _loading = false;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        setState(() => _future = widget.api.listRestaurants());
        await _loadFavorites();
      },
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final rs = snap.data!;
          if (rs.isEmpty) return const Center(child: Text('No restaurants'));
          return ListView.separated(
            itemCount: rs.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final r = rs[i];
              final city = (r['city'] as String?) ?? '';
              final ratingAvg = r['rating_avg'];
              final ratingCnt = r['rating_count'];
              return ListTile(
                title: Text(r['name'] ?? ''),
                subtitle: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                  if (city.isNotEmpty) Chip(label: Text(city)),
                  Chip(avatar: const Icon(Icons.star, size: 16), label: Text(ratingAvg != null ? '${(ratingAvg as num).toStringAsFixed(1)} (${ratingCnt ?? 0})' : '- (${ratingCnt ?? 0})')),
                ]),
                trailing: Wrap(spacing: 4, children: [
                  IconButton(tooltip: 'Menu', onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => MenuScreen(api: widget.api, restaurant: r))), icon: const Icon(Icons.restaurant_menu)),
                  IconButton(tooltip: 'Reviews', onPressed: () => _showReviews(r['id'] as String, r['name'] as String? ?? ''), icon: const Icon(Icons.reviews_outlined)),
                  IconButton(tooltip: 'Fav', onPressed: () => _favorite(r['id'] as String), icon: const Icon(Icons.favorite_border)),
                  IconButton(tooltip: 'Unfav', onPressed: () => _unfavorite(r['id'] as String), icon: const Icon(Icons.favorite_outline)),
                ]),
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => MenuScreen(api: widget.api, restaurant: r))),
              );
            },
          );
        },
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _loadFavorites();
  }

  Future<void> _loadFavorites() async {
    setState(() { _loading = true; });
    try {
      final favs = await widget.api.listFavorites();
      if (!mounted) return;
      setState(() { _favorites = favs; _favoritesFetched = true; });
    } catch (_) {} finally {
      if (mounted) setState(() { _loading = false; });
    }
  }

  Future<void> _favorite(String rid) async {
    try { await widget.api.favoriteRestaurant(rid); await _loadFavorites(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()))); }
  }
  Future<void> _unfavorite(String rid) async {
    try { await widget.api.unfavoriteRestaurant(rid); await _loadFavorites(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()))); }
  }

  Future<void> _showReviews(String rid, String name) async {
    try {
      final list = await widget.api.listReviews(rid);
      if (!mounted) return;
      await showModalBottomSheet(context: context, isScrollControlled: true, builder: (_) => DraggableScrollableSheet(initialChildSize: 0.6, expand: false, builder: (ctx, scroll) {
        return Scaffold(
          appBar: AppBar(title: Text('Reviews — $name')),
          body: ListView.builder(controller: scroll, itemCount: list.length, itemBuilder: (c, i) {
            final rv = list[i];
            return ListTile(leading: const Icon(Icons.star), title: Text('Rating: ${rv['rating']}'), subtitle: Text(rv['comment'] ?? ''));
          }),
          bottomNavigationBar: SafeArea(child: Padding(padding: const EdgeInsets.all(12), child: FilledButton.icon(onPressed: () => _addReviewDialog(rid), icon: const Icon(Icons.add_comment_outlined), label: const Text('Add review')))),
        );
      }));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _addReviewDialog(String rid) async {
    final ratingCtrl = TextEditingController(text: '5');
    final commentCtrl = TextEditingController();
    final ok = await showDialog<bool>(context: context, builder: (_) => AlertDialog(title: const Text('Add review'), content: Column(mainAxisSize: MainAxisSize.min, children: [
      TextField(controller: ratingCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Rating (1-5)')),
      TextField(controller: commentCtrl, decoration: const InputDecoration(labelText: 'Comment')),
    ]), actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save'))]));
    if (ok != true) return;
    final rating = int.tryParse(ratingCtrl.text) ?? 5;
    try { await widget.api.addReview(restaurantId: rid, rating: rating, comment: commentCtrl.text.trim()); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Review added'))); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()))); }
  }
}
