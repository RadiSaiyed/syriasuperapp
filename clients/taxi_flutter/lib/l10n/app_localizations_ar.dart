// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appTitleRider => 'راكب تاكسي';

  @override
  String get navRider => 'راكب';

  @override
  String get openPayments => 'فتح المدفوعات';

  @override
  String get setBaseUrl => 'تعيين عنوان الخادم';

  @override
  String get save => 'حفظ';

  @override
  String get cancel => 'إلغاء';

  @override
  String get tapSets => 'النقر يحدد:';

  @override
  String get pickup => 'الانطلاق';

  @override
  String get dropoff => 'الوصول';

  @override
  String get quote => 'تسعير';

  @override
  String get requestRide => 'طلب رحلة';

  @override
  String get myRides => 'رحلاتي';

  @override
  String get lastRide => 'آخر رحلة:';

  @override
  String get status => 'الحالة:';

  @override
  String get applyDev => 'تفعيل (تجريبي)';

  @override
  String get setLoc => 'تعيين الموقع';

  @override
  String get profileEarnings => 'الملف / الأرباح';

  @override
  String get topup => 'شحن الرصيد';

  @override
  String fareQuoted(Object amount) {
    return 'الأجرة (تقديري): $amount';
  }

  @override
  String fareFinal(Object amount) {
    return 'الأجرة (نهائي): $amount';
  }

  @override
  String get rideCanceled => 'تم إلغاء الرحلة';

  @override
  String get paymentsNotAvailable => 'تطبيق المدفوعات غير متوفر';

  @override
  String get actions => 'إجراءات';

  @override
  String get rideCompleted => 'تم إنهاء الرحلة';

  @override
  String get cashPlease => 'يرجى الدفع نقداً. شكراً!';

  @override
  String priceOfRide(Object amount) {
    return 'سعر الرحلة: $amount (نقداً)';
  }

  @override
  String get bookPayApp => 'احجز وادفع عبر التطبيق';

  @override
  String get bookPayCash => 'احجز وادفع نقداً';

  @override
  String get riderRewardApplied => 'مكافأة الولاء: هذه الرحلة مجانية!';

  @override
  String get driverRewardApplied => 'مكافأة السائق: تم إعفاء عمولة المنصة.';

  @override
  String get walletTitle => 'المحفظة';

  @override
  String get walletBalanceLabel => 'الرصيد';

  @override
  String get refresh => 'تحديث';

  @override
  String eta(Object mins) {
    return 'الوصول ~ $mins دقيقة';
  }

  @override
  String get rateFive => 'تقييم 5★';

  @override
  String get chooseTaxiClass => 'اختر فئة التاكسي';
  @override
  String get rideClassStandard => 'عادي';
  @override
  String get rideClassComfort => 'مريح';
  @override
  String get rideClassYellow => 'الأصفر';
  @override
  String get rideClassVIP => 'VIP';
  @override
  String get rideClassVAN => 'فان';
  @override
  String get rideClassElectro => 'كهربائي';

  @override
  String get cancelRide => 'إلغاء الرحلة';

  @override
  String get schedule15m => 'جدولة (15د)';

  @override
  String get dispatchDev => 'تشغيل (تجريبي)';

  @override
  String get optionalStopPromo => 'توقف اختياري ورمز ترويجي';

  @override
  String get stopLatOptional => 'إحداثي توقف (اختياري)';

  @override
  String get stopLonOptional => 'إحداثي توقف (اختياري)';

  @override
  String get promoCodeOptional => 'رمز ترويجي (اختياري)';

  @override
  String get favorites => 'المفضلة';

  @override
  String get saveCurrentPickup => 'حفظ نقطة الانطلاق الحالية';

  @override
  String get setPickup => 'تعيين الانطلاق';

  @override
  String get setDrop => 'تعيين الوصول';

  @override
  String get continueLabel => 'متابعة';

  @override
  String scheduledAt(Object ts) {
    return 'تمت الجدولة عند $ts';
  }

  @override
  String get dispatchRequested => 'تم طلب التنفيذ (تجريبي)';

  @override
  String get searchAddress => 'ابحث عن عنوان';

  @override
  String get typeAnAddress => 'اكتب عنوانًا';

  @override
  String get mapSectionTitle => 'الخريطة';

  @override
  String get tripPlannerSectionTitle => 'مخطط الرحلة';

  @override
  String get rideOptionsSectionTitle => 'خيارات الرحلة';

  @override
  String get quoteSummarySectionTitle => 'ملخص التسعير';

  @override
  String get scheduledRidesSectionTitle => 'الرحلات المجدولة';

  @override
  String get developerToolsSectionTitle => 'أدوات المطوّر';

  @override
  String get showDriverLocation => 'إظهار موقع السائق';

  @override
  String get hideDriverLocation => 'إخفاء موقع السائق';

  @override
  String get fullscreenMap => 'خريطة بملء الشاشة';

  @override
  String get quotePriceLabel => 'السعر';

  @override
  String get quoteSurgeLabel => 'عامل الزيادة';

  @override
  String get quoteDistanceLabel => 'المسافة';

  @override
  String get quoteEtaLabel => 'المدة المتوقعة';

  @override
  String get pickScheduleDateTime => 'اختر التاريخ والوقت';

  @override
  String get scheduleRideCta => 'جدولة الرحلة';

  @override
  String get scheduledEmpty => 'لا توجد رحلات مجدولة';

  @override
  String get testingShortcutsTitle => 'اختصارات الاختبار';

  @override
  String get dispatchPending => 'إطلاق الرحلات المعلّقة';

  @override
  String get close => 'إغلاق';
}
