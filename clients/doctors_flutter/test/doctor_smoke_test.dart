import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:doctors_flutter/api.dart';
import 'package:doctors_flutter/screens/doctor_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8089', tokenStore: TokenStore());
  @override
  Future<List<Map<String, dynamic>>> mySlots() async => [
    {'id':'s1','doctor_id':'d1','start_time':'2025-01-01T10:00:00Z','end_time':'2025-01-01T10:30:00Z','is_booked':false},
  ];
  @override
  Future<List<Map<String, dynamic>>> doctorAppointments() async => [];
}

void main() {
  testWidgets('DoctorScreen shows slots and actions', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: DoctorScreen(api: api))));
    await tester.pump();
    expect(find.textContaining('T10:00:00Z'), findsOneWidget);
    expect(find.text('Free'), findsOneWidget);
  });
}

