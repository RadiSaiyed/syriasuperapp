import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:jobs_flutter/api.dart';
import 'package:jobs_flutter/screens/seeker_screen.dart';

class _FakeApi extends ApiClient {
  _FakeApi(): super(baseUrl: 'http://localhost:8087', tokenStore: TokenStore());

  @override
  Future<List<Map<String, dynamic>>> listOpenJobs() async => [
    {'id': 'j1', 'company_id': 'c1', 'title': 'Software Engineer', 'location': 'Damascus', 'salary_cents': 1500000, 'status': 'open', 'created_at': DateTime.now().toIso8601String()},
  ];

  @override
  Future<Map<String, dynamic>> apply(String jobId, {String? coverLetter}) async => {
    'id': 'a1', 'job_id': jobId, 'user_id': 'u1', 'status': 'applied', 'cover_letter': coverLetter, 'created_at': DateTime.now().toIso8601String()
  };

  @override
  Future<List<Map<String, dynamic>>> myApplications() async => [
    {'id': 'a1', 'job_id': 'j1', 'user_id': 'u1', 'status': 'applied', 'cover_letter': 'Hallo', 'created_at': DateTime.now().toIso8601String()},
  ];
}

void main() {
  testWidgets('SeekerScreen shows open jobs and applications tabs', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SeekerScreen(api: api))));
    // Let FutureBuilders run
    await tester.pumpAndSettle(const Duration(milliseconds: 100));

    expect(find.text('Open Jobs'), findsOneWidget);
    expect(find.text('My Applications'), findsOneWidget);
    expect(find.text('Software Engineer'), findsOneWidget);

    // Switch to Applications tab and expect an item
    await tester.tap(find.text('My Applications'));
    await tester.pumpAndSettle(const Duration(milliseconds: 100));
    expect(find.textContaining('Application #').evaluate().isNotEmpty || find.textContaining('applied').evaluate().isNotEmpty, true);
  });
}
