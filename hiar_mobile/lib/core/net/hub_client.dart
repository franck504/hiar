import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../bus/envelope.dart';
import '../bus/topics.dart';

class HubClient {
  static final HubClient instance = HubClient._internal();
  HubClient._internal();

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  Timer? _heartbeatTimer;

  static const List<String> candidateIps = ["127.0.0.1", "192.168.43.181", "10.42.0.1", "192.168.0.105"];
  int _candidateIndex = 0;
  bool _manualIpSet = false;

  String serverIp = "127.0.0.1";
  int serverPort = 5000;
  bool _isConnected = false;
  int _seq = 0;

  bool get isConnected => _isConnected;

  // Callbacks
  Function(bool connected)? onConnectionChange;
  Function(String textToSpeak)? onTtsRequested;
  Function(String actionId, Map<String, dynamic> args)? onActionRequested;
  Function(String missionState)? onMissionStatus;
  Function(Map<String, dynamic> instruction)? onServerInstruction;

  String? _lastTtsDispatched;
  DateTime? _lastTtsDispatchedTime;

  /// Diffuse un ordre TTS en filtrant les doublons rapprochés (< 2.5s)
  void _triggerTts(String text) {
    final clean = text.trim();
    if (clean.isEmpty) return;
    final now = DateTime.now();
    if (_lastTtsDispatched != null &&
        _lastTtsDispatched == clean &&
        _lastTtsDispatchedTime != null &&
        now.difference(_lastTtsDispatchedTime!) < const Duration(milliseconds: 2500)) {
      debugPrint("HubClient: Doublon TTS ignoré: « $clean »");
      return;
    }
    _lastTtsDispatched = clean;
    _lastTtsDispatchedTime = now;
    onTtsRequested?.call(clean);
  }

  /// Démarre la connexion WebSocket vers le Raspberry Pi
  void connect({String? ip, int? port}) {
    if (ip != null) {
      _manualIpSet = true;
      serverIp = ip;
    }
    if (port != null) serverPort = port;

    _reconnectTimer?.cancel();
    final wsUrl = Uri.parse("ws://$serverIp:$serverPort/ws");

    debugPrint("HubClient: Tentative de connexion à $wsUrl");

    try {
      _channel = WebSocketChannel.connect(wsUrl);
      _subscription = _channel!.stream.listen(
        _onMessage,
        onDone: _onDisconnected,
        onError: (err) {
          debugPrint("HubClient: Erreur WebSocket: $err");
          _onDisconnected();
        },
      );

      _isConnected = true;
      onConnectionChange?.call(true);

      // 1. Envoi du handshake "hello" selon hiar_contract_v1.json
      _sendHello();

      // 2. Abonnement aux topics du Pi
      _subscribe(HiarTopics.voiceTtsRequest);
      _subscribe(HiarTopics.uiActionRequest);
      _subscribe(HiarTopics.robotMissionStatus);
      _subscribe("server/instruction");

      // Heartbeat régulier
      _startHeartbeat();
    } catch (e) {
      debugPrint("HubClient: Exception connexion: $e");
      _onDisconnected();
    }
  }

  void _sendHello() {
    final hello = HiarEnvelope(
      type: "hello",
      deviceId: "mobile_client_1",
      role: "kiosk",
      appVersion: "1.0.0",
      token: "kiosk_token",
    );
    _send(hello);
  }

  void _subscribe(String topic) {
    _seq++;
    final sub = HiarEnvelope(
      type: "sub",
      id: "sub_$_seq",
      topic: topic,
    );
    _send(sub);
  }

  void _send(HiarEnvelope envelope) {
    if (_channel != null && _isConnected) {
      try {
        _channel!.sink.add(envelope.encode());
      } catch (e) {
        debugPrint("HubClient: Erreur d'envoi: $e");
      }
    }
  }

  void _onMessage(dynamic raw) {
    try {
      final jsonMap = json.decode(raw.toString()) as Map<String, dynamic>;
      final envelope = HiarEnvelope.fromJson(jsonMap);

      if (envelope.type == "welcome") {
        debugPrint("HubClient: Bienvenue reçu du Hub Raspberry Pi");
      } else if (envelope.type == "pong") {
        // Pong de heartbeat normal, rien à afficher
      } else if (envelope.type == "pub" || envelope.type == "publish") {
        _handleIncomingPub(envelope.topic ?? "", envelope.payload ?? {});
      } else {
        debugPrint("HubClient: Message de type non géré: ${envelope.type}");
      }
    } catch (e) {
      debugPrint("HubClient: Erreur décodage message entrant: $e");
    }
  }

