import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:crypto/crypto.dart' as crypto;
import 'api.dart';
import 'kiosk_beep_stub.dart' if (dart.library.html) 'kiosk_beep_web.dart';
import 'print_helper_stub.dart' if (dart.library.html) 'print_helper_web.dart';
import 'web_download_stub.dart' if (dart.library.html) 'web_download_web.dart';

void main() {
  runApp(const OperatorPortalApp());
}

class OperatorPortalApp extends StatelessWidget {
  const OperatorPortalApp({super.key});
  @override
  Widget build(BuildContext context) {
    final theme = ThemeData(
      useMaterial3: true,
      colorSchemeSeed: const Color(0xFF0A84FF),
    );
    return MaterialApp(
      title: 'Bus Operator Portal',
      theme: theme,
      home: const _Root(),
    );
}

}

class _Root extends StatefulWidget {
  const _Root();
  @override
  State<_Root> createState() => _RootState();
}

class _RootState extends State<_Root> {
  Api? _api;
  @override
  void initState() {
    super.initState();
    Api.load().then((a) async {
      // If a JWT is already stored (dev flow), skip login and go to Home
      try {
        final prefs = await SharedPreferences.getInstance();
        final jwt = prefs.getString('jwt');
        if (mounted && jwt != null && jwt.isNotEmpty) {
          setState(() => _api = a);
          // Navigate after first frame to avoid build context issues
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => HomeScreen(api: a)),
              );
            }
          });
          return;
        }
      } catch (_) {}
      if (mounted) setState(() => _api = a);
    });
  }
  @override
  Widget build(BuildContext context) {
    if (_api == null) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return LoginScreen(api: _api!);
  }
}

class LoginScreen extends StatefulWidget {
  final Api api;
  const LoginScreen({super.key, required this.api});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phone = TextEditingController(text: '+963900000001');
  final _otp = TextEditingController();
  bool _sent = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Operator Portal Login'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () async {
              final url = await showDialog<String>(
                context: context,
                builder: (_) => _BaseUrlDialog(current: widget.api.baseUrl),
              );
              if (url != null) {
                await widget.api.setBaseUrl(url);
                setState(() {});
              }
            },
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(controller: _phone, decoration: const InputDecoration(labelText: 'Phone (+963...)')),
                const SizedBox(height: 8),
                if (_sent)
                  TextField(controller: _otp, decoration: const InputDecoration(labelText: 'OTP (dev: 123456)')),
                const SizedBox(height: 12),
                if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
                const SizedBox(height: 12),
                Row(children: [
                  ElevatedButton(
                    onPressed: () async {
                      try {
                        await widget.api.requestOtp(_phone.text.trim());
                        setState(() { _sent = true; _error = null; });
                      } catch (e) { setState(() => _error = '$e'); }
                    },
                    child: const Text('Send OTP'),
                  ),
                  const SizedBox(width: 12),
                  if (_sent)
                    ElevatedButton(
                      onPressed: () async {
                        try {
                          await widget.api.verifyOtp(_phone.text.trim(), _otp.text.trim(), name: 'Operator');
                          if (!context.mounted) return;
                          Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => HomeScreen(api: widget.api)));
                        } catch (e) { setState(() => _error = '$e'); }
                      },
                      child: const Text('Login'),
                    ),
                ]),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class HomeScreen extends StatefulWidget {
  final Api api;
  const HomeScreen({super.key, required this.api});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<Map<String, dynamic>> _ops = [];
  Map<String, dynamic>? _op;
  int _tab = 0;
  @override
  void initState() {
    super.initState();
    _load();
  }
  Future<void> _load() async {
    final ops = await widget.api.myOperators();
    final prefs = await SharedPreferences.getInstance();
    final savedId = prefs.getString('selected_operator_id');
    Map<String, dynamic>? sel;
    if (savedId != null) {
      for (final m in ops) { if (m['operator_id'] == savedId) { sel = m; break; } }
    }
    setState(() { _ops = ops; _op = sel ?? (ops.isNotEmpty ? ops.first : null); });
  }

  @override
  Widget build(BuildContext context) {
    final op = _op;
    return Scaffold(
      appBar: AppBar(
        title: Text('Operator: ${op?['operator_name'] ?? '—'}'),
        actions: [
          if (_ops.length > 1)
            Padding(
              padding: const EdgeInsets.only(right: 8.0),
              child: DropdownButton<String>(
                value: (op?['operator_id'] as String?),
                underline: const SizedBox.shrink(),
                items: _ops.map<DropdownMenuItem<String>>((m) => DropdownMenuItem<String>(value: m['operator_id'] as String, child: Text(m['operator_name'] as String))).toList(),
                onChanged: (id) async {
                  if (id == null) return;
                  final sel = _ops.firstWhere((e) => e['operator_id'] == id);
                  setState(() { _op = sel; });
                  final prefs = await SharedPreferences.getInstance();
                  await prefs.setString('selected_operator_id', id);
                },
              ),
            ),
          if (op != null)
            Padding(
              padding: const EdgeInsets.only(right: 8.0),
              child: Chip(
                label: Text(((op?['role'] ?? '') as String).toUpperCase()),
                backgroundColor: ((op?['role'] ?? '') == 'admin') ? Colors.orange.shade200 : Colors.blue.shade200,
              ),
            ),
        ],
      ),
      body: op == null ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Text('No operator membership found.'),
        const SizedBox(height: 8),
        FilledButton(onPressed: () async {
          String name = 'Demo Operator';
          final ok = await showDialog<bool>(context: context, builder: (_) {
            final c = TextEditingController(text: name);
            final m = TextEditingController();
            return AlertDialog(
              title: const Text('Create Operator (DEV)'),
              content: SizedBox(width: 420, child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextField(controller: c, decoration: const InputDecoration(labelText: 'Name')),
                TextField(controller: m, decoration: const InputDecoration(labelText: 'Merchant Phone (optional)')),
              ])),
              actions: [
                TextButton(onPressed: ()=>Navigator.pop(context, false), child: const Text('Cancel')),
                FilledButton(onPressed: (){ name = c.text.trim(); Navigator.pop(context, true); }, child: const Text('Create')),
              ],
            );
          });
          if (ok == true) {
            try {
              await widget.api.registerOperator(name);
              await _load();
            } catch (e) {
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create failed: $e')));
            }
          }
        }, child: const Text('Create Operator')),
      ])) :
        IndexedStack(index: _tab, children: [
          TripsTab(api: widget.api, operatorId: op['operator_id']),
          BookingsTab(api: widget.api, operatorId: op['operator_id']),
          SummaryTab(api: widget.api, operatorId: op['operator_id']),
          TicketsTab(api: widget.api, operatorId: op['operator_id']),
          MembersTab(api: widget.api, operatorId: op['operator_id']),
          PromosTab(api: widget.api, operatorId: op['operator_id']),
          VehiclesTab(api: widget.api, operatorId: op['operator_id']),
          BranchesTab(api: widget.api, operatorId: op['operator_id']),
          AnalyticsTab(api: widget.api, operatorId: op['operator_id']),
          SettlementTab(api: widget.api, operatorId: op['operator_id']),
          WebhooksTab(api: widget.api, operatorId: op['operator_id']),
        ]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.event_seat_outlined), label: 'Trips'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label: 'Bookings'),
          NavigationDestination(icon: Icon(Icons.query_stats_outlined), label: 'Summary'),
          NavigationDestination(icon: Icon(Icons.qr_code_scanner), label: 'Tickets'),
          NavigationDestination(icon: Icon(Icons.group_outlined), label: 'Members'),
          NavigationDestination(icon: Icon(Icons.percent_outlined), label: 'Promos'),
          NavigationDestination(icon: Icon(Icons.directions_bus_outlined), label: 'Vehicles'),
          NavigationDestination(icon: Icon(Icons.store_outlined), label: 'Branches'),
          NavigationDestination(icon: Icon(Icons.bar_chart_outlined), label: 'Analytics'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label: 'Settlement'),
          NavigationDestination(icon: Icon(Icons.cloud_sync_outlined), label: 'Webhooks'),
        ],
      ),
    );
  }
}

