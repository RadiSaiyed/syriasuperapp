import 'package:flutter/material.dart';
import '../api.dart';

class LoginScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback onLoggedIn;
  const LoginScreen({super.key, required this.api, required this.onLoggedIn});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _loading = false;
  Future<void> _devLogin() async { setState(()=>_loading=true); try { const phone='+963900000001'; await widget.api.requestOtp(phone); await widget.api.verifyOtp(phone: phone, otp:'123456', name:'User'); widget.onLoggedIn(); } catch(e){ if(mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));} finally { if(mounted) setState(()=>_loading=false);} }

  @override
  Widget build(BuildContext context) {
    return Center(child: FilledButton(onPressed: _loading?null:_devLogin, child: const Text('Continue')));
  }
}