  void _handleIncomingPub(String topic, Map<String, dynamic> payload) {
    debugPrint("HubClient: Message reçu sur [$topic] -> $payload");

    // 0. Instruction globale unifiée du serveur (TTS + UI + Données / Signes vitaux)
    if (topic == "server/instruction") {
      onServerInstruction?.call(payload);
      final text = payload['text_to_speak'] as String?;
      if (text != null && text.isNotEmpty) {
        _triggerTts(text);
      }
    }

    // 1. Ordre de parler (TTS demandé par le Raspberry Pi 4)
    else if (topic == HiarTopics.voiceTtsRequest) {
      final text = payload['text'] as String?;
      if (text != null && text.isNotEmpty) {
        _triggerTts(text);
      }
    }

    // 2. Action d'interface demandée par le Raspberry Pi 4
    else if (topic == HiarTopics.uiActionRequest) {
      final actionId = payload['action_id'] as String?;
      final args = payload['args'] as Map<String, dynamic>? ?? {};
      if (actionId != null) {
        onActionRequested?.call(actionId, args);
      }
    }

    // 3. Statut du robot relayé par ROS 2
    else if (topic == HiarTopics.robotMissionStatus) {
      final state = payload['state'] as String?;
      if (state != null) {
        onMissionStatus?.call(state);
      }
    }
  }

  /// PUBLICATION STT : Envoie le texte brut entendu par le micro au Raspberry Pi
  void publishSttFinal(String rawText, {double confidence = 0.95}) {
    if (!_isConnected) return;
    _seq++;
    final nowTs = DateTime.now().millisecondsSinceEpoch;

    final pub = HiarEnvelope(
      type: "pub",
      id: "stt_$_seq",
      topic: HiarTopics.voiceSttFinal,
      ts: nowTs,
      seq: _seq,
      qos: 1,
      payload: {
        "utt": "utt_$_seq",
        "text": rawText,
        "lang": "fr",
        "conf": confidence,
        "mode": "command",
        "sensitive": false,
      },
    );

    debugPrint("HubClient: Envoi STT vers Raspberry Pi: « $rawText »");
    _send(pub);
  }

  /// PUBLICATION TACTILE : Envoie une action déclenchée par un clic sur l'écran
  void publishAction(String actionId, Map<String, dynamic> args) {
    if (!_isConnected) return;
    _seq++;
    final nowTs = DateTime.now().millisecondsSinceEpoch;

    final pub = HiarEnvelope(
      type: "pub",
      id: "act_$_seq",
      topic: HiarTopics.uiActionRequest,
      ts: nowTs,
      seq: _seq,
      qos: 1,
      payload: {
        "action_id": actionId,
        "args": args,
        "origin": "touch",
        "corr": "corr_$_seq",
        "epoch": nowTs,
      },
    );

    debugPrint("HubClient: Envoi Action tactile vers Raspberry Pi: $actionId");
    _send(pub);
  }

  /// PUBLICATION UI STATE : Notifie le Pi de l'écran affiché
  void publishUiState(String screenName, List<String> activeActions) {
    if (!_isConnected) return;
    _seq++;
    final nowTs = DateTime.now().millisecondsSinceEpoch;

    final pub = HiarEnvelope(
      type: "pub",
      id: "state_$_seq",
      topic: HiarTopics.uiState,
      ts: nowTs,
      seq: _seq,
      qos: 0,
      payload: {
        "screen": screenName,
        "epoch": nowTs,
        "actions": activeActions,
        "mission_active": screenName == 'mission',
      },
    );

    _send(pub);
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      if (_isConnected) {
        final ping = HiarEnvelope(type: "ping");
        _send(ping);
      }
    });
  }

  void _onDisconnected() {
    _isConnected = false;
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    _channel = null;
    onConnectionChange?.call(false);

    // Si aucune IP manuelle n'a été saisie, essayer le candidat suivant (127.0.0.1, 10.42.0.1, 192.168.0.105)
    if (!_manualIpSet) {
      _candidateIndex = (_candidateIndex + 1) % candidateIps.length;
      serverIp = candidateIps[_candidateIndex];
    }

    // Tentative de reconnexion automatique en boucle
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      connect();
    });
  }

  void disconnect() {
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _channel = null;
    _isConnected = false;
  }
}
