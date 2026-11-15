import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/theme/hiar_colors.dart';

class MissionScreen extends StatelessWidget {
  final String destinationLabel;
  final String missionState; // 'STARTING', 'RUNNING', 'STOPPED', 'TIMEOUT'
  final VoidCallback onStopRobot;
  final VoidCallback? onResumeRobot;
  final VoidCallback onFinish;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;
  final VoidCallback? onSettingsTap;
  final bool isRobotConnected;
  final Map<String, dynamic>? dynamicFields;

  const MissionScreen({
    super.key,
    required this.destinationLabel,
    this.missionState = 'RUNNING',
    required this.onStopRobot,
    this.onResumeRobot,
    required this.onFinish,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Accompagnement en cours",
    this.recognizedText,
    this.onMicTap,
    this.onSettingsTap,
    this.isRobotConnected = true,
    this.dynamicFields,
  });

  @override
  Widget build(BuildContext context) {
    final isStopped = missionState == 'STOPPED' || missionState == 'TIMEOUT';

    return LandscapeScaffold(
      title: "Accompagnement",
      showBack: isStopped,
      onBack: onFinish,
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: isStopped ? "Dites « Reprendre » ou « Terminer »" : "Dites « Stop » pour arrêter le robot",
      onMicTap: onMicTap,
      onSettingsTap: onSettingsTap,
      isRobotConnected: isRobotConnected,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 580),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: HiarColors.border),
              boxShadow: const [
                BoxShadow(
                  color: Colors.black12,
                  blurRadius: 10,
                  offset: Offset(0, 4),
                )
              ],
            ),
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    isStopped ? Icons.stop_circle_outlined : Icons.directions_walk,
                    size: 44,
                    color: isStopped ? HiarColors.err : HiarColors.azur,
                  ),
                  const SizedBox(height: 10),
                  Text(
                    isStopped
                        ? "Le robot s'est arrêté."
                        : "Je vous accompagne vers : $destinationLabel",
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: HiarColors.marine,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 6),
                Text(
                  isStopped
                      ? "Vous pouvez retourner à l'accueil."
                      : "Veuillez me suivre en restant vigilant.",
                  style: const TextStyle(
                    fontSize: 16,
                    color: HiarColors.text2,
                  ),
                  textAlign: TextAlign.center,
                ),
                if (!isStopped && (dynamicFields?['distance'] != null || dynamicFields?['eta'] != null)) ...[
                  const SizedBox(height: 14),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: HiarColors.azurSoft,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (dynamicFields?['distance'] != null) ...[
                          const Icon(Icons.straighten, size: 18, color: HiarColors.azur),
                          const SizedBox(width: 6),
                          Text(
                            "Distance : ${dynamicFields!['distance']}",
                            style: const TextStyle(fontWeight: FontWeight.w600, color: HiarColors.marine),
                          ),
                        ],
                        if (dynamicFields?['distance'] != null && dynamicFields?['eta'] != null)
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 8),
                            child: Text("•", style: TextStyle(color: HiarColors.text2)),
                          ),
                        if (dynamicFields?['eta'] != null) ...[
                          const Icon(Icons.timer_outlined, size: 18, color: HiarColors.azur),
                          const SizedBox(width: 6),
                          Text(
                            "Arrivée : ${dynamicFields!['eta']}",
                            style: const TextStyle(fontWeight: FontWeight.w600, color: HiarColors.marine),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 14),
                if (!isStopped)
                  // Bouton ARRÊT d'urgence
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: HiarColors.err,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        elevation: 4,
                      ),
                      icon: const Icon(Icons.stop, size: 26),
                      label: const Text(
                        "ARRÊT DU ROBOT  (🎤 « Stop »)",
                        style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
                      ),
                      onPressed: onStopRobot,
                    ),
                  )
                else ...[
                  // 1. Bouton Reprendre le guidage
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: HiarColors.ok,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        elevation: 2,
                      ),
                      icon: const Icon(Icons.play_arrow, size: 24),
                      label: const Text(
                        "Reprendre le guidage  (🎤 « Reprendre »)",
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                      ),
                      onPressed: onResumeRobot,
                    ),
                  ),
                  const SizedBox(height: 10),
                  // 2. Bouton Terminer la mission
                  SizedBox(
                    width: double.infinity,
                    height: 44,
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: HiarColors.marine,
                        side: const BorderSide(color: HiarColors.border, width: 1.5),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      icon: const Icon(Icons.home_outlined, size: 20),
                      label: const Text(
                        "Terminer la mission  (🎤 « Terminer »)",
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                      ),
                      onPressed: onFinish,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    ),
  );
}
}
