import 'package:flutter/material.dart';
import '../api.dart';
import '../ui/glass.dart';

class FavoritesScreen extends StatefulWidget {
  final ApiClient api;
  const FavoritesScreen({super.key, required this.api});
  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try { final rows = await widget.api.listFavorites(); setState(() => _items = rows); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }

  Future<void> _remove(String id) async { setState(() => _loading = true); try { await widget.api.removeFavorite(id); await _load(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if (mounted) setState(() => _loading = false);} }

  @override
  void initState() { super.initState(); _load(); }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      if (_loading) const LinearProgressIndicator(),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.builder(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: _items.length,
            itemBuilder: (context, i) {
              final l = _items[i];
              return GlassCard(
                child: ListTile(
                  title: Text(l['title'] as String? ?? ''),
                  subtitle: Text('Make: ${l['make'] ?? ''} • Model: ${l['model'] ?? ''} • Year: ${l['year'] ?? ''}\nPrice: ${l['price_cents']} SYP'),
                  isThreeLine: true,
                  trailing: IconButton(onPressed: _loading ? null : () => _remove(l['id'] as String), icon: const Icon(Icons.favorite, color: Colors.red)),
                ),
              );
            },
          ),
        ),
      ),
    ]);
  }
}
