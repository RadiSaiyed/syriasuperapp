import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
// Using Image.network to avoid extra iOS pods (offline‑friendly)

import '../api.dart';

class MenuScreen extends StatefulWidget {
  final ApiClient api;
  final Map<String, dynamic> restaurant;
  const MenuScreen({super.key, required this.api, required this.restaurant});

  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  late Future<List<Map<String, dynamic>>> _future = widget.api.listMenu(widget.restaurant['id'] as String);
  late Future<List<Map<String, dynamic>>> _imagesFuture = widget.api.listRestaurantImages(widget.restaurant['id'] as String);
  final NumberFormat _fmt = NumberFormat.currency(locale: 'de_DE', symbol: 'SYP', decimalDigits: 2);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.restaurant['name'] ?? 'Menu')),
      body: Column(children: [
        SizedBox(
          height: 140,
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: _imagesFuture,
            builder: (context, snap) {
              final imgs = snap.data ?? const [];
              if (imgs.isEmpty) return const SizedBox.shrink();
              return ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                scrollDirection: Axis.horizontal,
                itemCount: imgs.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (context, i) => ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.network(
                    imgs[i]['url'] ?? '',
                    height: 120,
                    width: 200,
                    fit: BoxFit.cover,
                    loadingBuilder: (ctx, child, prog) => prog == null ? child : Container(color: Colors.black12, width: 200, height: 120),
                    errorBuilder: (ctx, err, stack) => Container(color: Colors.black26, width: 200, height: 120, child: const Icon(Icons.broken_image_outlined)),
                  )
                ),
              );
            },
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: _future,
            builder: (context, snap) {
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              final items = snap.data!;
              if (items.isEmpty) return const Center(child: Text('No items'));
              return ListView.separated(
                itemCount: items.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, i) {
                  final m = items[i];
                  final price = _fmt.format(((m['price_cents'] ?? 0) as int) / 100.0);
                  return ListTile(
                    title: Text(m['name'] ?? ''),
                    subtitle: Text([m['description'] ?? '', price].where((x) => (x as String).isNotEmpty).join(' • ')),
                    trailing: FilledButton(
                      onPressed: () async {
                        try {
                          await widget.api.addCartItem(menuItemId: m['id'] as String, qty: 1);
                          if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Added to cart')));
                        } catch (e) {
                          if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                        }
                      },
                      child: const Text('Add'),
                    ),
                  );
                },
              );
            },
          ),
        ),
      ]),
    );
  }
}
