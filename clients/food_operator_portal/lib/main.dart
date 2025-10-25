import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'api.dart';
import 'ui/glass.dart';

void main() {
  runApp(const OperatorPortalApp());
}

class OperatorPortalApp extends StatelessWidget {
  const OperatorPortalApp({super.key});
  @override
  Widget build(BuildContext context) {
    final seed = const Color(0xFF0A84FF);
    return MaterialApp(
      title: 'Food Operator',
      themeMode: ThemeMode.dark,
      theme: ThemeData(
        useMaterial3: true,
        textTheme: GoogleFonts.interTextTheme(),
        colorScheme:
            ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.light),
        scaffoldBackgroundColor: Colors.transparent,
        appBarTheme: const AppBarTheme(
            backgroundColor: Colors.transparent,
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            centerTitle: true),
        dialogTheme: DialogThemeData(
            backgroundColor: Colors.white.withValues(alpha: 0.16),
            surfaceTintColor: Colors.transparent,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16))),
        cardTheme: CardThemeData(
            color: Colors.white.withValues(alpha: 0.18),
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16))),
        inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: Colors.white.withValues(alpha: 0.08),
            border:
                OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
        bottomSheetTheme: const BottomSheetThemeData(
            backgroundColor: Colors.transparent,
            surfaceTintColor: Colors.transparent,
            elevation: 0),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        textTheme: GoogleFonts.interTextTheme(),
        colorScheme:
            ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark),
        scaffoldBackgroundColor: Colors.transparent,
        appBarTheme: const AppBarTheme(
            backgroundColor: Colors.transparent,
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            centerTitle: true),
        dialogTheme: DialogThemeData(
            backgroundColor: Colors.white.withValues(alpha: 0.08),
            surfaceTintColor: Colors.transparent,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16))),
        cardTheme: CardThemeData(
            color: Colors.white.withValues(alpha: 0.10),
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16))),
        inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: Colors.white.withValues(alpha: 0.06),
            border:
                OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
        bottomSheetTheme: const BottomSheetThemeData(
            backgroundColor: Colors.transparent,
            surfaceTintColor: Colors.transparent,
            elevation: 0),
      ),
      builder: (context, child) => Stack(children: [
        const LiquidBackground(),
        const LiquidGlassOverlay(opacity: 0.24, blur: 48),
        if (child != null) child,
      ]),
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
    Api.load().then((a) => setState(() => _api = a));
  }

  @override
  Widget build(BuildContext context) {
    return _api == null
        ? const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          )
        : LoginScreen(api: _api!);
  }
}

class LoginScreen extends StatefulWidget {
  final Api api;
  const LoginScreen({super.key, required this.api});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phone = TextEditingController(text: '+963900000010');
  final _otp = TextEditingController();
  bool _sent = false;
  String? _err;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Operator Login'),
        flexibleSpace: const Glass(
            padding: EdgeInsets.zero,
            blur: 24,
            opacity: 0.16,
            borderRadius: BorderRadius.zero),
        actions: [
          IconButton(
              icon: const Icon(Icons.settings),
              onPressed: () async {
                final url = await showDialog<String>(
                    context: context,
                    builder: (_) => _BaseUrlDialog(current: widget.api.baseUrl));
                if (url != null) {
                  await widget.api.setBaseUrl(url);
                  if (mounted) setState(() {});
                }
              })
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Glass(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                    controller: _phone,
                    decoration:
                        const InputDecoration(labelText: 'Phone (+963...)')),
                const SizedBox(height: 8),
                if (_sent)
                  TextField(
                      controller: _otp,
                      decoration:
                          const InputDecoration(labelText: 'OTP (123456)')),
                const SizedBox(height: 12),
                if (_err != null)
                  Text(_err!, style: const TextStyle(color: Colors.red)),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(
                      child: FilledButton(
                          onPressed: () async {
                            try {
                              await widget.api
                                  .requestOtp(_phone.text.trim());
                              setState(() => _sent = true);
                            } catch (e) {
                              setState(() => _err = '$e');
                            }
                          },
                          child: const Text('Send OTP'))),
                  const SizedBox(width: 12),
                  if (_sent)
                    Expanded(
                        child: FilledButton(
                            onPressed: () async {
                              try {
                                await widget.api.verifyOtp(
                                    _phone.text.trim(), _otp.text.trim(),
                                    name: 'Operator');
                                await widget.api.becomeOperatorAdmin();
                                if (!mounted) return;
                                Navigator.of(context).pushReplacement(
                                    MaterialPageRoute(
                                        builder: (_) => HomeScreen(
                                              api: widget.api,
                                            )));
                              } catch (e) {
                                setState(() => _err = '$e');
                              }
                            },
                            child: const Text('Login'))),
                ])
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
  int _tab = 0;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Food Operator'),
        flexibleSpace: const Glass(
            padding: EdgeInsets.zero,
            blur: 24,
            opacity: 0.16,
            borderRadius: BorderRadius.zero),
      ),
      body: IndexedStack(index: _tab, children: [
        RestaurantsTab(api: widget.api),
        OrdersTab(api: widget.api),
        SummaryTab(api: widget.api)
      ]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.store_mall_directory_outlined),
              label: 'Restaurants'),
          NavigationDestination(
              icon: Icon(Icons.receipt_long_outlined), label: 'Orders'),
          NavigationDestination(
              icon: Icon(Icons.query_stats_outlined), label: 'Summary')
        ],
      ),
    );
  }
}

