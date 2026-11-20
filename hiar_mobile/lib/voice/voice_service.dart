import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:flutter_tts/flutter_tts.dart';

enum VoiceServiceState {
  uninitialized,
  listening,
  processing,
  speaking,
  error,
}

class VoiceService {
  static final VoiceService instance = VoiceService._internal();
  VoiceService._internal();

  final SpeechToText _speech = SpeechToText();
  final FlutterTts _tts = FlutterTts();

  bool _isSpeechAvailable = false;
  bool _isListeningPermanently = false;
  bool _isSpeaking = false;
  bool get isSpeaking => _isSpeaking;

  VoiceServiceState state = VoiceServiceState.uninitialized;

  // Callbacks : texte reconnu, et indicateur booléen isFinal
  Function(String text, bool isFinal)? onRecognizedText;
  Function(VoiceServiceState state, String statusMessage)? onStateChanged;

  String? lastSpokenText;
  DateTime? lastSpokenEndTime;
  final List<String> _recentSpokenTexts = [];
  String? _lastSpokenPhrase;
  DateTime? _lastSpokenTime;

  Future<bool> init() async {
    try {
      // 1. Initialisation TTS
      final langRes = await _tts.setLanguage("fr-FR");
      debugPrint("VoiceService: TTS setLanguage fr-FR -> $langRes");
      await _tts.setSpeechRate(0.9);
      await _tts.setVolume(1.0);
      await _tts.setPitch(1.0);

      _tts.setStartHandler(() {
        _isSpeaking = true;
        state = VoiceServiceState.speaking;
        onStateChanged?.call(state, "HIAR parle…");
      });

      _tts.setCompletionHandler(() {
        _isSpeaking = false;
        lastSpokenEndTime = DateTime.now();
        state = VoiceServiceState.listening;
        onStateChanged?.call(state, "J'écoute en continu…");
        if (_isListeningPermanently && !_speech.isListening) {
          _restartListeningWithDelay(200);
        }
      });

      _tts.setErrorHandler((msg) {
        _isSpeaking = false;
        lastSpokenEndTime = DateTime.now();
        state = VoiceServiceState.listening;
        onStateChanged?.call(state, "J'écoute en continu…");
        if (_isListeningPermanently && !_speech.isListening) {
          _restartListeningWithDelay(200);
        }
      });

      // 2. Initialisation STT
      _isSpeechAvailable = await _speech.initialize(
        onError: (val) {
          debugPrint('STT Error: ${val.errorMsg}');
          if (_isListeningPermanently && !_isSpeaking) {
            final delay = val.errorMsg.contains('busy') ? 1500 : 250;
            _restartListeningWithDelay(delay);
          }
        },
        onStatus: (val) {
          debugPrint('STT Status: $val');
          if (val == 'notListening' || val == 'done') {
            if (_isListeningPermanently && !_isSpeaking) {
              _restartListeningWithDelay(150);
            }
          }
        },
      );

      return _isSpeechAvailable;
    } catch (e) {
      debugPrint("VoiceService init error: $e");
      return false;
    }
  }

  /// Démarre l'écoute permanente sans interruption
  void startPermanentListening() {
    _isListeningPermanently = true;
    _startListeningLoop();
  }

  /// Arrête l'écoute permanente
  void stopPermanentListening() {
    _isListeningPermanently = false;
    _restartTimer?.cancel();
    _speech.stop();
    state = VoiceServiceState.uninitialized;
    onStateChanged?.call(state, "Écoute désactivée");
  }

  Timer? _restartTimer;

  void _restartListeningWithDelay([int delayMs = 600]) {
    _restartTimer?.cancel();
    _restartTimer = Timer(Duration(milliseconds: delayMs), () {
      if (_isListeningPermanently && !_speech.isListening) {
        _startListeningLoop();
      }
    });
  }

