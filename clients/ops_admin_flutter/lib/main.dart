import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_ui/shared_ui.dart';
import 'package:shared_ui/message_host.dart';
import 'package:shared_ui/toast.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

class App extends StatelessWidget {
  const App({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SuperApp Admin',
      themeMode: ThemeMode.dark,
      darkTheme: SharedTheme.dark(),
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blueGrey),
      scaffoldMessengerKey: MessageHost.messengerKey,
      home: MessageHost(child: const _Home()),
    );
  }
}

class _Home extends StatefulWidget {
  const _Home();
  @override State<_Home> createState() => _HomeState();
}

class _HomeState extends State<_Home> {
  int _tab = 0;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('SuperApp Admin')),
      body: Column(children: [
        NavigationBar(selectedIndex: _tab, onDestinationSelected: (i)=>setState(()=>_tab=i), destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Overview'),
          NavigationDestination(icon: Icon(Icons.payment_outlined), label: 'Payments'),
          NavigationDestination(icon: Icon(Icons.local_taxi_outlined), label: 'Taxi'),
        ]),
        const Divider(height: 1),
        Expanded(child: _tab==0 ? const OverviewTab() : _tab==1 ? const PaymentsTab() : const TaxiTab()),
      ]),
    );
  }
}

class OverviewTab extends StatelessWidget {
  const OverviewTab({super.key});
  @override Widget build(BuildContext context) => const Center(child: Text('Ops-Admin Overview'));
}

class PaymentsTab extends StatefulWidget { const PaymentsTab({super.key}); @override State<PaymentsTab> createState()=>_PaymentsTabState(); }
class _PaymentsTabState extends State<PaymentsTab> {
  final _baseCtrl = TextEditingController();
  final _userCtrl = TextEditingController(text: 'admin');
  final _passCtrl = TextEditingController(text: 'admin');
  String? _jwt; bool _loading=false;

  static const _kPB='payments_admin_base'; static const _kPJ='payments_dev_jwt';
  @override void initState(){ super.initState(); _load(); }
  Future<void> _load() async { final p=await SharedPreferences.getInstance(); setState((){ _baseCtrl.text=p.getString(_kPB)??'http://localhost:8080'; _jwt=p.getString(_kPJ); }); }
  Future<void> _saveBase() async { final p=await SharedPreferences.getInstance(); await p.setString(_kPB, _baseCtrl.text.trim()); }
  String get _b => _baseCtrl.text.trim().replaceAll(RegExp(r"/+$"), "");
  void _toast(String m){ if(!mounted) return; showToast(context, m); }

  Future<void> _devLogin() async {
    await _saveBase(); setState(()=>_loading=true);
    try{
      final uri = Uri.parse('$_b/auth/dev_login');
      final r = await http.post(uri, headers:{'Content-Type':'application/json'}, body: jsonEncode({'username': _userCtrl.text.trim(), 'password': _passCtrl.text.trim()})).timeout(const Duration(seconds:5));
      if(r.statusCode>=400) throw r.body; final js=(jsonDecode(r.body) as Map).cast<String,dynamic>();
      final tok=(js['access_token'] as String?)??''; if(tok.isEmpty) throw 'no token';
      final p=await SharedPreferences.getInstance(); await p.setString(_kPJ, tok); setState(()=>_jwt=tok); _toast('Logged in');
    } catch(e){ _toast('Login failed: $e'); } finally { if(mounted) setState(()=>_loading=false);} }

  Future<void> _logout() async {
    setState(()=>_loading=true);
    try {
      final p = await SharedPreferences.getInstance();
      await p.remove(_kPJ);
      if (mounted) setState(()=>_jwt = null);
      _toast('Logged out');
    } catch (_) {} finally { if(mounted) setState(()=>_loading=false); }
  }

