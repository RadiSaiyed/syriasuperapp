import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/services.dart';
import 'package:shared_ui/glass.dart';
import 'package:shared_ui/toast.dart';
import '../services.dart';
import '../apps/stays_api.dart';
import '../map_view.dart';
import 'package:latlong2/latlong.dart';
import 'package:flutter_map/flutter_map.dart';
import '../ui/errors.dart';
import '../animations.dart';

class StaysScreen extends StatefulWidget {
  final String? initialCity;
  final String? initialCheckIn;
  final String? initialCheckOut;
  final String? initialGuests;
  final String? initialPropertyId;
  const StaysScreen({super.key, this.initialCity, this.initialCheckIn, this.initialCheckOut, this.initialGuests, this.initialPropertyId});
  @override
  State<StaysScreen> createState() => _StaysScreenState();
}

class _StaysScreenState extends State<StaysScreen> {
  static const _service = 'stays';
  final _api = StaysApi();
  final _tokens = MultiTokenStore();
  bool _loading = false;
  String _health = '?';
  bool _authed = false;
  // Search inputs
  final _city = TextEditingController(text: 'Damascus');
  final _checkIn = TextEditingController();
  final _checkOut = TextEditingController();
  final _guests = TextEditingController(text: '2');
  // Filters
  String _type = 'any';
  final _minPrice = TextEditingController();
  final _maxPrice = TextEditingController();
  final _capacityMin = TextEditingController();
  final _amenities = TextEditingController();
  String _amenitiesMode = 'any';
  // Property name cache
  final Map<String, String> _propNameCache = {};
  // Price slider (SYP cents)
  RangeValues _priceRange = const RangeValues(0, 200000);
  static const double _priceMinBound = 0;
  static const double _priceMaxBound = 1000000;
  // Quick amenity chips
  final Set<String> _amenityChips = {
    'wifi',
    'ac',
    'parking',
    'kitchen',
    'pool',
    'pet_friendly'
  };
  final Set<String> _selectedAmenities = {};
  void _clearFilters() {
    setState(() {
      _type = 'any';
      _minPrice.clear();
      _maxPrice.clear();
      _capacityMin.clear();
      _amenities.clear();
      _selectedAmenities.clear();
      _amenitiesMode = 'any';
      _priceRange = const RangeValues(_priceMinBound, 200000);
    });
  }

