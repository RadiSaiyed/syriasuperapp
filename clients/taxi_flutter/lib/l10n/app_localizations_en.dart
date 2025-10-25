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
  String get navRider => 'Rider';

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
  String fareQuoted(Object amount) {
    return 'Fare (quoted): $amount';
  }

  @override
  String fareFinal(Object amount) {
    return 'Fare (final): $amount';
  }

  @override
  String get rideCanceled => 'Ride canceled';

  @override
  String get paymentsNotAvailable => 'Payments app not available';

  @override
  String get actions => 'Actions';

  @override
  String get rideCompleted => 'Ride completed';

  @override
  String get cashPlease => 'Please pay cash. Thank you!';

  @override
  String priceOfRide(Object amount) {
    return 'Price of ride: $amount (cash)';
  }

  @override
  String get bookPayApp => 'Book & pay in app';

  @override
  String get bookPayCash => 'Book & pay cash';

  @override
  String get riderRewardApplied => 'Loyalty reward: this ride was free!';

  @override
  String get driverRewardApplied => 'Driver reward: platform fee waived.';

  @override
  String get walletTitle => 'Wallet';

  @override
  String get walletBalanceLabel => 'Balance';

  @override
  String get refresh => 'Refresh';

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
  String get mapSectionTitle => 'Map';

  @override
  String get tripPlannerSectionTitle => 'Trip planner';

  @override
  String get rideOptionsSectionTitle => 'Ride options';

  @override
  String get quoteSummarySectionTitle => 'Quote summary';

  @override
  String get scheduledRidesSectionTitle => 'Scheduled rides';

  @override
  String get developerToolsSectionTitle => 'Developer tools';

  @override
  String get showDriverLocation => 'Show driver location';

  @override
  String get hideDriverLocation => 'Hide driver location';

  @override
  String get fullscreenMap => 'Fullscreen map';

  @override
  String get quotePriceLabel => 'Price';

  @override
  String get quoteSurgeLabel => 'Surge';

  @override
  String get quoteDistanceLabel => 'Distance';

  @override
  String get quoteEtaLabel => 'ETA';

  @override
  String get pickScheduleDateTime => 'Pick date & time';

  @override
  String get scheduleRideCta => 'Schedule ride';

  @override
  String get scheduledEmpty => 'No scheduled rides';

  @override
  String get testingShortcutsTitle => 'Testing shortcuts';

  @override
  String get dispatchPending => 'Dispatch pending';

  @override
  String get close => 'Close';
}
