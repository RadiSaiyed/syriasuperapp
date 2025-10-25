import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:patient_flutter/api.dart';
import 'package:patient_flutter/screens/patient_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8089', tokenStore: TokenStore());
  @override
  Future<List<Map<String, dynamic>>> searchSlots({String? city, String? specialty, required String startTime, required String endTime}) async => [
    {'doctor_id':'d1','doctor_name':'Dr. Noor','specialty':'dentist','city':'Damascus','slot_id':'s1','start_time':startTime,'end_time':endTime},
  ];
  @override
  Future<Map<String, dynamic>> book(String slotId) async => {'id':'a1','slot_id':slotId,'status':'created'};
  @override
  Future<List<Map<String, dynamic>>> myAppointments() async => [{'id':'a1','slot_id':'s1','status':'created'}];
}

void main() {
  testWidgets('PatientScreen tabs render', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PatientScreen(api: api))));
    await tester.pump();
    expect(find.text('Search Slots'), findsOneWidget);
    expect(find.text('My Appointments'), findsOneWidget);
  });
}

