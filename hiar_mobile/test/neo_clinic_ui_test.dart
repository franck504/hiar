import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/features/consultation/consultation_screen.dart';
import 'package:hiar_mobile/features/home/home_screen.dart';
import 'package:hiar_mobile/features/information/information_screen.dart';
import 'package:hiar_mobile/features/orientation/mission_screen.dart';
import 'package:hiar_mobile/features/orientation/orientation_screen.dart';
import 'package:hiar_mobile/features/splash/splash_screen.dart';
import 'package:hiar_mobile/ui/components/animated_robot_face.dart';
import 'package:hiar_mobile/ui/components/hiar_surfaces.dart';
import 'package:hiar_mobile/ui/rail/voice_rail.dart';

void main() {
  testWidgets('AnimatedRobotFace s anime et se demonte sans fuite de timer', (tester) async {
    for (final expr in RobotFaceExpression.values) {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: AnimatedRobotFace(
                expression: expr,
                showLoadingRing: expr == RobotFaceExpression.thinking,
              ),
            ),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 200));
    }
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('VoiceRail affiche le loading pendant VoiceState.thinking', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: VoiceRail(
            voiceState: VoiceState.thinking,
            statusText: "Réflexion en cours…",
            recognizedText: "Où est la pharmacie ?",
            voiceTip: "Patientez un instant",
          ),
        ),
      ),
    );

    expect(find.byType(AnimatedRobotFace), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNWidgets(2));
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.text("Réflexion en cours…"), findsOneWidget);
    expect(find.text("Analyse de votre demande…"), findsOneWidget);

    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('Tous les ecrans restyles Néo-Clinique s affichent sans overflow en paysage', (tester) async {
    tester.view.physicalSize = const Size(1280, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    // 1. Splash
    await tester.pumpWidget(MaterialApp(home: SplashScreen(onStart: () {})));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(AnimatedRobotFace), findsOneWidget);
    expect(find.text("Bonjour !"), findsOneWidget);

    // 2. Home (avec bouton Retour)
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          onOpenOrientation: () {},
          onOpenInformation: () {},
          onOpenConsultation: () {},
          onBack: () {},
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(HiarHeroCard), findsOneWidget);
    expect(find.text("Retour"), findsOneWidget);
    expect(find.text("Orientation"), findsOneWidget);
    expect(find.text("Renseignements"), findsOneWidget);
    expect(find.text("Consultation"), findsOneWidget);

    // 3. Orientation (avec bouton Retour)
    await tester.pumpWidget(
      MaterialApp(
        home: OrientationScreen(
          onDestinationSelected: (_, _) {},
          onBack: () {},
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text("Retour"), findsOneWidget);
    expect(find.text("Pharmacie"), findsOneWidget);
    expect(find.text("Radiologie"), findsOneWidget);

    // 4. Mission (avec bouton Retour même pendant RUNNING)
    await tester.pumpWidget(
      MaterialApp(
        home: MissionScreen(
          destinationLabel: "Pharmacie",
          missionState: "RUNNING",
          onStopRobot: () {},
          onFinish: () {},
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text("Retour"), findsOneWidget);
    expect(find.textContaining("Pharmacie"), findsOneWidget);

    // 5. Information + filtre pilule + bouton Retour
    await tester.pumpWidget(
      MaterialApp(
        home: InformationScreen(
          onSelectTopic: (_, _) {},
          onBack: () {},
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text("Retour"), findsOneWidget);
    expect(find.text("Toutes les fiches"), findsOneWidget);
    await tester.tap(find.text("Maladies chroniques"));
    await tester.pump();
    expect(find.text("Diabète"), findsOneWidget);

    // 6. Consultation Ticket Reçu festonné (étape 6 + bouton Retour)
    await tester.pumpWidget(
      MaterialApp(
        home: ConsultationScreen(
          initialStep: 6,
          dynamicFields: const {
            'ticket_label': 'A-MAT-3',
            'temperature': 36.8,
            'heart_rate': 72,
            'spo2': 98,
          },
          onCancel: () {},
          onFinish: () {},
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text("Retour"), findsOneWidget);
    expect(find.byType(HiarReceiptCard), findsOneWidget);
    expect(find.text("A-MAT-3"), findsOneWidget);
    expect(find.text("36.8 °C"), findsOneWidget);

    await tester.pumpWidget(const SizedBox());
  });
}
