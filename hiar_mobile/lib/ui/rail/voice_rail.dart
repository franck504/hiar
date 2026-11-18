import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';
import '../components/animated_robot_face.dart';
import '../components/auto_scroll_text.dart';
import '../components/hiar_surfaces.dart';

enum VoiceState { idle, listening, thinking, speaking, error }

class VoiceRail extends StatelessWidget {
  final VoiceState voiceState;
  final String statusText;
  final String? recognizedText;
  final String? voiceTip;
  final bool isRobotConnected;
  final String? faceExpression;
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
    this.faceExpression,
    this.onMicTap,
    this.onSilenceTap,
    this.onStopRobotTap,
    this.onSettingsTap,
  });

  RobotFaceExpression _resolveFaceExpression() {
    // 1. Les états temps réel prioritaires (attente réponse vocale, alerte, parole)
    if (voiceState == VoiceState.thinking) return RobotFaceExpression.thinking;
    if (voiceState == VoiceState.error) return RobotFaceExpression.emergency;
    if (voiceState == VoiceState.speaking) return RobotFaceExpression.speaking;

    // 2. Expression explicite envoyée par le serveur (happy, emergency, ...)
    if (faceExpression != null && faceExpression!.isNotEmpty) {
      final parsed = parseRobotFaceExpression(faceExpression);
      if (parsed != RobotFaceExpression.idle) return parsed;
    }

    // 3. Par défaut selon l'état d'écoute
    if (voiceState == VoiceState.listening) return RobotFaceExpression.listening;
    return RobotFaceExpression.idle;
  }

  @override
  Widget build(BuildContext context) {
    final isThinking = voiceState == VoiceState.thinking;
    final isListening = voiceState == VoiceState.listening;
    final resolvedExpression = _resolveFaceExpression();

    return Container(
      width: 248,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            HiarColors.primaryLight,
            HiarColors.primarySoft,
            HiarColors.turquoisePale,
          ],
          stops: [0.0, 0.55, 1.0],
        ),
        border: Border(
          right: BorderSide(color: Colors.white.withOpacity(0.65), width: 1.5),
        ),
        boxShadow: HiarShadows.card,
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
        child: Column(
          children: [
            // 1. Tête animée du robot HIAR (sourire, yeux qui bougent, inclinaison)
            AnimatedRobotFace(
              expression: resolvedExpression,
              width: 82,
              height: 60,
              showLoadingRing: isThinking,
            ),
            const SizedBox(height: 8),

            // 2. Libellé d'état vocal (+ pastille de chargement en mode réflexion)
            if (isThinking)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3.5),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.85),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: HiarColors.azur.withOpacity(0.25)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const SizedBox(
                      width: 11,
                      height: 11,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: HiarColors.azur,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        statusText,
                        style: const TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w700,
                          color: HiarColors.marine,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              )
            else
              Text(
                statusText,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: HiarColors.marine,
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            const SizedBox(height: 10),

            // 3. Rangée de boutons circulaires flottants façon UI_style.jpeg
            //    [ Silence/Son ]  [ Micro central Sarcelle ]  [ Paramètres ]
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                HiarCircularButton(
                  icon: voiceState == VoiceState.speaking ? Icons.volume_off : Icons.volume_up_outlined,
                  size: 38,
                  iconSize: 18,
                  tooltip: voiceState == VoiceState.speaking ? "Couper la voix" : "Voix active",
                  onTap: voiceState == VoiceState.speaking ? onSilenceTap : null,
                ),
                const SizedBox(width: 12),
                _buildMicButton(isListening: isListening, isThinking: isThinking),
                const SizedBox(width: 12),
                HiarCircularButton(
                  icon: Icons.settings_outlined,
                  size: 38,
                  iconSize: 18,
                  tooltip: "Paramètres de connexion (IP)",
                  onTap: onSettingsTap,
                ),
              ],
            ),
            const SizedBox(height: 10),

            // 4. Carte de transcription en direct + barre de chargement + conseil vocal
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.76),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Colors.white, width: 1.3),
                  boxShadow: [
                    BoxShadow(
                      color: HiarColors.slateTealStart.withOpacity(0.06),
                      blurRadius: 10,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (isThinking) ...[
                      ClipRRect(
                        borderRadius: BorderRadius.circular(999),
                        child: const LinearProgressIndicator(
                          minHeight: 3,
                          backgroundColor: HiarColors.emeraldPastel,
                          valueColor: AlwaysStoppedAnimation<Color>(HiarColors.azur),
                        ),
                      ),
                      const SizedBox(height: 6),
                    ],
                    if (recognizedText != null && recognizedText!.isNotEmpty) ...[
                      Row(
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: isThinking ? HiarColors.azur : HiarColors.emerald,
                            ),
                          ),
                          const SizedBox(width: 5),
                          Expanded(
                            child: Text(
                              isThinking ? "Analyse de votre demande…" : "Entendu :",
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 10.5,
                                color: HiarColors.azurDark,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 3),
                      Expanded(
                        child: Text(
                          "« $recognizedText »",
                          style: const TextStyle(
                            fontSize: 13.5,
                            color: HiarColors.marine,
                            fontStyle: FontStyle.italic,
                            fontWeight: FontWeight.w500,
                          ),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ] else ...[
                      const Spacer(),
                    ],
                    if (voiceTip != null) ...[
                      Divider(color: HiarColors.border.withOpacity(0.7), height: 10),
                      Row(
                        children: [
                          const Icon(Icons.lightbulb_outline, size: 14, color: HiarColors.emerald),
                          const SizedBox(width: 6),
                          Expanded(
                            child: AutoScrollText(
                              text: voiceTip!,
                              style: const TextStyle(
                                fontSize: 11.5,
                                color: HiarColors.text2,
                                fontWeight: FontWeight.w600,
                              ),
                              velocity: 30.0,
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

            // 5. Pastille de liaison robot (cliquable → paramètres)
            InkWell(
              onTap: onSettingsTap,
              borderRadius: BorderRadius.circular(999),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.75),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: Colors.white),
                ),
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
                      isRobotConnected ? "Robot connecté" : "Robot hors ligne",
                      style: const TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                        color: HiarColors.marine,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMicButton({required bool isListening, required bool isThinking}) {
    return GestureDetector(
      onTap: onMicTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        width: 54,
        height: 54,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: isThinking
                ? const [HiarColors.azur, HiarColors.cyan]
                : (isListening
                    ? const [HiarColors.slateTealEnd, HiarColors.cyan]
                    : const [HiarColors.slateTealStart, HiarColors.slateTealEnd]),
          ),
          border: Border.all(color: Colors.white.withOpacity(0.65), width: 1.5),
          boxShadow: [
            BoxShadow(
              color: (isListening || isThinking ? HiarColors.cyan : HiarColors.slateTealStart)
                  .withOpacity(isListening || isThinking ? 0.42 : 0.28),
              blurRadius: isListening || isThinking ? 16 : 10,
              spreadRadius: isListening ? 2 : 0,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Center(
          child: isThinking
              ? const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.6,
                    color: Colors.white,
                  ),
                )
              : Icon(
                  isListening ? Icons.mic : Icons.mic_none,
                  color: Colors.white,
                  size: 25,
                ),
        ),
      ),
    );
  }
}
