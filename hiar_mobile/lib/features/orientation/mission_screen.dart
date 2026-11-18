import 'package:flutter/material.dart';
import '../../ui/components/hiar_surfaces.dart';
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
      body: Center(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 580),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 1. Carte Héros Ardoise → Sarcelle (ou alerte si arrêté)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: isStopped
                          ? const [Color(0xFF7F1D1D), Color(0xFFB91C1C)]
                          : const [HiarColors.slateTealStart, HiarColors.slateTealEnd],
                    ),
                    borderRadius: BorderRadius.circular(22),
                    boxShadow: [
                      BoxShadow(
                        color: (isStopped ? HiarColors.err : HiarColors.slateTealStart).withOpacity(0.24),
                        blurRadius: 18,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.16),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white.withOpacity(0.28)),
                        ),
                        child: Icon(
                          isStopped ? Icons.stop_circle_outlined : Icons.directions_walk_rounded,
                          size: 30,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        isStopped
                            ? "Le robot s'est arrêté."
                            : "Je vous accompagne vers : $destinationLabel",
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                          letterSpacing: -0.3,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        isStopped
                            ? "Vous pouvez reprendre le guidage ou retourner à l'accueil."
                            : "Veuillez me suivre en restant vigilant.",
                        style: const TextStyle(
                          fontSize: 13.5,
                          color: Colors.white70,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      if (!isStopped && (dynamicFields?['distance'] != null || dynamicFields?['eta'] != null)) ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(color: Colors.white.withOpacity(0.22)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (dynamicFields?['distance'] != null) ...[
                                const Icon(Icons.straighten, size: 15, color: HiarColors.cyanSoft),
                                const SizedBox(width: 5),
                                Text(
                                  "Distance : ${dynamicFields!['distance']}",
                                  style: const TextStyle(
                                    fontSize: 12.5,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                  ),
                                ),
                              ],
                              if (dynamicFields?['distance'] != null && dynamicFields?['eta'] != null)
                                const Padding(
                                  padding: EdgeInsets.symmetric(horizontal: 8),
                                  child: Text("•", style: TextStyle(color: Colors.white54)),
                                ),
                              if (dynamicFields?['eta'] != null) ...[
                                const Icon(Icons.timer_outlined, size: 15, color: HiarColors.cyanSoft),
                                const SizedBox(width: 5),
                                Text(
                                  "Arrivée : ${dynamicFields!['eta']}",
                                  style: const TextStyle(
                                    fontSize: 12.5,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 14),

                // 2. Commandes d'action (Arrêt d'urgence ou Reprise / Terminer)
                HiarGlassCard(
                  padding: const EdgeInsets.all(14),
                  child: !isStopped
                      ? SizedBox(
                          width: double.infinity,
                          height: 52,
                          child: ElevatedButton.icon(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: HiarColors.err,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(999),
                              ),
                              elevation: 4,
                            ),
                            icon: const Icon(Icons.stop_rounded, size: 26),
                            label: const Text(
                              "ARRÊT DU ROBOT  (🎤 « Stop »)",
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                            ),
                            onPressed: onStopRobot,
                          ),
                        )
                      : Row(
                          children: [
                            Expanded(
                              child: SizedBox(
                                height: 48,
                                child: ElevatedButton.icon(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: HiarColors.ok,
                                    foregroundColor: Colors.white,
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                    elevation: 2,
                                  ),
                                  icon: const Icon(Icons.play_arrow_rounded, size: 22),
                                  label: const Text(
                                    "Reprendre (🎤 « Reprendre »)",
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700),
                                  ),
                                  onPressed: onResumeRobot,
                                ),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: SizedBox(
                                height: 48,
                                child: OutlinedButton.icon(
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: HiarColors.marine,
                                    backgroundColor: Colors.white,
                                    side: const BorderSide(color: HiarColors.border, width: 1.4),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                  ),
                                  icon: const Icon(Icons.home_outlined, size: 19),
                                  label: const Text(
                                    "Terminer (🎤 « Terminer »)",
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700),
                                  ),
                                  onPressed: onFinish,
                                ),
                              ),
                            ),
                          ],
                        ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
