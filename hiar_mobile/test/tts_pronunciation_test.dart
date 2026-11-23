import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/voice/tts_pronunciation.dart';

void main() {
  group('TtsPronunciation (noms malgaches prononcés par une voix française)', () {
    const respelled = 'Razakaharissoua';

    test('réécrit RAZAKAHARISOA quelle que soit la casse', () {
      for (final written in ['RAZAKAHARISOA', 'Razakaharisoa', 'razakaharisoa', 'RaZaKaHaRiSoA']) {
        expect(TtsPronunciation.apply('conçu par $written, ingénieure'), contains(respelled), reason: written);
      }
    });

    test('gère le nom coupé « Razaka Harisoa » ou « Razaka-Harisoa »', () {
      expect(TtsPronunciation.apply('Cecilia Razaka Harisoa'), endsWith(respelled));
      expect(TtsPronunciation.apply('Cecilia RAZAKA-HARISOA'), endsWith(respelled));
    });

    test('phrase complète de présentation du robot', () {
      final spoken = TtsPronunciation.apply(
        "J'ai été conçu par Mlle Cecilia RAZAKAHARISOA, ingénieure en IoT et IA.",
      );
      expect(spoken, "J'ai été conçu par Mlle Cécilia Razakaharissoua, ingénieure en IoT et IA.");
      expect(spoken.contains('RAZAKAHARISOA'), isFalse);
    });

    test('ne touche pas aux autres phrases', () {
      const text = 'Très bien, suivez-moi vers la Pharmacie.';
      expect(TtsPronunciation.apply(text), text);
      expect(TtsPronunciation.apply(''), '');
    });

    test('idempotent : réappliquer ne change plus rien (pas de double correction)', () {
      const text = 'Mlle Cecilia RAZAKAHARISOA';
      final once = TtsPronunciation.apply(text);
      expect(TtsPronunciation.apply(once), once);
    });
  });
}
