import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';
import '../theme/hiar_typography.dart';
import '../rail/voice_rail.dart';
import 'hiar_surfaces.dart';
import 'hiar_kit.dart';
import '../theme/hiar_tokens.dart';

/// Gabarit Paysage officiel HIAR — Direction Néo-Clinique (Soft Medical Glassmorphism)
/// Divisé en 2 zones : Rail vocal fixe à gauche (248 dp) + Scène atmosphérique à droite.
class LandscapeScaffold extends StatelessWidget {
  final String title;
  final String? step;
  final bool showBack;
  final VoidCallback? onBack;
  final Widget body;
  final Widget? bottomBar;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final String? voiceTip;
  final String? faceExpression;
  final VoidCallback? onMicTap;
  final VoidCallback? onSilenceTap;
  final VoidCallback? onStopRobotTap;
  final VoidCallback? onSettingsTap;
  final bool isRobotConnected;

  const LandscapeScaffold({
    super.key,
    required this.title,
    this.step,
    this.showBack = true,
    this.onBack,
    required this.body,
    this.bottomBar,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Touchez le micro ou parlez",
    this.recognizedText,
    this.voiceTip,
    this.faceExpression,
    this.onMicTap,
    this.onSilenceTap,
    this.onStopRobotTap,
    this.onSettingsTap,
    this.isRobotConnected = true,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: false,
      backgroundColor: HiarColors.canvasBottom,
      body: SafeArea(
        child: Row(
          children: [
            // 1. Zone GAUCHE : Rail Vocal verre glacier/menthe (248 dp)
            VoiceRail(
              voiceState: voiceState,
              statusText: voiceStatus,
              recognizedText: recognizedText,
              voiceTip: voiceTip,
              faceExpression: faceExpression,
              onMicTap: onMicTap,
              onSilenceTap: onSilenceTap,
              onStopRobotTap: onStopRobotTap,
              onSettingsTap: onSettingsTap,
              isRobotConnected: isRobotConnected,
            ),

            // 2. Zone DROITE : Scène Néo-Clinique avec dégradé glacier/menthe + halftone
            Expanded(
              child: HiarAtmosphericBackground(
                child: Column(
                  children: [
                    // Barre d'en-tête translucide (52 dp)
                    Container(
                      height: 60,
                      padding: const EdgeInsets.symmetric(horizontal: HiarSpace.lg),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.68),
                        border: Border(
                          bottom: BorderSide(color: Colors.white.withOpacity(0.9), width: 1.2),
                        ),
                      ),
                      child: Row(
                        children: [
                          if (showBack)
                            Padding(
                              padding: const EdgeInsets.only(right: 12),
                              child: HiarCircularButton(
                                icon: Icons.arrow_back_rounded,
                                size: 36,
                                iconSize: 19,
                                tooltip: "Retour",
                                onTap: onBack ?? () => Navigator.of(context).maybePop(),
                              ),
                            ),
                          Expanded(
                            child: Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    title,
                                    style: HiarTypography.title,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                if (step != null) ...[
                                  const SizedBox(width: 10),
                                  HiarPastelBadge(
                                    label: step!,
                                    backgroundColor: HiarColors.emeraldPastel,
                                    textColor: HiarColors.azurDark,
                                  ),
                                ],
                              ],
                            ),
                          ),
                          if (onStopRobotTap != null) ...[
                            const SizedBox(width: HiarSpace.md),
                            HiarButton.danger(
                              label: "STOP ROBOT",
                              icon: Icons.stop_rounded,
                              compact: true,
                              onPressed: onStopRobotTap,
                            ),
                          ],
                        ],
                      ),
                    ),

                    // Contenu principal de la scène
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(HiarSpace.xl, HiarSpace.lg, HiarSpace.xl, HiarSpace.lg),
                        child: body,
                      ),
                    ),

                    // Barre d'actions inférieure translucide (si présente)
                    if (bottomBar != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: HiarSpace.xl, vertical: HiarSpace.md),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.84),
                          border: Border(
                            top: BorderSide(color: Colors.white.withOpacity(0.95), width: 1.2),
                          ),
                        ),
                        child: bottomBar!,
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
}
