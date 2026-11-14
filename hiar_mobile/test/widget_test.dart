import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/core/net/hub_client.dart';
import 'package:hiar_mobile/main.dart';

void main() {
  testWidgets('HIAR App launches on Splash Screen', (WidgetTester tester) async {
    await tester.pumpWidget(const HiarApp());
    expect(find.text('Bonjour !'), findsOneWidget);
    expect(find.text('Touchez l’écran ou dites « Commencer »'), findsOneWidget);

    // Nettoyage des timers lors du démontage
    await tester.pumpWidget(const SizedBox());
    HubClient.instance.disconnect();
  });
}
