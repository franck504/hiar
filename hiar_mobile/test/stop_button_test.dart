import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:hiar_mobile/core/net/hub_client.dart';
import 'package:hiar_mobile/features/splash/splash_screen.dart';
import 'package:hiar_mobile/main.dart';
import 'package:hiar_mobile/ui/components/hiar_toast.dart';

/// Régression « STOP ROBOT » : appuis répétés, notification qui ne masque aucun bouton
/// et état « arrêté » conservé quand le Supervisor publie IDLE.
void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    HiarToast.resetForTests();
  });

  Future<void> openHome(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(const HiarApp());
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(find.byType(SplashScreen));
    await tester.pump(const Duration(milliseconds: 400));
    // L'accueil déborde de quelques pixels avec la police de test (Ahem) : sans rapport avec le STOP.
    tester.takeException();
  }

  Future<void> closeApp(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    HubClient.instance.disconnect();
    await tester.pump(const Duration(seconds: 4));
    tester.takeException();
  }

  testWidgets('STOP ROBOT : appuis répétés sans exception, une seule notification étroite en bas à gauche',
      (tester) async {
    await openHome(tester);

    final stop = find.text('STOP ROBOT');
    expect(stop, findsOneWidget);

    for (var i = 0; i < 6; i++) {
      await tester.tap(stop);
      await tester.pump(const Duration(milliseconds: 80));
      expect(tester.takeException(), isNull, reason: 'appui $i');
    }

    // Pas de file d'attente : une seule notification visible
    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.text("ARRÊT D'URGENCE DU ROBOT !"), findsOneWidget);

    // Étroite et ancrée au-dessus du rail vocal (248 dp à gauche) : jamais sur les boutons de la scène.
    // (le SnackBar englobe ses marges : on mesure son contenu)
    final bubble = tester.getRect(find.descendant(
      of: find.byType(SnackBar),
      matching: find.byType(Material),
    ).first);
    expect(bubble.width, lessThanOrEqualTo(HiarToast.width + 1));
    expect(bubble.left, lessThan(24));
    expect(bubble.right, lessThan(248));
    expect(bubble.bottom, greaterThan(600)); // en bas de l'écran, côté rail

    // Disparaît d'elle-même
    await tester.pump(const Duration(seconds: 4));
    await tester.pump(const Duration(seconds: 1));
    expect(find.byType(SnackBar), findsNothing);

    await closeApp(tester);
  });

  testWidgets('Mission : le statut IDLE du Supervisor ne rouvre pas la mission après un STOP', (tester) async {
    await openHome(tester);

    // Le serveur confirme l'orientation -> écran Mission en cours
    HubClient.instance.onActionRequested?.call('orientation.confirm', {});
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.textContaining('Je vous accompagne vers'), findsOneWidget);

    // Sur l'écran Mission, le grand bouton rouge central est le bouton d'arrêt
    await tester.tap(find.textContaining('ARRÊT DU ROBOT'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text("Le robot s'est arrêté."), findsOneWidget);

    // Le Supervisor publie IDLE juste après le STOP : l'écran doit rester « arrêté »
    HubClient.instance.onMissionStatus?.call('IDLE');
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text("Le robot s'est arrêté."), findsOneWidget);
    expect(find.textContaining('Je vous accompagne vers'), findsNothing);

    // « Reprendre » rouvre bien la mission
    await tester.tap(find.textContaining('Reprendre ('));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.textContaining('Je vous accompagne vers'), findsOneWidget);
    expect(find.text('REPRISE DU GUIDAGE !'), findsOneWidget);

    await closeApp(tester);
  });
}
