import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale) : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate = _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates = <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en')
  ];

  /// No description provided for @appTitleRider.
  ///
  /// In en, this message translates to:
  /// **'Taxi Rider'**
  String get appTitleRider;

  /// No description provided for @navRider.
  ///
  /// In en, this message translates to:
  /// **'Rider'**
  String get navRider;

  /// No description provided for @openPayments.
  ///
  /// In en, this message translates to:
  /// **'Open Payments'**
  String get openPayments;

  /// No description provided for @setBaseUrl.
  ///
  /// In en, this message translates to:
  /// **'Set Base URL'**
  String get setBaseUrl;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @tapSets.
  ///
  /// In en, this message translates to:
  /// **'Tap sets:'**
  String get tapSets;

  /// No description provided for @pickup.
  ///
  /// In en, this message translates to:
  /// **'Pickup'**
  String get pickup;

  /// No description provided for @dropoff.
  ///
  /// In en, this message translates to:
  /// **'Dropoff'**
  String get dropoff;

  /// No description provided for @quote.
  ///
  /// In en, this message translates to:
  /// **'Quote'**
  String get quote;

  /// No description provided for @requestRide.
  ///
  /// In en, this message translates to:
  /// **'Request Ride'**
  String get requestRide;

  /// No description provided for @myRides.
  ///
  /// In en, this message translates to:
  /// **'My rides'**
  String get myRides;

  /// No description provided for @lastRide.
  ///
  /// In en, this message translates to:
  /// **'Last ride:'**
  String get lastRide;

  /// No description provided for @status.
  ///
  /// In en, this message translates to:
  /// **'Status:'**
  String get status;

  /// No description provided for @applyDev.
  ///
  /// In en, this message translates to:
  /// **'Apply (dev)'**
  String get applyDev;

  /// No description provided for @setLoc.
  ///
  /// In en, this message translates to:
  /// **'Set loc'**
  String get setLoc;

  /// No description provided for @profileEarnings.
  ///
  /// In en, this message translates to:
  /// **'Profile / Earnings'**
  String get profileEarnings;

  /// No description provided for @topup.
  ///
  /// In en, this message translates to:
  /// **'Top up'**
  String get topup;

  /// No description provided for @fareQuoted.
  ///
  /// In en, this message translates to:
  /// **'Fare (quoted): {amount}'**
  String fareQuoted(Object amount);

  /// No description provided for @fareFinal.
  ///
  /// In en, this message translates to:
  /// **'Fare (final): {amount}'**
  String fareFinal(Object amount);

  /// No description provided for @rideCanceled.
  ///
  /// In en, this message translates to:
  /// **'Ride canceled'**
  String get rideCanceled;

  /// No description provided for @paymentsNotAvailable.
  ///
  /// In en, this message translates to:
  /// **'Payments app not available'**
  String get paymentsNotAvailable;

  /// No description provided for @actions.
  ///
  /// In en, this message translates to:
  /// **'Actions'**
  String get actions;

  /// No description provided for @rideCompleted.
  ///
  /// In en, this message translates to:
  /// **'Ride completed'**
  String get rideCompleted;

  /// No description provided for @cashPlease.
  ///
  /// In en, this message translates to:
  /// **'Please pay cash. Thank you!'**
  String get cashPlease;

  /// No description provided for @priceOfRide.
  ///
  /// In en, this message translates to:
  /// **'Price of ride: {amount} (cash)'**
  String priceOfRide(Object amount);

  /// No description provided for @bookPayApp.
  ///
  /// In en, this message translates to:
  /// **'Book & pay in app'**
  String get bookPayApp;

  /// No description provided for @bookPayCash.
  ///
  /// In en, this message translates to:
  /// **'Book & pay cash'**
  String get bookPayCash;

  /// No description provided for @riderRewardApplied.
  ///
  /// In en, this message translates to:
  /// **'Loyalty reward: this ride was free!'**
  String get riderRewardApplied;

  /// No description provided for @driverRewardApplied.
  ///
  /// In en, this message translates to:
  /// **'Driver reward: platform fee waived.'**
  String get driverRewardApplied;

  /// No description provided for @walletTitle.
  ///
  /// In en, this message translates to:
  /// **'Wallet'**
  String get walletTitle;

  /// No description provided for @walletBalanceLabel.
  ///
  /// In en, this message translates to:
  /// **'Balance'**
  String get walletBalanceLabel;

  /// No description provided for @refresh.
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get refresh;

  /// No description provided for @eta.
  ///
  /// In en, this message translates to:
  /// **'ETA ~ {mins} min'**
  String eta(Object mins);

  // Taxi classes
  String get chooseTaxiClass;
  String get rideClassStandard;
  String get rideClassComfort;
  String get rideClassYellow;
  String get rideClassVIP;
  String get rideClassVAN;
  String get rideClassElectro;

  /// No description provided for @rateFive.
  ///
  /// In en, this message translates to:
  /// **'Rate 5★'**
  String get rateFive;

  /// No description provided for @cancelRide.
  ///
  /// In en, this message translates to:
  /// **'Cancel ride'**
  String get cancelRide;

  /// No description provided for @schedule15m.
  ///
  /// In en, this message translates to:
  /// **'Schedule (15m)'**
  String get schedule15m;

  /// No description provided for @dispatchDev.
  ///
  /// In en, this message translates to:
  /// **'Dispatch (dev)'**
  String get dispatchDev;

  /// No description provided for @optionalStopPromo.
  ///
  /// In en, this message translates to:
  /// **'Optional Stop and Promo'**
  String get optionalStopPromo;

  /// No description provided for @stopLatOptional.
  ///
  /// In en, this message translates to:
  /// **'Stop lat (optional)'**
  String get stopLatOptional;

  /// No description provided for @stopLonOptional.
  ///
  /// In en, this message translates to:
  /// **'Stop lon (optional)'**
  String get stopLonOptional;

  /// No description provided for @promoCodeOptional.
  ///
  /// In en, this message translates to:
  /// **'Promo code (optional)'**
  String get promoCodeOptional;

  /// No description provided for @favorites.
  ///
  /// In en, this message translates to:
  /// **'Favorites'**
  String get favorites;

  /// No description provided for @saveCurrentPickup.
  ///
  /// In en, this message translates to:
  /// **'Save current pickup'**
  String get saveCurrentPickup;

  /// No description provided for @setPickup.
  ///
  /// In en, this message translates to:
  /// **'Set pickup'**
  String get setPickup;

  /// No description provided for @setDrop.
  ///
  /// In en, this message translates to:
  /// **'Set drop'**
  String get setDrop;

  /// No description provided for @continueLabel.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get continueLabel;

  /// No description provided for @scheduledAt.
  ///
  /// In en, this message translates to:
  /// **'Scheduled at {ts}'**
  String scheduledAt(Object ts);

  /// No description provided for @dispatchRequested.
  ///
  /// In en, this message translates to:
  /// **'Dispatch requested (dev)'**
  String get dispatchRequested;

  /// No description provided for @searchAddress.
  ///
  /// In en, this message translates to:
  /// **'Search address'**
  String get searchAddress;

  /// No description provided for @typeAnAddress.
  ///
  /// In en, this message translates to:
  /// **'Type an address'**
  String get typeAnAddress;

  /// No description provided for @mapSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Map'**
  String get mapSectionTitle;

  /// No description provided for @tripPlannerSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Trip planner'**
  String get tripPlannerSectionTitle;

  /// No description provided for @rideOptionsSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Ride options'**
  String get rideOptionsSectionTitle;

  /// No description provided for @quoteSummarySectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Quote summary'**
  String get quoteSummarySectionTitle;

  /// No description provided for @scheduledRidesSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Scheduled rides'**
  String get scheduledRidesSectionTitle;

  /// No description provided for @developerToolsSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Developer tools'**
  String get developerToolsSectionTitle;

  /// No description provided for @showDriverLocation.
  ///
  /// In en, this message translates to:
  /// **'Show driver location'**
  String get showDriverLocation;

  /// No description provided for @hideDriverLocation.
  ///
  /// In en, this message translates to:
  /// **'Hide driver location'**
  String get hideDriverLocation;

  /// No description provided for @fullscreenMap.
  ///
  /// In en, this message translates to:
  /// **'Fullscreen map'**
  String get fullscreenMap;

  /// No description provided for @quotePriceLabel.
  ///
  /// In en, this message translates to:
  /// **'Price'**
  String get quotePriceLabel;

  /// No description provided for @quoteSurgeLabel.
  ///
  /// In en, this message translates to:
  /// **'Surge'**
  String get quoteSurgeLabel;

  /// No description provided for @quoteDistanceLabel.
  ///
  /// In en, this message translates to:
  /// **'Distance'**
  String get quoteDistanceLabel;

  /// No description provided for @quoteEtaLabel.
  ///
  /// In en, this message translates to:
  /// **'ETA'**
  String get quoteEtaLabel;

  /// No description provided for @pickScheduleDateTime.
  ///
  /// In en, this message translates to:
  /// **'Pick date & time'**
  String get pickScheduleDateTime;

  /// No description provided for @scheduleRideCta.
  ///
  /// In en, this message translates to:
  /// **'Schedule ride'**
  String get scheduleRideCta;

  /// No description provided for @scheduledEmpty.
  ///
  /// In en, this message translates to:
  /// **'No scheduled rides'**
  String get scheduledEmpty;

  /// No description provided for @testingShortcutsTitle.
  ///
  /// In en, this message translates to:
  /// **'Testing shortcuts'**
  String get testingShortcutsTitle;

  /// No description provided for @dispatchPending.
  ///
  /// In en, this message translates to:
  /// **'Dispatch pending'**
  String get dispatchPending;

  /// No description provided for @close.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;
}

class _AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>['ar', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {


  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar': return AppLocalizationsAr();
    case 'en': return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.'
  );
}