  @override Widget build(BuildContext context){
    return Padding(padding: const EdgeInsets.all(12), child: ListView(children:[
      if(_loading) const LinearProgressIndicator(),
      const Text('Payments Dev Login', style: TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height:6),
      Row(children:[ Expanded(child: TextField(controller:_baseCtrl, decoration: const InputDecoration(labelText:'Payments Base URL', hintText:'http://localhost:8080'))), const SizedBox(width:8), FilledButton(onPressed:_saveBase, child: const Text('Save')) ]),
      const SizedBox(height:8),
      Row(children:[ SizedBox(width:180, child: TextField(controller:_userCtrl, decoration: const InputDecoration(labelText:'Username'))), const SizedBox(width:8), SizedBox(width:180, child: TextField(controller:_passCtrl, decoration: const InputDecoration(labelText:'Password'), obscureText:true)), const SizedBox(width:8), FilledButton(onPressed:_devLogin, child: const Text('Dev Login')), const SizedBox(width:8), OutlinedButton(onPressed: (_jwt==null||_jwt!.isEmpty)? null : _logout, child: const Text('Logout')) ]),
      if((_jwt??'').isNotEmpty) Padding(padding: const EdgeInsets.only(top:8), child: Text('JWT saved: ${_jwt!.substring(0,16)}…')),
    ]));
  }
}

class TaxiTab extends StatefulWidget { const TaxiTab({super.key}); @override State<TaxiTab> createState()=>_TaxiTabState(); }
class _TaxiTabState extends State<TaxiTab> {
  final _baseCtrl = TextEditingController();
  final _admCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController(text: '+963900000010');
  final _usernameCtrl = TextEditingController(text: 'driver');
  final _passwordCtrl = TextEditingController(text: 'driver');
  final _nameCtrl = TextEditingController();
  final _vehMakeCtrl = TextEditingController();
  final _vehPlateCtrl = TextEditingController();
  final List<String> _classes = const ['standard','comfort','yellow','vip','van','electro'];
  String _rideClass = 'standard';
  bool _loading=false;
  Map<String,dynamic>? _driver; List<Map<String,dynamic>> _report=[]; List<Map<String,dynamic>> _drivers=[];
  String _filterClass = '';
  final _filterQ = TextEditingController();
  String? _jwt;

  static const _kTB='taxi_admin_base'; static const _kTT='taxi_admin_token'; static const _kTJ='taxi_dev_jwt';
  @override void initState(){ super.initState(); _load(); }
  Future<void> _load() async { final p=await SharedPreferences.getInstance(); setState((){ _baseCtrl.text = p.getString(_kTB)??'http://localhost:8081'; _admCtrl.text = p.getString(_kTT)??''; _jwt = p.getString(_kTJ); }); }
  Future<void> _saveBaseTok() async { final p=await SharedPreferences.getInstance(); await p.setString(_kTB,_baseCtrl.text.trim()); await p.setString(_kTT,_admCtrl.text.trim()); }
  String get _b => _baseCtrl.text.trim().replaceAll(RegExp(r"/+$"), "");
  Map<String,String> _adminHeaders()=>{'Content-Type':'application/json','X-Admin-Token':_admCtrl.text.trim()};
  void _toast(String m){ if(!mounted) return; showToast(context, m); }

  Future<void> _devLogin() async {
    await _saveBaseTok(); setState(()=>_loading=true);
    try{
      final uri = Uri.parse('$_b/auth/dev_login');
      final r = await http.post(uri, headers:{'Content-Type':'application/json'}, body: jsonEncode({'username': _usernameCtrl.text.trim(), 'password': _passwordCtrl.text.trim()})).timeout(const Duration(seconds:5));
      if(r.statusCode>=400) throw r.body; _toast('Dev login OK');
      final js = (jsonDecode(r.body) as Map).cast<String,dynamic>();
      final tok = (js['access_token'] as String?)??''; if(tok.isNotEmpty){ final p=await SharedPreferences.getInstance(); await p.setString(_kTJ, tok); if(mounted) setState(()=>_jwt = tok); }
    } catch(e){ _toast('Login failed: $e'); } finally { if(mounted) setState(()=>_loading=false); }
  }

  Future<void> _logout() async {
    setState(()=>_loading=true);
    try{ final p=await SharedPreferences.getInstance(); await p.remove(_kTJ); if(mounted) setState(()=>_jwt=null); _toast('Logged out'); } catch(_){ } finally { if(mounted) setState(()=>_loading=false); }
  }

  Future<void> _setDriverClass() async {
    await _saveBaseTok(); setState(()=>_loading=true);
    try{
      final body = jsonEncode({'driver_phone': _phoneCtrl.text.trim(), 'ride_class': _rideClass});
      final r = await http.post(Uri.parse('$_b/admin/driver/set_class'), headers: _adminHeaders(), body: body).timeout(const Duration(seconds:5));
      if(r.statusCode>=400) throw r.body; _toast('Set driver class: ${r.statusCode}');
      await _loadDriver();
    } catch(e){ _toast('Error: $e'); } finally { if(mounted) setState(()=>_loading=false);} }