class TripsTab extends StatefulWidget {
  final Api api; final String operatorId;
  const TripsTab({super.key, required this.api, required this.operatorId});
  @override
  State<TripsTab> createState() => _TripsTabState();
}
class _TripsTabState extends State<TripsTab> {
  List<Map<String, dynamic>> _trips = [];
  List<Map<String, dynamic>> _vehicles = [];
  String? _vehicleId;
  final _form = GlobalKey<FormState>();
  final _origin = TextEditingController(text: 'Damascus');
  final _destination = TextEditingController(text: 'Aleppo');
  DateTime _departAt = DateTime.now().add(const Duration(hours: 6));
  DateTime? _arriveAt;
  int _price = 20000;
  int _seats = 40;
  final _busModel = TextEditingController();
  final _busYear = TextEditingController();

  Future<void> _load() async {
    final t = await widget.api.listTrips(widget.operatorId);
    final vs = await widget.api.listVehicles(widget.operatorId);
    setState(() { _trips = t; _vehicles = vs; });
  }
  @override
  void initState() { super.initState(); _load(); }

  Future<void> _showSeats(String tripId) async {
    try {
      final data = await widget.api.tripSeats(widget.operatorId, tripId);
      final seatsTotal = (data['seats_total'] as num).toInt();
      final reserved = ((data['reserved'] as List?) ?? []).cast<num>().map((e) => e.toInt()).toSet();
      await showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Seat Map'),
          content: SizedBox(
            width: 400,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(spacing: 8, runSpacing: 8, children: List.generate(seatsTotal, (i) {
                  final n = i + 1;
                  final taken = reserved.contains(n);
                  return SizedBox(
                    width: 56,
                    child: Chip(
                      label: Text('$n'),
                      backgroundColor: taken ? Colors.red.shade200 : Colors.green.shade200,
                    ),
                  );
                })),
                const SizedBox(height: 8),
                Text('Reserved: ${reserved.length} / $seatsTotal'),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: ()=>Navigator.pop(context), child: const Text('Close')),
          ],
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to load seats: $e')));
    }
  }

  Future<void> _editTrip(Map<String, dynamic> t) async {
    final cOrigin = TextEditingController(text: (t['origin'] ?? '').toString());
    final cDest = TextEditingController(text: (t['destination'] ?? '').toString());
    DateTime depart = DateTime.parse(t['depart_at']).toLocal();
    DateTime? arrive = t['arrive_at'] != null ? DateTime.tryParse((t['arrive_at']).toString())?.toLocal() : null;
    final cPrice = TextEditingController(text: '${t['price_cents']}');
    final cSeats = TextEditingController();
    final cModel = TextEditingController(text: (t['bus_model'] ?? '').toString());
    final cYear = TextEditingController(text: (t['bus_year'] ?? '').toString());
    final formKey = GlobalKey<FormState>();
    // vehicles for selection
    final vehicles = await widget.api.listVehicles(widget.operatorId);
    String? vehicleId = (t['vehicle_id'] as String?);
    final updated = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Edit Trip'),
        content: SizedBox(
          width: 420,
          child: Form(
            key: formKey,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextFormField(controller: cOrigin, decoration: const InputDecoration(labelText: 'Origin')),
              TextFormField(controller: cDest, decoration: const InputDecoration(labelText: 'Destination')),
              Row(children: [
                Expanded(child: Text('Depart: $depart')),
                IconButton(icon: const Icon(Icons.edit_calendar_outlined), onPressed: () async {
                  final d = await showDatePicker(context: context, initialDate: depart, firstDate: DateTime.now().subtract(const Duration(days: 1)), lastDate: DateTime.now().add(const Duration(days: 365)));
                  if (d == null) return;
                  final tm = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(depart));
                  if (tm == null) return;
                  depart = DateTime(d.year, d.month, d.day, tm.hour, tm.minute);
                })
              ]),
              Row(children: [
                const Text('Vehicle:'), const SizedBox(width: 8),
                DropdownButton<String>(
                  value: vehicleId,
                  hint: const Text('None'),
                  items: vehicles.map<DropdownMenuItem<String>>((v) => DropdownMenuItem<String>(value: v['id'] as String, child: Text(v['name'] as String))).toList(),
                  onChanged: (v){ vehicleId = v; },
                ),
              ]),
              Row(children: [
                Expanded(child: Text('Arrive: ${arrive?.toLocal() ?? '—'}')),
                IconButton(icon: const Icon(Icons.edit_calendar_outlined), onPressed: () async {
                  final base = arrive ?? depart.add(const Duration(hours: 4));
                  final d = await showDatePicker(context: context, initialDate: base, firstDate: depart, lastDate: depart.add(const Duration(days: 2)));
                  if (d == null) return;
                  final tm = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(base));
                  if (tm == null) return;
                  arrive = DateTime(d.year, d.month, d.day, tm.hour, tm.minute);
                })
              ]),
              Row(children: [
                Expanded(child: TextFormField(controller: cPrice, decoration: const InputDecoration(labelText: 'Price (cents)'), keyboardType: TextInputType.number)),
                const SizedBox(width: 8),
                Expanded(child: TextFormField(controller: cSeats, decoration: const InputDecoration(labelText: 'Seats Total (leave blank to keep)'), keyboardType: TextInputType.number)),
              ]),
              Row(children: [
                Expanded(child: TextFormField(controller: cModel, decoration: const InputDecoration(labelText: 'Bus Model'))),
                const SizedBox(width: 8),
                Expanded(child: TextFormField(controller: cYear, decoration: const InputDecoration(labelText: 'Bus Year'), keyboardType: TextInputType.number)),
              ]),
            ]),
          ),
        ),
        actions: [
          TextButton(onPressed: ()=>Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: (){ Navigator.pop(context, true); }, child: const Text('Save')),
        ],
      ),
    );
    if (updated == true) {
      final Map<String, dynamic> body = <String, dynamic>{
        'origin': cOrigin.text.trim(),
        'destination': cDest.text.trim(),
        'depart_at': depart.toUtc().toIso8601String(),
      };
      if (arrive != null) body['arrive_at'] = arrive!.toUtc().toIso8601String();
      final pc = int.tryParse(cPrice.text.trim()); if (pc != null) body['price_cents'] = pc;
      final st = int.tryParse(cSeats.text.trim()); if (st != null) body['seats_total'] = st;
      if (cModel.text.trim().isNotEmpty) body['bus_model'] = cModel.text.trim();
      final by = int.tryParse(cYear.text.trim()); if (by != null) body['bus_year'] = by;
      if (vehicleId != null) body['vehicle_id'] = vehicleId; else body['vehicle_id'] = "";
      await widget.api.updateTrip(widget.operatorId, t['id'], body);
      _load();
    }
  }

  Future<void> _cloneTripDialog(String tripId, DateTime srcDepart) async {
    DateTime start = DateTime(srcDepart.year, srcDepart.month, srcDepart.day);
    DateTime end = start.add(const Duration(days: 7));
    final weekdays = List<bool>.filled(7, false);
    weekdays[start.weekday % 7] = true; // default same weekday
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => StatefulBuilder(builder: (context, setS) {
        return AlertDialog(
          title: const Text('Clone Trip'),
          content: SizedBox(
            width: 420,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Row(children: [
                Expanded(child: Text('Start: ${start.toLocal()}')),
                IconButton(icon: const Icon(Icons.edit_calendar_outlined), onPressed: () async {
                  final d = await showDatePicker(context: context, initialDate: start, firstDate: start.subtract(const Duration(days: 1)), lastDate: start.add(const Duration(days: 365)));
                  if (d != null) setS(() => start = DateTime(d.year, d.month, d.day));
                })
              ]),
              Row(children: [
                Expanded(child: Text('End:   ${end.toLocal()}')),
                IconButton(icon: const Icon(Icons.edit_calendar_outlined), onPressed: () async {
                  final d = await showDatePicker(context: context, initialDate: end, firstDate: start, lastDate: start.add(const Duration(days: 365)));
                  if (d != null) setS(() => end = DateTime(d.year, d.month, d.day));
                })
              ]),
              const SizedBox(height: 8),
              const Align(alignment: Alignment.centerLeft, child: Text('Weekdays')),
              Wrap(spacing: 6, children: List.generate(7, (i) {
                const labels = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
                return FilterChip(
                  label: Text(labels[i]),
                  selected: weekdays[i],
                  onSelected: (v){ setS(() => weekdays[i] = v); },
                );
              })),
            ]),
          ),
          actions: [
            TextButton(onPressed: ()=>Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: ()=>Navigator.pop(context, true), child: const Text('Clone')),
          ],
        );
      }),
    );
    if (ok == true) {
      final selected = <int>[];
      for (int i=0;i<7;i++){ if (weekdays[i]) selected.add(i); }
      await widget.api.cloneTrip(widget.operatorId, tripId, startDate: start, endDate: end, weekdays: selected.isEmpty ? null : selected);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Clone done')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 2,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Trips', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Expanded(
                  child: RefreshIndicator(
                    onRefresh: _load,
                    child: ListView.builder(
                      itemCount: _trips.length,
                      itemBuilder: (_, i) {
                        final t = _trips[i];
                        final depart = DateTime.parse(t['depart_at']).toLocal();
                        return Card(
                          child: ListTile(
                            title: Text('${t['origin']} → ${t['destination']} • ${(t['price_cents'] / 100).toStringAsFixed(2)}'),
                            subtitle: Text('Departs: $depart • Seats avail: ${t['seats_available']}'),
                            trailing: Wrap(spacing: 4, children: [
                              IconButton(
                                tooltip: 'Seats',
                                icon: const Icon(Icons.event_seat_outlined),
                                onPressed: () => _showSeats(t['id']),
                              ),
                              IconButton(
                                tooltip: 'Manifest',
                                icon: const Icon(Icons.list_alt_outlined),
                                onPressed: () async {
                                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => ManifestPage(api: widget.api, operatorId: widget.operatorId, tripId: t['id'])));
                                },
                              ),
                              IconButton(
                                tooltip: 'Clone',
                                icon: const Icon(Icons.copy_all_outlined),
                                onPressed: () async {
                                  await _cloneTripDialog(t['id'], depart);
                                  _load();
                                },
                              ),
                              IconButton(
                                tooltip: 'Edit',
                                icon: const Icon(Icons.edit_outlined),
                                onPressed: () => _editTrip(t),
                              ),
                              IconButton(
                                tooltip: 'Delete',
                                icon: const Icon(Icons.delete_outline),
                                onPressed: () async {
                                  await widget.api.deleteTrip(widget.operatorId, t['id']);
                                  _load();
                                },
                              ),
                            ]),
                          ),
                        );
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Create Trip', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Form(
                  key: _form,
                  child: Column(children: [
                    TextFormField(controller: _origin, decoration: const InputDecoration(labelText: 'Origin')),
                    TextFormField(controller: _destination, decoration: const InputDecoration(labelText: 'Destination')),
                    Row(children: [
                      Expanded(child: Text('Depart: ${_departAt.toLocal()}')),
                      IconButton(icon: const Icon(Icons.edit_calendar_outlined), onPressed: () async {
                        final d = await showDatePicker(context: context, initialDate: _departAt, firstDate: DateTime.now().subtract(const Duration(days: 1)), lastDate: DateTime.now().add(const Duration(days: 365)));
                        if (d == null) return;
                        final t = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(_departAt));
                        if (t == null) return;
                        setState(() => _departAt = DateTime(d.year, d.month, d.day, t.hour, t.minute));
                      })
                    ]),
                    Row(children: [
                      const Text('Vehicle:'), const SizedBox(width: 8),
                      DropdownButton<String>(
                        value: _vehicleId,
                        hint: const Text('None'),
                        items: _vehicles.map<DropdownMenuItem<String>>((v) => DropdownMenuItem<String>(value: v['id'] as String, child: Text(v['name'] as String))).toList(),
                        onChanged: (v){ setState(() { _vehicleId = v; if (v != null) { final match = _vehicles.firstWhere((e)=>e['id']==v, orElse: ()=>{} as Map<String,dynamic>); final st = (match['seats_total'] as int?); if (st!=null) _seats = st; } }); },
                      ),
                    ]),
                    Row(children: [
                      Expanded(child: Text('Arrive: ${_arriveAt?.toLocal() ?? '—'}')),
                      IconButton(icon: const Icon(Icons.edit_calendar_outlined), onPressed: () async {
                        final base = _arriveAt ?? _departAt.add(const Duration(hours: 4));
                        final d = await showDatePicker(context: context, initialDate: base, firstDate: _departAt, lastDate: _departAt.add(const Duration(days: 2)));
                        if (d == null) return;
                        final t = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(base));
                        if (t == null) return;
                        setState(() => _arriveAt = DateTime(d.year, d.month, d.day, t.hour, t.minute));
                      })
                    ]),
                    Row(children: [
                      Expanded(child: TextFormField(initialValue: '$_price', decoration: const InputDecoration(labelText: 'Price (cents)'), onChanged: (v) => _price = int.tryParse(v) ?? _price)),
                      const SizedBox(width: 8),
                      Expanded(child: TextFormField(initialValue: '$_seats', decoration: const InputDecoration(labelText: 'Seats Total'), onChanged: (v) => _seats = int.tryParse(v) ?? _seats)),
                    ]),
                    Row(children: [
                      Expanded(child: TextField(controller: _busModel, decoration: const InputDecoration(labelText: 'Bus Model'))),
                      const SizedBox(width: 8),
                      Expanded(child: TextField(controller: _busYear, decoration: const InputDecoration(labelText: 'Bus Year'))),
                    ]),
                    const SizedBox(height: 8),
                    FilledButton(
                      onPressed: () async {
                        final Map<String, dynamic> body = {
                          'origin': _origin.text.trim(),
                          'destination': _destination.text.trim(),
                          'depart_at': _departAt.toUtc().toIso8601String(),
                          'price_cents': _price,
                          'seats_total': _seats,
                        };
                        if (_arriveAt != null) body['arrive_at'] = _arriveAt!.toUtc().toIso8601String();
                        if (_busModel.text.trim().isNotEmpty) body['bus_model'] = _busModel.text.trim();
                        final by = int.tryParse(_busYear.text.trim());
                        if (by != null) body['bus_year'] = by;
                        if (_vehicleId != null) body['vehicle_id'] = _vehicleId;
                        await widget.api.createTrip(widget.operatorId, body);
                        _load();
                      },
                      child: const Text('Create'),
                    ),
                  ]),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class BookingsTab extends StatefulWidget {
  final Api api; final String operatorId;
  const BookingsTab({super.key, required this.api, required this.operatorId});
  @override
  State<BookingsTab> createState() => _BookingsTabState();
}
class _BookingsTabState extends State<BookingsTab> {
  List<Map<String, dynamic>> _items = [];
  String? _filter;
  final _phone = TextEditingController();
  DateTime? _from;
  DateTime? _to;
  Future<void> _load() async {
    final b = await widget.api.listBookings(widget.operatorId, status: _filter, phone: _phone.text.trim().isNotEmpty ? _phone.text.trim() : null, from: _from, to: _to);
    setState(() => _items = b);
  }
  @override
  void initState() { super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(8.0),
        child: Row(children: [
          const Text('Filter:'), const SizedBox(width: 8),
          DropdownButton<String>(value: _filter, hint: const Text('All'), items: const [
            DropdownMenuItem(value: 'reserved', child: Text('Reserved')),
            DropdownMenuItem(value: 'confirmed', child: Text('Confirmed')),
            DropdownMenuItem(value: 'canceled', child: Text('Canceled')),
          ], onChanged: (v){ setState(() => _filter = v); _load(); }),
          const SizedBox(width: 12),
          SizedBox(width: 180, child: TextField(controller: _phone, decoration: const InputDecoration(labelText: 'Phone contains'), onSubmitted: (_)=>_load())),
          const SizedBox(width: 8),
          OutlinedButton.icon(onPressed: () async {
            final now = DateTime.now();
            final d = await showDatePicker(context: context, initialDate: _from ?? now.subtract(const Duration(days: 7)), firstDate: now.subtract(const Duration(days: 365)), lastDate: now.add(const Duration(days: 1)));
            if (d!=null) setState(()=>_from = DateTime(d.year,d.month,d.day));
          }, icon: const Icon(Icons.date_range), label: Text(_from==null? 'From' : _from!.toLocal().toString().split(' ').first)),
          const SizedBox(width: 6),
          OutlinedButton.icon(onPressed: () async {
            final now = DateTime.now();
            final d = await showDatePicker(context: context, initialDate: _to ?? now, firstDate: now.subtract(const Duration(days: 365)), lastDate: now.add(const Duration(days: 1)));
            if (d!=null) setState(()=>_to = DateTime(d.year,d.month,d.day,23,59,59));
          }, icon: const Icon(Icons.date_range), label: Text(_to==null? 'To' : _to!.toLocal().toString().split(' ').first)),
          const Spacer(),
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          IconButton(
            tooltip: 'Export CSV',
            icon: const Icon(Icons.download_outlined),
            onPressed: () async {
              try {
                final csv = await widget.api.bookingsCsv(widget.operatorId, status: _filter, phone: _phone.text.trim().isNotEmpty ? _phone.text.trim() : null, from: _from, to: _to);
                await downloadCsv(csv, 'bookings.csv');
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('CSV export failed: $e')));
              }
            },
          ),
        ]),
      ),
      Expanded(
        child: ListView.builder(
          itemCount: _items.length,
          itemBuilder: (_, i){
            final b = _items[i];
            final seats = (b['seat_numbers'] as List?)?.cast<num>().map((e) => e.toInt()).toList() ?? const [];
            final seatsText = seats.isNotEmpty ? ' [${seats.join(', ')}]' : '';
            return Card(child: ListTile(
              title: Text('${b['origin']} → ${b['destination']} • ${b['status']}'),
              subtitle: Text('Seats: ${b['seats_count']}$seatsText • Total: ${(b['total_price_cents']/100).toStringAsFixed(2)} • User: ${b['user_phone'] ?? ''}'),
              trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                IconButton(onPressed: () async { await widget.api.confirmBooking(widget.operatorId, b['id']); _load(); }, icon: const Icon(Icons.check_circle_outline)),
                IconButton(onPressed: () async { await widget.api.cancelBooking(widget.operatorId, b['id']); _load(); }, icon: const Icon(Icons.cancel_outlined)),
              ]),
            ));
          },
        ),
      ),
    ]);
  }
}

