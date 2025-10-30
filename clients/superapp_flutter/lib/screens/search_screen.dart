import 'dart:async';
import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_core/shared_core.dart';
import '../services.dart';

class SearchScreen extends StatefulWidget {
  final String initialQuery;
  const SearchScreen({super.key, this.initialQuery = ''});
  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TextEditingController _ctrl = TextEditingController();
  Timer? _deb;
  bool _loading = false;
  List<Map<String, dynamic>> _items = const [];

  @override
  void initState() {
    super.initState();
    _ctrl.text = widget.initialQuery;
    if (_ctrl.text.trim().isNotEmpty) _search();
  }

  @override
  void dispose() {
    _deb?.cancel();
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final q = _ctrl.text.trim();
    if (q.isEmpty) {
      setState(() { _items = const []; _loading = false; });
      return;
    }
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson('superapp', '/v1/search', query: {'q': q}, options: const RequestOptions(idempotent: true));
      final list = (js['results'] as List?) ?? const [];
      setState(() { _items = list.cast<Map<String, dynamic>>(); });
    } catch (_) {} finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Search')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Glass(
            child: TextField(
              controller: _ctrl,
              decoration: InputDecoration(
                hintText: 'Search across the Super‑App…',
                suffixIcon: _loading ? const Padding(padding: EdgeInsets.all(10), child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))) : IconButton(icon: const Icon(Icons.search), onPressed: _search),
              ),
              onChanged: (_) { _deb?.cancel(); _deb = Timer(const Duration(milliseconds: 400), _search); },
              onSubmitted: (_) => _search(),
            ),
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: _items.length,
            itemBuilder: (_, i) {
              final it = _items[i];
              final service = (it['service'] ?? '').toString();
              final title = (it['title'] ?? '').toString();
              final kind = (it['kind'] ?? '').toString();
              return ListTile(
                leading: CircleAvatar(child: Text(service.isEmpty ? '?' : service.substring(0,1).toUpperCase())),
                title: Text(title),
                subtitle: Text(kind.isEmpty ? service : '$service • $kind'),
                onTap: () {},
              );
            },
          ),
        )
      ]),
    );
  }
}