  Future<void> _loadDriver() async {
    await _saveBaseTok(); setState(()=>_loading=true);
    try{
      final uri=Uri.parse('$_b/admin/user').replace(queryParameters:{'phone':_phoneCtrl.text.trim()});
      final r=await http.get(uri, headers:_adminHeaders()).timeout(const Duration(seconds:5));
      if(r.statusCode>=400) throw r.body; setState(()=>_driver=(jsonDecode(r.body) as Map).cast<String,dynamic>());
    } catch(e){ _toast('Load user failed'); } finally { if(mounted) setState(()=>_loading=false);} }

  Future<void> _loadReport() async {
    await _saveBaseTok(); setState(()=>_loading=true);
    try{
      final r=await http.get(Uri.parse('$_b/admin/report/ride_classes'), headers:_adminHeaders()).timeout(const Duration(seconds:5));
      if(r.statusCode>=400) throw r.body; final js=(jsonDecode(r.body) as Map).cast<String,dynamic>();
      setState(()=>_report=((js['items'] as List?)??[]).cast<Map<String,dynamic>>());
    } catch(e){ _toast('Report failed'); } finally { if(mounted) setState(()=>_loading=false);} }

  Future<void> _exportReportCsv() async {
    try{
      if(_report.isEmpty){ _toast('Report is empty'); return; }
      final buf = StringBuffer('ride_class,count,sum_quoted_cents,sum_final_cents\n');
      for(final it in _report){ buf.writeln('${(it['ride_class']??'')},${it['count']??0},${it['sum_quoted_cents']??0},${it['sum_final_cents']??0}'); }
      final dir = await getApplicationDocumentsDirectory();
      final ts = DateTime.now().toIso8601String().replaceAll(':','-');
      final f = File('${dir.path}/taxi_class_report_$ts.csv');
      await f.writeAsString(buf.toString());
      _toast('Saved ${f.path}');
    } catch(e){ _toast('Export failed: $e'); }
  }

  Future<void> _promoteDriver() async {
    await _saveBaseTok(); setState(()=>_loading=true);
    try{
      final body = jsonEncode({
        'phone': _phoneCtrl.text.trim(),
        if(_nameCtrl.text.trim().isNotEmpty) 'name': _nameCtrl.text.trim(),
        'ride_class': _rideClass,
        if(_vehMakeCtrl.text.trim().isNotEmpty) 'vehicle_make': _vehMakeCtrl.text.trim(),
        if(_vehPlateCtrl.text.trim().isNotEmpty) 'vehicle_plate': _vehPlateCtrl.text.trim(),
      });
      final r = await http.post(Uri.parse('$_b/admin/driver/promote'), headers: _adminHeaders(), body: body).timeout(const Duration(seconds:5));
      if(r.statusCode>=400) throw r.body; _toast('Promoted/created');
      await _loadDriver();
    } catch(e){ _toast('Promote failed: $e'); } finally { if(mounted) setState(()=>_loading=false); }
  }

  Future<void> _loadDrivers() async {
    await _saveBaseTok(); setState(()=>_loading=true);
    try{
      final qp = <String,String>{ 'limit':'200' };
      if(_filterClass.isNotEmpty) qp['ride_class'] = _filterClass;
      if(_filterQ.text.trim().isNotEmpty) qp['q'] = _filterQ.text.trim();
      final uri = Uri.parse('$_b/admin/drivers').replace(queryParameters: qp);
      final r = await http.get(uri, headers: _adminHeaders()).timeout(const Duration(seconds:5));
      if(r.statusCode>=400) throw r.body; final js=(jsonDecode(r.body) as Map).cast<String,dynamic>();
      setState(()=>_drivers=((js['items'] as List?)??[]).cast<Map<String,dynamic>>());
    } catch(e){ _toast('Load drivers failed'); } finally { if(mounted) setState(()=>_loading=false);} }

