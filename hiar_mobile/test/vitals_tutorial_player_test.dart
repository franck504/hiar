import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/features/consultation/consultation_screen.dart';
import 'package:hiar_mobile/ui/components/vitals_tutorial_player.dart';

void main() {
  testWidgets('VitalsTutorialPlayer bascule entre Température et Pouls & SpO2', (tester) async {
    bool started = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 420,
            child: VitalsTutorialPlayer(
              enableVideoPlayback: false,
              onStartMeasure: () => started = true,
            ),
          ),
        ),
      ),
    );

    // Onglet par défaut : Température (sonde DS18B20 / bmp_animation.mp4)
    expect(find.text('Température'), findsOneWidget);
    expect(find.text('Pouls & SpO2'), findsOneWidget);
    expect(find.textContaining('sonde métallique'), findsOneWidget);
    expect(kVitalsTutorials[0].assetPath, 'assets/videos/bmp_animation.mp4');
    expect(kVitalsTutorials[1].assetPath, 'assets/videos/spo2_animation.mp4');

    // Basculer sur Pouls & SpO2 (capteur MAX30102 / spo2_animation.mp4)
    await tester.tap(find.text('Pouls & SpO2'));
    await tester.pump();
    expect(find.textContaining('index sur le capteur'), findsOneWidget);

    // Ouvrir le guide agrandi et cliquer sur "J'ai compris, démarrer"
    await tester.tap(find.byIcon(Icons.open_in_full));
    await tester.pumpAndSettle();
    expect(find.text('Comment placer les capteurs'), findsOneWidget);
    await tester.tap(find.text("J'ai compris, démarrer"));
    await tester.pumpAndSettle();
    expect(started, isTrue);
  });

  testWidgets('ConsultationScreen étape 4 affiche le tutoriel vidéo et les 3 constantes en paysage', (tester) async {
    tester.view.physicalSize = const Size(1280, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          initialStep: 4,
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(VitalsTutorialPlayer), findsOneWidget);
    expect(find.text('Température corporelle'), findsOneWidget);
    expect(find.text('Fréquence cardiaque'), findsOneWidget);
    expect(find.text('Oxygénation sanguine (SpO2)'), findsOneWidget);

    // Cliquer sur la carte SpO2 synchronise le tutoriel sur le capteur MAX30102
    await tester.tap(find.text('Oxygénation sanguine (SpO2)'));
    await tester.pump();
    expect(find.textContaining('index sur le capteur'), findsOneWidget);
  });
}
