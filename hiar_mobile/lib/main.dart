import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/net/hub_client.dart';
import 'features/splash/splash_screen.dart';
import 'features/home/home_screen.dart';
import 'features/orientation/orientation_screen.dart';
import 'features/orientation/mission_screen.dart';
import 'features/information/information_screen.dart';
import 'features/consultation/consultation_screen.dart';
import 'ui/rail/voice_rail.dart';
import 'ui/theme/hiar_colors.dart';
import 'voice/voice_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Forcer le mode paysage horizontal
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  runApp(const HiarApp());
}

class HiarApp extends StatefulWidget {
  const HiarApp({super.key});

  @override
  State<HiarApp> createState() => _HiarAppState();
}

class _HiarAppState extends State<HiarApp> {
  final HubClient _hub = HubClient.instance;
  final GlobalKey<ConsultationScreenState> _consultationKey = GlobalKey<ConsultationScreenState>();

  String _currentScreen = 'splash';
  String _selectedDestination = 'Pharmacie';
  String _missionState = 'RUNNING';

  // État vocal & réseau
  VoiceState _voiceState = VoiceState.listening;
  String _voiceStatus = "J'écoute en continu…";
  String? _currentVoiceTip;
  String? _recognizedText;
  String? _faceExpression;
  bool _isRobotConnected = false;
  bool _awaitingVoiceResponse = false;
  Timer? _voiceResponseTimeoutTimer;

  // Données dynamiques transmises par le Raspberry Pi 4 / ROS 2 (ex: température, rythme cardiaque, étape)
  final Map<String, dynamic> _dynamicFields = {};
  int _consultationStep = 1;

  String? _lastSentSttText;
  DateTime? _lastSentSttTime;
  Timer? _sttDebounceTimer;
  String? _pendingSttText;

  void _clearVoiceLoading() {
    _voiceResponseTimeoutTimer?.cancel();
    _voiceResponseTimeoutTimer = null;
    if (_awaitingVoiceResponse) {
      _awaitingVoiceResponse = false;
    }
  }

  void _startVoiceLoading() {
    _voiceResponseTimeoutTimer?.cancel();
    if (!mounted) return;
    setState(() {
      _awaitingVoiceResponse = true;
      _voiceState = VoiceState.thinking;
      _voiceStatus = "Réflexion en cours…";
    });
    // Timeout de sécurité (si fragment ignoré ou latence réseau)
    _voiceResponseTimeoutTimer = Timer(const Duration(seconds: 12), () {
      if (!mounted || !_awaitingVoiceResponse) return;
      setState(() {
        _awaitingVoiceResponse = false;
        _voiceState = VoiceState.listening;
        _voiceStatus = "J'écoute en continu…";
      });
    });
  }

  void _sendSttFinalDebounced(String text) {
    final clean = text.trim();
    if (clean.isEmpty) return;

    final voice = VoiceService.instance;
    if (voice.isSpeaking) {
      voice.stopSpeaking();
    }

    // Protection anti-écho robuste : ignorer si le micro a capté ce que le TTS a prononcé
    if (voice.isAcousticEcho(clean)) {
      debugPrint("STT ignoré car écho acoustique du robot: « $clean »");
      return;
    }

    final now = DateTime.now();
    if (_lastSentSttText != null &&
        _lastSentSttText!.toLowerCase() == clean.toLowerCase() &&
        _lastSentSttTime != null &&
        now.difference(_lastSentSttTime!) < const Duration(milliseconds: 2500)) {
      debugPrint("STT ignoré car doublon récent (< 2.5s): « $clean »");
      return;
    }
    _lastSentSttText = clean;
    _lastSentSttTime = now;
    debugPrint("🎤 HubClient: Envoi STT vers serveur: « $clean »");
    if (_isRobotConnected) {
      _startVoiceLoading();
    }
    _hub.publishSttFinal(clean);
  }

