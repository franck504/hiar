import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/ui/components/auto_scroll_text.dart';

/// Sur l'écran Mission, le conseil vocal change au moment du STOP
/// (« Dites Stop… » -> « Dites Reprendre ou Terminer »), en pleine animation.
void main() {
  Widget host(String text) => MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 120,
              child: AutoScrollText(text: text, pauseDuration: const Duration(milliseconds: 100)),
            ),
          ),
        ),
      );

  testWidgets('changer le texte pendant le défilement ne lève aucune exception', (tester) async {
    await tester.pumpWidget(host('Dites « Stop » pour arrêter le robot immédiatement, merci'));
    await tester.pump(const Duration(milliseconds: 300)); // fin de la pause initiale
    await tester.pump(const Duration(milliseconds: 600)); // en plein défilement

    for (var i = 0; i < 5; i++) {
      await tester.pumpWidget(host(i.isEven
          ? 'Dites « Reprendre » ou « Terminer » pour continuer la mission'
          : 'Dites « Stop » pour arrêter le robot immédiatement, merci'));
      await tester.pump(const Duration(milliseconds: 250));
      await tester.pump(const Duration(milliseconds: 400));
    }
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 3));
    expect(tester.takeException(), isNull);
  });
}
