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
        // Délai de 800ms pour laisser l'audio matériel se stabiliser et éliminer l'écho acoustique
        if (_isListeningPermanently) {
          _restartListeningWithDelay(800);
        }
      });

      _tts.setErrorHandler((msg) {
        _isSpeaking = false;
        if (_isListeningPermanently) {
          _restartListeningWithDelay(800);
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
      if (_isListeningPermanently && !_isSpeaking && !_speech.isListening) {
        _startListeningLoop();
      }
    });
  }

  Future<void> _startListeningLoop() async {
    if (!_isSpeechAvailable || _isSpeaking) return;

    if (_speech.isListening) {
      return;
    }

    state = VoiceServiceState.listening;
    onStateChanged?.call(state, "J'écoute en continu…");

    try {
      await _speech.listen(
        onResult: (result) {
          if (_isSpeaking) return;
          final text = result.recognizedWords.trim();
          if (text.isNotEmpty) {
            onRecognizedText?.call(text, result.finalResult);
          }
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
      _restartListeningWithDelay(2000);
    }
  }

  /// Synthèse vocale parlée (TTS) avec anti-doublon strict (supprime les répétitions rapprochées)
  Future<void> speak(String text) async {
    final cleanText = text.trim();
    if (cleanText.isEmpty) return;

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

    // Bloquer immédiatement l'écoute pour éviter tout écho acoustique du haut-parleur
    _isSpeaking = true;
    _restartTimer?.cancel();
    state = VoiceServiceState.speaking;
    onStateChanged?.call(state, "HIAR parle…");

    debugPrint("VoiceService: Demande speak: « $cleanText »");
    lastSpokenText = cleanText;
    if (_speech.isListening) {
      await _speech.cancel();
    }
    final res = await _tts.speak(cleanText);
    debugPrint("VoiceService: Résultat _tts.speak: $res");
  }

  /// Interrompt la parole (Silence)
  Future<void> stopSpeaking() async {
    await _tts.stop();
    _isSpeaking = false;
    if (_isListeningPermanently) {
      _startListeningLoop();
    }
  }
}
