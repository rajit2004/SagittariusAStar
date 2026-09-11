import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/models/cycle_log.dart';
import 'package:rhythma/providers/cycle_provider.dart';
import 'package:rhythma/screens/cycle/components/calendar_grid.dart';
import 'package:rhythma/services/local_storage_service.dart';
import '../test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  Widget buildTestableWidget({required Widget child, CycleProvider? cycleProvider}) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => cycleProvider ?? CycleProvider()),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: child,
        ),
      ),
    );
  }

  testWidgets('CalendarGrid renders and handles date selection',
      (WidgetTester tester) async {
    final pageController = PageController(initialPage: 12000);

    await tester.pumpWidget(buildTestableWidget(
      child: CalendarGrid(
        pageController: pageController,
        initialPageOffset: 12000,
      ),
    ));

    await tester.pumpAndSettle();

    await tester.tap(find.text('1').first);
    await tester.pump();

    expect(find.text('1'), findsWidgets);
  });

  testWidgets('CalendarGrid supports month swiping via PageController',
      (WidgetTester tester) async {
    final pageController = PageController(initialPage: 12000);

    await tester.pumpWidget(buildTestableWidget(
      child: CalendarGrid(
        pageController: pageController,
        initialPageOffset: 12000,
      ),
    ));
    await tester.pumpAndSettle();

    pageController.nextPage(
        duration: const Duration(milliseconds: 100), curve: Curves.linear);
    await tester.pumpAndSettle();

    expect(find.text('1'), findsWidgets);
  });

  testWidgets(
      'Calendar markers reflect real Hive data and do not fallback to hardcoded mock state (#131)',
      (WidgetTester tester) async {
    final now = DateTime.now();
    final seededDate = DateTime(now.year, now.month, 15);

    await tester.runAsync(() async {
      await seedCycleLogs('test-user', [
        CycleLog(
          startDate: seededDate,
          flowIntensity: 'medium',
          symptoms: ['cramps'],
        ).toJson(),
      ]);
    });

    final cycleProvider = CycleProvider();
    final pageController = PageController(initialPage: 12000);

    await tester.pumpWidget(buildTestableWidget(
      cycleProvider: cycleProvider,
      child: CalendarGrid(
        pageController: pageController,
        initialPageOffset: 12000,
      ),
    ));
    await tester.pumpAndSettle();

    expect(cycleProvider.hasLogsForDate(seededDate), isTrue);

    final unloggedDate = DateTime(now.year, now.month, 28);
    if (unloggedDate.day != seededDate.day) {
      expect(cycleProvider.hasLogsForDate(unloggedDate), isFalse);
    }
  });

  group('logSeverityForDate', () {
    Future<void> seedLog(DateTime date, Map<String, dynamic> fields) {
      return LocalStorageService.saveCycleLog({
        'start_date':
            '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}',
        ...fields,
      });
    }

    test('returns 0 for unlogged dates', () {
      final provider = CycleProvider();
      expect(
        provider.logSeverityForDate(DateTime(2023, 5, 5)),
        0,
      );
    });

    test('rates heavy flow and severe symptoms as serious', () async {
      final provider = CycleProvider();
      final heavyDay = DateTime(2024, 3, 10);
      final severeDay = DateTime(2024, 3, 11);
      await seedLog(heavyDay, {'flow_intensity': 'heavy'});
      await seedLog(severeDay, {'symptoms': ['fainting']});

      expect(provider.logSeverityForDate(heavyDay), 3);
      expect(provider.logSeverityForDate(severeDay), 3);
    });

    test('rates medium flow, mild symptoms, high stress as moderate',
        () async {
      final provider = CycleProvider();
      final mediumDay = DateTime(2024, 3, 12);
      final crampDay = DateTime(2024, 3, 13);
      final stressDay = DateTime(2024, 3, 14);
      await seedLog(mediumDay, {'flow_intensity': 'medium'});
      await seedLog(crampDay, {'symptoms': ['Cramps']});
      await seedLog(stressDay, {'stress_level': 4});

      expect(provider.logSeverityForDate(mediumDay), 2);
      expect(provider.logSeverityForDate(crampDay), 2);
      expect(provider.logSeverityForDate(stressDay), 2);
    });

    test('rates light logs and healthy days as light', () async {
      final provider = CycleProvider();
      final lightDay = DateTime(2024, 3, 15);
      final healthyDay = DateTime(2024, 3, 16);
      await seedLog(lightDay, {'flow_intensity': 'light'});
      await seedLog(healthyDay, {'symptoms': ['healthy_none']});

      expect(provider.logSeverityForDate(lightDay), 1);
      expect(provider.logSeverityForDate(healthyDay), 1);
    });
  });
}
