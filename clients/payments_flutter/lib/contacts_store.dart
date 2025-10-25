import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class ContactsStore {
  static const _key = 'contacts_json';

  Future<List<Map<String, String>>> load() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_key);
    if (raw == null || raw.isEmpty) return [];
    final List<dynamic> list = jsonDecode(raw);
    return list
        .whereType<Map<String, dynamic>>()
        .map((m) => {'name': (m['name'] ?? '') as String, 'phone': (m['phone'] ?? '') as String})
        .toList();
  }

  Future<void> save(List<Map<String, String>> contacts) async {
    final p = await SharedPreferences.getInstance();
    final raw = jsonEncode(contacts);
    await p.setString(_key, raw);
  }

  Future<void> add(String name, String phone) async {
    final list = await load();
    list.add({'name': name, 'phone': phone});
    await save(list);
  }

  Future<void> removeAt(int index) async {
    final list = await load();
    if (index < 0 || index >= list.length) return;
    list.removeAt(index);
    await save(list);
  }
}