class ManifestPage extends StatefulWidget {
  final Api api; final String operatorId; final String tripId;
  const ManifestPage({super.key, required this.api, required this.operatorId, required this.tripId});
  @override
  State<ManifestPage> createState() => _ManifestPageState();
}
class _ManifestPageState extends State<ManifestPage> {
  Map<String, dynamic>? _m;
  Future<void> _load() async { final m = await widget.api.manifest(widget.operatorId, widget.tripId); setState(() => _m = m); }
  @override
  void initState(){ super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    final m = _m;
    return Scaffold(
      appBar: AppBar(title: const Text('Manifest'), actions: [
        if (m != null)
          IconButton(icon: const Icon(Icons.print), onPressed: (){
            Navigator.of(context).push(MaterialPageRoute(builder: (_)=> PrintManifestPage(manifest: m)));
          })
      ]),
      body: m == null ? const Center(child: CircularProgressIndicator()) : Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${m['origin']} → ${m['destination']} • Departs: ${DateTime.parse(m['depart_at']).toLocal()}'),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              itemCount: (m['items'] as List).length,
              itemBuilder: (_, i){
                final it = (m['items'] as List)[i] as Map<String, dynamic>;
                final seats = ((it['seat_numbers'] as List?)?.join(', ') ?? '—').toString();
                final phone = (it['user_phone'] ?? '').toString();
                final name = (it['user_name'] ?? '').toString();
                return ListTile(
                  dense: true,
                  title: Text(name.isNotEmpty ? '$name  ·  $phone' : phone),
                  subtitle: Text('Seats: ${it['seats_count']}  [$seats] • Status: ${it['status']}'),
                );
              },
            ),
          )
        ]),
      ),
    );
  }
}

