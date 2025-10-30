import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:shared_ui/toast.dart';
import 'package:shared_ui/message_host.dart';

import '../services.dart';
import 'package:shared_ui/glass.dart';

class TaxiHistoryScreen extends StatefulWidget {
  const TaxiHistoryScreen({super.key});
  @override
  State<TaxiHistoryScreen> createState() => _TaxiHistoryScreenState();
}

class _TaxiHistoryScreenState extends State<TaxiHistoryScreen> {
  final _tokens = MultiTokenStore();
  bool _loading = true;
  List<Map<String, dynamic>> _rides = [];
  String? _error;

  Future<Map<String, String>> _taxiHeaders() =>
      authHeaders('taxi', store: _tokens);

  Uri _taxiUri(String path, {Map<String, String>? query}) =>
      ServiceConfig.endpoint('taxi', path, query: query);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await http.get(_taxiUri('/rides'),
          headers: await _taxiHeaders());
      if (res.statusCode >= 400) {
        setState(() {
          _error = res.body;
        });
        return;
      }
      final js = jsonDecode(res.body) as Map<String, dynamic>;
      final list = (js['rides'] as List? ?? []).cast<Map<String, dynamic>>();
      setState(() {
        _rides = list;
      });
    } catch (e) {
      setState(() {
        _error = '$e';
      });
    } finally {
      setState(() {
        _loading = false;
      });
    }
  }

  String _fmtSyp(dynamic cents) {
    final c = (cents is int) ? cents : int.tryParse('$cents') ?? 0;
    return 'SYP ${c ~/ 100}';
  }

  String _fmtDt(dynamic iso) {
    try {
      if (iso == null) return '';
      final dt = (iso is DateTime) ? iso : DateTime.parse('$iso');
      return DateFormat('dd.MM.yyyy HH:mm').format(dt.toLocal());
    } catch (_) {
      return '';
    }
  }

  Color _statusColor(String s) {
    switch (s) {
      case 'completed':
        return Colors.green;
      case 'enroute':
        return Colors.blue;
      case 'accepted':
        return Colors.orange;
      case 'assigned':
        return Colors.teal;
      case 'requested':
        return Colors.grey;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Taxi — History')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : (_error != null)
                ? ListView(children: [
                    Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text('Error: $_error')),
                  ])
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: _rides.length,
                    itemBuilder: (_, i) {
                      final r = _rides[i];
                      final id = (r['id'] ?? '') as String;
                      final status = (r['status'] ?? '-') as String;
                      final fare =
                          r['final_fare_cents'] ?? r['quoted_fare_cents'];
                      final dist = (r['distance_km'] as num?)?.toDouble();
                      final when = r['completed_at'] ??
                          r['started_at'] ??
                          r['created_at'];
                      final dt = _fmtDt(when);
                      final ratingVal = (r['my_rating'] as num?)?.toInt();
                      final ratingComment =
                          (r['my_rating_comment'] ?? '').toString();
                      final details = <String>[];
                      if (dt.isNotEmpty) details.add(dt);
                      details.add(status);
                      if (fare != null) details.add(_fmtSyp(fare));
                      if (dist != null) {
                        details.add('${dist.toStringAsFixed(1)} km');
                      }
                      if (ratingVal != null) {
                        final stars =
                            List.generate(5, (i) => i < ratingVal ? '★' : '☆')
                                .join();
                        details.add('Bewertung: $stars');
                        if (ratingComment.isNotEmpty) {
                          details.add('Kommentar: $ratingComment');
                        }
                      }
                      final subtitle = details.join('\n');
                      return Glass(
                        padding: const EdgeInsets.symmetric(
                            vertical: 10, horizontal: 12),
                        child: ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          leading: CircleAvatar(
                              backgroundColor: _statusColor(status),
                              child: const Icon(Icons.local_taxi,
                                  color: Colors.white)),
                          title: Text('Ride $id',
                              maxLines: 1, overflow: TextOverflow.ellipsis),
                          subtitle: Text(subtitle),
                          trailing: status == 'completed'
                              ? TextButton(
                                  onPressed: () => _rateRide(id,
                                      initialRating: ratingVal,
                                      initialComment: ratingComment.isEmpty
                                          ? null
                                          : ratingComment),
                                  child: Text(ratingVal != null
                                      ? 'Bearbeiten'
                                      : 'Bewerten'),
                                )
                              : null,
                          onTap: () {},
                        ),
                      );
                    },
                  ),
      ),
    );
  }

  Future<void> _rateRide(String rideId,
      {int? initialRating, String? initialComment}) async {
    int rating = initialRating ?? 5;
    final ctrl = TextEditingController(text: initialComment ?? '');
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (ctx, setState) {
        return AlertDialog(
          title: Text(initialRating != null
              ? 'Bewertung bearbeiten'
              : 'Fahrt bewerten'),
          content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                    children: List.generate(5, (i) {
                  final idx = i + 1;
                  final on = idx <= rating;
                  return IconButton(
                      onPressed: () {
                        setState(() => rating = idx);
                      },
                      icon: Icon(on ? Icons.star : Icons.star_border));
                })),
                TextField(
                    controller: ctrl,
                    decoration: const InputDecoration(
                        labelText: 'Kommentar (optional)'),
                    maxLines: 3),
              ]),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Abbrechen')),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Speichern')),
          ],
        );
      }),
    );
    if (ok != true) return;
    try {
      final res = await http.post(_taxiUri('/rides/$rideId/rate'),
          headers: await _taxiHeaders(),
          body: jsonEncode({
            "rating": rating,
            "comment": ctrl.text.trim().isEmpty ? null : ctrl.text.trim()
          }));
      if (res.statusCode >= 400) throw Exception(res.body);
      if (!mounted) return;
      showToast(context, 'Danke für deine Bewertung');
    } catch (e) {
      if (!mounted) return;
      MessageHost.showErrorBanner(context, 'Bewertung fehlgeschlagen: $e');
    }
  }
}