class RestaurantsTab extends StatefulWidget {
  final Api api;
  const RestaurantsTab({super.key, required this.api});
  @override
  State<RestaurantsTab> createState() => _RestaurantsTabState();
}

class _RestaurantsTabState extends State<RestaurantsTab> {
  List<Map<String, dynamic>> _items = [];
  final _name = TextEditingController();
  final _city = TextEditingController();
  final _address = TextEditingController();
  final _owner = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final r = await widget.api.listRestaurants();
    setState(() => _items = r);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
          child: Glass(
            child: RefreshIndicator(
              onRefresh: _load,
              child: ListView.builder(
                  itemCount: _items.length,
                  itemBuilder: (_, i) {
                    final r = _items[i];
                    return GlassCard(
                        child: ListTile(
                            title: Text(r['name'] ?? ''),
                            subtitle: Text(
                                '${r['city'] ?? ''} • ${r['address'] ?? ''} (rating: ${r['rating_avg'] ?? '-'} / ${r['rating_count'] ?? 0})')));
                  }),
            ),
          ),
        ),
        const SizedBox(width: 12),
        SizedBox(
          width: 360,
          child: Glass(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Neues Restaurant',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                TextField(
                    controller: _name,
                    decoration: const InputDecoration(labelText: 'Name')),
                const SizedBox(height: 8),
                TextField(
                    controller: _city,
                    decoration: const InputDecoration(labelText: 'Stadt')),
                const SizedBox(height: 8),
                TextField(
                    controller: _address,
                    decoration: const InputDecoration(labelText: 'Adresse')),
                const SizedBox(height: 8),
                TextField(
                    controller: _owner,
                    decoration: const InputDecoration(
                        labelText: 'Owner Telefon (+963...)')),
                const SizedBox(height: 12),
                FilledButton(
                    onPressed: () async {
                      if (_name.text.trim().isEmpty) return;
                      await widget.api.createRestaurant(
                          name: _name.text.trim(),
                          city: _city.text.trim().isEmpty
                              ? null
                              : _city.text.trim(),
                          address: _address.text.trim().isEmpty
                              ? null
                              : _address.text.trim(),
                          ownerPhone: _owner.text.trim().isEmpty
                              ? null
                              : _owner.text.trim());
                      _name.clear();
                      _city.clear();
                      _address.clear();
                      _owner.clear();
                      _load();
                    },
                    child: const Text('Anlegen'))
              ],
            ),
          ),
        )
      ]),
    );
  }
}

class OrdersTab extends StatefulWidget {
  final Api api;
  const OrdersTab({super.key, required this.api});
  @override
  State<OrdersTab> createState() => _OrdersTabState();
}

class _OrdersTabState extends State<OrdersTab> {
  List<Map<String, dynamic>> _orders = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final o = await widget.api.listOrders();
    setState(() => _orders = o);
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(8),
        child: Glass(
          child: Row(children: [
            const Text('Alle Bestellungen'),
            const Spacer(),
            IconButton(icon: const Icon(Icons.refresh), onPressed: _load)
          ]),
        ),
      ),
      Expanded(
        child: Glass(
          child: ListView.builder(
            itemCount: _orders.length,
            itemBuilder: (_, i) {
              final o = _orders[i];
              return GlassCard(
                child: ListTile(
                  title: Text(
                      '${o['status']} • ${(o['total_cents'] / 100).toStringAsFixed(2)}'),
                  subtitle: Text(
                      'Restaurant: ${o['restaurant_id']} • Addresse: ${o['delivery_address'] ?? ''}'),
                ),
              );
            },
          ),
        ),
      )
    ]);
  }
}

class SummaryTab extends StatefulWidget {
  final Api api;
  const SummaryTab({super.key, required this.api});
  @override
  State<SummaryTab> createState() => _SummaryTabState();
}

class _SummaryTabState extends State<SummaryTab> {
  Map<String, dynamic>? _s;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final s = await widget.api.summary();
    setState(() => _s = s);
  }

  @override
  Widget build(BuildContext context) {
    final s = _s;
    if (s == null) return const Center(child: CircularProgressIndicator());
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Wrap(spacing: 16, runSpacing: 16, children: [
        _Kpi('Orders', '${s['orders_total']}'),
        _Kpi('Delivered', '${s['orders_delivered']}'),
        _Kpi('Revenue', (s['gross_revenue_cents'] / 100).toStringAsFixed(2)),
      ]),
    );
  }
}

class _Kpi extends StatelessWidget {
  final String title;
  final String value;
  const _Kpi(this.title, this.value, {super.key});
  @override
  Widget build(BuildContext context) {
    return Glass(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(fontSize: 20))
          ],
        ),
      ),
    );
  }
}

class _BaseUrlDialog extends StatefulWidget {
  final String current;
  const _BaseUrlDialog({required this.current});
  @override
  State<_BaseUrlDialog> createState() => _BaseUrlDialogState();
}

class _BaseUrlDialogState extends State<_BaseUrlDialog> {
  late final _c = TextEditingController(text: widget.current);
  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('API Base URL'),
      content: TextField(controller: _c),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Abbrechen')),
        FilledButton(
            onPressed: () => Navigator.pop(context, _c.text.trim()),
            child: const Text('Speichern'))
      ],
    );
  }
}
