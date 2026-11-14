/// Catalogue des topics WebSocket HIAR v1 (hiar_contract_v1.json)
class HiarTopics {
  HiarTopics._();

  // Voix : VAD et micro
  static const String voiceVad = "voice/vad";
  static const String voiceMicControl = "voice/mic/control";

  // Voix : STT
  static const String voiceSttState = "voice/stt/state";
  static const String voiceSttPartial = "voice/stt/partial";
  static const String voiceSttFinal = "voice/stt/final";
  static const String voiceSttError = "voice/stt/error";

  // Voix : TTS
  static const String voiceTtsRequest = "voice/tts/request";
  static const String voiceTtsControl = "voice/tts/control";
  static const String voiceTtsState = "voice/tts/state";

  // Voix : Intentions
  static const String voiceIntentResolved = "voice/intent/resolved";
  static const String voiceIntentUnresolved = "voice/intent/unresolved";
  static const String voiceIntentSuggest = "voice/intent/suggest";

  // Interface et actions
  static const String uiState = "ui/state";
  static const String uiActionRequest = "ui/action/request";
  static const String uiActionResult = "ui/action/result";
  static const String uiConfirmRequest = "ui/confirm/request";
  static const String uiConfirmAnswer = "ui/confirm/answer";

  // Robot (relais ROS 2 en lecture seule)
  static const String robotHmiStatus = "robot/hmi/status";
  static const String robotMissionStatus = "robot/mission/status";
  static const String robotSafety = "robot/safety";
  static const String robotSupervisorStatus = "robot/supervisor/status";
  static const String robotLink = "robot/link";

  // Signes vitaux
  static const String vitalsState = "vitals/state";
  static const String vitalsResult = "vitals/result";

  // Système
  static const String sysConfig = "sys/config";
  static const String sysHealth = "sys/health";
  static const String sysError = "sys/error";
}
