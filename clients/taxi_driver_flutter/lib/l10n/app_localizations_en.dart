// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitleRider => 'Taxi Rider';
  @override
  String get appTitleDriver => 'Taxi Driver';

  @override
  String get navRider => 'Rider';
  @override
  String get navDriver => 'Driver';

  @override
  String get openPayments => 'Open Payments';

  @override
  String get setBaseUrl => 'Set Base URL';

  @override
  String get save => 'Save';

  @override
  String get cancel => 'Cancel';

  @override
  String get tapSets => 'Tap sets:';

  @override
  String get pickup => 'Pickup';

  @override
  String get dropoff => 'Dropoff';

  @override
  String get quote => 'Quote';

  @override
  String get requestRide => 'Request Ride';

  @override
  String get myRides => 'My rides';

  @override
  String get lastRide => 'Last ride:';

  @override
  String get status => 'Status:';

  @override
  String get applyDev => 'Apply (dev)';

  @override
  String get setLoc => 'Set loc';

  @override
  String get profileEarnings => 'Profile / Earnings';

  @override
  String get topup => 'Top up';
  @override
  String get accept => 'Accept';
  @override
  String get start => 'Start';
  @override
  String get complete => 'Complete';

  @override
  String fareQuoted(Object cents) {
    return 'Fare (quoted): $cents cents';
  }

  @override
  String fareFinal(Object cents) {
    return 'Fare (final): $cents cents';
  }

  @override
  String get rideCanceled => 'Ride canceled';
  @override
  String get driverEnabled => 'Driver enabled';
  @override
  String get driverInfoLoaded => 'Driver info loaded';

  @override
  String get paymentsNotAvailable => 'Payments app not available';

  @override
  String get actions => 'Actions';

  @override
  String get rideCompleted => 'Ride completed';

  @override
  String get cashPlease => 'Please pay cash. Thank you!';

  @override
  String priceOfRide({required Object cents}) {
    return 'Price of ride: ${cents}c (cash)';
  }

  @override
  String eta(Object mins) {
    return 'ETA ~ $mins min';
  }

  @override
  String get rateFive => 'Rate 5★';

  @override
  String get chooseTaxiClass => 'Choose Taxi Class';
  @override
  String get rideClassStandard => 'Standard';
  @override
  String get rideClassComfort => 'Comfort';
  @override
  String get rideClassYellow => 'Yellow';
  @override
  String get rideClassVIP => 'VIP';
  @override
  String get rideClassVAN => 'VAN';
  @override
  String get rideClassElectro => 'Electro';

  @override
  String get cancelRide => 'Cancel ride';

  @override
  String get schedule15m => 'Schedule (15m)';

  @override
  String get dispatchDev => 'Dispatch (dev)';

  @override
  String get optionalStopPromo => 'Optional Stop and Promo';

  @override
  String get stopLatOptional => 'Stop lat (optional)';

  @override
  String get stopLonOptional => 'Stop lon (optional)';

  @override
  String get promoCodeOptional => 'Promo code (optional)';

  @override
  String get favorites => 'Favorites';

  @override
  String get saveCurrentPickup => 'Save current pickup';

  @override
  String get setPickup => 'Set pickup';

  @override
  String get setDrop => 'Set drop';

  @override
  String get continueLabel => 'Continue';

  @override
  String scheduledAt(Object ts) {
    return 'Scheduled at $ts';
  }

  @override
  String get dispatchRequested => 'Dispatch requested (dev)';

  @override
  String get searchAddress => 'Search address';

  @override
  String get typeAnAddress => 'Type an address';

  @override
  String get close => 'Close';
}
