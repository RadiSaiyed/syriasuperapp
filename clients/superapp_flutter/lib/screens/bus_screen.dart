import 'package:flutter/material.dart';
import '../services.dart';
import 'package:shared_ui/glass.dart';
import 'bus_trip_screen.dart';
import 'bus_booking_detail_screen.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';
import 'package:shared_core/shared_core.dart';

import '../ui/errors.dart';

const List<String> _syrianProvinces = [
  'Damascus',
  'Aleppo',
  'Rif Dimashq',
  'Homs',
  'Hama',
  'Latakia',
  'Tartus',
  'Idlib',
  'Raqqa',
  'Deir ez-Zor',
  'Al-Hasakah',
  'Daraa',
  'As-Suwayda',
  'Quneitra',
];

class BusScreen extends StatefulWidget {
  const BusScreen({super.key});
  @override
  State<BusScreen> createState() => _BusScreenState();
}

class _BusScreenState extends State<BusScreen> {
  static const _service = 'bus';
  String _health = '?';
  bool _loading = false;
  // Search form
  String _origin = 'Damascus';
  String _destination = 'Aleppo';
  DateTime? _date = DateTime.now();
  final List<Map<String, dynamic>> _results = [];
  final _tokens = MultiTokenStore();
  bool _bookingsLoading = false;
  List<Map<String, dynamic>> _upcomingBookings = [];
  List<Map<String, dynamic>> _pastBookings = [];

