import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'api.dart';

void main(){ runApp(const VendorPortalApp()); }

class VendorPortalApp extends StatelessWidget{
  const VendorPortalApp({super.key});
  @override Widget build(BuildContext context){
    return MaterialApp(title: 'Food Vendor Portal', theme: ThemeData(useMaterial3: true, textTheme: GoogleFonts.interTextTheme(), colorSchemeSeed: const Color(0xFF0A84FF)), home: const _Root());
  }
}

class _Root extends StatefulWidget{ const _Root(); @override State<_Root> createState()=>_RootState(); }
class _RootState extends State<_Root>{ Api? _api; @override void initState(){ super.initState(); Api.load().then((a)=>setState(()=>_api=a)); }
  @override Widget build(BuildContext context){ return _api==null? const Scaffold(body: Center(child:CircularProgressIndicator())): LoginScreen(api: _api!);} }

class LoginScreen extends StatefulWidget{ final Api api; const LoginScreen({super.key, required this.api}); @override State<LoginScreen> createState()=>_LoginScreenState(); }
class _LoginScreenState extends State<LoginScreen>{ final _phone=TextEditingController(text:'+963900000001'); final _otp=TextEditingController(); bool _sent=false; String? _err;
  @override Widget build(BuildContext context){
    return Scaffold(appBar: AppBar(title: const Text('Vendor Login'), actions:[IconButton(icon: const Icon(Icons.settings), onPressed: () async { final url = await showDialog<String>(context: context, builder: (_)=>_BaseUrlDialog(current: widget.api.baseUrl)); if(url!=null){ await widget.api.setBaseUrl(url); setState((){});} })]),
      body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 420), child: Padding(padding: const EdgeInsets.all(16), child: Column(mainAxisSize: MainAxisSize.min, children:[
        TextField(controller:_phone, decoration: const InputDecoration(labelText:'Phone (+963...)')),
        const SizedBox(height:8), if(_sent) TextField(controller:_otp, decoration: const InputDecoration(labelText:'OTP (123456)')),
        const SizedBox(height:12), if(_err!=null) Text(_err!, style: const TextStyle(color:Colors.red)), const SizedBox(height:12),
        Row(children:[FilledButton(onPressed:() async { try{ await widget.api.requestOtp(_phone.text.trim()); setState(()=>_sent=true); }catch(e){ setState(()=>_err='$e'); } }, child: const Text('Send OTP')), const SizedBox(width:12), if(_sent) FilledButton(onPressed:() async{ try{ await widget.api.verifyOtp(_phone.text.trim(), _otp.text.trim(), name:'Vendor'); if(!context.mounted)return; Navigator.of(context).pushReplacement(MaterialPageRoute(builder:(_)=>HomeScreen(api: widget.api))); }catch(e){ setState(()=>_err='$e'); } }, child: const Text('Login'))])
      ])))));
  }
}

class HomeScreen extends StatefulWidget{ final Api api; const HomeScreen({super.key, required this.api}); @override State<HomeScreen> createState()=>_HomeScreenState(); }
class _HomeScreenState extends State<HomeScreen>{ int _tab=0; String? _restaurantId; @override Widget build(BuildContext context){ return Scaffold(appBar: AppBar(title: const Text('Vendor')), body: IndexedStack(index:_tab, children:[
  RestaurantsTab(api: widget.api, onPick: (id)=> setState(()=>_restaurantId=id)),
  MenuTab(api: widget.api, restaurantId: _restaurantId),
  OrdersTab(api: widget.api),
]), bottomNavigationBar: NavigationBar(selectedIndex:_tab, onDestinationSelected:(i)=>setState(()=>_tab=i), destinations: const [NavigationDestination(icon: Icon(Icons.storefront_outlined), label:'Restaurants'), NavigationDestination(icon: Icon(Icons.restaurant_menu), label:'Menu'), NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label:'Orders')],)); }
}

class RestaurantsTab extends StatefulWidget{ final Api api; final void Function(String id) onPick; const RestaurantsTab({super.key, required this.api, required this.onPick}); @override State<RestaurantsTab> createState()=>_RestaurantsTabState(); }
class _RestaurantsTabState extends State<RestaurantsTab>{ List<Map<String,dynamic>> _items=[]; @override void initState(){ super.initState(); _load(); } Future<void> _load() async{ final r = await widget.api.myRestaurants(); setState(()=>_items=r); }
  @override Widget build(BuildContext context){ return RefreshIndicator(onRefresh:_load, child: ListView.builder(itemCount:_items.length, itemBuilder: (_,i){ final r=_items[i]; return Card(child: ListTile(title: Text(r['name']??''), subtitle: Text('${r['city']??''}  •  ${r['address']??''}'), onTap: ()=>widget.onPick(r['id']))); })); }
}

