import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';
import '../theme/hiar_typography.dart';
import '../rail/voice_rail.dart';

/// Gabarit Paysage officiel HIAR V4
/// Divisé en 2 zones : Rail vocal fixe à gauche (248 dp) + Scène dynamique à droite.
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
  final VoidCallback? onMicTap;
  final VoidCallback? onSilenceTap;
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
    this.onMicTap,
    this.onSilenceTap,
    this.isRobotConnected = true,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: HiarColors.brume,
      body: SafeArea(
        child: Row(
          children: [
            // 1. Zone GAUCHE : Rail Vocal fixe (248 dp)
            VoiceRail(
              voiceState: voiceState,
              statusText: voiceStatus,
              recognizedText: recognizedText,
              voiceTip: voiceTip,
              onMicTap: onMicTap,
              onSilenceTap: onSilenceTap,
              isRobotConnected: isRobotConnected,
            ),

            // 2. Zone DROITE : La Scène
            Expanded(
              child: Column(
                children: [
                  // Barre d'en-tête de scène (50 dp)
                  Container(
                    height: 50,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      border: Border(
                        bottom: BorderSide(color: HiarColors.border, width: 1),
                      ),
                    ),
                    child: Row(
                      children: [
                        if (showBack)
                          Padding(
                            padding: const EdgeInsets.only(right: 10),
                            child: IconButton(
                              icon: const Icon(Icons.arrow_back, color: HiarColors.marine, size: 22),
                              tooltip: "Retour",
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(),
                              onPressed: onBack ?? () => Navigator.of(context).maybePop(),
                            ),
                          ),
                        Expanded(
                          child: Row(
                            children: [
                              Flexible(
                                child: Text(
                                  title,
                                  style: HiarTypography.screenTitle.copyWith(fontSize: 20),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              if (step != null) ...[
                                const SizedBox(width: 10),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: HiarColors.azurSoft,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    step!,
                                    style: const TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: HiarColors.marine,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Contenu principal de la scène
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(16.0, 10.0, 16.0, 10.0),
                      child: body,
                    ),
                  ),

                  // Barre d'actions inférieure (si présente)
                  if (bottomBar != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                      decoration: const BoxDecoration(
                        color: Colors.white,
                        border: Border(
                          top: BorderSide(color: HiarColors.border, width: 1),
                        ),
                      ),
                      child: bottomBar!,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