class SummaryTab extends StatefulWidget {
  final Api api; final String operatorId;
  const SummaryTab({super.key, required this.api, required this.operatorId});
  @override
  State<SummaryTab> createState() => _SummaryTabState();
}
class _SummaryTabState extends State<SummaryTab> {
  Map<String, dynamic>? _sum;
  Timer? _timer;
  Future<void> _load() async { final s = await widget.api.summary(widget.operatorId); setState(() => _sum = s); }
  @override
  void initState() { super.initState(); _load(); _timer = Timer.periodic(const Duration(seconds: 10), (_) => _load()); }
  @override
  void dispose() { _timer?.cancel(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    final s = _sum;
    if (s == null) return const Center(child: CircularProgressIndicator());
    return Padding(padding: const EdgeInsets.all(16), child: Wrap(spacing: 16, runSpacing: 16, children: [
      _Kpi('Bookings', '${s['total_bookings']}'),
      _Kpi('Confirmed', '${s['confirmed_bookings']}'),
      _Kpi('Revenue', (s['gross_revenue_cents']/100).toStringAsFixed(2)),
      _Kpi('Avg Occupancy %', (s['avg_occupancy_percent']).toStringAsFixed(1)),
    ]));
  }
}

class TicketsTab extends StatefulWidget {
  final Api api; final String operatorId;
  const TicketsTab({super.key, required this.api, required this.operatorId});
  @override
  State<TicketsTab> createState() => _TicketsTabState();
}
class _TicketsTabState extends State<TicketsTab> {
  final _qr = TextEditingController();
  Map<String, dynamic>? _result;
  String? _err;
  List<Map<String, dynamic>> _offlineQueue = [];
  Timer? _syncTimer;

