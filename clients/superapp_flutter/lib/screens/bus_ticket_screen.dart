import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:qr_flutter/qr_flutter.dart';
import '../ui/glass.dart';
import '../services.dart';

class BusTicketScreen extends StatefulWidget {
  final String bookingId;
  final String? qrText;
  const BusTicketScreen({super.key, required this.bookingId, this.qrText});

  @override
  State<BusTicketScreen> createState() => _BusTicketScreenState();
}

class _BusTicketScreenState extends State<BusTicketScreen> {
  final _tokens = MultiTokenStore();
  String? _qr;
  bool _loading = false;

  Future<Map<String, String>> _authHeaders() =>
      authHeaders('bus', store: _tokens);

  Uri _busUri(String path) =>
      ServiceConfig.endpoint('bus', path);

  @override
  void initState() {
    super.initState();
    _qr = widget.qrText;
    if (_qr == null || _qr!.isEmpty) _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final r = await http.get(
        _busUri('/bookings/${widget.bookingId}/ticket'),
        headers: await _authHeaders(),
      );
      if (r.statusCode >= 400) throw Exception(r.body);
      final js = jsonDecode(r.body) as Map<String, dynamic>;
      setState(() => _qr = js['qr_text']?.toString());
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Ticket load failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ticket'),
        flexibleSpace: const Glass(
            padding: EdgeInsets.zero,
            blur: 24,
            opacity: 0.16,
            borderRadius: BorderRadius.zero),
      ),
      body: Center(
        child: _loading
            ? const CircularProgressIndicator()
            : (_qr == null || _qr!.isEmpty)
                ? const Text('Ticket unavailable')
                : Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: QrImageView(data: _qr!, size: 260, backgroundColor: Colors.white),
                      ),
                      const SizedBox(height: 12),
                      Text('Booking: ${widget.bookingId.substring(0, 8)}', style: const TextStyle(color: Colors.white70)),
                    ],
                  ),
      ),
    );
  }
}
