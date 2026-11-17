import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/ui/components/sensor_monitor_panel.dart';

void main() {
  testWidgets('SensorMonitorPanel displays live sensor lifecycle and updates dynamically', (tester) async {
    final connected = ValueNotifier<bool>(false);
    final diagnostics = ValueNotifier<Map<String, dynamic>?>(null);
    bool refreshTapped = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 540,
            child: SensorMonitorPanel(
              diagnosticsListenable: diagnostics,
              connectedListenable: connected,
              onRefresh: () => refreshTapped = true,
            ),
          ),
        ),
      ),
    );

    // Hors ligne au départ
    expect(find.text('Moniteur système & capteurs'), findsOneWidget);
    expect(find.text('Hors ligne'), findsOneWidget);
    expect(find.text('ESP32 (USB)'), findsOneWidget);

    // Passage en ligne + réception diagnostic Option B en direct
    connected.value = true;
    diagnostics.value = {
      'firmware_diagnostics': 'option_b',
      'esp32': {'status': 'ok', 'detail': 'Connecté (/dev/ttyUSB0)'},
      'sensors': {
        'ultrasonic': {'status': 'ok', 'distance_cm': 42.5, 'detail': '42.5 cm'},
        'ir_left': {'status': 'ok', 'state': 1, 'raw': 3100, 'detail': 'Libre (ADC 3100)'},
        'ir_right': {'status': 'ok', 'state': 0, 'raw': 800, 'detail': 'Obstacle (ADC 800)'},
        'ds18b20': {'status': 'ok', 'detail': '1-Wire OK (GPIO 23)'},
        'max30102': {'status': 'absent', 'detail': 'Non détecté (I²C 0x57)'},
      },
      'ros_nodes': {'status': 'ok', 'detail': '6/6 actifs'},
      'llm': {'status': 'ok', 'detail': 'Qwen 2.5 prêt'},
    };
    await tester.pump();

    expect(find.text('Sonde live'), findsOneWidget);
    expect(find.textContaining('42.5 cm'), findsOneWidget);
    expect(find.textContaining('1-Wire OK'), findsOneWidget);
    expect(find.textContaining('Non détecté'), findsOneWidget);
    expect(find.textContaining('6/6 actifs'), findsOneWidget);

    // Tap bouton rafraîchir
    await tester.tap(find.byIcon(Icons.refresh_rounded));
    await tester.pump();
    expect(refreshTapped, isTrue);

    connected.dispose();
    diagnostics.dispose();
  });
}