  @override
  void initState(){ super.initState(); _loadQueue(); _syncTimer = Timer.periodic(const Duration(seconds: 15), (_)=>_trySync()); }
  @override
  void dispose(){ _syncTimer?.cancel(); super.dispose(); }

  Future<void> _loadQueue() async { try { final prefs = await SharedPreferences.getInstance(); final raw = prefs.getString('offline_boardings') ?? '[]'; final xs = (jsonDecode(raw) as List).map((e)=> (e as Map).cast<String, dynamic>()).toList(); setState(()=>_offlineQueue = xs); } catch (_) {} }
  Future<void> _saveQueue() async { final prefs = await SharedPreferences.getInstance(); await prefs.setString('offline_boardings', jsonEncode(_offlineQueue)); }
  Future<void> _enqueueBoarding(String bookingId) async { setState(()=>_offlineQueue.add({'booking_id': bookingId, 'ts': DateTime.now().toUtc().toIso8601String()})); await _saveQueue(); }
  Future<void> _trySync() async {
    if (_offlineQueue.isEmpty) return;
    final copy = List<Map<String, dynamic>>.from(_offlineQueue);
    for (final it in copy) {
      try {
        await widget.api.markBoarded(widget.operatorId, it['booking_id'] as String);
        setState(()=>_offlineQueue.removeWhere((e)=>e['booking_id']==it['booking_id']));
        await _saveQueue();
      } catch (_) { /* keep for next round */ }
    }
  }
  @override
  Widget build(BuildContext context) {
    final r = _result;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Validate Ticket', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: TextField(controller: _qr, decoration: const InputDecoration(labelText: 'QR text (BUS|<booking_id>)'))),
          const SizedBox(width: 8),
          FilledButton(onPressed: () async {
            try {
              final res = await widget.api.validateTicket(widget.operatorId, _qr.text.trim());
              setState(() { _result = res; _err = null; });
            } catch (e) { setState(() { _err = '$e'; }); }
          }, child: const Text('Check')),
          const SizedBox(width: 8),
          OutlinedButton.icon(onPressed: _trySync, icon: const Icon(Icons.sync), label: Text('Sync (${_offlineQueue.length})')),
          const SizedBox(width: 8),
          OutlinedButton.icon(onPressed: () async {
            try {
              final scanned = await Navigator.of(context).push<String>(
                MaterialPageRoute(builder: (_) => const QrScanPage()),
              );
              if (scanned != null && scanned.isNotEmpty) {
                _qr.text = scanned;
                final res = await widget.api.validateTicket(widget.operatorId, scanned);
                setState(() { _result = res; _err = null; });
              }
            } catch (e) {
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Scan failed: $e')));
            }
          }, icon: const Icon(Icons.qr_code_scanner), label: const Text('Scan')),
          const SizedBox(width: 8),
          OutlinedButton.icon(onPressed: () async { await Navigator.of(context).push(MaterialPageRoute(builder: (_) => KioskScanPage(api: widget.api, operatorId: widget.operatorId))); _loadQueue(); }, icon: const Icon(Icons.fullscreen), label: const Text('Kiosk')),
        ]),
        const SizedBox(height: 12),
        if (_err != null) Text(_err!, style: const TextStyle(color: Colors.red)),
        if (r != null) ...[
          Text('Valid: ${r['valid']}  ${r['reason'] ?? ''}'),
          if (r['booking'] != null) ...[
            Text('Seats: ' + (((r['booking']['seat_numbers'] as List?)?.join(', ') ?? '—').toString())),
            const SizedBox(height: 8),
          ],
          if (r['booking'] != null) Row(children: [
            FilledButton(onPressed: r['valid'] == true ? () async {
              try {
                await widget.api.markBoarded(widget.operatorId, r['booking']['id']);
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Boarded marked')));
              } catch (_) {
                await _enqueueBoarding(r['booking']['id']);
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Offline queued')));
              }
            } : null, child: const Text('Mark boarded')),
          ])
        ]
      ]),
    );
  }
}

class QrScanPage extends StatefulWidget {
  const QrScanPage({super.key});
  @override
  State<QrScanPage> createState() => _QrScanPageState();
}
class _QrScanPageState extends State<QrScanPage> {
  bool _done = false;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan QR')),
      body: Center(
        child: AspectRatio(
          aspectRatio: 3/4,
          child: MobileScanner(
            fit: BoxFit.contain,
            onDetect: (capture) {
              if (_done) return;
              final codes = capture.barcodes;
              final raw = codes.isNotEmpty ? (codes.first.rawValue ?? '') : '';
              if (raw.isNotEmpty) {
                _done = true;
                Navigator.of(context).pop(raw);
              }
            },
          ),
        ),
      ),
    );
  }
}

class KioskScanPage extends StatefulWidget {
  final Api api; final String operatorId;
  const KioskScanPage({super.key, required this.api, required this.operatorId});
  @override
  State<KioskScanPage> createState() => _KioskScanPageState();
}
class _KioskScanPageState extends State<KioskScanPage> {
  bool _torch = false;
  final Set<String> _recent = {};
  final List<String> _log = [];
  final MobileScannerController _controller = MobileScannerController();
  String? _overlay; // 'ok' | 'fail'
  DateTime? _overlayUntil;
  void _showOverlay(String kind){
    setState((){ _overlay = kind; _overlayUntil = DateTime.now().add(const Duration(milliseconds: 700)); });
    Future.delayed(const Duration(milliseconds: 720), (){ if (!mounted) return; if (_overlayUntil!=null && DateTime.now().isAfter(_overlayUntil!)) setState(()=> _overlay=null); });
  }
  void _append(String s){ setState(()=>_log.insert(0, s)); if (_log.length>50) _log.removeLast(); }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Kiosk Scan'), actions: [
        IconButton(icon: Icon(_torch? Icons.flash_on : Icons.flash_off), onPressed: () async { try { await _controller.toggleTorch(); } catch (_) {} setState(()=>_torch=!_torch); }),
      ]),
      body: Row(children: [
        Expanded(child: Center(child: AspectRatio(aspectRatio: 3/4, child: Stack(children:[
          MobileScanner(
            fit: BoxFit.cover,
            controller: _controller,
            onDetect: (capture) async {
              final codes = capture.barcodes;
              final raw = codes.isNotEmpty ? (codes.first.rawValue ?? '') : '';
              if (raw.isEmpty || _recent.contains(raw)) return;
              _recent.add(raw); Future.delayed(const Duration(seconds: 5), ()=>_recent.remove(raw));
              if (!raw.startsWith('BUS|')) { _append('Invalid: $raw'); return; }
              try {
                final res = await widget.api.validateTicket(widget.operatorId, raw);
                if (res['valid'] == true) {
                try { await widget.api.markBoarded(widget.operatorId, res['booking']['id']); _append('Boarded: ${res['booking']['id']}'); _showOverlay('ok'); beep(); }
                catch (_) { _append('Queued: ${res['booking']['id']}'); _showOverlay('ok'); }
              } else { _append('Not valid: ${res['reason'] ?? ''}'); _showOverlay('fail'); beep(); }
              } catch (e) { _append('Error: $e'); }
          },
        ),
        if (_overlay!=null) Positioned.fill(child: IgnorePointer(child: Container(color: _overlay=='ok'? Colors.green.withOpacity(0.25): Colors.red.withOpacity(0.25), child: Center(child: Icon(_overlay=='ok'? Icons.check_circle_outline: Icons.highlight_off, color: _overlay=='ok'? Colors.green: Colors.red, size: 160))))),
        ])))),
        SizedBox(width: 360, child: Padding(padding: const EdgeInsets.all(8), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Recent'),
          const SizedBox(height: 8),
          Expanded(child: ListView.builder(itemCount: _log.length, itemBuilder: (_,i)=>Text(_log[i]))),
        ]))),
      ]),
    );
  }
}

