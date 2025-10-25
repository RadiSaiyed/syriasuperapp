import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services.dart';

class DoctorsScreen extends StatefulWidget {
  const DoctorsScreen({super.key});
  @override
  State<DoctorsScreen> createState() => _DoctorsScreenState();
}

class _DoctorsScreenState extends State<DoctorsScreen> {
  String _health = '?';
  bool _loading = false;
  Uri _doctorsUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('doctors', path, query: query);
  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final r = await http.get(_doctorsUri('/health'));
      final js = jsonDecode(r.body);
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      _toast('$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  void _toast(String m) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
        appBar: AppBar(title: const Text('Doctors')),
        body: Padding(
            padding: const EdgeInsets.all(16),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ElevatedButton(
                  onPressed: _loading ? null : _healthCheck,
                  child: const Text('Health')),
              const SizedBox(height: 8),
              Text('Status: $_health')
            ])));
  }
}
