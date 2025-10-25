import 'dart:math';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
// Using Image.network to avoid extra iOS pods (offline‑friendly)
import '../api.dart';
import 'menu_screen.dart';

class HomeScreen extends StatefulWidget {
  final ApiClient api;
  const HomeScreen({super.key, required this.api});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _search = TextEditingController();
  String _city = '';
  String _q = '';
  late Future<List<Map<String, dynamic>>> _future = widget.api.listRestaurants();
  final List<String> _cities = const ['Damascus', 'Aleppo', 'Latakia'];
  final List<_Cuisine> _cuisines = const [
    _Cuisine('Pizza', Icons.local_pizza_outlined),
    _Cuisine('Burger', Icons.lunch_dining_outlined),
    _Cuisine('Sushi', Icons.rice_bowl_outlined),
    _Cuisine('Kebab', Icons.restaurant_outlined),
    _Cuisine('Shawarma', Icons.set_meal_outlined),
    _Cuisine('Desserts', Icons.icecream_outlined),
  ];
  final _fmt = NumberFormat.currency(locale: 'de_DE', symbol: 'SYP', decimalDigits: 2);

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() {
      _future = widget.api.listRestaurants(city: _city.isEmpty ? null : _city, q: _q.isEmpty ? null : _q);
    });
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          // Search + City picker
          Row(children: [
            Expanded(
              child: TextField(
                controller: _search,
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.search),
                  hintText: 'Search dishes, restaurants…',
                  filled: true,
                  fillColor: Theme.of(context).colorScheme.surface,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onSubmitted: (v) { setState(() { _q = v.trim(); }); _reload(); },
              ),
            ),
            const SizedBox(width: 8),
            DropdownButton<String>(
              value: _city.isEmpty ? null : _city,
              hint: const Text('City'),
              items: _cities.map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
              onChanged: (v) { setState(() { _city = v ?? ''; }); _reload(); },
            )
          ]),
          const SizedBox(height: 12),
  _Banners(),
          const SizedBox(height: 12),
          SizedBox(
            height: 44,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _cuisines.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (ctx, i) {
                final c = _cuisines[i];
                final selected = _q.toLowerCase() == c.name.toLowerCase();
                return ChoiceChip(
                  label: Text(c.name),
                  avatar: Icon(c.icon, size: 18),
                  selected: selected,
                  onSelected: (_) { setState(() { _q = c.name; _search.text = c.name; }); _reload(); },
                );
              },
            ),
          ),
          const SizedBox(height: 8),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _future,
            builder: (context, snap) {
              if (!snap.hasData) return const Padding(padding: EdgeInsets.only(top: 40), child: Center(child: CircularProgressIndicator()));
              final rs = snap.data!;
              if (rs.isEmpty) return const Padding(padding: EdgeInsets.only(top: 40), child: Center(child: Text('No restaurants')));
              return ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: rs.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, i) => _RestaurantCard(restaurant: rs[i], api: widget.api, onOpen: () async {
                  if (!context.mounted) return;
                  Navigator.push(context, MaterialPageRoute(builder: (_) => MenuScreen(api: widget.api, restaurant: rs[i])));
                }, fmt: _fmt),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _Cuisine {
  final String name; final IconData icon;
  const _Cuisine(this.name, this.icon);
}

class _Banners extends StatelessWidget {
  final List<String> _urls = const [
    'https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?w=1600',
    'https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=1600',
    'https://images.unsplash.com/photo-1550547660-d9450f859349?w=1600',
  ];
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 140,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _urls.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (ctx, i) => ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Image.network(_urls[i], width: 280, height: 140, fit: BoxFit.cover,
              loadingBuilder: (ctx, child, prog) => prog == null ? child : Container(color: Colors.black12, width: 280, height: 140)),
        ),
      ),
    );
  }
}

class _RestaurantCard extends StatefulWidget {
  final Map<String, dynamic> restaurant;
  final VoidCallback onOpen;
  final NumberFormat fmt;
  final ApiClient api;
  const _RestaurantCard({required this.restaurant, required this.onOpen, required this.fmt, required this.api});
  @override
  State<_RestaurantCard> createState() => _RestaurantCardState();
}

class _RestaurantCardState extends State<_RestaurantCard> {
  String get id => widget.restaurant['id'] as String? ?? '';
  String get name => widget.restaurant['name'] as String? ?? '';
  String get city => widget.restaurant['city'] as String? ?? '';
  double? get rating => (widget.restaurant['rating_avg'] as num?)?.toDouble();
  int get ratingCount => (widget.restaurant['rating_count'] as num?)?.toInt() ?? 0;
  String get desc => widget.restaurant['description'] as String? ?? '';

  // Consistent pseudo‑randoms for ETA/fee and tags, derived from id hash
  int get _seed => id.hashCode;
  String get eta => '${20 + (_seed % 15)}–${35 + (_seed % 20)} min';
  String get fee => (_seed % 3 == 0) ? 'Free delivery' : 'Fee ${(1000 + (_seed % 6) * 500)} SYP';
  List<String> get tags {
    const pool = ['Pizza', 'Grill', 'Shawarma', 'Sushi', 'Burger', 'Desserts', 'Seafood'];
    final r = Random(_seed);
    final t = <String>{};
    while (t.length < 2) { t.add(pool[r.nextInt(pool.length)]); }
    return t.toList();
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: widget.onOpen,
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _HeaderImage(restaurantId: id, api: widget.api),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600))),
                const Icon(Icons.timer_outlined, size: 16),
                const SizedBox(width: 4),
                Text(eta, style: TextStyle(color: Theme.of(context).hintColor)),
              ]),
              const SizedBox(height: 4),
              Wrap(spacing: 6, runSpacing: -8, children: [
                if (city.isNotEmpty) Chip(label: Text(city), visualDensity: VisualDensity.compact),
                Chip(avatar: const Icon(Icons.star, size: 16), label: Text(rating != null ? '${rating!.toStringAsFixed(1)} (${ratingCount})' : '- ($ratingCount)'), visualDensity: VisualDensity.compact),
                Chip(label: Text(tags.join(' • ')), visualDensity: VisualDensity.compact),
                Chip(label: Text(fee), visualDensity: VisualDensity.compact),
              ]),
              if (desc.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text(desc, maxLines: 2, overflow: TextOverflow.ellipsis)),
            ]),
          )
        ]),
      ),
    );
  }
}

class _HeaderImage extends StatefulWidget {
  final String restaurantId;
  final ApiClient api;
  const _HeaderImage({required this.restaurantId, required this.api});
  @override
  State<_HeaderImage> createState() => _HeaderImageState();
}

class _HeaderImageState extends State<_HeaderImage> {
  List<Map<String, dynamic>> _imgs = const [];
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await widget.api.listRestaurantImages(widget.restaurantId);
      if (!mounted) return;
      setState(() { _imgs = res; _loaded = true; });
    } catch (_) {
      if (mounted) setState(() { _loaded = true; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_imgs.isEmpty) {
      return Container(
        height: 140,
        color: Colors.black12,
        child: const Center(child: Icon(Icons.restaurant_outlined, size: 40)),
      );
    }
    final url = _imgs.first['url'] as String? ?? '';
    return Image.network(url, height: 140, width: double.infinity, fit: BoxFit.cover,
      loadingBuilder: (ctx, child, prog) => prog == null ? child : Container(color: Colors.black12, height: 140),
      errorBuilder: (ctx, err, st) => Container(color: Colors.black26, height: 140, child: const Center(child: Icon(Icons.broken_image_outlined))),
    );
  }
}
