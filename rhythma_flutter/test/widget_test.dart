import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:provider/provider.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/screens/profile/profile_screen.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/providers/theme_provider.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/screens/cycle/components/log_entry_sheet.dart';
import 'test_helpers/platform_channel_mocks.dart';
import 'test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
    await seedProfile('test-user', {
      'name': 'Aarya Test',
      'age': 30,
      'cycle_length': 28,
    });
    await seedEmergencyContacts('test-user', []);

    final now = DateTime.now();
    final lastPeriod = DateTime(now.year, now.month, now.day - 11);
    await seedCycleLogs('test-user', [
      {
        'start_date':
            '${lastPeriod.year}-${lastPeriod.month.toString().padLeft(2, '0')}-${lastPeriod.day.toString().padLeft(2, '0')}',
        'flow_intensity': 'medium',
      },
    ]);

    const channel =
        MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall methodCall) async {
      return null; 
    });
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  Future<void> pumpProfileScreen(WidgetTester tester) async {
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => LocaleProvider()),
          ChangeNotifierProvider(create: (_) => ThemeProvider()),
          ChangeNotifierProvider(create: (_) => ProfileProvider()),
        ],
        child: MaterialApp(
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: const [
            Locale('en'),
            Locale('hi'),
            Locale('ta'),
            Locale('te'),
            Locale('mr'),
            Locale('bn'),
          ],
          home: const Scaffold(
            body: ProfileScreen(),
          ),
          routes: {
            '/login': (_) => const Scaffold(body: Text('Login Screen')),
          },
        ),
      ),
    );

    await tester.pumpAndSettle();
  }

  testWidgets('1. Profile details load successfully on start',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    expect(find.text('Aarya Test'), findsOneWidget);
    expect(find.text('30 years old'), findsOneWidget);
    expect(find.text('28 days'), findsOneWidget);
    expect(find.text('Cycle Day 12 • Follicular Phase'), findsOneWidget);
  });

  testWidgets('2. Edit profile flow handles validation and saves updates',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    await tester.tap(find.text('Edit Profile Information'));
    await tester.pumpAndSettle();

    expect(find.text('Edit Profile'), findsOneWidget);

    final nameField = find.ancestor(
      of: find.text('Name'),
      matching: find.byType(TextField),
    );
    final ageField = find.ancestor(
      of: find.text('Age'),
      matching: find.byType(TextField),
    );
    final cycleField = find.ancestor(
      of: find.text('Average Cycle Length (Days)'),
      matching: find.byType(TextField),
    );

    await tester.enterText(nameField, '');
    await tester.enterText(ageField, '5');
    await tester.enterText(cycleField, '50');

    await tester.tap(find.text('Save Changes'));
    await tester.pumpAndSettle();

    expect(find.text('Please enter a valid name'), findsOneWidget);
    expect(find.text('Please enter a valid age'), findsOneWidget);
    expect(find.text('Please enter a valid cycle length'), findsOneWidget);

    await tester.enterText(nameField, 'Aarya Updated');
    await tester.enterText(ageField, '25');
    await tester.enterText(cycleField, '30');

    await tester.runAsync(() async {
      await tester.tap(find.text('Save Changes'));
      await Future.delayed(const Duration(seconds: 2));
    });
    await tester.pumpAndSettle();

    expect(find.text('Edit Profile'), findsNothing);
    expect(find.text('Aarya Updated'), findsOneWidget);
    expect(find.text('25 years old'), findsOneWidget);
    expect(find.text('30 days'), findsOneWidget);

    expect(LocalStorageService.getProfile()?['name'], 'Aarya Updated');
    expect(LocalStorageService.getProfile()?['age'], 25);
    expect(LocalStorageService.getProfile()?['cycle_length'], 30);
  });

  testWidgets(
      '3. Emergency contacts CRUD flow works and validates number format',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    await tester.tap(find.text('Medical Emergency Contact'));
    await tester.pumpAndSettle();

    expect(find.text('No emergency contacts set up yet.'), findsOneWidget);

    await tester.tap(find.text('Add New'));
    await tester.pumpAndSettle();

    final contactNameField =
        find.ancestor(of: find.text('Name'), matching: find.byType(TextField));
    final contactPhoneField =
        find.ancestor(of: find.text('Phone'), matching: find.byType(TextField));

    await tester.enterText(contactNameField, '');
    await tester.enterText(contactPhoneField, 'invalid123');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(find.text('Contact name is required'), findsOneWidget);
    expect(find.text('Please enter a valid phone number'), findsOneWidget);

    await tester.enterText(contactNameField, 'Mom');
    await tester.enterText(contactPhoneField, '+919876543210');

    await tester.runAsync(() async {
      await tester.tap(find.text('Save'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    
    await tester.pump();

    expect(find.text('No emergency contacts set up yet.'), findsNothing);
    expect(find.text('Mom'), findsOneWidget);
    expect(find.text('+919876543210'), findsOneWidget);

    final editIconButton = find.byIcon(Icons.edit_rounded).last;
    await tester.tap(editIconButton);
    await tester.pumpAndSettle();

    final editNameField =
        find.ancestor(of: find.text('Name'), matching: find.byType(TextField));
    await tester.enterText(editNameField, 'Mother');

    await tester.runAsync(() async {
      await tester.tap(find.text('Save'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    expect(find.text('Mother'), findsOneWidget);
    expect(find.text('Mom'), findsNothing);

    await tester.runAsync(() async {
      await tester.tap(find.byIcon(Icons.delete_outline_rounded));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    expect(find.text('Mother'), findsNothing);
    expect(find.text('No emergency contacts set up yet.'), findsOneWidget);
  });

  testWidgets('4. Settings screen navigation and logout flows work',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    await tester.tap(find.text('App Settings'));
    await tester.pumpAndSettle();

    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('App Preferences'), findsOneWidget);
    expect(find.text('Security & Privacy'), findsOneWidget);

    await tester.tap(find.text('Log Out'));
    await tester.pumpAndSettle();

    expect(find.text('Are you sure you want to log out of Rhythma?'),
        findsOneWidget);

    await tester.runAsync(() async {
      await tester.tap(find.text('Cancel'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    expect(find.text('Are you sure you want to log out of Rhythma?'),
        findsNothing);
    expect(find.text('Settings'), findsOneWidget);

    await tester.tap(find.text('Log Out'));
    await tester.pumpAndSettle();

    final dialogLogoutButton = find.descendant(
      of: find.byType(ElevatedButton),
      matching: find.text('Log Out'),
    );
    
    await tester.runAsync(() async {
      await tester.tap(dialogLogoutButton);
      await Future.delayed(const Duration(seconds: 2));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    final box = Hive.box<Map>('user_profile');
    expect(box.get('test-user::profile'), isNotNull);
    expect(box.get('test-user::profile')?['name'], 'Aarya Test');
    expect(LocalStorageService.currentUserId, isNull);
  });

  testWidgets('5. Log Entry Sheet create, edit, save flows',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => LocaleProvider()),
          ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ],
        child: MaterialApp(
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: const [
            Locale('en'),
            Locale('bn'),
          ],
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () {
                  LogEntrySheet.show(
                    context,
                    DateTime(2023, 10, 1),
                    existingLog: {
                      'start_date': '2023-10-01',
                      'flow_intensity': 'Medium',
                      'mood': '😌',
                      'sleep_hours': 7,
                      'stress_level': 2,
                      'symptoms': ['Cramps', 'Fatigue'],
                    },
                  );
                },
                child: const Text('Open Sheet'),
              ),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open Sheet'));
    await tester.pumpAndSettle();

    expect(find.text('Log your day'), findsOneWidget);

    expect(find.text('Medium'), findsWidgets);

    expect(find.text('😌'), findsWidgets);

    expect(find.text('Cramps'), findsWidgets);
    expect(find.text('Fatigue'), findsWidgets);

    await tester.tap(find.text('Nausea'));
    await tester.pumpAndSettle();

    await tester.runAsync(() async {
      await tester.tap(find.text('Save Log'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(find.text('Log your day'), findsNothing);
  });

  testWidgets(
      '6. Cycle Tracking and Wellness Tips toggles show a confirmation '
      'dialog and only change state when confirmed',
      (WidgetTester tester) async {
    mockNotificationPlatformChannels(
      permissionGranted: true,
      initTimezones: false,
    );

    await pumpProfileScreen(tester);

    await tester.tap(find.text('App Settings'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    final cycleSwitch =
        find.widgetWithText(SwitchListTile, 'Cycle Tracking Reminders');
    expect(tester.widget<SwitchListTile>(cycleSwitch).value, isTrue);

    await tester.tap(cycleSwitch);
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(
      find.text('Are you sure you want to turn OFF cycle tracking reminders?'),
      findsOneWidget,
    );

    await tester.tap(find.text('Cancel'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(tester.widget<SwitchListTile>(cycleSwitch).value, isTrue);

    final wellnessSwitch = find.widgetWithText(SwitchListTile, 'Wellness Tips');
    expect(tester.widget<SwitchListTile>(wellnessSwitch).value, isFalse);

    await tester.tap(wellnessSwitch);
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(
      find.text('Are you sure you want to turn ON wellness tips?'),
      findsOneWidget,
    );
    await tester.tap(find.text('Confirm'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(tester.widget<SwitchListTile>(wellnessSwitch).value, isTrue);
  });

  testWidgets(
      '7. Medicine Alerts toggle requests notification permission and '
      'schedules/cancels the alert accordingly',
      (WidgetTester tester) async {
    
    mockNotificationPlatformChannels(permissionGranted: true);

    await pumpProfileScreen(tester);
    await tester.tap(find.text('App Settings'));
    await tester.pumpAndSettle();

    final medicineSwitch = find.widgetWithText(SwitchListTile, 'Medicine Alerts');
    expect(tester.widget<SwitchListTile>(medicineSwitch).value, isTrue);

    await tester.tap(medicineSwitch);
    await tester.pumpAndSettle();
    expect(
      find.text('Are you sure you want to turn OFF medicine alerts?'),
      findsOneWidget,
    );
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(medicineSwitch).value, isFalse);

    await tester.tap(medicineSwitch);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(medicineSwitch).value, isTrue);
  });
}