  @override Widget build(BuildContext context){
    return Padding(padding: const EdgeInsets.all(12), child: ListView(children: [
      if(_loading) const LinearProgressIndicator(),
      const Text('Taxi Admin', style: TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height:6),
      Row(children:[ Expanded(child: TextField(controller:_baseCtrl, decoration: const InputDecoration(labelText:'Taxi Base URL', hintText:'http://localhost:8081'))), const SizedBox(width:8), Expanded(child: TextField(controller:_admCtrl, decoration: const InputDecoration(labelText:'X-Admin-Token'))), const SizedBox(width:8), FilledButton(onPressed:_saveBaseTok, child: const Text('Save')) ]),
      const SizedBox(height:8),
      Row(children:[ SizedBox(width:180, child: TextField(controller:_usernameCtrl, decoration: const InputDecoration(labelText:'Username'))), const SizedBox(width:8), SizedBox(width:180, child: TextField(controller:_passwordCtrl, decoration: const InputDecoration(labelText:'Password'), obscureText: true)), const SizedBox(width:8), FilledButton(onPressed:_devLogin, child: const Text('Dev Login')), const SizedBox(width:8), OutlinedButton(onPressed: (_jwt==null||_jwt!.isEmpty)? null : _logout, child: const Text('Logout')) ]),
      if((_jwt??'').isNotEmpty) Padding(padding: const EdgeInsets.only(top:8), child: Text('JWT saved: ${_jwt!.substring(0,16)}…')),
      const SizedBox(height:16), const Divider(),
      const Text('Create/Promote Driver', style: TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height:6),
      Row(children:[ Expanded(child: TextField(controller:_phoneCtrl, decoration: const InputDecoration(labelText:'Driver phone (+963...)'))), const SizedBox(width:8), Expanded(child: TextField(controller:_nameCtrl, decoration: const InputDecoration(labelText:'Name (optional)'))), ]),
      const SizedBox(height:6),
      Row(children:[ Expanded(child: TextField(controller:_vehMakeCtrl, decoration: const InputDecoration(labelText:'Vehicle make'))), const SizedBox(width:8), Expanded(child: TextField(controller:_vehPlateCtrl, decoration: const InputDecoration(labelText:'Vehicle plate'))), ]),
      const SizedBox(height:6),
      Row(children:[ DropdownButton<String>(value:_rideClass, items:_classes.map((c)=>DropdownMenuItem(value:c, child: Text(c.toUpperCase()))).toList(), onChanged:(v)=>setState(()=>_rideClass=v??_rideClass)), const SizedBox(width:8), FilledButton(onPressed:_promoteDriver, child: const Text('Promote/Create')), const SizedBox(width:8), OutlinedButton(onPressed:_setDriverClass, child: const Text('Set Class Only')) ]),
      const SizedBox(height:8),
      Row(children:[ OutlinedButton(onPressed:_loadDriver, child: const Text('Load user')), const SizedBox(width:8), if(_driver!=null) Text('Driver class: ${((_driver?['driver']??{}) as Map?)?['ride_class'] ?? '-'}') ]),
      const SizedBox(height:16), const Divider(),
      const Text('Ride Classes Report', style: TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height:6),
      Row(children:[ FilledButton(onPressed:_loadReport, child: const Text('Load report')), const SizedBox(width:8), OutlinedButton(onPressed:_exportReportCsv, child: const Text('Export CSV')) ]),
      const SizedBox(height:6),
      ..._report.map((it)=>ListTile(title: Text((it['ride_class']??'—').toString()), subtitle: Text('count: ${it['count']}'), trailing: Text('Σ quoted: ${it['sum_quoted_cents']}  Σ final: ${it['sum_final_cents']}'))),
      const SizedBox(height:16), const Divider(),
      const Text('Drivers by Class', style: TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height:6),
      Row(children:[ DropdownButton<String>(value: _filterClass.isEmpty? null : _filterClass, hint: const Text('class (any)'), items:(['']+_classes).map((c)=>DropdownMenuItem(value:c, child: Text(c.isEmpty? 'ANY' : c.toUpperCase()))).toList(), onChanged:(v)=>setState(()=>_filterClass = (v??''))), const SizedBox(width:8), SizedBox(width:220, child: TextField(controller:_filterQ, decoration: const InputDecoration(labelText:'Phone/Name contains'))), const SizedBox(width:8), FilledButton(onPressed:_loadDrivers, child: const Text('Load drivers')) ]),
      const SizedBox(height:6),
      ..._drivers.map((d)=>ListTile(title: Text('${d['phone']??''} ${d['name']??''}'), subtitle: Text('status: ${d['status']}'), trailing: Text('class: ${d['ride_class']??'-'}'))),
    ]));
  }
}
