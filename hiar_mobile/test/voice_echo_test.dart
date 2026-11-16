import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/voice/voice_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('VoiceService Acoustic Echo Cancellation Tests', () {
    final voice = VoiceService.instance;

    test('normalizeText handles punctuation, accents and spaces', () {
      final raw = "Bonjour, je suis le robot ! Suivez-moi, s'il vous plaît...";
      final normalized = VoiceService.normalizeText(raw);
      expect(
        normalized,
        "bonjour je suis le robot suivez moi s il vous plaît",
      );
    });

    test('isAcousticEcho returns false when robot never spoke', () {
      voice.lastSpokenText = null;
      voice.lastSpokenEndTime = null;
      expect(voice.isAcousticEcho("bonjour"), isFalse);
    });

    test('isAcousticEcho detects echo while robot is speaking with punctuation mismatch', () {
      voice.lastSpokenText =
          "Je n'ai pas bien compris votre demande. Vous pouvez me demander la pharmacie, le laboratoire, mesurer vos constantes ou des informations de santé.";
      // Simule que le TTS a terminé il y a 200 ms (latence buffer STT)
      voice.lastSpokenEndTime = DateTime.now().subtract(const Duration(milliseconds: 200));

      // 1. Transcription brute STT Android (sans ponctuation ni majuscules)
      const sttCaptured =
          "je n'ai pas bien compris votre demande vous pouvez me demander la pharmacie le laboratoire";
      expect(voice.isAcousticEcho(sttCaptured), isTrue);

      // 2. Fragment de phrase capté
      expect(voice.isAcousticEcho("vous pouvez me demander la pharmacie"), isTrue);
      expect(voice.isAcousticEcho("la pharmacie le laboratoire"), isTrue);

      // 3. Phrase avec légère variation de transcription STT (overlap >= 50%)
      expect(voice.isAcousticEcho("vous pouvez demander pharmacie laboratoire"), isTrue);
    });

    test('isAcousticEcho does NOT flag legitimate user speech (Barge-in / New intent)', () {
      voice.lastSpokenText =
          "Je n'ai pas bien compris votre demande. Vous pouvez me demander la pharmacie, le laboratoire...";
      voice.lastSpokenEndTime = DateTime.now().subtract(const Duration(milliseconds: 200));

      // L'utilisateur interrompt le robot avec un mot court ou une commande
      expect(voice.isAcousticEcho("stop"), isFalse);
      expect(voice.isAcousticEcho("arrête"), isFalse);
      expect(voice.isAcousticEcho("non"), isFalse);
      expect(voice.isAcousticEcho("attends"), isFalse);
      expect(voice.isAcousticEcho("emmène-moi aux urgences"), isFalse);
      expect(voice.isAcousticEcho("docteur martin"), isFalse);
    });

    test('isAcousticEcho allows all user input after cooldown window has expired', () {
      voice.lastSpokenText = "Suivez-moi, nous allons à la pharmacie.";
      // Le robot a terminé de parler il y a plus de 2.5 secondes
      voice.lastSpokenEndTime = DateTime.now().subtract(const Duration(milliseconds: 2500));

      // L'usager peut maintenant prononcer n'importe quel mot sans être filtré
      expect(voice.isAcousticEcho("pharmacie"), isFalse);
      expect(voice.isAcousticEcho("la pharmacie"), isFalse);
      expect(voice.isAcousticEcho("suivez-moi"), isFalse);
    });
  });
}
