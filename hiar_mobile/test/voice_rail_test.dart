import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/ui/components/auto_scroll_text.dart';
import 'package:hiar_mobile/ui/rail/voice_rail.dart';

void main() {
  testWidgets('AutoScrollText displays text and disposes cleanly without timer leaks', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 150,
            child: AutoScrollText(
              text: 'Dites « Orientation », « Renseignements » ou « Consultation »',
            ),
          ),
        ),
      ),
    );

    expect(find.text('Dites « Orientation », « Renseignements » ou « Consultation »'), findsOneWidget);

    // Pump un frame
    await tester.pump(const Duration(milliseconds: 50));

    // Démonte le widget
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('VoiceRail renders reduced bot face, mic button and auto-scrolling tip', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: VoiceRail(
            voiceState: VoiceState.idle,
            statusText: "Prêt",
            voiceTip: "Dites « Orientation », « Renseignements » ou « Consultation »",
            onMicTap: () {},
          ),
        ),
      ),
    );

    // Vérifie le statut
    expect(find.text("Prêt"), findsOneWidget);

    // Vérifie la présence du guide dans AutoScrollText
    expect(find.byType(AutoScrollText), findsOneWidget);
    expect(find.text("Dites « Orientation », « Renseignements » ou « Consultation »"), findsOneWidget);

    // Vérifie la présence de l'icône du micro
    expect(find.byIcon(Icons.mic_none), findsOneWidget);

    // Démonte le widget proprement
    await tester.pumpWidget(const SizedBox());
  });
}
