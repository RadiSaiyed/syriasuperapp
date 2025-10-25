import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:jobs_flutter/api.dart';
import 'package:jobs_flutter/screens/employer_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8087', tokenStore: TokenStore());

  @override
  Future<Map<String, dynamic>?> getCompany() async => {'id': 'c1', 'name': 'ACME', 'description': 'Test Co'};

  @override
  Future<List<Map<String, dynamic>>> myJobs() async => [
    {'id': 'j1', 'company_id': 'c1', 'title': 'QA Engineer', 'location': 'Aleppo', 'salary_cents': 800000, 'status': 'open', 'created_at': DateTime.now().toIso8601String()},
  ];

  @override
  Future<List<Map<String, dynamic>>> jobApplications(String jobId) async => [
    {'id': 'a1', 'job_id': jobId, 'user_id': 'u2', 'status': 'applied', 'cover_letter': 'Hi', 'created_at': DateTime.now().toIso8601String()},
  ];
}

void main() {
  testWidgets('EmployerScreen shows company and jobs, opens applications dialog', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: EmployerScreen(api: api))));
    await tester.pumpAndSettle(const Duration(milliseconds: 100));

    expect(find.text('ACME'), findsOneWidget);
    expect(find.text('QA Engineer'), findsOneWidget);

    // Tap job to open applications dialog
    await tester.tap(find.text('QA Engineer'));
    await tester.pumpAndSettle(const Duration(milliseconds: 100));

    expect(find.text('Applications'), findsOneWidget);
    expect(find.textContaining('applied'), findsOneWidget);
  });
}
