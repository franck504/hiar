import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
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
  RawDatagramSocket? _discoverySocket;
  Timer? _discoveryProbeTimer;

  static const int discoveryPort = 5005;
  static const List<String> candidateIps = [
    "192.168.43.52",
    "cecilia-desktop.local",
    "127.0.0.1",
    "10.42.0.1",
    "192.168.0.105",
  ];
  int _candidateIndex = 0;
  bool _manualIpSet = false;
  int _consecutiveFailures = 0;
  bool _isConnecting = false;
  bool _isDisposed = false;

  String serverIp = "192.168.43.52";
  int serverPort = 5000;
  bool useTls = const bool.fromEnvironment('HIAR_USE_TLS', defaultValue: false);
  String? authToken;
  bool _isConnected = false;
  int _seq = 0;

  bool get isConnected => _isConnected;

  // Callbacks
  Function(bool connected)? onConnectionChange;
  Function(String textToSpeak, [String? targetScreen])? onTtsRequested;
  Function(String actionId, Map<String, dynamic> args)? onActionRequested;
  Function(String missionState)? onMissionStatus;
  Function(Map<String, dynamic> instruction)? onServerInstruction;
  Function(String ip, int port)? onRobotDiscovered;

  /// Dernier diagnostic capteurs / nœuds reçu en direct du Raspberry Pi
  final ValueNotifier<Map<String, dynamic>?> diagnosticsNotifier = ValueNotifier(null);
  final ValueNotifier<bool> connectedNotifier = ValueNotifier(false);

  String? _lastTtsDispatched;
  DateTime? _lastTtsDispatchedTime;

  /// Diffuse un ordre TTS en filtrant les doublons rapprochés (< 2.5s)
  void _triggerTts(String text, {String? targetScreen}) {
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
    onTtsRequested?.call(clean, targetScreen);
  }

  /// Active la découverte automatique UDP sur le réseau Wi-Fi local (port 5005)
  Future<void> _ensureDiscoveryListening() async {
    if (kIsWeb || _isDisposed || _discoverySocket != null) return;
    try {
      final sock = await RawDatagramSocket.bind(
        InternetAddress.anyIPv4,
        discoveryPort,
        reuseAddress: true,
      );
      if (_isDisposed) {
        sock.close();
        return;
      }
      sock.broadcastEnabled = true;
      _discoverySocket = sock;
      debugPrint("HubClient: Écoute auto-découverte Wi-Fi UDP sur le port $discoveryPort");

      sock.listen(
        (event) {
          if (event != RawSocketEvent.read) return;
          final datagram = sock.receive();
          if (datagram == null) return;
          _handleDiscoveryDatagram(datagram);
        },
        onError: (err) {
          debugPrint("HubClient: Erreur socket découverte UDP: $err");
        },
      );

      _sendDiscoveryProbe();
      _discoveryProbeTimer?.cancel();
      _discoveryProbeTimer = Timer.periodic(const Duration(seconds: 4), (_) {
        if (!_isConnected && !_isDisposed) {
          _sendDiscoveryProbe();
        }
      });
    } catch (e) {
      debugPrint("HubClient: Impossible de lier le port UDP $discoveryPort: $e");
    }
  }

  void _sendDiscoveryProbe() {
    final sock = _discoverySocket;
    if (sock == null) return;
    final data = utf8.encode("HIAR_DISCOVER");
    const targets = ["255.255.255.255", "192.168.43.255", "192.168.0.255", "10.42.0.255"];
    for (final target in targets) {
      try {
        sock.send(data, InternetAddress(target), discoveryPort);
      } catch (_) {}
    }
  }

  bool _verifyDiscoverySignature(Map<String, dynamic> parsed) {
    final sig = parsed["sig"];
    if (sig is! String || sig.isEmpty) {
      const strict = bool.fromEnvironment('HIAR_REQUIRE_BEACON_SIG', defaultValue: false);
      return !strict;
    }
    try {
      const secretStr = String.fromEnvironment('HIAR_DISCOVERY_SECRET', defaultValue: 'hiar_discovery_shared_token_2026');
      final secretBytes = utf8.encode(secretStr);
      final copy = Map<String, dynamic>.from(parsed)..remove("sig");
      final keys = copy.keys.toList()..sort();
      final sortedMap = {for (var k in keys) k: copy[k]};
      final canonicalJson = json.encode(sortedMap);
      final expectedSig = Hmac(sha256, secretBytes).convert(utf8.encode(canonicalJson)).toString();
      return expectedSig == sig;
    } catch (_) {
      return false;
    }
  }

  void _handleDiscoveryDatagram(Datagram datagram) {
    try {
      final raw = utf8.decode(datagram.data, allowMalformed: true).trim();
      if (!raw.startsWith("{")) return;
      final parsed = json.decode(raw);
      if (parsed is! Map<String, dynamic>) return;
      if (parsed["service"] != "hiar_robot") return;

      if (!_verifyDiscoverySignature(parsed)) {
        debugPrint("HubClient: ⚠️ Balise UDP ignorée : signature invalide (usurpation potentielle)");
        return;
      }

      final sourceIp = datagram.address.address;
      final advertisedIp = (parsed["ip"] as String?)?.trim();
      final discoveredIp = (sourceIp.isNotEmpty && sourceIp != "0.0.0.0")
          ? sourceIp
          : (advertisedIp ?? "");
      final discoveredPort = (parsed["ws_port"] is int)
          ? parsed["ws_port"] as int
          : int.tryParse(parsed["ws_port"]?.toString() ?? "5000") ?? 5000;

      if (parsed["auth_token"] is String) {
        final token = (parsed["auth_token"] as String).trim();
        if (token.isNotEmpty) {
          authToken = token;
        }
      }

      if (discoveredIp.isEmpty) return;

      // Si déjà connecté sur cette IP, rien à faire
      if (_isConnected && serverIp == discoveredIp && serverPort == discoveredPort) {
        return;
      }

      // Si une IP manuelle a été fixée et n'a pas encore échoué 2 fois, on la respecte
      if (_manualIpSet && _consecutiveFailures < 2) {
        return;
      }

      if (!_isConnected) {
        debugPrint("HubClient: 📡 Robot HIAR découvert automatiquement sur Wi-Fi -> $discoveredIp:$discoveredPort");
        serverIp = discoveredIp;
        serverPort = discoveredPort;
        _manualIpSet = false;
        _consecutiveFailures = 0;
        onRobotDiscovered?.call(discoveredIp, discoveredPort);
        _reconnectTimer?.cancel();
        connect();
      }
    } catch (_) {}
  }

  /// Relance une détection automatique Wi-Fi du Raspberry Pi
  void triggerAutoDiscovery() {
    _manualIpSet = false;
    _consecutiveFailures = 0;
    _candidateIndex = 0;
    _isDisposed = false;
    _ensureDiscoveryListening().then((_) => _sendDiscoveryProbe());
    if (!_isConnected) {
      _reconnectTimer?.cancel();
      connect();
    }
  }

  /// Démarre la connexion WebSocket vers le Raspberry Pi
  Future<void> connect({String? ip, int? port}) async {
    _isDisposed = false;
    if (ip != null) {
      _manualIpSet = true;
      _consecutiveFailures = 0;
      serverIp = ip;
    }
    if (port != null) serverPort = port;

    if (_isConnecting) return;
    _isConnecting = true;

    _reconnectTimer?.cancel();
    await _ensureDiscoveryListening();

    // Fermer une éventuelle connexion précédente proprement
    _heartbeatTimer?.cancel();
    await _subscription?.cancel();
    _subscription = null;
    try {
      await _channel?.sink.close();
    } catch (_) {}
    _channel = null;

    final scheme = useTls ? "wss" : "ws";
    final wsUrl = Uri.parse("$scheme://$serverIp:$serverPort/ws");
    debugPrint("HubClient: Tentative de connexion à $wsUrl");

    try {
      final channel = WebSocketChannel.connect(wsUrl);
      _channel = channel;

      // Attendre que la poignée de main TCP/WebSocket aboutisse (évite faux "Connecté")
      await channel.ready.timeout(const Duration(seconds: 3));

      if (_isDisposed || _channel != channel) {
        try {
          await channel.sink.close();
        } catch (_) {}
        _isConnecting = false;
        return;
      }

      _subscription = channel.stream.listen(
        _onMessage,
        onDone: _onDisconnected,
        onError: (err) {
          debugPrint("HubClient: Erreur WebSocket: $err");
          _onDisconnected();
        },
      );

      _isConnecting = false;
      _isConnected = true;
      _consecutiveFailures = 0;
      connectedNotifier.value = true;
      onConnectionChange?.call(true);
      debugPrint("HubClient: ✅ Connecté à $wsUrl");

      // 1. Envoi du handshake "hello" selon hiar_contract_v1.json
      _sendHello();

      // 2. Abonnement aux topics du Pi
      _subscribe(HiarTopics.voiceTtsRequest);
      _subscribe(HiarTopics.uiActionRequest);
      _subscribe(HiarTopics.robotMissionStatus);
      _subscribe("server/instruction");
      _subscribe("robot/diagnostics");

      // Heartbeat régulier
      _startHeartbeat();
    } catch (e) {
      debugPrint("HubClient: Échec connexion ($wsUrl): $e");
      _isConnecting = false;
      _onDisconnected();
    }
  }

  void _sendHello() {
    final hello = HiarEnvelope(
      type: "hello",
      deviceId: "mobile_client_1",
      role: "kiosk",
      appVersion: "1.0.0",
      token: authToken ?? const String.fromEnvironment('HIAR_WS_AUTH_TOKEN', defaultValue: "kiosk_token"),
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
      final targetScreen = (payload['instruction_ui'] as Map?)?['screen']?.toString() ?? payload['screen']?.toString();
      if (text != null && text.isNotEmpty) {
        _triggerTts(text, targetScreen: targetScreen);
      }
    }

    // 1. Ordre de parler (TTS demandé par le Raspberry Pi 4)
    else if (topic == HiarTopics.voiceTtsRequest) {
      final text = payload['text'] as String?;
      final targetScreen = payload['screen']?.toString();
      if (text != null && text.isNotEmpty) {
        _triggerTts(text, targetScreen: targetScreen);
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
      final state = (payload['state'] ?? payload['status']) as String?;
      if (state != null) {
        onMissionStatus?.call(state);
      }
    }

    // 4. Diagnostics matériels / capteurs / nœuds ROS 2 en direct
    else if (topic == "robot/diagnostics") {
      diagnosticsNotifier.value = Map<String, dynamic>.from(payload);
    }
  }

  /// Demande un rafraîchissement immédiat des capteurs et diagnostics au Raspberry Pi
  void requestDiagnosticsRefresh() {
    publishAction("diagnostics.refresh", {});
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
  void publishUiState(String screenName, List<String> activeActions, {int? step, Map<String, dynamic>? consultationData}) {
    if (!_isConnected) return;
    _seq++;
    final nowTs = DateTime.now().millisecondsSinceEpoch;

    final payload = <String, dynamic>{
      "screen": screenName,
      "step": step,
      "epoch": nowTs,
      "actions": activeActions,
      "mission_active": screenName == 'mission',
    };
    if (consultationData != null && consultationData.isNotEmpty) {
      payload["consultation_data"] = consultationData;
    }

    final pub = HiarEnvelope(
      type: "pub",
      id: "state_$_seq",
      topic: HiarTopics.uiState,
      ts: nowTs,
      seq: _seq,
      qos: 0,
      payload: payload,
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
    if (_isDisposed) return;
    final wasConnected = _isConnected;
    _isConnected = false;
    _isConnecting = false;
    _consecutiveFailures++;
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    _subscription = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;

    if (wasConnected) {
      connectedNotifier.value = false;
      onConnectionChange?.call(false);
    }

    // Relancer une sonde UDP pour découvrir le Pi sur le Wi-Fi
    _sendDiscoveryProbe();

    // Si aucune IP manuelle n'a été forcée (ou si elle échoue >= 2 fois), basculer sur les candidats suivants
    if (!_manualIpSet || _consecutiveFailures >= 2) {
      _candidateIndex = (_candidateIndex + 1) % candidateIps.length;
      serverIp = candidateIps[_candidateIndex];
    }

    // Tentative de reconnexion automatique en boucle
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 2), () {
      if (!_isDisposed) {
        connect();
      }
    });
  }

  void disconnect() {
    _isDisposed = true;
    _isConnecting = false;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
    _discoveryProbeTimer?.cancel();
    _discoveryProbeTimer = null;
    _subscription?.cancel();
    _subscription = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
    try {
      _discoverySocket?.close();
    } catch (_) {}
    _discoverySocket = null;
    _isConnected = false;
    connectedNotifier.value = false;
  }
}