  @override
  void initState() {
    super.initState();
    _loadBookings();
  }

  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson(
        _service,
        '/health',
        options: const RequestOptions(cacheTtl: Duration(minutes: 5), staleIfOffline: true),
      );
      if (!mounted) return;
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Health check failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: _date ?? now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 180)),
    );
    if (d != null) setState(() => _date = d);
  }

  Future<void> _search() async {
    final from = _origin.trim();
    final to = _destination.trim();
    if (from.isEmpty || to.isEmpty || _date == null) { MessageHost.showInfoBanner(context, 'Please select from, to and date'); return; }
    setState(() => _loading = true);
    try {
      final body = {
        'origin': from,
        'destination': to,
        'date': _date!.toIso8601String().substring(0, 10),
      };
      final js = await servicePostJson(
        _service,
        '/trips/search',
        body: body,
        options: const RequestOptions(expectValidationErrors: true),
      );
      final trips = (js['trips'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      if (!mounted) return;
      setState(() {
        _results
          ..clear()
          ..addAll(trips);
      });
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Search failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadBookings() async {
    setState(() => _bookingsLoading = true);
    try {
      final js = await serviceGetJson(
        _service,
        '/bookings',
        options: const RequestOptions(expectValidationErrors: true),
      );
      final rows = ((js['bookings'] as List?) ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final now = DateTime.now();
      final upcoming = <Map<String, dynamic>>[];
      final past = <Map<String, dynamic>>[];
      for (final row in rows) {
        final enriched = Map<String, dynamic>.from(row);
        DateTime? departAt;
        final departRaw = row['depart_at']?.toString();
        if (departRaw != null && departRaw.isNotEmpty) {
          try {
            departAt = DateTime.parse(departRaw).toLocal();
          } catch (_) {}
        }
        enriched['__departAt'] = departAt;
        final status = (row['status'] ?? '').toString().toLowerCase();
        final isPast = departAt != null
            ? departAt.isBefore(now)
            : status == 'completed' ||
                status == 'canceled' ||
                status == 'cancelled' ||
                status == 'expired';
        if (isPast) {
          past.add(enriched);
        } else {
          upcoming.add(enriched);
        }
      }
      int compare(Map<String, dynamic> a, Map<String, dynamic> b,
          {bool desc = false}) {
        final da = a['__departAt'] as DateTime?;
        final db = b['__departAt'] as DateTime?;
        if (da == null && db == null) return 0;
        if (da == null) return 1;
        if (db == null) return -1;
        return desc ? db.compareTo(da) : da.compareTo(db);
      }

      upcoming.sort((a, b) => compare(a, b));
      past.sort((a, b) => compare(a, b, desc: true));

      if (!mounted) return;
      setState(() {
        _upcomingBookings = upcoming;
        _pastBookings = past;
      });
    } on ApiError catch (error) {
      if (!mounted) return;
      if (error.kind == CoreErrorKind.unauthorized || error.kind == CoreErrorKind.forbidden) {
        MessageHost.showInfoBanner(context, 'Bitte im Profil anmelden, um Buchungen zu sehen.');
        setState(() {
          _upcomingBookings = [];
          _pastBookings = [];
        });
        return;
      }
      presentError(context, error, message: 'Bookings failed');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Bookings failed');
    } finally {
      if (mounted) {
        setState(() => _bookingsLoading = false);
      }
    }
  }

  // Per-app OTP login removed: use central login

  void _toast(String m) {
    if (!mounted) return;
    showToast(context, m);
  }

  @override
  Widget build(BuildContext context) {
    final dateLabel = _date != null
        ? '${_date!.year}-${_date!.month.toString().padLeft(2, '0')}-${_date!.day.toString().padLeft(2, '0')}'
        : 'Select date';

    String fmtTimeLocal(String? iso) {
      if (iso == null || iso.isEmpty) return '--:--';
      try {
        final dt = DateTime.parse(iso).toLocal();
        final hh = dt.hour.toString().padLeft(2, '0');
        final mm = dt.minute.toString().padLeft(2, '0');
        return '$hh:$mm';
      } catch (_) {
        return '--:--';
      }
    }

    String fmtDurationLocal(String? startIso, String? endIso) {
      if (startIso == null || endIso == null) return '';
      try {
        final a = DateTime.parse(startIso);
        final b = DateTime.parse(endIso);
        final mins = b.difference(a).inMinutes.abs();
        if (mins <= 59) {
          final mm = mins.toString().padLeft(2, '0');
          return '$mm:00';
        }
        final hh = (mins ~/ 60).toString().padLeft(2, '0');
        final mm = (mins % 60).toString().padLeft(2, '0');
        return '$hh:$mm';
      } catch (_) {
        return '';
      }
    }

    String fmtDateTimeLocal(String? iso) {
      if (iso == null || iso.isEmpty) return '--';
      try {
        final dt = DateTime.parse(iso).toLocal();
        final y = dt.year.toString().padLeft(4, '0');
        final m = dt.month.toString().padLeft(2, '0');
        final d = dt.day.toString().padLeft(2, '0');
        final h = dt.hour.toString().padLeft(2, '0');
        final min = dt.minute.toString().padLeft(2, '0');
        return '$y-$m-$d $h:$min';
      } catch (_) {
        return iso;
      }
    }

    Widget bookingTile(Map<String, dynamic> b) {
      final id = (b['id'] ?? '').toString();
      final operatorName = (b['operator_name'] ?? '').toString();
      final departLabel = fmtDateTimeLocal(b['depart_at']?.toString());
      final seats = b['seats_count'];
      final total = b['total_price_cents'];
      final status = (b['status'] ?? '').toString();
      final ratingVal = (b['my_rating'] as num?)?.toInt();
      final ratingComment = (b['my_rating_comment'] ?? '').toString();
      final lines = <String>[];
      if (operatorName.isNotEmpty) {
        lines.add(operatorName);
      }
      lines.add('Abfahrt: $departLabel');
      lines.add(
          'Plätze: ${seats ?? '--'} • Summe: ${total != null ? '$total SYP' : '--'}');
      lines.add('Status: ${status.isEmpty ? '—' : status}');
      if (ratingVal != null) {
        final stars = List.generate(5, (i) => i < ratingVal ? '★' : '☆').join();
        lines.add('Bewertung: $stars');
        if (ratingComment.isNotEmpty) {
          lines.add('"$ratingComment"');
        }
      } else {
        lines.add('Noch keine Bewertung – tippe zum Bewerten.');
      }

      return Card(
        margin: const EdgeInsets.only(top: 8),
        child: ListTile(
          leading: const Icon(Icons.confirmation_number_outlined),
          title: Text('${b['origin'] ?? '?'} → ${b['destination'] ?? '?'}'),
          subtitle: Text(lines.join('\n')),
          trailing: id.isEmpty
              ? null
              : (ratingVal != null
                  ? Text('$ratingVal★',
                      style: const TextStyle(fontWeight: FontWeight.w600))
                  : const Icon(Icons.chevron_right, size: 18)),
          onTap: id.isEmpty
              ? null
              : () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => BusBookingDetailScreen(bookingId: id)),
                  ).then((_) => _loadBookings());
                },
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
          title: const Text('Bus'),
          flexibleSpace: const Glass(
              padding: EdgeInsets.zero,
              blur: 24,
              opacity: 0.16,
              borderRadius: BorderRadius.zero)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        // Per-app login removed. Use central login from Profile/Payments.
        const SizedBox(height: 12),
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Search',
                      style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                        child: DropdownButtonFormField<String>(
                      initialValue: _origin,
                      decoration: const InputDecoration(labelText: 'From'),
                      items: _syrianProvinces
                          .map((p) => DropdownMenuItem<String>(
                              value: p, child: Text(p)))
                          .toList(),
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() => _origin = value);
                      },
                      isExpanded: true,
                    )),
                    const SizedBox(width: 8),
                    Expanded(
                        child: DropdownButtonFormField<String>(
                      initialValue: _destination,
                      decoration: const InputDecoration(labelText: 'To'),
                      items: _syrianProvinces
                          .map((p) => DropdownMenuItem<String>(
                              value: p, child: Text(p)))
                          .toList(),
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() => _destination = value);
                      },
                      isExpanded: true,
                    )),
                  ]),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                        child: OutlinedButton.icon(
                            onPressed: _pickDate,
                            icon: const Icon(Icons.event),
                            label: Text(dateLabel))),
                    const SizedBox(width: 8),
                    FilledButton.icon(
                        onPressed: _loading ? null : _search,
                        icon: const Icon(Icons.search),
                        label: const Text('Search')),
                  ]),
                ]),
          ),
        ),
        const SizedBox(height: 12),
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(children: [
                    const Expanded(
                        child: Text('Results',
                            style: TextStyle(fontWeight: FontWeight.w600))),
                    OutlinedButton.icon(
                        onPressed: _loading ? null : _healthCheck,
                        icon: const Icon(Icons.favorite),
                        label: const Text('Health')),
                  ]),
                  const SizedBox(height: 8),
                  Text('Status: $_health'),
                  const SizedBox(height: 8),
                  if (_results.isEmpty)
                    const Text('No results yet. Search above.')
                  else ...[
                    for (final r in _results)
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: ListTile(
                            leading: const Text('🚌',
                                style: TextStyle(fontSize: 22)),
                            title: Text('${r['origin']} → ${r['destination']}'),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Times + duration
                                Text(
                                    'Dep ${fmtTimeLocal(r['depart_at']?.toString())} • Arr ${fmtTimeLocal(r['arrive_at']?.toString())} • Dur ${fmtDurationLocal(r['depart_at']?.toString(), r['arrive_at']?.toString())}'),
                                // Operator
                                Text(
                                    '${r['operator_name']} • seats: ${r['seats_available']}'),
                                // Bus details if available
                                Text(
                                    'Bus: ${r['bus_model'] != null ? r['bus_model'].toString() : '—'}${r['bus_year'] != null ? ' (${r['bus_year']})' : ''}'),
                              ],
                            ),
                            trailing: Text('${r['price_cents']} SYP'),
                            onTap: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) =>
                                      BusTripScreen(tripId: r['id'] as String),
                                ),
                              );
                            },
                          ),
                        ),
                      )
                  ]
                ]),
          ),
        ),
        const SizedBox(height: 12),
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(children: [
                    const Expanded(
                        child: Text('Meine Reisen',
                            style: TextStyle(fontWeight: FontWeight.w600))),
                    OutlinedButton.icon(
                        onPressed: _bookingsLoading ? null : _loadBookings,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Aktualisieren')),
                  ]),
                  if (_bookingsLoading)
                    const Padding(
                        padding: EdgeInsets.symmetric(vertical: 8),
                        child: LinearProgressIndicator(minHeight: 2)),
                  if (!_bookingsLoading &&
                      _upcomingBookings.isEmpty &&
                      _pastBookings.isEmpty)
                    const Padding(
                        padding: EdgeInsets.only(top: 8),
                        child: Text('Noch keine Buchungen.')),
                  if (_upcomingBookings.isNotEmpty) ...[
                    const Padding(
                        padding: EdgeInsets.only(top: 12),
                        child: Text('Gebuchte Reisen',
                            style: TextStyle(fontWeight: FontWeight.w600))),
                    for (final b in _upcomingBookings) bookingTile(b),
                  ],
                  if (_pastBookings.isNotEmpty) ...[
                    const Padding(
                        padding: EdgeInsets.only(top: 12),
                        child: Text('Abgelaufene Reisen',
                            style: TextStyle(fontWeight: FontWeight.w600))),
                    for (final b in _pastBookings) bookingTile(b),
                  ],
                ]),
          ),
        ),
      ]),
    );
  }
}