  /// Normalise un texte (minuscules, sans ponctuation, espaces régularisés)
  static String normalizeText(String text) {
    return text
        .toLowerCase()
        .replaceAll('_', ' ')
        .replaceAll(RegExp(r"[^\w\sàâäéèêëîïôöùûüçœæÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŒÆ]", caseSensitive: false), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
  }

  /// Détecte si le texte capté par le micro provient du haut-parleur du robot (écho acoustique).
  ///
  /// L'écho peut survenir soit pendant que le robot parle (`isSpeaking`), soit pendant
  /// la latence de traitement audio du STT Android (jusqu'à `cooldownMs` ms après la fin du TTS).
  bool isAcousticEcho(String recognized, {int cooldownMs = 1800}) {
    final clean = recognized.trim();
    if (clean.isEmpty) return false;

    final now = DateTime.now();
    final wasRecentlySpeaking = _isSpeaking ||
        (lastSpokenEndTime != null &&
            now.difference(lastSpokenEndTime!) < Duration(milliseconds: cooldownMs));

    if (!wasRecentlySpeaking) {
      return false;
    }

    final rNorm = normalizeText(clean);
    if (rNorm.isEmpty) return false;

    // Comparaison avec les phrases récemment émises par le robot
    final candidates = <String>{};
    if (lastSpokenText != null && lastSpokenText!.trim().isNotEmpty) {
      candidates.add(lastSpokenText!.trim());
    }
    candidates.addAll(_recentSpokenTexts);

    if (candidates.isEmpty) return false;

    for (final cand in candidates) {
      final sNorm = normalizeText(cand);
      if (sNorm.isEmpty) continue;

      // 1. Inclusion directe : le texte capté est inclus dans la phrase parlée ou vice-versa
      if (sNorm.contains(rNorm) || rNorm.contains(sNorm)) {
        return true;
      }

      // 2. Chevauchement de mots significatifs (mots >= 3 caractères)
      final rWords = rNorm.split(' ').where((w) => w.length >= 3).toList();
      final sWords = sNorm.split(' ').where((w) => w.length >= 3).toSet();

      if (rWords.isNotEmpty) {
        int matchCount = 0;
        for (final w in rWords) {
          if (sWords.contains(w)) matchCount++;
        }

        // Si au moins 50% des mots captés correspondent à la phrase du robot
        final ratio = matchCount / rWords.length;
        if (ratio >= 0.5) {
          return true;
        }

        // Si au moins 3 mots distincts correspondent
        if (matchCount >= 3) {
          return true;
        }
      }
    }

    return false;
  }

  Future<void> _startListeningLoop() async {
    if (!_isSpeechAvailable) return;

    if (_speech.isListening) {
      return;
    }

    state = _isSpeaking ? VoiceServiceState.speaking : VoiceServiceState.listening;
    if (!_isSpeaking) {
      onStateChanged?.call(state, "J'écoute en continu…");
    }

    try {
      await _speech.listen(
        onResult: (result) async {
          final text = result.recognizedWords.trim();
          if (text.isEmpty) return;

          // 1. Filtrage anti-écho acoustique (micro entendant le haut-parleur)
          if (isAcousticEcho(text)) {
            debugPrint("VoiceService: Écho acoustique du robot ignoré: « $text »");
            return;
          }

          // 2. Si le robot parle et que ce n'est pas son écho -> L'utilisateur parle (Barge-In) !
          // Coupure immédiate du TTS pour laisser la parole à l'utilisateur
          if (_isSpeaking) {
            debugPrint("VoiceService: ⚡ Barge-in détecté ! L'utilisateur parle (« $text ») -> Coupure TTS immédiate.");
            await stopSpeaking();
          }

          onRecognizedText?.call(text, result.finalResult);
        },
        localeId: "fr_FR",
        listenFor: const Duration(minutes: 10),
        pauseFor: const Duration(seconds: 30),
        partialResults: true,
        cancelOnError: false,
        listenMode: ListenMode.dictation,
      );
    } catch (e) {
      debugPrint("Speech listen error: $e");
      _restartListeningWithDelay(1500);
    }
  }

  int _generation = 0;
  int get currentGeneration => _generation;

  /// Synthèse vocale parlée (TTS) avec anti-doublon strict et vérification de génération (évite de parler pour un écran passé)
  Future<void> speak(String text, {int? forGeneration}) async {
    final cleanText = text.trim();
    if (cleanText.isEmpty) return;

    final targetGen = forGeneration ?? _generation;
    if (targetGen != _generation) {
      debugPrint("VoiceService: Parole annulée car l'écran a changé (gen $targetGen != $_generation)");
      return;
    }

    final now = DateTime.now();
    if (_lastSpokenPhrase != null &&
        _lastSpokenPhrase == cleanText &&
        _lastSpokenTime != null &&
        now.difference(_lastSpokenTime!) < const Duration(milliseconds: 2500)) {
      debugPrint("VoiceService: Doublon TTS ignoré: « $cleanText » (délai < 2.5s)");
      return;
    }
    _lastSpokenPhrase = cleanText;
    _lastSpokenTime = now;

    _isSpeaking = true;
    _restartTimer?.cancel();
    state = VoiceServiceState.speaking;
    onStateChanged?.call(state, "HIAR parle…");

    debugPrint("VoiceService: Demande speak (gen $_generation): « $cleanText »");
    lastSpokenText = cleanText;
    _recentSpokenTexts.add(cleanText);
    if (_recentSpokenTexts.length > 5) {
      _recentSpokenTexts.removeAt(0);
    }

    // S'assurer que le micro reste ouvert pour permettre à l'utilisateur de couper la parole (Barge-In)
    if (!_speech.isListening && _isListeningPermanently) {
      _startListeningLoop();
    }

    final res = await _tts.speak(cleanText);
    debugPrint("VoiceService: Résultat _tts.speak: $res");

    // Si entre-temps l'écran a changé pendant le lancement du TTS, couper immédiatement
    if (targetGen != _generation) {
      await _tts.stop();
      _isSpeaking = false;
    }
  }

  /// Interrompt la parole (Silence immédiat) et invalide les messages vocaux de l'écran précédent
  Future<void> stopSpeaking() async {
    _generation++;
    _lastSpokenPhrase = null;
    await _tts.stop();
    _isSpeaking = false;
    lastSpokenEndTime = DateTime.now();
    state = VoiceServiceState.listening;
    onStateChanged?.call(state, "J'écoute en continu…");
    if (_isListeningPermanently && !_speech.isListening) {
      _startListeningLoop();
    }
  }
}