  // Map + coords cache
  final MapController _mapCtrl = MapController();
  final Map<String, LatLng> _propCoords = {}; // property_id -> LatLng
  bool _showMap = false;
  List<Map<String, dynamic>> _results = [];
  List<Map<String, dynamic>> _reservations = [];
  List<Map<String, dynamic>> _favorites = [];
  Set<String> get _favoriteIds => _favorites
      .map((e) => (e['id'] ?? e['property_id'] ?? e['id']).toString())
      .toSet();
  int? _nextOffset;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    final ci =
        DateTime(now.year, now.month, now.day).add(const Duration(days: 1));
    final co = ci.add(const Duration(days: 2));
    _checkIn.text = ci.toIso8601String().substring(0, 10);
    _checkOut.text = co.toIso8601String().substring(0, 10);
    _refreshAuth();
    // Apply incoming params and search
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (widget.initialCity != null && widget.initialCity!.isNotEmpty) {
        _city.text = widget.initialCity!;
      }
      if (widget.initialCheckIn != null && widget.initialCheckIn!.isNotEmpty) {
        _checkIn.text = widget.initialCheckIn!;
      }
      if (widget.initialCheckOut != null && widget.initialCheckOut!.isNotEmpty) {
        _checkOut.text = widget.initialCheckOut!;
      }
      if (widget.initialGuests != null && widget.initialGuests!.isNotEmpty) {
        _guests.text = widget.initialGuests!;
      }
      if ((widget.initialCity ?? '').isNotEmpty) {
        await _search();
      }
      if ((widget.initialPropertyId ?? '').isNotEmpty) {
        try {
          final prop = await _api.getProperty(widget.initialPropertyId!);
          if (!mounted) return;
          showDialog(context: context, builder: (_) => AlertDialog(
            title: Text(prop['name']?.toString() ?? 'Listing'),
            content: Text('City: ${prop['city'] ?? '-'}\nType: ${prop['type'] ?? '-'}'),
            actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Schließen'))],
          ));
        } catch (_) {}
      }
    });
  }

  Future<void> _refreshAuth() async {
    final t = await getTokenFor(_service, store: _tokens);
    if (!mounted) return;
    setState(() => _authed = t != null && t.isNotEmpty);
  }

  Future<void> _healthCheck() async {
    setState(() => _loading = true);
    try {
      final js = await serviceGetJson(_service, '/health');
      if (!mounted) return;
      setState(() => _health = '${js['status']} (${js['env']})');
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Health check failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loginDev() async {
    setState(() => _loading = true);
    try {
      const phone = '+963900000001';
      await verifyOtp(_service, phone, '123456', name: 'User');
      _toast('Logged in');
    } catch (e) {
      _toast('Login failed: $e');
    } finally {
      await _refreshAuth();
      if (_authed) {
        await _loadFavorites();
        await _loadReservations();
      }
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _search() async {
    setState(() => _loading = true);
    try {
      final page = await _api.searchAvailability(
        city: _city.text.trim(),
        propertyType: _type == 'any' ? null : _type,
        checkIn: _checkIn.text.trim(),
        checkOut: _checkOut.text.trim(),
        guests: int.tryParse(_guests.text.trim()) ?? 1,
        minPriceCents: int.tryParse(_minPrice.text.trim().isEmpty
            ? _priceRange.start.round().toString()
            : _minPrice.text.trim()),
        maxPriceCents: int.tryParse(_maxPrice.text.trim().isEmpty
            ? _priceRange.end.round().toString()
            : _maxPrice.text.trim()),
        capacityMin: int.tryParse(_capacityMin.text.trim()),
        amenities: {
          ..._selectedAmenities,
          ..._amenities.text
              .split(',')
              .map((e) => e.trim())
              .where((e) => e.isNotEmpty)
        }.toList(),
        amenitiesMode: _amenitiesMode,
      );
      setState(() {
        _results = (page['results'] as List).cast<Map<String, dynamic>>();
        _nextOffset = page['next_offset'] as int?;
      });
      if (_showMap) {
        await _ensureCoordsForResults();
      }
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Search failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadMore() async {
    if (_nextOffset == null) return;
    setState(() => _loading = true);
    try {
      final page = await _api.searchAvailability(
        city: _city.text.trim(),
        propertyType: _type == 'any' ? null : _type,
        checkIn: _checkIn.text.trim(),
        checkOut: _checkOut.text.trim(),
        guests: int.tryParse(_guests.text.trim()) ?? 1,
        minPriceCents: int.tryParse(_minPrice.text.trim().isEmpty
            ? _priceRange.start.round().toString()
            : _minPrice.text.trim()),
        maxPriceCents: int.tryParse(_maxPrice.text.trim().isEmpty
            ? _priceRange.end.round().toString()
            : _maxPrice.text.trim()),
        capacityMin: int.tryParse(_capacityMin.text.trim()),
        amenities: {
          ..._selectedAmenities,
          ..._amenities.text
              .split(',')
              .map((e) => e.trim())
              .where((e) => e.isNotEmpty)
        }.toList(),
        amenitiesMode: _amenitiesMode,
        offset: _nextOffset ?? 0,
      );
      setState(() {
        _results
            .addAll(((page['results'] as List).cast<Map<String, dynamic>>()));
        _nextOffset = page['next_offset'] as int?;
      });
      if (_showMap) await _ensureCoordsForResults();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Load more failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _ensureCoordsForResults() async {
    final ids = _results
        .map((e) => (e['property_id'] ?? '').toString())
        .where((s) => s.isNotEmpty)
        .toSet();
    for (final id in ids) {
      if (_propCoords.containsKey(id)) continue;
      try {
        final d = await _api.getProperty(id);
        final lat = double.tryParse((d['latitude'] ?? '').toString());
        final lon = double.tryParse((d['longitude'] ?? '').toString());
        if (lat != null && lon != null) {
          _propCoords[id] = LatLng(lat, lon);
        }
      } catch (_) {}
    }
    await _fitToMarkers();
    if (mounted) setState(() {});
  }

  Future<void> _fitToMarkers() async {
    if (_propCoords.isEmpty) return;
    try {
      final points = _propCoords.values.toList();
      if (points.length == 1) {
        _mapCtrl.move(points.first, 12);
      } else {
        final bounds = LatLngBounds.fromPoints(points);
        _mapCtrl.fitCamera(CameraFit.bounds(
            bounds: bounds, padding: const EdgeInsets.all(24)));
      }
    } catch (_) {}
  }

  Future<void> _book(Map<String, dynamic> r) async {
    setState(() => _loading = true);
    try {
      final res = await _api.createReservation(
        unitId: r['unit_id'] as String,
        checkIn: _checkIn.text.trim(),
        checkOut: _checkOut.text.trim(),
        guests: int.tryParse(_guests.text.trim()) ?? 1,
      );
      _toast('Booked');
      final pr = (res['payment_request_id'] ?? '') as String;
      if (pr.isNotEmpty) await _showPaymentCta(pr);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Booking failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _bookUnit(String unitId) async {
    if (unitId.isEmpty) return;
    setState(() => _loading = true);
    try {
      final res = await _api.createReservation(
        unitId: unitId,
        checkIn: _checkIn.text.trim(),
        checkOut: _checkOut.text.trim(),
        guests: int.tryParse(_guests.text.trim()) ?? 1,
      );
      _toast('Booked');
      final pr = (res['payment_request_id'] ?? '') as String;
      if (pr.isNotEmpty) await _showPaymentCta(pr);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Booking failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openPayment(String requestId) async {
    final uri = Uri.parse('payments://request/$requestId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      await Clipboard.setData(ClipboardData(text: requestId));
      _toast('Payments app not installed. Copied request ID.');
    }
  }

  Future<void> _showPaymentCta(String requestId) async {
    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(children: [
              Icon(Icons.hotel_outlined, size: 28),
              SizedBox(width: 8),
              Text('Reservation created',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))
            ]),
            const SizedBox(height: 8),
            const Text('Open the Payments app to pay for your stay.'),
            const SizedBox(height: 16),
            Row(children: [
              Expanded(
                child: FilledButton.icon(
                    onPressed: () {
                      Navigator.pop(ctx);
                      _openPayment(requestId);
                    },
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('Open in Payments')),
              )
            ]),
            const SizedBox(height: 8),
            TextButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: requestId));
                  _toast('Copied payment request ID');
                },
                icon: const Icon(Icons.copy_outlined),
                label: const Text('Copy request ID')),
          ],
        ),
      ),
    );
  }

  Future<void> _loadReservations() async {
    setState(() => _loading = true);
    try {
      final rows = await _api.myReservations();
      // Enrich with property names (fetch missing)
      final ids = rows
          .map((e) => (e['property_id'] ?? '').toString())
          .where((s) => s.isNotEmpty)
          .toSet();
      for (final id in ids) {
        if (!_propNameCache.containsKey(id)) {
          try {
            final d = await _api.getProperty(id);
            _propNameCache[id] = (d['name'] ?? id).toString();
          } catch (_) {}
        }
      }
      setState(() => _reservations = rows);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Reservations failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadFavorites() async {
    setState(() => _loading = true);
    try {
      final rows = await _api.listFavorites();
      if (!mounted) return;
      setState(() => _favorites = rows);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Favorites failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _toggleFavorite(String propertyId) async {
    if (!_authed) {
      _toast('Login first');
      return;
    }
    final fav = _favoriteIds.contains(propertyId);
    setState(() => _loading = true);
    try {
      if (fav) {
        await _api.removeFavorite(propertyId);
      } else {
        await _api.addFavorite(propertyId);
      }
      await _loadFavorites();
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Toggle favorite failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openPropertyDetails(String propertyId) async {
    setState(() => _loading = true);
    Map<String, dynamic>? detail;
    List<Map<String, dynamic>> reviews = [];
    try {
      detail = await _api.getProperty(propertyId);
      _propNameCache[propertyId] = (detail['name'] ?? propertyId).toString();
      reviews = await _api.listReviews(propertyId);
    } catch (e) {
      if (!mounted) return;
      presentError(context, e, message: 'Load property failed');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
    if (!mounted || detail == null) return;
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) {
        final fav = _favoriteIds.contains(propertyId);
        final imgs = (detail!['images'] as List? ?? []).cast<Map>();
        final units = (detail['units'] as List? ?? []).cast<Map>();
        final name = (detail['name'] ?? '') as String;
        final city = (detail['city'] ?? '') as String;
        final rating = detail['rating_avg'];
        final ratingCount = detail['rating_count'];
        final reviewCtrl = TextEditingController();
        double newRating = 5;
        return StatefulBuilder(builder: (ctx, setS) {
          return DraggableScrollableSheet(
            expand: false,
            initialChildSize: 0.8,
            minChildSize: 0.4,
            maxChildSize: 0.95,
            builder: (context, scroll) => Padding(
              padding:
                  EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom)
                      .add(const EdgeInsets.all(16)),
              child: ListView(controller: scroll, children: [
                Row(children: [
                  Expanded(
                      child: Text('$name — $city',
                          style: const TextStyle(
                              fontSize: 18, fontWeight: FontWeight.bold))),
                  IconButton(
                    tooltip: fav ? 'Unfavorite' : 'Favorite',
                    icon: Icon(fav ? Icons.favorite : Icons.favorite_border,
                        color: fav ? Colors.pinkAccent : null),
                    onPressed: () async {
                      Navigator.pop(ctx);
                      await _toggleFavorite(propertyId);
                      _openPropertyDetails(propertyId);
                    },
                  ),
                ]),
                if (rating != null)
                  Text(
                      'Rating: ${rating.toStringAsFixed(1)} (${ratingCount ?? 0})'),
                const SizedBox(height: 8),
                if (imgs.isNotEmpty)
                  SizedBox(
                      height: 160,
                      child: ListView.separated(
                          scrollDirection: Axis.horizontal,
                          itemBuilder: (_, i) {
                            final u = imgs[i]['url']?.toString() ?? '';
                            return ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: CachedNetworkImage(
                                    imageUrl: u,
                                    width: 220,
                                    height: 160,
                                    fit: BoxFit.cover,
                                    placeholder: (_, __) => Container(
                                        width: 220,
                                        height: 160,
                                        color: Colors.black12),
                                    errorWidget: (_, __, ___) =>
                                        const Icon(Icons.broken_image)));
                          },
                          separatorBuilder: (_, __) => const SizedBox(width: 8),
                          itemCount: imgs.length)),
                const SizedBox(height: 12),
                const Text('Units',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                for (final u in units)
                  ListTile(
                    title: Text(u['name']?.toString() ?? ''),
                    subtitle: Text(
                        'Cap ${u['capacity']} • ${(u['price_cents_per_night'] / 100).toStringAsFixed(2)}/night • Min ${u['min_nights']} nights'),
                    trailing: FilledButton(
                        onPressed: _authed
                            ? () async {
                                Navigator.pop(ctx);
                                await _bookUnit((u['id'] ?? '').toString());
                              }
                            : null,
                        child: const Text('Book')),
                  ),
                const Divider(),
                const Text('Reviews',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                if (reviews.isEmpty)
                  const Text('No reviews yet')
                else ...[
                  for (final r in reviews)
                    ListTile(
                        title: Text('⭐️ x${r['rating']}'),
                        subtitle: Text(r['comment']?.toString() ?? ''))
                ],
                if (_authed) ...[
                  const SizedBox(height: 8),
                  const Text('Add review'),
                  Slider(
                      value: newRating,
                      onChanged: (v) => setS(() => newRating = v),
                      min: 1,
                      max: 5,
                      divisions: 4,
                      label: newRating.toStringAsFixed(0)),
                  TextField(
                      controller: reviewCtrl,
                      decoration: const InputDecoration(
                          hintText: 'Comment (optional)')),
                  const SizedBox(height: 8),
                  FilledButton(
                      onPressed: () async {
                        try {
                          await _api.createReview(propertyId,
                              rating: newRating.round(),
                              comment: reviewCtrl.text.trim());
                          final newReviews = await _api.listReviews(propertyId);
                          setS(() => reviews = newReviews);
                          reviewCtrl.clear();
                          _toast('Review posted');
                        } catch (e) {
                          _toast('$e');
                        }
                      },
                      child: const Text('Submit')),
                ],
              ]),
            ),
          );
        });
      },
    );
  }

  Future<void> _pickDate(TextEditingController controller,
      {required bool isCheckIn}) async {
    final now = DateTime.now();
    final init = DateTime.tryParse(controller.text) ??
        now.add(Duration(days: isCheckIn ? 1 : 3));
    final firstDate = now;
    final lastDate = now.add(const Duration(days: 365));
    final picked = await showDatePicker(
        context: context,
        initialDate: init,
        firstDate: firstDate,
        lastDate: lastDate);
    if (picked != null) {
      controller.text = picked.toIso8601String().substring(0, 10);
      // auto adjust check-out if before check-in
      if (isCheckIn) {
        final co = DateTime.tryParse(_checkOut.text);
        if (co == null || !picked.isBefore(co)) {
          _checkOut.text = picked
              .add(const Duration(days: 2))
              .toIso8601String()
              .substring(0, 10);
        }
      }
      setState(() {});
    }
  }

  void _toast(String m) { if (!mounted) return; showToast(context, m); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: const Text('Stays'),
          flexibleSpace: const Glass(
              padding: EdgeInsets.zero,
              blur: 24,
              opacity: 0.16,
              borderRadius: BorderRadius.zero)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Glass(child: Wrap(spacing: 8, children: [
            FilledButton.tonal(onPressed: _loading ? null : () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StaysFavoritesScreen())), child: const Text('Favorites')),
            FilledButton.tonal(onPressed: _loading ? null : () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StaysReservationsScreen())), child: const Text('Reservations')),
          ])),
          const SizedBox(height: 8),
          if (_loading) const LinearProgressIndicator(),
          Row(children: [
            Glass(
                child: FilledButton(
                    onPressed: _loading ? null : _healthCheck,
                    child: const Text('Health'))),
            const SizedBox(width: 8),
            Glass(
                child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    child: Text('Status: $_health'))),
            const Spacer(),
            Glass(
                child: OutlinedButton.icon(
                    onPressed: _loading
                        ? null
                        : () async {
                            setState(() => _showMap = !_showMap);
                            if (_showMap) await _ensureCoordsForResults();
                          },
                    icon: const Icon(Icons.map_outlined),
                    label: Text(_showMap ? 'Hide Map' : 'Show Map'))),
            const SizedBox(width: 8),
            Glass(
                child: FilledButton(
                    onPressed: _loading ? null : _loginDev,
                    child: const Text('Continue'))),
            const SizedBox(width: 8),
            Glass(
                child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    child: Text(_authed ? 'Logged in' : 'Guest',
                        style: TextStyle(
                            color: _authed
                                ? Colors.greenAccent
                                : Colors.orangeAccent))))
          ]),
          const SizedBox(height: 12),
          if (_showMap)
            Glass(
              child: SizedBox(
                height: 220,
                child: SuperMapView(
                  center: const LatLng(33.5138, 36.2765),
                  zoom: 11,
                  markers: [
                    for (final e in _propCoords.entries)
                      MapMarker(point: e.value, color: Colors.redAccent, size: 36),
                  ],
                ),
              ),
            ),
          if (_showMap) const SizedBox(height: 12),
          Glass(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Search',
                  style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: TextField(
                        controller: _city,
                        decoration: const InputDecoration(labelText: 'City'))),
                const SizedBox(width: 8),
                Expanded(
                    child: TextField(
                        controller: _checkIn,
                        readOnly: true,
                        decoration: InputDecoration(
                            labelText: 'Check-in',
                            suffixIcon: IconButton(
                                icon: const Icon(Icons.date_range),
                                onPressed: () =>
                                    _pickDate(_checkIn, isCheckIn: true))))),
                const SizedBox(width: 8),
                Expanded(
                    child: TextField(
                        controller: _checkOut,
                        readOnly: true,
                        decoration: InputDecoration(
                            labelText: 'Check-out',
                            suffixIcon: IconButton(
                                icon: const Icon(Icons.date_range),
                                onPressed: () =>
                                    _pickDate(_checkOut, isCheckIn: false))))),
                const SizedBox(width: 8),
                SizedBox(
                    width: 80,
                    child: TextField(
                        controller: _guests,
                        keyboardType: TextInputType.number,
                        decoration:
                            const InputDecoration(labelText: 'Guests'))),
                const SizedBox(width: 8),
                FilledButton(
                    onPressed: _loading ? null : _search,
                    child: const Text('Search')),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                // Type filter
                DropdownButton<String>(
                  value: _type,
                  items: const [
                    DropdownMenuItem(value: 'any', child: Text('Any type')),
                    DropdownMenuItem(value: 'hotel', child: Text('Hotel')),
                    DropdownMenuItem(
                        value: 'apartment', child: Text('Apartment')),
                  ],
                  onChanged: (v) => setState(() => _type = v ?? 'any'),
                ),
                const SizedBox(width: 8),
                SizedBox(
                    width: 140,
                    child: TextField(
                        controller: _minPrice,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                            labelText: 'Min (SYP cents)'))),
                const SizedBox(width: 8),
                SizedBox(
                    width: 140,
                    child: TextField(
                        controller: _maxPrice,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                            labelText: 'Max (SYP cents)'))),
                const SizedBox(width: 8),
                SizedBox(
                    width: 120,
                    child: TextField(
                        controller: _capacityMin,
                        keyboardType: TextInputType.number,
                        decoration:
                            const InputDecoration(labelText: 'Min cap'))),
                const SizedBox(width: 8),
                Expanded(
                    child: TextField(
                        controller: _amenities,
                        decoration: const InputDecoration(
                            labelText: 'Amenities (comma)'))),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _amenitiesMode,
                  items: const [
                    DropdownMenuItem(value: 'any', child: Text('Any amenity')),
                    DropdownMenuItem(
                        value: 'all', child: Text('All amenities')),
                  ],
                  onChanged: (v) => setState(() => _amenitiesMode = v ?? 'any'),
                ),
              ]),
              const SizedBox(height: 8),
              // Quick amenity chips
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final tag in _amenityChips)
                  FilterChip(
                    label: Text(tag),
                    selected: _selectedAmenities.contains(tag),
                    onSelected: (v) => setState(() {
                      if (v) {
                        _selectedAmenities.add(tag);
                      } else {
                        _selectedAmenities.remove(tag);
                      }
                    }),
                  ),
              ]),
              const SizedBox(height: 8),
              // Price slider synced with text inputs
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Price range (SYP cents)'),
                RangeSlider(
                  values: _priceRange,
                  min: _priceMinBound,
                  max: _priceMaxBound,
                  divisions: 20,
                  labels: RangeLabels(_priceRange.start.round().toString(),
                      _priceRange.end.round().toString()),
                  onChanged: (v) => setState(() {
                    _priceRange = v;
                  }),
                  onChangeEnd: (_) {
                    _minPrice.text = _priceRange.start.round().toString();
                    _maxPrice.text = _priceRange.end.round().toString();
                  },
                ),
              ]),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: Wrap(spacing: 8, children: [
                  OutlinedButton.icon(
                      onPressed: _loading
                          ? null
                          : () {
                              _clearFilters();
                              _search();
                            },
                      icon: const Icon(Icons.clear_all),
                      label: const Text('Clear filters')),
                ]),
              ),
              const SizedBox(height: 8),
              AnimatedSwitcher(
                duration: AppAnimations.switcherDuration,
                child: _loading && _results.isEmpty
                    ? Column(key: const ValueKey('stays_skel'), children: List.generate(5, (i) => const _StaySkeletonTile()))
                    : Column(key: const ValueKey('stays_list'), children: [
                        if (_results.isEmpty) const Text('No results') else const Divider(),
                        for (final r in _results)
                          Builder(builder: (context) {
                            final pid = (r['property_id'] ?? '').toString();
                            final fav = _favoriteIds.contains(pid);
                            return ListTile(
                              onTap: () => _openPropertyDetails(pid),
                              leading: IconButton(
                                icon: Icon(fav ? Icons.favorite : Icons.favorite_border,
                                    color: fav ? Colors.pinkAccent : null),
                                onPressed: _loading ? null : () => _toggleFavorite(pid),
                              ),
                              title: Text('${r['property_name']} — ${r['unit_name']}'),
                              subtitle: Text('Cap ${r['capacity']} • ${(r['nightly_price_cents'] / 100).toStringAsFixed(2)}/night • total ${(r['total_cents'] / 100).toStringAsFixed(2)}'),
                              trailing: FilledButton(onPressed: !_authed || _loading ? null : () => _book(r), child: const Text('Book')),
                            );
                          }),
                        if (_nextOffset != null) ...[
                          const SizedBox(height: 8),
                          Center(child: OutlinedButton(onPressed: _loading ? null : _loadMore, child: const Text('Load more'))),
                        ]
                      ]),
              )
            ]),
          ),
          const SizedBox(height: 12),
          Glass(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Text('My Reservations',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const Spacer(),
                OutlinedButton(
                    onPressed: _loading ? null : _loadReservations,
                    child: const Text('Refresh')),
              ]),
              AnimatedSwitcher(
                duration: AppAnimations.switcherDuration,
                child: _loading && _reservations.isEmpty
                    ? Column(key: const ValueKey('resv_skel'), children: List.generate(3, (i) => const _StaySkeletonTile()))
                    : Column(key: const ValueKey('resv_list'), children: [
                        if (_reservations.isEmpty)
                          const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Text('No reservations'))
                        else ...[
                          const Divider(),
                          for (final r in _reservations)
                            ListTile(
                              title: Text('${_propNameCache[(r['property_id'] ?? '').toString()] ?? r['property_id']}'),
                              subtitle: Text('Status: ${r['status']} • Total ${(r['total_cents'] / 100).toStringAsFixed(2)}'),
                            )
                        ]
                      ]),
              )
            ]),
          ),
          const SizedBox(height: 12),
          Glass(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Text('Favorites',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const Spacer(),
                OutlinedButton(
                    onPressed: _loading ? null : _loadFavorites,
                    child: const Text('Refresh')),
              ]),
              AnimatedSwitcher(
                duration: AppAnimations.switcherDuration,
                child: _loading && _favorites.isEmpty
                    ? Column(key: const ValueKey('favs_skel'), children: List.generate(3, (i) => const _StaySkeletonTile()))
                    : Column(key: const ValueKey('favs_list'), children: [
                        if (_favorites.isEmpty)
                          const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Text('No favorites'))
                        else ...[
                          const Divider(),
                          for (final p in _favorites)
                            ListTile(title: Text('${p['name']} — ${p['city']}'), subtitle: Text(p['description'] ?? ''))
                        ]
                      ]),
              )
            ]),
          ),
        ],
      ),
    );
  }
}
class _StaySkeletonTile extends StatelessWidget {
  const _StaySkeletonTile();
  @override
  Widget build(BuildContext context) {
    return GlassCard(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Container(width: 48, height: 48, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8))),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(height: 12, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(4))),
            const SizedBox(height: 6),
            Container(height: 10, width: 140, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(4))),
          ])),
          const SizedBox(width: 12),
          Container(width: 64, height: 28, decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(14))),
        ]),
      ),
    );
  }
}
// ignore_for_file: use_build_context_synchronously
