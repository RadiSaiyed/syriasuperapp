import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_core/shared_core.dart';
import '../services.dart';

class StaysFavoritesScreen extends StatefulWidget {
  const StaysFavoritesScreen({super.key});
  @override
  State<StaysFavoritesScreen> createState() => _StaysFavoritesScreenState();
}

class _StaysFavoritesScreenState extends State<StaysFavoritesScreen> {
  bool _loading = false;
  List<dynamic> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJsonList('superapp', '/v1/stays/favorites', options: const RequestOptions(cacheTtl: Duration(seconds: 30)));
      if (!mounted) return;
      setState(() => _items = js);
    } catch (_) {} finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Favorites'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: _loading ? const Center(child: CircularProgressIndicator()) : ListView.builder(
        itemCount: _items.length,
        itemBuilder: (_, i) {
          final it = _items[i] as Map<String, dynamic>? ?? const {};
          return GlassCard(child: ListTile(title: Text(it['name']?.toString() ?? 'Listing'), subtitle: Text('${it['city'] ?? '-'} • ${it['type'] ?? '-'}')));
        },
      ),
    );
  }
}

