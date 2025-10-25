import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:carmarket_flutter/api.dart';
import 'package:carmarket_flutter/screens/login_screen.dart';
void main(){ testWidgets('Login renders', (t) async { final api=ApiClient(baseUrl:'http://localhost:8086', tokenStore: TokenStore()); await t.pumpWidget(MaterialApp(home: Scaffold(body: LoginScreen(api: api, onLoggedIn: (){})))); expect(find.text('Login'), findsOneWidget);});}
