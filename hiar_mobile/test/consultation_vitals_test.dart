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
}