class PrintManifestPage extends StatelessWidget {
  final Map<String, dynamic> manifest;
  const PrintManifestPage({super.key, required this.manifest});
  @override
  Widget build(BuildContext context) {
    WidgetsBinding.instance.addPostFrameCallback((_){ triggerPrint(); });
    final items = (manifest['items'] as List).cast<Map>();
    return Scaffold(
      appBar: AppBar(title: const Text('Print Manifest')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${manifest['origin']} → ${manifest['destination']}'),
          Text('Departs: ${DateTime.parse(manifest['depart_at']).toLocal()}'),
          const SizedBox(height: 8),
          Expanded(child: ListView.builder(
            itemCount: items.length,
            itemBuilder: (_, i){ final it = items[i]; final seats = ((it['seat_numbers'] as List?)?.join(', ') ?? '—').toString(); return Text('${i+1}. ${it['user_name'] ?? ''} ${it['user_phone'] ?? ''}  •  Seats: ${it['seats_count']} [$seats]  •  ${it['status']}'); },
          )),
        ]),
      ),
    );
  }

}

String hmacSignatureHex(String secret, String bodyJson) {
  final key = utf8.encode(secret);
  final bytes = utf8.encode(bodyJson);
  final mac = crypto.Hmac(crypto.sha256, key).convert(bytes);
  return mac.toString();
}

class MembersTab extends StatefulWidget {
  final Api api; final String operatorId;
  const MembersTab({super.key, required this.api, required this.operatorId});
  @override
  State<MembersTab> createState() => _MembersTabState();
}
class _MembersTabState extends State<MembersTab> {
  List<Map<String, dynamic>> _members = [];
  final _phone = TextEditingController();
  String _role = 'agent';
  List<Map<String, dynamic>> _branches = [];
  String? _branchId;
  Future<void> _load() async {
    final ms = await widget.api.listMembers(widget.operatorId);
    final bs = await widget.api.listBranches(widget.operatorId);
    setState(() { _members = ms; _branches = bs; });
  }
  @override
  void initState() { super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Members', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: TextField(controller: _phone, decoration: const InputDecoration(labelText: 'Phone (+963...)'))),
          const SizedBox(width: 8),
          DropdownButton<String>(value: _role, items: const [
            DropdownMenuItem(value: 'checker', child: Text('Checker')),
            DropdownMenuItem(value: 'cashier', child: Text('Cashier')),
            DropdownMenuItem(value: 'agent', child: Text('Agent')),
            DropdownMenuItem(value: 'admin', child: Text('Admin')),
          ], onChanged: (v){ if (v!=null) setState(()=>_role=v); }),
          const SizedBox(width: 8),
          DropdownButton<String>(
            value: _branchId,
            hint: const Text('Branch'),
            items: _branches.map<DropdownMenuItem<String>>((b)=>DropdownMenuItem<String>(value: b['id'] as String, child: Text(b['name'] as String))).toList(),
            onChanged: (v){ setState(()=>_branchId=v); },
          ),
          const SizedBox(width: 8),
          FilledButton(onPressed: () async {
            try {
              await widget.api.addMember(widget.operatorId, phone: _phone.text.trim(), role: _role);
              if (_branchId != null) {
                final ms = await widget.api.listMembers(widget.operatorId);
                final created = ms.firstWhere((m)=>m['phone']==_phone.text.trim(), orElse: ()=>{} as Map<String,dynamic>);
                if (created is Map<String,dynamic> && created['id']!=null) {
                  await widget.api.setMemberBranch(widget.operatorId, created['id'], branchId: _branchId);
                }
              }
              _phone.clear();
              _role = 'agent';
              _branchId = null;
              _load();
            } catch (e) {
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Add failed: $e')));
            }
          }, child: const Text('Add')),
        ]),
        const SizedBox(height: 12),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView.builder(
              itemCount: _members.length,
              itemBuilder: (_, i){
                final m = _members[i];
                final phone = (m['phone'] ?? '').toString();
                final name = (m['name'] ?? '').toString();
                String role = (m['role'] ?? 'agent').toString();
                final id = (m['id']).toString();
                final branchName = (m['branch_name'] ?? '').toString();
                return Card(child: ListTile(
                  title: Text(name.isNotEmpty ? '$name  ·  $phone' : phone),
                  subtitle: Text('Role: $role  ·  Branch: ${branchName.isNotEmpty? branchName : '—'}'),
                  trailing: Wrap(spacing: 8, children: [
                    DropdownButton<String>(
                      value: role,
                      items: const [
                        DropdownMenuItem(value: 'checker', child: Text('Checker')),
                        DropdownMenuItem(value: 'cashier', child: Text('Cashier')),
                        DropdownMenuItem(value: 'agent', child: Text('Agent')),
                        DropdownMenuItem(value: 'admin', child: Text('Admin')),
                      ],
                      onChanged: (v) async {
                        if (v == null || v == role) return;
                        try {
                          await widget.api.setMemberRole(widget.operatorId, id, v);
                          _load();
                        } catch (e) {
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Role change failed: $e')));
                        }
                      },
                    ),
                    DropdownButton<String>(
                      value: (m['branch_id'] as String?),
                      hint: const Text('Branch'),
                      items: _branches.map<DropdownMenuItem<String>>((b)=>DropdownMenuItem<String>(value: b['id'] as String, child: Text(b['name'] as String))).toList(),
                      onChanged: (v) async {
                        try {
                          await widget.api.setMemberBranch(widget.operatorId, id, branchId: v);
                          _load();
                        } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Set branch failed: $e'))); }
                      },
                    ),
                    IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async {
                      try {
                        await widget.api.removeMember(widget.operatorId, id);
                        _load();
                      } catch (e) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Remove failed: $e')));
                      }
                    })
                  ]),
                ));
              },
            ),
          ),
        )
      ]),
    );
  }
}

