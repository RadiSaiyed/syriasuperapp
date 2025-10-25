import 'package:flutter/material.dart';
import '../api.dart';
import 'products_screen.dart';

class ShopsScreen extends StatefulWidget {
  final ApiClient api;
  const ShopsScreen({super.key, required this.api});
  @override
  State<ShopsScreen> createState() => _ShopsScreenState();
}

class _ShopsScreenState extends State<ShopsScreen> {
  bool _loading = false;
  List<Map<String, dynamic>> _shops = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final rows = await widget.api.listShops();
      setState(() => _shops = rows);
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
      Expanded(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            itemCount: _shops.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final s = _shops[i];
              return ListTile(
                title: Text(s['name'] as String? ?? ''),
                subtitle: Text(s['description'] as String? ?? ''),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => ProductsScreen(api: widget.api, shopId: s['id'] as String, shopName: s['name'] as String? ?? 'Shop')));
                },
              );
            },
          ),
        ),
      )
    ]);
  }
}

