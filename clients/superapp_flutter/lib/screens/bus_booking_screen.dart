import 'package:flutter/material.dart';
import '../ui/glass.dart';

class BusBookingScreen extends StatefulWidget {
  final Map<String, dynamic> journey;
  const BusBookingScreen({super.key, required this.journey});

  @override
  State<BusBookingScreen> createState() => _BusBookingScreenState();
}

class _BusBookingScreenState extends State<BusBookingScreen> {
  final _nameCtrl = TextEditingController(text: 'Guest');
  final _phoneCtrl = TextEditingController(text: '+963');
  int _seats = 1;

  @override
  Widget build(BuildContext context) {
    final j = widget.journey;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Booking'),
        flexibleSpace: const Glass(
            padding: EdgeInsets.zero,
            blur: 24,
            opacity: 0.16,
            borderRadius: BorderRadius.zero),
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Journey', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Text('${j['from']}  ${j['to']}'),
              Text('Date: ${j['date']}    Time: ${j['time']}'),
              Text('Operator: ${j['operator']}'),
              Text('Duration: ${j['duration_min']} min'),
              Text('Seats left: ${j['seats_left']}'),
              Text('Price: ${j['price_syp']} SYP per seat'),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        Glass(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Passenger', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
              const SizedBox(height: 8),
              TextField(controller: _phoneCtrl, decoration: const InputDecoration(labelText: 'Phone (+963...)'), keyboardType: TextInputType.phone),
              const SizedBox(height: 8),
              Row(children: [
                const Text('Seats:'),
                const SizedBox(width: 8),
                DropdownButton<int>(
                  value: _seats,
                  items: const [1, 2, 3, 4].map((e) => DropdownMenuItem(value: e, child: Text('$e'))).toList(),
                  onChanged: (v) => setState(() => _seats = v ?? 1),
                ),
                const Spacer(),
                Text('Total: ${_seats * (j['price_syp'] as int)} SYP'),
              ]),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Booking reserved (demo)')));
                },
                child: const Text('Reserve'),
              )
            ]),
          ),
        ),
      ]),
    );
  }
}

