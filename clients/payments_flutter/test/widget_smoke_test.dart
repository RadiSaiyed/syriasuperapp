import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:payments_flutter/screens/receive_qr_screen.dart';

void main() {
  testWidgets('ReceiveQrScreen builds', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ReceiveQrScreen(phone: '+963900000000')));
    expect(find.text('Receive (P2P)'), findsOneWidget);
  });
}

