import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:hiar_mobile/core/net/hub_client.dart';
import 'package:hiar_mobile/features/splash/splash_screen.dart';
import 'package:hiar_mobile/main.dart';

/// Un patient quitte la consultation PAR LA VOIX (« terminer », « accueil »…) : le suivant ne doit voir
/// ni son nom, ni son téléphone, ni ses constantes vitales (données de santé).
void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<void> boot(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(const HiarApp());
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(find.byType(SplashScreen));
    await tester.pump(const Duration(milliseconds: 400));
    tester.takeException(); // débordement de police de test sur l'accueil, sans rapport
  }

  Future<void> server(WidgetTester tester, Map<String, dynamic> instruction) async {
    HubClient.instance.onServerInstruction!(instruction);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(milliseconds: 200));
  }

  Future<void> shutdown(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    HubClient.instance.disconnect();
    await tester.pump(const Duration(seconds: 4));
    tester.takeException();
  }

  testWidgets('identité dictée : remplie à l étape 3, effacée quand le patient quitte par la voix', (tester) async {
    await boot(tester);

    await server(tester, {
      'instruction_ui': {'screen': 'consultation', 'step': 3},
      'fields': {'patient_name': 'Jean Dupont', 'patient_phone': '034 12 345 67', 'selected_doctor': 'B'},
    });
    expect(find.widgetWithText(TextField, 'Jean Dupont'), findsOneWidget);
    expect(find.widgetWithText(TextField, '034 12 345 67'), findsOneWidget);

    await server(tester, {'instruction_ui': {'screen': 'home'}});       // « terminer » / « accueil »
    await server(tester, {'instruction_ui': {'screen': 'consultation', 'step': 3}});  // patient suivant

    expect(find.text('Jean Dupont'), findsNothing);
    expect(find.text('034 12 345 67'), findsNothing);
    await shutdown(tester);
  });

  testWidgets('constantes du patient précédent : jamais réaffichées au suivant', (tester) async {
    await boot(tester);

    await server(tester, {
      'instruction_ui': {'screen': 'consultation', 'step': 4},
      'fields': {'temperature_c': 36.8, 'heart_rate_bpm': 72, 'spo2_percent': 98, 'vitals_state': 'done'},
    });
    expect(find.text('36.8 °C'), findsOneWidget);
    expect(find.text('72 BPM'), findsOneWidget);

    await server(tester, {'instruction_ui': {'screen': 'home'}});
    await server(tester, {'instruction_ui': {'screen': 'consultation', 'step': 4}});

    expect(find.text('36.8 °C'), findsNothing);
    expect(find.text('72 BPM'), findsNothing);
    expect(find.text('—'), findsNWidgets(3));
    await shutdown(tester);
  });

  testWidgets('ticket du patient précédent : un nouveau rendez-vous repart de l étape 1', (tester) async {
    await boot(tester);

    await server(tester, {
      'instruction_ui': {'screen': 'consultation', 'step': 6},
      'fields': {'ticket_label': 'B-AM-3', 'patient_name': 'Jean Dupont', 'doctor': 'B', 'period': 'AM'},
    });
    expect(find.text('B-AM-3'), findsOneWidget);

    await server(tester, {'instruction_ui': {'screen': 'home'}});
    await server(tester, {'instruction_ui': {'screen': 'consultation', 'step': 1}});

    expect(find.text('B-AM-3'), findsNothing);
    expect(find.text('Étape 1 sur 5'), findsOneWidget);
    await shutdown(tester);
  });
}
