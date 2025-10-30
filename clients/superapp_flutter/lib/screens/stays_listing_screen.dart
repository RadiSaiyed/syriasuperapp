import 'package:flutter/material.dart';
import 'package:shared_ui/glass.dart';
import '../apps/stays_api.dart';

class StaysListingScreen extends StatefulWidget {
  final String propertyId;
  const StaysListingScreen({super.key, required this.propertyId});
  @override
  State<StaysListingScreen> createState() => _StaysListingScreenState();
}

class _StaysListingScreenState extends State<StaysListingScreen> {
  final _api = StaysApi();
  bool _loading = true;
  Map<String, dynamic>? _prop;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final p = await _api.getProperty(widget.propertyId);
      if (!mounted) return;
      setState(() => _prop = p);
    } catch (_) {} finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _prop ?? const <String, dynamic>{};
    return Scaffold(
      appBar: AppBar(title: Text(p['name']?.toString() ?? 'Listing'), flexibleSpace: const Glass(padding: EdgeInsets.zero, blur: 24, opacity: 0.16, borderRadius: BorderRadius.zero)),
      body: _loading ? const Center(child: CircularProgressIndicator()) : ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text('City: ${p['city'] ?? '-'}  •  Type: ${p['type'] ?? '-'}'))),
          const SizedBox(height: 8),
          if (p['description'] != null) Glass(child: Padding(padding: const EdgeInsets.all(12), child: Text(p['description'].toString()))),
        ],
      ),
    );
  }
}

