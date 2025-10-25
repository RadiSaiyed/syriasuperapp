import 'package:flutter/material.dart';
import '../contacts_store.dart';

class ContactsScreen extends StatefulWidget {
  final void Function(String phone)? onTransfer;
  final void Function(String phone)? onRequest;
  const ContactsScreen({super.key, this.onTransfer, this.onRequest});

  @override
  State<ContactsScreen> createState() => _ContactsScreenState();
}

class _ContactsScreenState extends State<ContactsScreen> {
  final _store = ContactsStore();
  List<Map<String, String>> _contacts = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final list = await _store.load();
    if (mounted) setState(() { _contacts = list; _loading = false;});
  }

  Future<void> _addContact() async {
    final nameCtrl = TextEditingController();
    final phoneCtrl = TextEditingController(text: '+963');
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Add contact'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
          TextField(controller: phoneCtrl, decoration: const InputDecoration(labelText: 'Phone')), 
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Add')),
        ],
      ),
    );
    if (ok == true) {
      await _store.add(nameCtrl.text.trim(), phoneCtrl.text.trim());
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Contacts'), actions: [
        IconButton(onPressed: _addContact, icon: const Icon(Icons.person_add))
      ]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _contacts.isEmpty
              ? const Center(child: Text('No contacts yet'))
              : ListView.separated(
                  itemCount: _contacts.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final c = _contacts[i];
                    return ListTile(
                      title: Text(c['name']!.isEmpty ? c['phone']! : c['name']!),
                      subtitle: Text(c['phone'] ?? ''),
                      trailing: Wrap(spacing: 8, children: [
                        IconButton(
                          icon: const Icon(Icons.send),
                          tooltip: 'Transfer',
                          onPressed: () => widget.onTransfer?.call(c['phone']!),
                        ),
                        IconButton(
                          icon: const Icon(Icons.request_page),
                          tooltip: 'Request',
                          onPressed: () => widget.onRequest?.call(c['phone']!),
                        ),
                        IconButton(
                          icon: const Icon(Icons.delete_outline),
                          tooltip: 'Remove',
                          onPressed: () async {
                            await _store.removeAt(i);
                            await _load();
                          },
                        )
                      ]),
                    );
                  },
                ),
    );
  }
}
