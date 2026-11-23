import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/features/consultation/consultation_screen.dart';

void main() {
  testWidgets('ConsultationScreen Step 4 displays "—" when no vitals measured', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          initialStep: 4,
          dynamicFields: const {},
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );

    // Initial step 4 with no measurements should display '—' for all three metrics
    expect(find.text('—'), findsNWidgets(3));
  });

  testWidgets('ConsultationScreen Step 4 displays real values when dynamicFields provided', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          initialStep: 4,
          dynamicFields: const {
            'temperature': '37.1 °C',
            'heart_rate': '78 bpm',
            'spo2': '99 %',
          },
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );

    expect(find.text('37.1 °C'), findsOneWidget);
    expect(find.text('78 BPM'), findsOneWidget);
    expect(find.text('99 %'), findsOneWidget);
  });

  testWidgets('ConsultationScreen resets vitals to "—" when measuring starts with "--"', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          initialStep: 4,
          dynamicFields: const {
            'temperature': '-- °C',
            'heart_rate': '-- bpm',
            'spo2': '-- %',
            'vitals_state': 'measuring',
          },
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );

    expect(find.text('—'), findsNWidgets(3));
  });

  testWidgets('ConsultationScreen triggers onRequestMeasure on start button tap', (tester) async {
    bool measureRequested = false;

    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          initialStep: 4,
          dynamicFields: const {},
          onRequestMeasure: () {
            measureRequested = true;
          },
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );

    final measureBtn = find.widgetWithText(ElevatedButton, 'Démarrer la mesure des constantes (🎤 « Mesurer »)');
    expect(measureBtn, findsOneWidget);
    await tester.tap(measureBtn);
    await tester.pump();

    expect(measureRequested, isTrue);
    expect(find.textContaining('Mesure en cours'), findsOneWidget);

    // Clean unmount
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('ConsultationScreen allows progressing from Step 4 to Step 5 and confirming without vitals', (tester) async {
    Map<String, dynamic>? submittedPayload;

    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          initialStep: 4,
          dynamicFields: const {
            'selected_reason': 'consultation_generale',
            'selected_doctor': 'A',
            'selected_period': 'MAT',
            'patient_name': 'Jean Dupont',
            'patient_phone': '0601020304',
          },
          onConfirmAppointment: (payload) {
            submittedPayload = payload;
          },
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );

    // Initialement à l'étape 4 sans constantes
    expect(find.text('Étape 4 sur 5'), findsOneWidget);
    expect(find.text('La prise de constantes est facultative pour la consultation.'), findsOneWidget);

    // Bouton continuer vers étape 5
    final continueBtn = find.widgetWithText(ElevatedButton, 'Continuer (🎤 « Suivant »)');
    expect(continueBtn, findsOneWidget);
    await tester.tap(continueBtn);
    await tester.pump(const Duration(milliseconds: 300));

    // Doit être arrivé à l'étape 5
    expect(find.text('Étape 5 sur 5'), findsOneWidget);
    expect(find.text('Récapitulatif de votre rendez-vous'), findsOneWidget);
    expect(find.text('Non mesurées'), findsOneWidget);

    // Bouton de confirmation finale
    final confirmBtn = find.widgetWithText(ElevatedButton, 'Confirmer (🎤 « Confirmer »)');
    expect(confirmBtn, findsOneWidget);
    await tester.tap(confirmBtn);
    await tester.pump(const Duration(milliseconds: 300));

    // Vérifie que le payload a bien été envoyé avec des constantes nulles
    expect(submittedPayload, isNotNull);
    expect(submittedPayload!['patient_name'], 'Jean Dupont');
    expect(submittedPayload!['contact'], '0601020304');
    expect(submittedPayload!['temperature_c'], isNull);
    expect(submittedPayload!['heart_rate_bpm'], isNull);
    expect(submittedPayload!['spo2_percent'], isNull);

    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('ConsultationScreen resetForm efface tous les champs et constantes', (tester) async {
    final key = GlobalKey<ConsultationScreenState>();

    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          key: key,
          initialStep: 3,
          dynamicFields: const {
            'patient_name': 'Alice Test',
            'patient_phone': '0320000000',
            'temperature_c': 37.2,
            'heart_rate_bpm': 75,
            'spo2_percent': 98,
          },
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Alice Test'), findsOneWidget);

    key.currentState?.resetForm();
    await tester.pump();

    expect(find.text('Alice Test'), findsNothing);
  });
}