class PromosTab extends StatefulWidget {
  final Api api; final String operatorId;
  const PromosTab({super.key, required this.api, required this.operatorId});
  @override
  State<PromosTab> createState() => _PromosTabState();
}
class _PromosTabState extends State<PromosTab> {
  List<Map<String, dynamic>> _items = [];
  final _code = TextEditingController();
  final _amount = TextEditingController();
  final _percent = TextEditingController();
  Future<void> _load() async { final xs = await widget.api.listPromos(widget.operatorId); setState(()=>_items=xs); }
  @override
  void initState(){ super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Promos', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Row(children: [
          SizedBox(width: 160, child: TextField(controller: _code, decoration: const InputDecoration(labelText: 'Code'))),
          const SizedBox(width: 8),
          SizedBox(width: 140, child: TextField(controller: _amount, decoration: const InputDecoration(labelText: 'Amount off (cents)'))),
          const SizedBox(width: 8),
          SizedBox(width: 140, child: TextField(controller: _percent, decoration: const InputDecoration(labelText: 'Percent off (bps)'))),
          const SizedBox(width: 8),
          FilledButton(onPressed: () async {
            try {
              final body = <String, dynamic>{'code': _code.text.trim(), 'active': true};
              final p = int.tryParse(_percent.text.trim()); if (p!=null) body['percent_off_bps']=p;
              final a = int.tryParse(_amount.text.trim()); if (a!=null) body['amount_off_cents']=a;
              await widget.api.createPromo(widget.operatorId, body);
              _code.clear(); _amount.clear(); _percent.clear();
              _load();
            } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create failed: $e')));} 
          }, child: const Text('Create')),
        ]),
        const SizedBox(height: 12),
        Expanded(child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.builder(
            itemCount: _items.length,
            itemBuilder: (_, i){
              final x = _items[i];
              return Card(child: ListTile(
                title: Text(x['code'] ?? ''),
                subtitle: Text('amount_off: ${x['amount_off_cents'] ?? '-'}  percent_off_bps: ${x['percent_off_bps'] ?? '-'}  uses: ${x['uses_count']}  active: ${x['active']}'),
                trailing: Wrap(spacing: 8, children: [
                  IconButton(icon: const Icon(Icons.toggle_on_outlined), onPressed: () async { try { await widget.api.updatePromo(widget.operatorId, x['id'], {'active': !(x['active']==true)}); _load(); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Toggle failed: $e')));} }),
                  IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async { try { await widget.api.deletePromo(widget.operatorId, x['id']); _load(); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e')));} }),
                ]),
              ));
            },
          ),
        )),
      ]),
    );
  }
}

class VehiclesTab extends StatefulWidget {
  final Api api; final String operatorId;
  const VehiclesTab({super.key, required this.api, required this.operatorId});
  @override
  State<VehiclesTab> createState() => _VehiclesTabState();
}
class _VehiclesTabState extends State<VehiclesTab> {
  List<Map<String, dynamic>> _items = [];
  final _name = TextEditingController();
  final _seats = TextEditingController(text: '40');
  final _cols = TextEditingController();
  Future<void> _load() async { final xs = await widget.api.listVehicles(widget.operatorId); setState(()=>_items=xs); }
  @override
  void initState(){ super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Vehicles', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Row(children: [
          SizedBox(width: 200, child: TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name'))),
          const SizedBox(width: 8),
          SizedBox(width: 100, child: TextField(controller: _seats, decoration: const InputDecoration(labelText: 'Seats'), keyboardType: TextInputType.number)),
          const SizedBox(width: 8),
          SizedBox(width: 120, child: TextField(controller: _cols, decoration: const InputDecoration(labelText: 'Seat Columns'), keyboardType: TextInputType.number)),
          const SizedBox(width: 8),
          FilledButton(onPressed: () async { try {
            final st = int.tryParse(_seats.text.trim()) ?? 40; final sc = int.tryParse(_cols.text.trim());
            await widget.api.createVehicle(widget.operatorId, name: _name.text.trim(), seatsTotal: st, seatColumns: sc);
            _name.clear(); _seats.text = '40'; _cols.clear(); _load();
          } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create failed: $e')));} }, child: const Text('Add')),
        ]),
        const SizedBox(height: 12),
        Expanded(child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.builder(
            itemCount: _items.length,
            itemBuilder: (_, i){
              final v = _items[i];
              return Card(child: ListTile(
                title: Text(v['name'] ?? ''),
                subtitle: Text('Seats: ${v['seats_total']}  Columns: ${v['seat_columns'] ?? '-'}'),
                trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async { try { await widget.api.deleteVehicle(widget.operatorId, v['id']); _load(); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e')));} }),
              ));
            },
          ),
        )),
      ]),
    );
  }
}

class BranchesTab extends StatefulWidget {
  final Api api; final String operatorId;
  const BranchesTab({super.key, required this.api, required this.operatorId});
  @override
  State<BranchesTab> createState() => _BranchesTabState();
}
class _BranchesTabState extends State<BranchesTab> {
  List<Map<String, dynamic>> _items = [];
  final _name = TextEditingController();
  final _bps = TextEditingController();
  Future<void> _load() async { final xs = await widget.api.listBranches(widget.operatorId); setState(()=>_items=xs); }
  @override
  void initState(){ super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Branches', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Row(children: [
          SizedBox(width: 220, child: TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name'))),
          const SizedBox(width: 8),
          SizedBox(width: 160, child: TextField(controller: _bps, decoration: const InputDecoration(labelText: 'Commission BPS (e.g. 250)'), keyboardType: TextInputType.number)),
          const SizedBox(width: 8),
          FilledButton(onPressed: () async { try { await widget.api.createBranch(widget.operatorId, name: _name.text.trim(), commissionBps: int.tryParse(_bps.text.trim())); _name.clear(); _bps.clear(); _load(); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create failed: $e')));} }, child: const Text('Add')),
        ]),
        const SizedBox(height: 12),
        Expanded(child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.builder(
            itemCount: _items.length,
            itemBuilder: (_, i){
              final b = _items[i];
              return Card(child: ListTile(
                title: Text(b['name'] ?? ''),
                subtitle: Text('Commission: ${b['commission_bps'] ?? '-'} bps'),
                trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async { try { await widget.api.deleteBranch(widget.operatorId, b['id']); _load(); } catch(e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e')));} }),
              ));
            },
          ),
        )),
      ]),
    );
  }
}

class AnalyticsTab extends StatefulWidget {
  final Api api; final String operatorId;
  const AnalyticsTab({super.key, required this.api, required this.operatorId});
  @override
  State<AnalyticsTab> createState() => _AnalyticsTabState();
}
class _AnalyticsTabState extends State<AnalyticsTab> {
  Map<String, dynamic>? _data;
  Future<void> _load() async { final d = await widget.api.analyticsRoutes(widget.operatorId, days: 30); setState(()=>_data=d); }
  @override
  void initState(){ super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    final d = _data; if (d==null) return const Center(child: CircularProgressIndicator());
    final routes = (d['routes'] as List).cast<Map>();
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Top Routes (last 30 days)', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Expanded(child: ListView.builder(
          itemCount: routes.length,
          itemBuilder: (_, i){
            final r = routes[i];
            return ListTile(title: Text(r['route'].toString()), subtitle: Text('confirmed: ${r['confirmed']}  total: ${r['total']}  revenue: ${(r['revenue_cents']/100).toStringAsFixed(2)}'));
          },
        ))
      ]),
    );
  }
}

