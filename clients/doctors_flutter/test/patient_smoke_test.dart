import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:doctors_flutter/api.dart';
import 'package:doctors_flutter/screens/patient_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8089', tokenStore: TokenStore());

  @override
  Future<List<Map<String, dynamic>>> searchSlots({String? doctorId, String? city, String? specialty, required String startTime, required String endTime}) async => [
    {'doctor_id':'d1','doctor_name':'Dr. Noor','specialty':'dentist','city':'Damascus','slot_id':'s1','start_time':startTime,'end_time':endTime},
  ];

  @override
  Future<Map<String, dynamic>> book(String slotId) async => {'id':'a1','doctor_id':'d1','patient_user_id':'u1','slot_id':slotId,'status':'created'};

  @override
  Future<List<Map<String, dynamic>>> myAppointments() async => [
    {'id':'a1','doctor_id':'d1','patient_user_id':'u1','slot_id':'s1','status':'created'},
  ];
}

void main() {
  testWidgets('PatientScreen shows search and appointments', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PatientScreen(api: api))));
    await tester.pump();
    expect(find.text('Search Slots'), findsOneWidget);
    expect(find.text('My Appointments'), findsOneWidget);
  });
}

