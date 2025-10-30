import 'dart:async';

import 'package:flutter/material.dart';
import 'package:uni_links/uni_links.dart';

import 'screens/payments_screen.dart';
import 'apps/taxi_module.dart';
import 'screens/food_screen.dart';
import 'screens/flights_screen.dart';
import 'screens/bus_screen.dart';
import 'apps/chat_module.dart';
import 'screens/carmarket_screen.dart';
import 'screens/freight_screen.dart';
import 'screens/carrental_screen.dart';
import 'screens/stays_screen.dart';
import 'screens/realestate_screen.dart';
import 'screens/jobs_screen.dart';
import 'screens/utilities_screen.dart';
import 'screens/doctors_screen.dart';
import 'screens/commerce_screen.dart';
import 'screens/parking_screen.dart';
import 'screens/garages_screen.dart';
import 'screens/agriculture_screen.dart';
import 'screens/livestock_screen.dart';
import 'screens/ai_gateway_screen.dart';
import 'screens/search_screen.dart';
import 'package:taxi_flutter/api.dart' as taxi_api;
import 'services.dart';
import 'package:shared_core/shared_core.dart';

class DeepLinks {
  static StreamSubscription? _sub;

  static Future<void> init(BuildContext context) async {
    try {
      final uri = await getInitialUri();
      if (uri != null) _handleUri(context, uri);
    } catch (_) {}

    _sub?.cancel();
    _sub = uriLinkStream.listen((Uri? uri) {
      if (uri != null) _handleUri(context, uri);
    }, onError: (_) {});
  }

  static void dispose() {
    _sub?.cancel();
    _sub = null;
  }

  // Public handler for programmatic deep-links (e.g., push notification tap)
  static void handleUri(BuildContext context, Uri uri) {
    _handleUri(context, uri);
  }

  static void _handleUri(BuildContext context, Uri uri) {
    if (uri.scheme != 'superapp') return;
    final seg = uri.pathSegments;
    if (seg.isEmpty) return;
    final first = seg.first.toLowerCase();
    if (first == 'feature' && seg.length >= 2) {
      _openFeature(context, seg[1].toLowerCase(), uri);
      return;
    }
    if (first == 'search') {
      final q = uri.queryParameters['q'] ?? '';
      Navigator.push(context, MaterialPageRoute(builder: (_) => SearchScreen(initialQuery: q)));
      return;
    }
    // Also support superapp://payments etc.
    _openFeature(context, first, uri);
  }

  static void _openFeature(BuildContext context, String id, Uri? uri) {
    Widget? page;
    switch (id) {
      case 'payments':
        final act = uri?.queryParameters['action'];
        final view = uri?.queryParameters['view'];
        final p2pTo = uri?.queryParameters['to'];
        final p2pAmt = uri?.queryParameters['amount'];
        page = PaymentsScreen(initialAction: act, view: view, p2pTo: p2pTo, p2pAmt: p2pAmt);
        break;
      case 'taxi':
        final pickup = uri?.queryParameters['pickup'];
        final drop = uri?.queryParameters['drop'];
        final mode = (uri?.queryParameters['action'] ?? 'request').toLowerCase();
        if (pickup != null && drop != null) {
          // Fire-and-open: create/quote ride, then open module
          _requestOrQuoteTaxi(context, pickup, drop, mode);
          page = TaxiModule.build();
        } else {
          page = TaxiModule.build();
        }
        break;
      case 'food':
        page = const FoodScreen();
        break;
      case 'flights':
        page = const FlightsScreen();
        break;
      case 'bus':
        page = const BusScreen();
        break;
      case 'chat':
        page = ChatModule.build();
        break;
      case 'carmarket':
        page = const CarMarketScreen();
        break;
      case 'freight':
        page = const FreightScreen();
        break;
      case 'carrental':
        page = const CarRentalScreen();
        break;
      case 'stays':
        final view = uri?.queryParameters['view'];
        final propId = uri?.queryParameters['property_id'];
        final resId = uri?.queryParameters['reservation_id'];
        if (view == 'listing' && propId != null && propId.isNotEmpty) {
          page = StaysListingScreen(propertyId: propId);
        } else if (view == 'reservation' && resId != null && resId.isNotEmpty) {
          page = StaysReservationDetailScreen(reservationId: resId);
        } else {
          page = StaysScreen(
            initialCity: uri?.queryParameters['city'],
            initialCheckIn: uri?.queryParameters['check_in'],
            initialCheckOut: uri?.queryParameters['check_out'],
            initialGuests: uri?.queryParameters['guests'],
            initialPropertyId: propId,
          );
        }
        break;
      case 'realestate':
        page = const RealEstateScreen();
        break;
      case 'jobs':
        page = const JobsScreen();
        break;
      case 'utilities':
        page = const UtilitiesScreen();
        break;
      case 'doctors':
        page = const DoctorsScreen();
        break;
      case 'commerce':
        final action = uri?.queryParameters['action'];
        final orderId = uri?.queryParameters['order_id'];
        if (action == 'order' && orderId != null && orderId.isNotEmpty) {
          page = CommerceOrderScreen(orderId: orderId);
        } else {
          page = CommerceScreen(
            initialShopId: uri?.queryParameters['shop_id'],
            initialProductId: uri?.queryParameters['product_id'],
            initialAction: action,
            initialOrderId: orderId,
          );
        }
        break;
      case 'parking':
        page = const ParkingScreen();
        break;
      case 'garages':
        page = const GaragesScreen();
        break;
      case 'agriculture':
        page = const AgricultureScreen();
        break;
      case 'livestock':
        page = const LivestockScreen();
        break;
      case 'ai':
      case 'assistant':
        page = const AIGatewayScreen();
        break;
      default:
        page = null;
    }
    if (page != null) {
      Navigator.push(context, MaterialPageRoute(builder: (_) => page!));
    }
  }

  static Future<void> _requestOrQuoteTaxi(BuildContext context, String pickup, String drop, String action) async {
    try {
      List<double> _p(String s) {
        final parts = s.split(',');
        if (parts.length != 2) throw Exception('bad coords');
        final lat = double.parse(parts[0]);
        final lon = double.parse(parts[1]);
        return [lat, lon];
      }
      final p = _p(pickup);
      final d = _p(drop);
      final base = ServiceConfig.baseUrl('taxi');
      final token = await getTokenFor('taxi');
      if (token == null || token.isEmpty) return;
      final api = taxi_api.ApiClient(baseUrl: base, tokenStore: _DeepLinkTaxiTokenStore(token));
      if (action == 'quote') {
        await api.quoteRide(pickupLat: p[0], pickupLon: p[1], dropLat: d[0], dropLon: d[1]);
      } else {
        await api.requestRide(pickupLat: p[0], pickupLon: p[1], dropLat: d[0], dropLon: d[1]);
      }
    } catch (_) {}
  }
}

class _DeepLinkTaxiTokenStore extends taxi_api.TokenStore {
  final String token;
  _DeepLinkTaxiTokenStore(this.token);
  @override
  Future<String?> getToken() async => token;
  @override
  Future<void> clear() async {}
  @override
  Future<void> setToken(String token) async {}
}