class MenuTab extends StatefulWidget{ final Api api; final String? restaurantId; const MenuTab({super.key, required this.api, required this.restaurantId}); @override State<MenuTab> createState()=>_MenuTabState(); }
class _MenuTabState extends State<MenuTab>{ List<Map<String,dynamic>> _menu=[]; final _name=TextEditingController(); final _price=TextEditingController(text:'10000');
  Future<void> _load() async { if(widget.restaurantId==null){ setState(()=>_menu=[]); return; } final m = await widget.api.menuAll(widget.restaurantId!); setState(()=>_menu=m); }
  @override void didUpdateWidget(covariant MenuTab old){ super.didUpdateWidget(old); if(old.restaurantId!=widget.restaurantId) _load(); }
  @override Widget build(BuildContext context){ if(widget.restaurantId==null) return const Center(child: Text('Restaurant wählen')); return Padding(padding: const EdgeInsets.all(12), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children:[
    Expanded(child: RefreshIndicator(onRefresh:_load, child: ListView.builder(itemCount:_menu.length, itemBuilder:(_,i){ final m=_menu[i]; return Card(child: ListTile(title: Text(m['name']??''), subtitle: Text('Preis: ${(m['price_cents']/100).toStringAsFixed(2)}  •  Verfügbar: ${m['available']}'), trailing: Row(mainAxisSize: MainAxisSize.min, children:[ IconButton(icon: const Icon(Icons.edit), onPressed: () async{ await widget.api.updateMenuItem(m['id'], priceCents: (m['price_cents'] as int)+1000); _load(); }), IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async{ await widget.api.deleteMenuItem(m['id']); _load(); }) ]))); }))),
    const SizedBox(width:12),
    SizedBox(width:300, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[ const Text('Neues Menü‑Item', style: TextStyle(fontWeight: FontWeight.w600)), TextField(controller:_name, decoration: const InputDecoration(labelText:'Name')), TextField(controller:_price, decoration: const InputDecoration(labelText:'Preis (Cent)')), const SizedBox(height:8), FilledButton(onPressed: () async { final p = int.tryParse(_price.text.trim())??0; if(p<=0||_name.text.trim().isEmpty) return; await widget.api.createMenuItem(widget.restaurantId!, name:_name.text.trim(), priceCents:p); _name.clear(); _load(); }, child: const Text('Erstellen')) ]))
  ])); }
}

class OrdersTab extends StatefulWidget{ final Api api; const OrdersTab({super.key, required this.api}); @override State<OrdersTab> createState()=>_OrdersTabState(); }
class _OrdersTabState extends State<OrdersTab>{ List<Map<String,dynamic>> _orders=[]; @override void initState(){ super.initState(); _load(); } Future<void> _load() async{ final o = await widget.api.listOrders(); setState(()=>_orders=o); }
  @override Widget build(BuildContext context){ return Column(children:[ Padding(padding: const EdgeInsets.all(8), child: Row(children:[ const Text('Bestellungen'), const Spacer(), IconButton(icon: const Icon(Icons.refresh), onPressed:_load) ])), Expanded(child: ListView.builder(itemCount:_orders.length, itemBuilder:(_,i){ final o=_orders[i]; return Card(child: ListTile(title: Text('${o['status']} • ${(o['total_cents']/100).toStringAsFixed(2)}'), subtitle: Text('Restaurant: ${o['restaurant_id']}  •  ${o['delivery_address']??''}'), trailing: PopupMenuButton<String>(onSelected: (s) async{ await widget.api.setOrderStatus(o['id'], s); _load(); }, itemBuilder:(_)=> const [PopupMenuItem(value:'accepted', child: Text('accept')), PopupMenuItem(value:'preparing', child: Text('preparing')), PopupMenuItem(value:'out_for_delivery', child: Text('out_for_delivery')), PopupMenuItem(value:'delivered', child: Text('delivered')), PopupMenuItem(value:'canceled', child: Text('canceled')) ]))); })) ]);
  }
}

class _BaseUrlDialog extends StatefulWidget{ final String current; const _BaseUrlDialog({required this.current}); @override State<_BaseUrlDialog> createState()=>_BaseUrlDialogState(); }
class _BaseUrlDialogState extends State<_BaseUrlDialog>{ late final _c = TextEditingController(text: widget.current); @override Widget build(BuildContext context){ return AlertDialog(title: const Text('API Base URL'), content: TextField(controller:_c), actions:[ TextButton(onPressed: ()=>Navigator.pop(context), child: const Text('Abbrechen')), FilledButton(onPressed: ()=>Navigator.pop(context,_c.text.trim()), child: const Text('Speichern')) ]); }
}