class SettlementTab extends StatefulWidget {
  final Api api; final String operatorId;
  const SettlementTab({super.key, required this.api, required this.operatorId});
  @override
  State<SettlementTab> createState() => _SettlementTabState();
}
class _SettlementTabState extends State<SettlementTab> {
  Map<String, dynamic>? _data;
  DateTime? _from; DateTime? _to;
  Future<void> _load() async { final d = await widget.api.settlementsDaily(widget.operatorId, from: _from, to: _to); setState(()=>_data=d); }
  @override
  void initState(){ super.initState(); _load(); }
  @override
  Widget build(BuildContext context) {
    final d = _data; if (d==null) return const Center(child: CircularProgressIndicator());
    final daily = (d['daily'] as Map).cast<String, dynamic>();
    final branches = (d['branches'] as Map?)?.cast<String, dynamic>() ?? {};
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          OutlinedButton.icon(onPressed: () async { final now = DateTime.now(); final dd = await showDatePicker(context: context, initialDate: _from ?? now.subtract(const Duration(days: 7)), firstDate: now.subtract(const Duration(days: 365)), lastDate: now); if (dd!=null) setState(()=>_from = DateTime(dd.year,dd.month,dd.day)); }, icon: const Icon(Icons.date_range), label: Text(_from==null? 'From' : _from!.toLocal().toString().split(' ').first)),
          const SizedBox(width: 6),
          OutlinedButton.icon(onPressed: () async { final now = DateTime.now(); final dd = await showDatePicker(context: context, initialDate: _to ?? now, firstDate: now.subtract(const Duration(days: 365)), lastDate: now.add(const Duration(days: 1))); if (dd!=null) setState(()=>_to = DateTime(dd.year,dd.month,dd.day,23,59,59)); }, icon: const Icon(Icons.date_range), label: Text(_to==null? 'To' : _to!.toLocal().toString().split(' ').first)),
          const SizedBox(width: 8),
          FilledButton(onPressed: _load, child: const Text('Load')),
          const SizedBox(width: 8),
          OutlinedButton(onPressed: () async { try { final csv = await widget.api.settlementsDailyCsv(widget.operatorId, from: _from, to: _to); await downloadCsv(csv, 'settlements.csv'); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Export failed: $e')));} }, child: const Text('Export CSV')),
          const SizedBox(width: 8),
          OutlinedButton(onPressed: () async { try { final csv = await widget.api.settlementsBranchesCsv(widget.operatorId, from: _from, to: _to); await downloadCsv(csv, 'settlements_branches.csv'); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Branches CSV failed: $e')));} }, child: const Text('Export Branches CSV')),
        ]),
        const SizedBox(height: 12),
        const Text('Daily Totals', style: TextStyle(fontWeight: FontWeight.w600)),
        Expanded(child: Builder(builder: (_) {
          final ks = daily.keys.toList()..sort();
          return ListView(children: ks.map((k) {
            final rec = (daily[k] as Map).cast<String, dynamic>();
            return ListTile(title: Text(k), subtitle: Text('bookings: ${rec['bookings']}  revenue: ${(rec['gross_revenue_cents']/100).toStringAsFixed(2)}'));
          }).toList());
        })),
        const SizedBox(height: 8),
        const Text('By Branch', style: TextStyle(fontWeight: FontWeight.w600)),
        Expanded(child: ListView(children: branches.keys.map((bid){ final b = (branches[bid] as Map).cast<String, dynamic>(); return ListTile(title: Text(b['name']?.toString() ?? bid), subtitle: Text('revenue: ${(b['gross_revenue_cents']/100).toStringAsFixed(2)}  commission: ${(b['commission_cents']/100).toStringAsFixed(2)}  (${b['commission_bps'] ?? 0} bps)')); }).toList())),
      ]),
    );
  }
}

class WebhooksTab extends StatefulWidget {
  final Api api; final String operatorId;
  const WebhooksTab({super.key, required this.api, required this.operatorId});
  @override
  State<WebhooksTab> createState() => _WebhooksTabState();
}
class _WebhooksTabState extends State<WebhooksTab> {
  List<Map<String, dynamic>> _items = [];
  final _url = TextEditingController();
  final _secret = TextEditingController();
  bool _active = true;
  final _testPayload = TextEditingController(text: '{"event":"booking.confirmed","data":{"booking_id":"123"}}');
  String? _computedSig;
  Future<void> _load() async { final xs = await widget.api.listWebhooks(widget.operatorId); setState(()=>_items = xs); }
  @override
  void initState(){ super.initState(); _load(); }
  @override
  Widget build(BuildContext context){
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Webhooks', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: TextField(controller: _url, decoration: const InputDecoration(labelText: 'URL'))),
          const SizedBox(width: 8),
          SizedBox(width: 220, child: TextField(controller: _secret, decoration: const InputDecoration(labelText: 'Secret'))),
          const SizedBox(width: 8),
          Checkbox(value: _active, onChanged: (v){ setState(()=> _active = v ?? true); }), const Text('Active'),
          const SizedBox(width: 8),
          FilledButton(onPressed: () async { try { await widget.api.createWebhook(widget.operatorId, url: _url.text.trim(), secret: _secret.text.trim(), active: _active); _url.clear(); _secret.clear(); _active=true; _load(); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Create failed: $e')));} }, child: const Text('Add')),
        ]),
        const SizedBox(height: 12),
        const Text('Signature Test (HMAC-SHA256)', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: TextField(controller: _testPayload, maxLines: 2, decoration: const InputDecoration(labelText: 'Body JSON'))),
          const SizedBox(width: 8),
          FilledButton(onPressed: (){ final sig = hmacSignatureHex(_secret.text.trim(), _testPayload.text); setState(()=>_computedSig = 'sha256='+sig); }, child: const Text('Compute')),
          const SizedBox(width: 8),
          if (_computedSig != null) SelectableText(_computedSig!),
        ]),
        const SizedBox(height: 12),
        Expanded(child: RefreshIndicator(
          onRefresh: _load,
          child: ListView.builder(
            itemCount: _items.length,
            itemBuilder: (_, i){
              final w = _items[i];
              return Card(child: ListTile(
                title: Text(w['url'] ?? ''),
                subtitle: Text('Active: ${w['active']} • Created: ${w['created_at'] ?? ''}'),
                trailing: Wrap(spacing: 8, children:[
                  IconButton(icon: const Icon(Icons.toggle_on_outlined), onPressed: () async { try { await widget.api.updateWebhook(widget.operatorId, w['id'], url: w['url'], secret: '', active: !(w['active']==true)); _load(); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Toggle failed: $e')));} }),
                  IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async { try { await widget.api.deleteWebhook(widget.operatorId, w['id']); _load(); } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e')));} }),
                ]),
              ));
            },
          ),
        )),
      ]),
    );
  }
}

class _Kpi extends StatelessWidget {
  final String title; final String value;
  const _Kpi(this.title, this.value);
  @override
  Widget build(BuildContext context) {
    return Card(child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontSize: 20)),
      ]),
    ));
  }
}

class _BaseUrlDialog extends StatefulWidget {
  final String current;
  const _BaseUrlDialog({required this.current});
  @override
  State<_BaseUrlDialog> createState() => _BaseUrlDialogState();
}
class _BaseUrlDialogState extends State<_BaseUrlDialog> {
  late final TextEditingController _c = TextEditingController(text: widget.current);
  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('API Base URL'),
      content: TextField(controller: _c),
      actions: [
        TextButton(onPressed: ()=>Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: ()=>Navigator.pop(context, _c.text.trim()), child: const Text('Save')),
      ],
    );
  }
}
