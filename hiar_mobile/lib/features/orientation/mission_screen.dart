import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/theme/hiar_colors.dart';
import '../../ui/components/hiar_kit.dart';
import '../../ui/theme/hiar_tokens.dart';
import '../../ui/theme/hiar_typography.dart';

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
  final String? faceExpression;

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
    this.faceExpression,
  });

  @override
  Widget build(BuildContext context) {
    final isStopped = missionState == 'STOPPED' || missionState == 'TIMEOUT';

    return LandscapeScaffold(
      title: "Accompagnement",
      showBack: true,
      onBack: () {
        if (!isStopped) {
          onStopRobot();
        }
        onFinish();
      },
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: isStopped ? "Dites « Reprendre » ou « Terminer »" : "Dites « Stop » pour arrêter le robot",
      faceExpression: isStopped ? 'emergency' : faceExpression,
      onMicTap: onMicTap,
      onSettingsTap: onSettingsTap,
      isRobotConnected: isRobotConnected,
      body: HiarSceneBody(
        maxWidth: HiarSize.contentNarrow,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 1. Carte d'état de la mission (bleu en route, rouge à l'arrêt)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: HiarSpace.xl, vertical: HiarSpace.xl),
              decoration: BoxDecoration(
                gradient: isStopped
                    ? const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [Color(0xFF7F1D1D), Color(0xFFB91C1C)],
                      )
                    : HiarGradients.heroDark,
                borderRadius: HiarRadius.lgAll,
                boxShadow: [
                  BoxShadow(
                    color: (isStopped ? HiarColors.err : HiarColors.secondary).withOpacity(0.22),
                    blurRadius: 24,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Column(
                children: [
                  HiarIconBox(
                    isStopped ? Icons.stop_circle_outlined : Icons.directions_walk_rounded,
                    onDark: true,
                    size: 56,
                  ),
                  const SizedBox(height: HiarSpace.md),
                  Text(
                    isStopped ? "Le robot s'est arrêté." : "Je vous accompagne vers : $destinationLabel",
                    style: HiarTypography.title.copyWith(color: Colors.white),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: HiarSpace.xs),
                  Text(
                    isStopped
                        ? "Vous pouvez reprendre le guidage ou retourner à l'accueil."
                        : "Veuillez me suivre en restant vigilant.",
                    style: HiarTypography.body.copyWith(color: Colors.white70),
                    textAlign: TextAlign.center,
                  ),
                  if (!isStopped && (dynamicFields?['distance'] != null || dynamicFields?['eta'] != null)) ...[
                    const SizedBox(height: HiarSpace.md),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.15),
                        borderRadius: HiarRadius.pillAll,
                        border: Border.all(color: Colors.white.withOpacity(0.22)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (dynamicFields?['distance'] != null) ...[
                            const Icon(Icons.straighten, size: 15, color: HiarColors.cyanSoft),
                            const SizedBox(width: 5),
                            Text("Distance : ${dynamicFields!['distance']}",
                                style: HiarTypography.caption.copyWith(color: Colors.white)),
                          ],
                          if (dynamicFields?['distance'] != null && dynamicFields?['eta'] != null)
                            const Padding(
                              padding: EdgeInsets.symmetric(horizontal: 8),
                              child: Text("•", style: TextStyle(color: Colors.white54)),
                            ),
                          if (dynamicFields?['eta'] != null) ...[
                            const Icon(Icons.timer_outlined, size: 15, color: HiarColors.cyanSoft),
                            const SizedBox(width: 5),
                            Text("Arrivée : ${dynamicFields!['eta']}",
                                style: HiarTypography.caption.copyWith(color: Colors.white)),
                          ],
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: HiarSpace.lg),

            // 2. Commandes : arrêt d'urgence, ou reprise / fin
            if (!isStopped)
              HiarButton.danger(
                label: "ARRÊT DU ROBOT",
                icon: Icons.stop_rounded,
                voiceHint: "Stop",
                expand: true,
                onPressed: onStopRobot,
              )
            else
              Row(
                children: [
                  Expanded(
                    child: HiarButton.success(
                      label: "Reprendre",
                      icon: Icons.play_arrow_rounded,
                      voiceHint: "Reprendre",
                      expand: true,
                      onPressed: onResumeRobot,
                    ),
                  ),
                  const SizedBox(width: HiarSpace.md),
                  Expanded(
                    child: HiarButton.secondary(
                      label: "Terminer",
                      icon: Icons.home_outlined,
                      voiceHint: "Terminer",
                      expand: true,
                      onPressed: onFinish,
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