  final GlobalKey<NavigatorState> _navKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    _initNetworkAndVoice();
  }

  @override
  void dispose() {
    _sttDebounceTimer?.cancel();
    _voiceResponseTimeoutTimer?.cancel();
    _hub.disconnect();
    super.dispose();
  }

  /// Initialise la liaison WebSocket avec le Raspberry Pi 4 et le moteur vocal
  Future<void> _initNetworkAndVoice() async {
    // 1. Liaison WebSocket avec le Raspberry Pi 4
    _hub.onConnectionChange = (connected) {
      if (!mounted) return;
      setState(() {
        _isRobotConnected = connected;
      });
    };

    // 2. Réception d'ordres TTS depuis le Raspberry Pi 4 : faire parler le robot à haute voix
    _hub.onTtsRequested = (textToSpeak, [targetScreen]) {
      _clearVoiceLoading();
      if (targetScreen != null && targetScreen != _currentScreen) {
        debugPrint("TTS ignoré car destiné à l'écran '$targetScreen' alors que l'écran actuel est '$_currentScreen'");
        return;
      }
      debugPrint("TTS Reçu du Pi 4 -> Émission vocale : « $textToSpeak »");
      VoiceService.instance.speak(textToSpeak, forGeneration: VoiceService.instance.currentGeneration);
    };

    // 3. Réception d'actions décidées par le Raspberry Pi 4 (après son analyse du texte ou ROS 2)
    _hub.onActionRequested = (actionId, args) {
      _clearVoiceLoading();
      debugPrint("Action reçue du Pi 4 -> $actionId avec $args");
      _handleServerAction(actionId, args);
    };

    // 4. Réception du paquet unifié ServerInstruction (UI + TTS + Données / Signes vitaux)
    _hub.onServerInstruction = (instruction) {
      _clearVoiceLoading();
      debugPrint("ServerInstruction reçu du Pi 4 -> $instruction");
      _handleServerInstruction(instruction);
    };

    // 5. Statut de mission robot reçu depuis ROS 2 via le hub
    _hub.onMissionStatus = (missionState) {
      if (!mounted) return;
      setState(() {
        _missionState = missionState;
      });
    };

    // 6. Auto-découverte Wi-Fi UDP du Raspberry Pi (sauvegarde automatique de l'IP)
    _hub.onRobotDiscovered = (discoveredIp, discoveredPort) async {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('server_ip', discoveredIp);
      await prefs.setInt('server_port', discoveredPort);
      if (mounted) {
        setState(() {});
      }
    };

    // Connexion au Hub WebSocket (restaure l'IP et le port sauvegardés)
    final prefs = await SharedPreferences.getInstance();
    final savedIp = prefs.getString('server_ip');
    final savedPort = prefs.getInt('server_port');
    if (savedIp != null && savedIp.isNotEmpty) {
      _hub.serverIp = savedIp;
    }
    if (savedPort != null && savedPort > 0) {
      _hub.serverPort = savedPort;
    }
    _hub.connect();

    // 5. Initialisation du moteur vocal natif (Écoute permanente)
    final voice = VoiceService.instance;
    final available = await voice.init();

    if (!mounted) return;

    if (available) {
      // DÈS QUE LE MICRO ENTEND DU TEXTE (ou VAD) :
      voice.onRecognizedText = (text, isFinal) {
        if (!mounted) return;

        // Protection supplémentaire contre l'écho acoustique
        if (voice.isAcousticEcho(text)) {
          debugPrint("onRecognizedText: Écho acoustique ignoré: « $text »");
          return;
        }

        if (voice.isSpeaking) {
          voice.stopSpeaking();
        }
        setState(() {
          _recognizedText = text;
        });

        // 1. Si on est sur l'écran d'accueil initial (Splash Screen) et qu'une voix est détectée :
        if (_currentScreen == 'splash') {
          _goToScreen('home');
        }

        // 2. Si le moteur vocal signale une fin de phrase (isFinal) :
        if (isFinal) {
          _sttDebounceTimer?.cancel();
          _pendingSttText = null;
          _sendSttFinalDebounced(text);
          return;
        }

        // 3. Temporisation intelligente VAD (Pause naturelle de parole) :
        // Évite de couper la phrase trop tôt quand l'usager respire ou hésite.
        _pendingSttText = text;
        _sttDebounceTimer?.cancel();

        final lower = text.trim().toLowerCase();
        // Commandes courtes ou d'urgence directes : transmission ultra-rapide (500 ms)
        final isUrgentOrShort = RegExp(r'^(stop|arrête|arret|pause|reprendre|terminer|bonjour|salut|docteur)$').hasMatch(lower);

        // Amorce de phrase incomplète en suspens (ex: "je veux aller au...", "direction la...")
        final isIncomplete = RegExp(r'(au|à|a|vers|pour|dans|le|la|les|du|de|aller|aller au|aller à|vers le|vers la|emmène|emmène-moi)$').hasMatch(lower);

        final delayMs = isUrgentOrShort
            ? 500
            : (isIncomplete ? 2200 : 1500);

        _sttDebounceTimer = Timer(Duration(milliseconds: delayMs), () {
          if (_pendingSttText != null && _pendingSttText!.trim().isNotEmpty) {
            _sendSttFinalDebounced(_pendingSttText!);
            _pendingSttText = null;
          }
        });
      };

      voice.onStateChanged = (state, message) {
        if (!mounted) return;
        // Ne pas écraser l'indicateur de chargement vocal pendant qu'on attend le serveur Pi
        if (_awaitingVoiceResponse && state != VoiceServiceState.speaking) {
          return;
        }
        setState(() {
          switch (state) {
            case VoiceServiceState.listening:
              _voiceState = VoiceState.listening;
              break;
            case VoiceServiceState.speaking:
              _clearVoiceLoading();
              _voiceState = VoiceState.speaking;
              break;
            case VoiceServiceState.processing:
              _voiceState = VoiceState.thinking;
              break;
            default:
              _voiceState = VoiceState.idle;
          }
          _voiceStatus = message;
        });
      };

      // Démarrage de l'écoute permanente sans interruption
      voice.startPermanentListening();
    } else {
      setState(() {
        _voiceStatus = "Micro non disponible";
      });
    }
  }

  static const Set<String> _invalidDestinationTokens = {
    'RUNNING',
    'STOPPED',
    'STARTING',
    'TIMEOUT',
    'EMERGENCY_STOP',
    'IDLE',
    'BLOCKED',
    'ORIENTATION',
    'NULL',
    'NONE',
  };

  /// Valide et normalise un libellé de destination (rejette les états comme RUNNING/STOPPED).
  String? _resolveDestinationLabel(dynamic raw) {
    if (raw == null) return null;
    final trimmed = raw.toString().trim();
    if (trimmed.isEmpty) return null;
    final upper = trimmed.toUpperCase();
    if (_invalidDestinationTokens.contains(upper)) return null;
    switch (upper) {
      case 'PHARMACY':
        return 'Pharmacie';
      case 'LABORATORY':
        return 'Laboratoire';
      case 'RADIOLOGY':
        return 'Radiologie';
      case 'RECEPTION':
        return 'Réception';
      default:
        return trimmed;
    }
  }

  /// Exécute une action envoyée par le Raspberry Pi 4
  void _handleServerAction(String actionId, Map<String, dynamic> args) {
    if (!mounted) return;

    switch (actionId) {
      case 'splash.start':
      case 'app.home':
        _goToScreen('home');
        break;

      case 'home.open_category':
        final cat = args['category']?.toString();
        if (cat == 'ORIENTATION') {
          _goToScreen('orientation');
        } else if (cat == 'INFORMATION') {
          _goToScreen('information');
        }
        break;

      case 'consult.start':
        _clearConsultationData();
        _goToScreen('consultation');
        break;

      case 'consult.finish':
      case 'consult.cancel':
        _clearConsultationData();
        _goToScreen('home');
        break;

      case 'consult.step':
        final s = int.tryParse(args['step']?.toString() ?? '1');
        if (s != null) {
          setState(() => _consultationStep = s);
          _goToScreen('consultation');
        }
        break;

      case 'consult.next':
        setState(() => _consultationStep++);
        _goToScreen('consultation');
        break;

      case 'info.open':
        final topic = args['topic']?.toString();
        _goToScreen('information');
        if (topic != null && topic.isNotEmpty) {
          _showInfoLeaflet(topic);
        }
        break;

      case 'info.close':
      case 'app.close_dialog':
        _closeDialogIfOpen();
        break;

      case 'orientation.select':
        final dest = args['destination']?.toString() ?? 'PHARMACY';
        final label = _resolveDestinationLabel(dest) ?? 'Pharmacie';
        // Toujours demander confirmation avant de mettre le robot en mouvement
        _selectedDestination = label;
        _goToScreen('orientation');
        _showOrientationConfirmationDialog(label, dest);
        break;

      case 'orientation.confirm':
        _closeDialogIfOpen();
        _missionState = 'RUNNING';
        _goToScreen('mission');
        break;

      case 'orientation.decline':
      case 'confirm.no':
        _closeDialogIfOpen();
        break;

      case 'robot.resume':
      case 'mission.resume':
        _triggerResume();
        break;

      case 'robot.stop':
        _triggerStop();
        break;

      case 'mission.dismiss':
      case 'mission.finish':
        _closeDialogIfOpen();
        _goToScreen('home');
        break;

      case 'app.back':
        _goToScreen('home');
        break;
    }
  }

  /// Traitement du paquet unifié ServerInstruction (UI + Données + Voix)
  void _handleServerInstruction(Map<String, dynamic> data) {
    if (!mounted) return;
    _clearVoiceLoading();

    final ui = data['instruction_ui'] as Map<String, dynamic>?;
    final valueToShow = data['value_to_show'] as Map<String, dynamic>?;
    final fields = data['fields'] as Map<String, dynamic>?;
    final robotStatus = data['robot_status'] as Map<String, dynamic>?;
    final hints = (data['voice_hints'] as List?)?.map((e) => e.toString()).toList();
    final priority = data['speech_priority']?.toString();

    // 0. Interruption prioritaire (ex: Arrêt d'urgence vocale)
    if (priority == 'interrupt') {
      VoiceService.instance.stopSpeaking();
    }

    // 1. Mise à jour des données dynamiques (signes vitaux, télémétrie, étapes)
    setState(() {
      if (valueToShow != null && valueToShow['field_id'] != null) {
        final fid = valueToShow['field_id'].toString();
        _dynamicFields[fid] = valueToShow['value'];
        if (fid == 'consultation_step' && valueToShow['value'] != null) {
          _consultationStep = int.tryParse(valueToShow['value'].toString()) ?? _consultationStep;
        }
        if (fid == 'destination') {
          final resolved = _resolveDestinationLabel(valueToShow['value']);
          if (resolved != null) {
            _selectedDestination = resolved;
          }
        }
        if (fid == 'mission_state' && valueToShow['value'] != null) {
          _missionState = valueToShow['value'].toString();
        }
      }

      if (fields != null) {
        _dynamicFields.addAll(fields);
        if (fields['consultation_step'] != null) {
          _consultationStep = int.tryParse(fields['consultation_step'].toString()) ?? _consultationStep;
        }
        final fieldDest = _resolveDestinationLabel(fields['destination']);
        if (fieldDest != null) {
          _selectedDestination = fieldDest;
        }
      }

      if (ui != null && ui['step'] != null) {
        _consultationStep = int.tryParse(ui['step'].toString()) ?? _consultationStep;
      }

      if (robotStatus != null && robotStatus['status_label'] != null) {
        _voiceStatus = robotStatus['status_label'].toString();
      }
      if (robotStatus != null && robotStatus['face_expression'] != null) {
        _faceExpression = robotStatus['face_expression'].toString();
      }
      if (_voiceState == VoiceState.thinking && !VoiceService.instance.isSpeaking) {
        _voiceState = VoiceState.listening;
      }
      if (hints != null && hints.isNotEmpty) {
        _currentVoiceTip = "Dites : ${hints.map((h) => "« $h »").join(", ")}";
      }
    });

    // 2. Traitement d'affichage UI (changement d'écran ou action)
    if (ui != null) {
      if (ui['action'] == 'stop') {
        _triggerStop();
      } else if (ui['action'] == 'resume') {
        _triggerResume();
      } else if (ui['action'] == 'next') {
        if (_currentScreen == 'consultation' && _consultationKey.currentState != null) {
          _consultationKey.currentState!.nextStep();
        } else {
          setState(() {
            if (_consultationStep < 6) _consultationStep++;
          });
          _goToScreen('consultation');
        }
      } else if (ui['action'] == 'prev') {
        if (_currentScreen == 'consultation' && _consultationKey.currentState != null) {
          _consultationKey.currentState!.prevStep();
        } else {
          setState(() {
            if (_consultationStep > 1) _consultationStep--;
          });
          _goToScreen('consultation');
        }
      }

      final targetScreen = ui['screen']?.toString();
      final valueDest = (valueToShow != null && valueToShow['field_id']?.toString() == 'destination')
          ? _resolveDestinationLabel(valueToShow['value'])
          : null;
      final candidateDest = _resolveDestinationLabel(ui['destination']) ??
          _resolveDestinationLabel(fields?['destination']) ??
          valueDest;
      final destination = candidateDest ?? _selectedDestination;

      // Règle : Si commande vocale ou confirmation non requise -> AUCUNE POP-UP !
      if (targetScreen != null) {
        if (targetScreen == 'mission') {
          if (candidateDest != null) {
            _selectedDestination = candidateDest;
          }
          _closeDialogIfOpen();
          _goToScreen('mission');
        } else if (targetScreen == 'orientation') {
          if (candidateDest != null) {
            // Uniquement pour ORIENTATION : toujours afficher la popup de confirmation avant départ
            _selectedDestination = candidateDest;
            _goToScreen('orientation');
            final targetKey = ui['target']?.toString() ?? fields?['target']?.toString() ?? fields?['pending_destination']?.toString() ?? 'PHARMACY';
            _showOrientationConfirmationDialog(destination, targetKey);
          } else {
            _closeDialogIfOpen();
            _goToScreen('orientation');
          }
        } else if (targetScreen == 'information') {
          _closeDialogIfOpen();
          _goToScreen('information');
          final topic = ui['topic']?.toString() ?? valueToShow?['value']?.toString() ?? fields?['topic']?.toString();
          if (topic != null && topic.isNotEmpty && topic != 'INFORMATION') {
            _showInfoLeaflet(topic);
          }
        } else {
          _closeDialogIfOpen();
          _goToScreen(targetScreen);
        }
      }
    }
  }

  void _closeDialogIfOpen() {
    if (_navKey.currentContext != null && Navigator.of(_navKey.currentContext!).canPop()) {
      Navigator.of(_navKey.currentContext!).pop();
    }
  }

  /// Boîte de dialogue de confirmation vocale / tactile pour l'orientation
  void _showOrientationConfirmationDialog(String destination, String targetKey) {
    _closeDialogIfOpen();
    if (_navKey.currentContext == null) return;

    showDialog(
      context: _navKey.currentContext!,
      barrierDismissible: true,
      builder: (ctx) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        child: Container(
          width: 460,
          padding: const EdgeInsets.all(22),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: HiarColors.azur.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.navigation_outlined, size: 30, color: HiarColors.azur),
              ),
              const SizedBox(height: 14),
              const Text(
                "Confirmation de guidage",
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: HiarColors.marine),
              ),
              const SizedBox(height: 8),
              const Text(
                "Voulez-vous que le robot vous guide vers :",
                style: TextStyle(fontSize: 14, color: HiarColors.text2),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              Text(
                destination,
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: HiarColors.azur),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              const Text(
                "Dites « Oui » ou « Non », ou confirmez à l'écran.",
                style: TextStyle(fontSize: 12, fontStyle: FontStyle.italic, color: HiarColors.text2),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: HiarColors.err,
                        side: const BorderSide(color: HiarColors.err),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      icon: const Icon(Icons.close, size: 18),
                      label: const Text("Non / Annuler"),
                      onPressed: () {
                        Navigator.pop(ctx);
                        _hub.publishAction('orientation.cancel', {});
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: HiarColors.azur,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      icon: const Icon(Icons.check, size: 18),
                      label: const Text("Oui / Confirmer"),
                      onPressed: () {
                        Navigator.pop(ctx);
                        _hub.publishAction('orientation.confirm', {'destination': targetKey});
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Affiche la fiche de renseignement de santé publique (OMS)
  Future<void> _showInfoLeaflet(String topicKey) async {
    try {
      final jsonString = await rootBundle.loadString('assets/content/info_fr.json');
      final data = json.decode(jsonString);
      final infoTexts = data['info_texts'] as Map<String, dynamic>?;
      final text = infoTexts?[topicKey] ?? "Fiche d'information non disponible.";
      final catalog = data['catalog']?['INFORMATION']?['items'] as Map<String, dynamic>?;
      final title = catalog?[topicKey]?['label'] ?? topicKey;

      if (!mounted) return;
      _closeDialogIfOpen();

      final media = MediaQuery.of(_navKey.currentContext ?? context);
      final dialogMaxWidth = (media.size.width * 0.75).clamp(320.0, 700.0);

      showDialog(
        context: _navKey.currentContext ?? context,
        builder: (ctx) => Dialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          child: Container(
            width: dialogMaxWidth,
            constraints: BoxConstraints(
              maxHeight: media.size.height * 0.82,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // En-tête avec titre et bouton de fermeture direct
                Row(
                  children: [
                    const Icon(Icons.menu_book, color: HiarColors.azur, size: 24),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        "Fiche OMS : $title",
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: HiarColors.marine,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, color: HiarColors.text2),
                      tooltip: "Fermer",
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      onPressed: () {
                        Navigator.pop(ctx);
                        _hub.publishAction('info.close', {'topic': topicKey});
                      },
                    ),
                  ],
                ),
                const Divider(height: 16, thickness: 1),
                // Contenu scrollable adaptatif
                Flexible(
                  child: SingleChildScrollView(
                    physics: const BouncingScrollPhysics(),
                    child: Text(
                      text,
                      style: const TextStyle(fontSize: 14, height: 1.45, color: HiarColors.text1),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                // Action inférieure
                Align(
                  alignment: Alignment.centerRight,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: HiarColors.azur,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                    ),
                    onPressed: () {
                      Navigator.pop(ctx);
                      _hub.publishAction('info.close', {'topic': topicKey});
                    },
                    child: const Text("Fermer"),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      debugPrint("Erreur chargement fiche: $e");
    }
  }

  /// Efface entièrement les données du formulaire de consultation et réinitialise les constantes.
  void _clearConsultationData() {
    setState(() {
      _consultationStep = 1;
      _dynamicFields.remove('patient_name');
      _dynamicFields.remove('contact');
      _dynamicFields.remove('patient_phone');
      _dynamicFields.remove('reason_code');
      _dynamicFields.remove('selected_reason');
      _dynamicFields.remove('doctor_code');
      _dynamicFields.remove('selected_doctor');
      _dynamicFields.remove('doctor');
      _dynamicFields.remove('period');
      _dynamicFields.remove('selected_period');
      _dynamicFields.remove('temperature_c');
      _dynamicFields.remove('temperature');
      _dynamicFields.remove('heart_rate_bpm');
      _dynamicFields.remove('heart_rate');
      _dynamicFields.remove('spo2_percent');
      _dynamicFields.remove('spo2');
      _dynamicFields.remove('ticket_label');
      _dynamicFields.remove('appointment_id');
      _dynamicFields.remove('booking_error');
      _dynamicFields.remove('form_validation_error');
      _dynamicFields.remove('vitals_state');
      _dynamicFields.remove('vitals_error');
    });
    _consultationKey.currentState?.resetForm();
  }

  void _goToScreen(String screen) {
    VoiceService.instance.stopSpeaking();
    setState(() {
      _currentScreen = screen;
      _recognizedText = null;
      if (screen == 'consultation' && _consultationStep == 1) {
        _dynamicFields.remove('ticket_label');
        _dynamicFields.remove('booking_error');
      }
    });

    // Notifie le Raspberry Pi de l'écran actuellement actif (et de l'étape de consultation)
    _hub.publishUiState(
      screen,
      _getActiveActionsForScreen(screen),
      step: screen == 'consultation' ? _consultationStep : null,
    );
  }

  List<String> _getActiveActionsForScreen(String screen) {
    switch (screen) {
      case 'splash':
        return ['splash.start', 'robot.stop'];
      case 'home':
        return ['home.open_category', 'consult.start', 'robot.stop'];
      case 'orientation':
        return ['orientation.select', 'app.back', 'robot.stop'];
      case 'mission':
        return ['robot.stop', 'mission.dismiss'];
      case 'information':
        return ['info.open', 'app.back', 'robot.stop'];
      case 'consultation':
        return ['consult.reason.select', 'consult.next', 'consult.cancel', 'robot.stop'];
      default:
        return ['robot.stop'];
    }
  }

  void _triggerStop() {
    setState(() {
      _missionState = 'STOPPED';
      _voiceStatus = "Robot arrêté";
    });
    ScaffoldMessenger.of(_navKey.currentContext ?? context).showSnackBar(
      const SnackBar(
        content: Text("ARRÊT D'URGENCE DU ROBOT !"),
        backgroundColor: HiarColors.err,
        duration: Duration(seconds: 4),
      ),
    );
  }

  void _triggerResume() {
    setState(() {
      _missionState = 'RUNNING';
      _voiceStatus = "Accompagnement en cours";
    });
    ScaffoldMessenger.of(_navKey.currentContext ?? context).showSnackBar(
      const SnackBar(
        content: Text("REPRISE DU GUIDAGE !"),
        backgroundColor: HiarColors.ok,
        duration: Duration(seconds: 3),
      ),
    );
  }

  void _toggleMic() {
    final voice = VoiceService.instance;
    if (_voiceState == VoiceState.listening) {
      voice.stopPermanentListening();
      setState(() {
        _voiceState = VoiceState.idle;
        _voiceStatus = "Micro en pause (touchez pour réactiver)";
      });
    } else {
      voice.startPermanentListening();
      setState(() {
        _voiceState = VoiceState.listening;
        _voiceStatus = "À votre écoute…";
      });
    }
  }

  /// Boîte de dialogue pour configurer l'IP/port et monitorer les capteurs & nœuds en direct
  void _showServerConfigDialog() {
    final ipController = TextEditingController(text: _hub.serverIp);
    final portController = TextEditingController(text: _hub.serverPort.toString());

    if (_hub.isConnected) {
      _hub.requestDiagnosticsRefresh();
    }

    showDialog(
      context: _navKey.currentContext ?? context,
      builder: (ctx) => Dialog(
        insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // En-tête : Titre et bouton de fermeture
                Row(
                  children: [
                    const Icon(Icons.settings_outlined, color: HiarColors.azur, size: 22),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: Text(
                        "Paramètres de connexion du robot",
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: HiarColors.marine),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 20, color: HiarColors.text2),
                      tooltip: "Fermer",
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      onPressed: () => Navigator.pop(ctx),
                    ),
                  ],
                ),
                const SizedBox(height: 8),

                // Indicateur de statut WebSocket en direct
                ValueListenableBuilder<bool>(
                  valueListenable: _hub.connectedNotifier,
                  builder: (_, connected, _) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: connected ? HiarColors.okBg : HiarColors.errBg,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: connected ? HiarColors.ok.withOpacity(0.3) : HiarColors.err.withOpacity(0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          connected ? Icons.check_circle : Icons.error_outline,
                          color: connected ? HiarColors.ok : HiarColors.err,
                          size: 16,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            connected
                                ? "Connecté : ws://${_hub.serverIp}:${_hub.serverPort}/ws"
                                : "Déconnecté (${_hub.serverIp}:${_hub.serverPort})",
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: connected ? HiarColors.marine : HiarColors.err,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),

                // Note : le moniteur des capteurs est désormais disponible dans l'UI Web Médecin
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: HiarColors.emeraldPastel.withOpacity(0.7),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.monitor_heart_outlined, size: 15, color: HiarColors.azurDark),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          "État des capteurs & ESP32 : http://${_hub.serverIp}:5001/",
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: HiarColors.marine,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),

                const Text(
                  "Adresse IP locale du robot :",
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: HiarColors.marine),
                ),
                const SizedBox(height: 4),
                TextField(
                  controller: ipController,
                  keyboardType: TextInputType.text,
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: "10.42.0.1 ou 192.168.0.x",
                    prefixIcon: const Icon(Icons.lan_outlined, size: 18),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
                const SizedBox(height: 8),

                const Text(
                  "Port WebSocket :",
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: HiarColors.marine),
                ),
                const SizedBox(height: 4),
                TextField(
                  controller: portController,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: "5000",
                    prefixIcon: const Icon(Icons.numbers_outlined, size: 18),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
                const SizedBox(height: 8),

                const Text(
                  "Raccourcis rapides :",
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: HiarColors.text2),
                ),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    ActionChip(
                      visualDensity: VisualDensity.compact,
                      avatar: const Icon(Icons.radar, size: 14, color: HiarColors.azur),
                      label: const Text("Auto-détecter (Wi-Fi)", style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                      onPressed: () {
                        _hub.triggerAutoDiscovery();
                        Navigator.pop(ctx);
                        if (mounted) {
                          ScaffoldMessenger.of(_navKey.currentContext ?? context).showSnackBar(
                            const SnackBar(
                              content: Text("Recherche automatique du Raspberry Pi sur le Wi-Fi..."),
                              duration: Duration(seconds: 3),
                            ),
                          );
                        }
                      },
                    ),
                    ActionChip(
                      visualDensity: VisualDensity.compact,
                      avatar: const Icon(Icons.wifi, size: 14),
                      label: const Text("192.168.43.52 (Pi Wi-Fi Ceyci)", style: TextStyle(fontSize: 11)),
                      onPressed: () {
                        ipController.text = "192.168.43.52";
                        portController.text = "5000";
                      },
                    ),
                    ActionChip(
                      visualDensity: VisualDensity.compact,
                      avatar: const Icon(Icons.dns_outlined, size: 14),
                      label: const Text("cecilia-desktop.local", style: TextStyle(fontSize: 11)),
                      onPressed: () {
                        ipController.text = "cecilia-desktop.local";
                        portController.text = "5000";
                      },
                    ),
                    ActionChip(
                      visualDensity: VisualDensity.compact,
                      avatar: const Icon(Icons.usb, size: 14),
                      label: const Text("127.0.0.1 (USB ADB)", style: TextStyle(fontSize: 11)),
                      onPressed: () {
                        ipController.text = "127.0.0.1";
                        portController.text = "5000";
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Boutons d'action scrollables dans le même flux
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text("Annuler", style: TextStyle(color: HiarColors.text2)),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: HiarColors.azur,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      ),
                      icon: const Icon(Icons.sync, size: 16),
                      label: const Text("Enregistrer & Connecter"),
                      onPressed: () async {
                        final newIp = ipController.text.trim();
                        final newPort = int.tryParse(portController.text.trim()) ?? 5000;
                        if (newIp.isNotEmpty) {
                          final prefs = await SharedPreferences.getInstance();
                          await prefs.setString('server_ip', newIp);
                          await prefs.setInt('server_port', newPort);
                          _hub.disconnect();
                          _hub.connect(ip: newIp, port: newPort);

                          if (mounted) {
                            ScaffoldMessenger.of(_navKey.currentContext ?? context).showSnackBar(
                              SnackBar(
                                content: Text("Reconnexion en cours à ws://$newIp:$newPort/ws..."),
                                duration: const Duration(seconds: 3),
                              ),
                            );
                          }
                        }
                        if (ctx.mounted) Navigator.pop(ctx);
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: _navKey,
      title: 'HIAR Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        fontFamily: 'Inter',
        colorScheme: HiarColors.colorScheme,
        scaffoldBackgroundColor: HiarColors.background,
        useMaterial3: true,
      ),
      home: Builder(
        builder: (ctx) {
          switch (_currentScreen) {
            case 'splash':
              return SplashScreen(
                onStart: () {
                  _hub.publishAction('splash.start', {});
                  _goToScreen('home');
                },
              );
            case 'home':
              return HomeScreen(
                isRobotConnected: _isRobotConnected,
                voiceState: _voiceState,
                voiceStatus: _voiceStatus,
                recognizedText: _recognizedText,
                voiceTip: _currentVoiceTip,
                faceExpression: _faceExpression,
                onBack: () => _goToScreen('splash'),
                onMicTap: _toggleMic,
                onSettingsTap: _showServerConfigDialog,
                onStopRobotTap: () {
                  _hub.publishAction('robot.stop', {});
                  _triggerStop();
                },
                onOpenOrientation: () {
                  _hub.publishAction('home.open_category', {'category': 'ORIENTATION'});
                  _goToScreen('orientation');
                },
                onOpenInformation: () {
                  _hub.publishAction('home.open_category', {'category': 'INFORMATION'});
                  _goToScreen('information');
                },
                onOpenConsultation: () {
                  _clearConsultationData();
                  _hub.publishAction('consult.start', {});
                  _goToScreen('consultation');
                },
              );
            case 'orientation':
              return OrientationScreen(
                isRobotConnected: _isRobotConnected,
                voiceState: _voiceState,
                voiceStatus: _voiceStatus,
                recognizedText: _recognizedText,
                faceExpression: _faceExpression,
                onMicTap: _toggleMic,
                onSettingsTap: _showServerConfigDialog,
                onStopRobotTap: () {
                  _hub.publishAction('robot.stop', {});
                  _triggerStop();
                },
                onBack: () {
                  _hub.publishAction('app.back', {});
                  _goToScreen('home');
                },
                onDestinationSelected: (key, label) {
                  // Uniquement pour ORIENTATION : popup de confirmation obligatoire avant départ
                  _selectedDestination = label;
                  _hub.publishAction('orientation.pending', {'destination': key, 'label': label});
                  _showOrientationConfirmationDialog(label, key);
                },
              );
            case 'mission':
              return MissionScreen(
                isRobotConnected: _isRobotConnected,
                destinationLabel: _selectedDestination,
                missionState: _missionState,
                voiceState: _voiceState,
                voiceStatus: _voiceStatus,
                recognizedText: _recognizedText,
                faceExpression: _faceExpression,
                onMicTap: _toggleMic,
                onSettingsTap: _showServerConfigDialog,
                dynamicFields: _dynamicFields,
                onStopRobot: () {
                  _hub.publishAction('robot.stop', {});
                  _triggerStop();
                },
                onResumeRobot: () {
                  _hub.publishAction('robot.resume', {});
                  _triggerResume();
                },
                onFinish: () {
                  _hub.publishAction('mission.dismiss', {});
                  _goToScreen('home');
                },
              );
            case 'information':
              return InformationScreen(
                isRobotConnected: _isRobotConnected,
                voiceState: _voiceState,
                voiceStatus: _voiceStatus,
                recognizedText: _recognizedText,
                faceExpression: _faceExpression,
                onMicTap: _toggleMic,
                onSettingsTap: _showServerConfigDialog,
                onStopRobotTap: () {
                  _hub.publishAction('robot.stop', {});
                  _triggerStop();
                },
                onBack: () {
                  _hub.publishAction('app.back', {});
                  _goToScreen('home');
                },
                onSelectTopic: (key, title) {
                  _hub.publishAction('info.open', {'topic': key});
                  _showInfoLeaflet(key);
                },
              );
            case 'consultation':
              return ConsultationScreen(
                key: _consultationKey,
                initialStep: _consultationStep,
                dynamicFields: _dynamicFields,
                voiceState: _voiceState,
                voiceStatus: _voiceStatus,
                recognizedText: _recognizedText,
                voiceTip: _currentVoiceTip,
                faceExpression: _faceExpression,
                onMicTap: _toggleMic,
                onSettingsTap: _showServerConfigDialog,
                isRobotConnected: _isRobotConnected,
                onStopRobotTap: () {
                  _hub.publishAction('robot.stop', {});
                  _triggerStop();
                },
                onStepChanged: (newStep) {
                  _consultationStep = newStep;
                  _hub.publishAction('consult.step_changed', {'step': newStep});
                  _hub.publishUiState(
                    'consultation',
                    ['step_$newStep'],
                    step: newStep,
                    consultationData: {
                      if (_dynamicFields.containsKey('temperature_c')) 'temperature_c': _dynamicFields['temperature_c'],
                      if (_dynamicFields.containsKey('temperature')) 'temperature': _dynamicFields['temperature'],
                      if (_dynamicFields.containsKey('heart_rate_bpm')) 'heart_rate_bpm': _dynamicFields['heart_rate_bpm'],
                      if (_dynamicFields.containsKey('heart_rate')) 'heart_rate': _dynamicFields['heart_rate'],
                      if (_dynamicFields.containsKey('spo2_percent')) 'spo2_percent': _dynamicFields['spo2_percent'],
                      if (_dynamicFields.containsKey('spo2')) 'spo2': _dynamicFields['spo2'],
                    },
                  );
                  if (!_isRobotConnected && newStep == 4) {
                    VoiceService.instance.speak(
                      "Prise des signes vitaux. Veuillez tenir la sonde de température dans votre main et poser votre index sur le capteur d'oxymétrie, puis appuyez sur Démarrer la mesure ou dites Mesurer.",
                    );
                  }
                },
                onRequestMeasure: () {
                  _hub.publishAction('consult.measure_vitals', {});
                },
                onConfirmAppointment: (data) {
                  setState(() {
                    _dynamicFields.remove('ticket_label');
                    _dynamicFields.remove('booking_error');
                  });
                  _hub.publishAction('consult.confirm', data);
                  _hub.publishUiState('consultation', ['confirming'], step: 5);
                },
                onCancel: () {
                  _clearConsultationData();
                  _hub.publishAction('consult.cancel', {});
                  _goToScreen('home');
                },
                onFinish: () {
                  _clearConsultationData();
                  _hub.publishAction('consult.finish', {});
                  _goToScreen('home');
                },
              );
            default:
              return const SizedBox.shrink();
          }
        },
      ),
    );
  }
}
