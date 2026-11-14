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

  String _currentScreen = 'splash';
  String _selectedDestination = 'Pharmacie';
  String _missionState = 'RUNNING';

  // État vocal & réseau
  VoiceState _voiceState = VoiceState.listening;
  String _voiceStatus = "J'écoute en continu…";
  String? _currentVoiceTip;
  String? _recognizedText;
  bool _isRobotConnected = false;

  // Données dynamiques transmises par le Raspberry Pi 4 / ROS 2 (ex: température, rythme cardiaque, étape)
  final Map<String, dynamic> _dynamicFields = {};
  int _consultationStep = 1;

  final GlobalKey<NavigatorState> _navKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    _initNetworkAndVoice();
  }

  @override
  void dispose() {
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
    _hub.onTtsRequested = (textToSpeak) {
      debugPrint("TTS Reçu du Pi 4 -> Émission vocale : « $textToSpeak »");
      VoiceService.instance.speak(textToSpeak);
    };

    // 3. Réception d'actions décidées par le Raspberry Pi 4 (après son analyse du texte ou ROS 2)
    _hub.onActionRequested = (actionId, args) {
      debugPrint("Action reçue du Pi 4 -> $actionId avec $args");
      _handleServerAction(actionId, args);
    };

    // 4. Réception du paquet unifié ServerInstruction (UI + TTS + Données / Signes vitaux)
    _hub.onServerInstruction = (instruction) {
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

    // Connexion au Hub WebSocket (restaure l'IP sauvegardée ou utilise 10.42.0.1)
    final prefs = await SharedPreferences.getInstance();
    final savedIp = prefs.getString('server_ip');
    if (savedIp != null && savedIp.isNotEmpty) {
      _hub.serverIp = savedIp;
    }
    _hub.connect();

    // 5. Initialisation du moteur vocal natif (Écoute permanente)
    final voice = VoiceService.instance;
    final available = await voice.init();

    if (!mounted) return;

    if (available) {
      // DÈS QUE LE MICRO ENTEND DU TEXTE (ou VAD) :
      voice.onRecognizedText = (text) {
        if (!mounted) return;
        setState(() {
          _recognizedText = text;
        });

        // 1. Si on est sur l'écran d'accueil initial (Splash Screen) et qu'une voix est détectée :
        // L'écran s'ouvre automatiquement sans avoir besoin de taper !
        if (_currentScreen == 'splash') {
          _goToScreen('home');
        }

        // 2. Envoi immédiat sur le topic WebSocket "voice/stt/final" vers le Raspberry Pi 4
        _hub.publishSttFinal(text);
      };

      voice.onStateChanged = (state, message) {
        if (!mounted) return;
        setState(() {
          switch (state) {
            case VoiceServiceState.listening:
              _voiceState = VoiceState.listening;
              break;
            case VoiceServiceState.speaking:
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
        _goToScreen('consultation');
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
        final label = dest == 'PHARMACY' ? 'Pharmacie' : (dest == 'LABORATORY' ? 'Laboratoire' : 'Réception');
        final isVoice = args['origin'] == 'voice' || args['by_voice'] == true;
        if (isVoice) {
          // Commande vocale : AUCUNE pop-up de confirmation !
          _selectedDestination = label;
          _closeDialogIfOpen();
          _goToScreen('mission');
        } else {
          // Clic tactile : boîte de dialogue de confirmation
          _showConfirmationDialog(label);
        }
        break;

      case 'orientation.confirm':
        _closeDialogIfOpen();
        _goToScreen('mission');
        break;

      case 'orientation.decline':
      case 'confirm.no':
        _closeDialogIfOpen();
        break;

      case 'robot.stop':
        _triggerStop();
        break;

      case 'app.back':
        _goToScreen('home');
        break;
    }
  }

  /// Traitement du paquet unifié ServerInstruction (UI + Données + Voix)
  void _handleServerInstruction(Map<String, dynamic> data) {
    if (!mounted) return;

    final origin = data['origin']?.toString() ?? 'server';
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
        if (fid == 'destination' && valueToShow['value'] != null) {
          _selectedDestination = valueToShow['value'].toString();
        }
      }

      if (fields != null) {
        _dynamicFields.addAll(fields);
        if (fields['consultation_step'] != null) {
          _consultationStep = int.tryParse(fields['consultation_step'].toString()) ?? _consultationStep;
        }
        if (fields['destination'] != null) {
          _selectedDestination = fields['destination'].toString();
        }
      }

      if (ui != null && ui['step'] != null) {
        _consultationStep = int.tryParse(ui['step'].toString()) ?? _consultationStep;
      }

      if (robotStatus != null && robotStatus['status_label'] != null) {
        _voiceStatus = robotStatus['status_label'].toString();
      }
      if (hints != null && hints.isNotEmpty) {
        _currentVoiceTip = "Dites : ${hints.map((h) => "« $h »").join(", ")}";
      }
    });

    // 2. Traitement d'affichage UI (changement d'écran ou action)
    if (ui != null) {
      if (ui['action'] == 'stop') {
        _triggerStop();
      } else if (ui['action'] == 'next') {
        setState(() {
          if (_consultationStep < 6) _consultationStep++;
        });
        _goToScreen('consultation');
      } else if (ui['action'] == 'prev') {
        setState(() {
          if (_consultationStep > 1) _consultationStep--;
        });
        _goToScreen('consultation');
      }

      final targetScreen = ui['screen']?.toString();
      final requireConfirmation = ui['require_confirmation'] == true;
      final destination = ui['destination']?.toString() ?? valueToShow?['value']?.toString() ?? _selectedDestination;

      // Règle : Si commande vocale ou confirmation non requise -> AUCUNE POP-UP !
      if (targetScreen != null) {
        if (targetScreen == 'mission') {
          _selectedDestination = destination;
          _closeDialogIfOpen();
          _goToScreen('mission');
        } else if (targetScreen == 'orientation') {
          if (origin == 'voice' || !requireConfirmation) {
            // Commande vocale pour une destination -> direct en mission !
            if (destination.isNotEmpty && destination != 'null' && destination != 'ORIENTATION') {
              _selectedDestination = destination;
              _closeDialogIfOpen();
              _goToScreen('mission');
            } else {
              _closeDialogIfOpen();
              _goToScreen('orientation');
            }
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

  void _goToScreen(String screen) {
    setState(() {
      _currentScreen = screen;
      _recognizedText = null;
    });

    // Notifie le Raspberry Pi de l'écran actuellement actif
    _hub.publishUiState(screen, _getActiveActionsForScreen(screen));
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

  void _showConfirmationDialog(String label) {
    _selectedDestination = label;

    showDialog(
      context: _navKey.currentContext ?? context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            const Icon(Icons.navigation, color: HiarColors.azur),
            const SizedBox(width: 8),
            Text("Accompagnement : $label"),
          ],
        ),
        content: Text(
          "Confirmez-vous que vous souhaitez aller à : $label ?\n\n(Ordre validé par le Raspberry Pi)",
          style: const TextStyle(fontSize: 16),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              _hub.publishAction('orientation.decline', {});
            },
            child: const Text("Annuler", style: TextStyle(color: HiarColors.text2)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: HiarColors.azur,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              _hub.publishAction('orientation.confirm', {'destination': label});
              _goToScreen('mission');
            },
            child: const Text("Confirmer"),
          ),
        ],
      ),
    );
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

  /// Boîte de dialogue pour configurer l'IP du Raspberry Pi 4 lors des essais
  void _showServerConfigDialog() {
    final controller = TextEditingController(text: _hub.serverIp);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Connexion au Raspberry Pi 4"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Adresse IP du Hub WebSocket :"),
            const SizedBox(height: 10),
            TextField(
              controller: controller,
              decoration: const InputDecoration(
                hintText: "10.42.0.1 ou 192.168.0.x",
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            const Text("Raccourcis rapides :", style: TextStyle(fontSize: 12, color: HiarColors.text2)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                ActionChip(
                  label: const Text("127.0.0.1 (USB ADB)"),
                  onPressed: () => controller.text = "127.0.0.1",
                ),
                ActionChip(
                  label: const Text("192.168.0.105 (Wi-Fi)"),
                  onPressed: () => controller.text = "192.168.0.105",
                ),
                ActionChip(
                  label: const Text("10.42.0.1 (Pi 4 AP)"),
                  onPressed: () => controller.text = "10.42.0.1",
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text("Annuler"),
          ),
          ElevatedButton(
            onPressed: () async {
              final newIp = controller.text.trim();
              if (newIp.isNotEmpty) {
                final prefs = await SharedPreferences.getInstance();
                await prefs.setString('server_ip', newIp);
                _hub.disconnect();
                _hub.connect(ip: newIp);
              }
              if (ctx.mounted) Navigator.pop(ctx);
            },
            child: const Text("Connecter"),
          ),
        ],
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
        colorScheme: ColorScheme.fromSeed(
          seedColor: HiarColors.azur,
          primary: HiarColors.azur,
        ),
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
                onMicTap: _showServerConfigDialog,
                onOpenOrientation: () {
                  _hub.publishAction('home.open_category', {'category': 'ORIENTATION'});
                  _goToScreen('orientation');
                },
                onOpenInformation: () {
                  _hub.publishAction('home.open_category', {'category': 'INFORMATION'});
                  _goToScreen('information');
                },
                onOpenConsultation: () {
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
                onMicTap: _showServerConfigDialog,
                onBack: () {
                  _hub.publishAction('app.back', {});
                  _goToScreen('home');
                },
                onDestinationSelected: (key, label) {
                  _hub.publishAction('orientation.select', {'destination': key});
                  _showConfirmationDialog(label);
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
                onMicTap: _showServerConfigDialog,
                dynamicFields: _dynamicFields,
                onStopRobot: () {
                  _hub.publishAction('robot.stop', {});
                  _triggerStop();
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
                onMicTap: _showServerConfigDialog,
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
                initialStep: _consultationStep,
                dynamicFields: _dynamicFields,
                voiceState: _voiceState,
                voiceStatus: _voiceStatus,
                recognizedText: _recognizedText,
                voiceTip: _currentVoiceTip,
                onMicTap: _showServerConfigDialog,
                isRobotConnected: _isRobotConnected,
                onStepChanged: (newStep) {
                  _consultationStep = newStep;
                  _hub.publishAction('consult.step_changed', {'step': newStep});
                },
                onRequestMeasure: () {
                  _hub.publishAction('consult.measure_vitals', {});
                },
                onCancel: () {
                  _consultationStep = 1;
                  _hub.publishAction('consult.cancel', {});
                  _goToScreen('home');
                },
                onFinish: () {
                  _consultationStep = 1;
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
