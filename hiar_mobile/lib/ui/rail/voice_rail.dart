import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';
import '../theme/hiar_typography.dart';

enum VoiceState { idle, listening, thinking, speaking, error }

class VoiceRail extends StatelessWidget {
  final VoiceState voiceState;
  final String statusText;
  final String? recognizedText;
  final String? voiceTip;
  final bool isRobotConnected;
  final VoidCallback? onMicTap;
  final VoidCallback? onSilenceTap;
  final VoidCallback? onStopRobotTap;
  final VoidCallback? onSettingsTap;

  const VoiceRail({
    super.key,
    this.voiceState = VoiceState.idle,
    this.statusText = "Touchez le micro ou parlez",
    this.recognizedText,
    this.voiceTip,
    this.isRobotConnected = true,
    this.onMicTap,
    this.onSilenceTap,
    this.onStopRobotTap,
    this.onSettingsTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 248,
      decoration: const BoxDecoration(
        color: HiarColors.marine,
        boxShadow: [
          BoxShadow(
            color: Colors.black26,
            blurRadius: 10,
            offset: Offset(2, 0),
          ),
        ],
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Column(
        children: [
          // 1. Robot stylisé HIAR
          _buildRobotFace(),
          const SizedBox(height: 8),

          // 2. Libellé d'état vocal
          Text(
            statusText,
            style: HiarTypography.voiceStatus,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 12),

          // 3. Bouton Microphone avec Halo
          _buildMicButton(),
          const SizedBox(height: 12),

          // 4. Transcription en direct & conseil vocal
          Expanded(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.06),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: Colors.white.withOpacity(0.12),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (recognizedText != null && recognizedText!.isNotEmpty) ...[
                    const Text(
                      "Entendu :",
                      style: TextStyle(
                        fontSize: 11,
                        color: HiarColors.cyanSoft,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Expanded(
                      child: Text(
                        "« $recognizedText »",
                        style: const TextStyle(
                          fontSize: 15,
                          color: Colors.white,
                          fontStyle: FontStyle.italic,
                        ),
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ] else ...[
                    const Spacer(),
                  ],
                  if (voiceTip != null) ...[
                    const Divider(color: Colors.white12, height: 12),
                    Row(
                      children: [
                        const Icon(Icons.lightbulb_outline, size: 14, color: HiarColors.cyan),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            voiceTip!,
                            style: const TextStyle(
                              fontSize: 12,
                              color: HiarColors.cyanSoft,
                              fontWeight: FontWeight.w500,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),

          // 5. Bas de rail : Statut liaison robot & Bouton Paramètres
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // Indicateur robot (cliquable pour ouvrir les paramètres si configuré)
              InkWell(
                onTap: onSettingsTap,
                borderRadius: BorderRadius.circular(8),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: isRobotConnected ? HiarColors.ok : HiarColors.err,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        isRobotConnected ? "Robot prêt" : "Robot hors ligne",
                        style: const TextStyle(fontSize: 12, color: Colors.white70),
                      ),
                    ],
                  ),
                ),
              ),

              // Actions droites : Silence vocal et Petit bouton de paramètres (IP)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (voiceState == VoiceState.speaking && onSilenceTap != null) ...[
                    IconButton(
                      icon: const Icon(Icons.volume_off, color: Colors.white70, size: 18),
                      tooltip: "Couper la voix",
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      onPressed: onSilenceTap,
                    ),
                    const SizedBox(width: 8),
                  ],
                  if (onSettingsTap != null)
                    IconButton(
                      icon: const Icon(Icons.settings_outlined, color: Colors.white70, size: 20),
                      tooltip: "Paramètres de connexion (IP)",
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      onPressed: onSettingsTap,
                    ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRobotFace() {
    return Container(
      width: 72,
      height: 56,
      decoration: BoxDecoration(
        color: const Color(0xFF102F55),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: HiarColors.cyan, width: 2.5),
      ),
      child: Center(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Œil gauche
            Container(
              width: 9,
              height: 14,
              decoration: BoxDecoration(
                color: HiarColors.cyanSoft,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 14),
            // Œil droit
            Container(
              width: 9,
              height: 14,
              decoration: BoxDecoration(
                color: HiarColors.cyanSoft,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMicButton() {
    final isListening = voiceState == VoiceState.listening;

    return GestureDetector(
      onTap: onMicTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        width: 68,
        height: 68,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: isListening ? HiarColors.cyan : HiarColors.azur,
          boxShadow: isListening
              ? [
                  BoxShadow(
                    color: HiarColors.cyan.withOpacity(0.55),
                    blurRadius: 18,
                    spreadRadius: 4,
                  )
                ]
              : [
                  const BoxShadow(
                    color: Colors.black26,
                    blurRadius: 6,
                    offset: Offset(0, 3),
                  )
                ],
        ),
        child: Icon(
          isListening ? Icons.mic : Icons.mic_none,
          color: isListening ? HiarColors.marine : Colors.white,
          size: 34,
        ),
      ),
    );
  }
}
