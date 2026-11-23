import 'package:flutter/material.dart';
import '../../ui/components/hiar_surfaces.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/theme/hiar_colors.dart';
import '../../ui/components/hiar_kit.dart';
import '../../ui/theme/hiar_tokens.dart';
import '../../ui/theme/hiar_typography.dart';


class HomeScreen extends StatelessWidget {
  final VoidCallback onOpenOrientation;
  final VoidCallback onOpenInformation;
  final VoidCallback onOpenConsultation;
  final VoidCallback? onBack;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;
  final VoidCallback? onSettingsTap;
  final bool isRobotConnected;
  final String? voiceTip;
  final String? faceExpression;
  final VoidCallback? onStopRobotTap;

  const HomeScreen({
    super.key,
    required this.onOpenOrientation,
    required this.onOpenInformation,
    required this.onOpenConsultation,
    this.onBack,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Touchez le micro ou parlez",
    this.recognizedText,
    this.onMicTap,
    this.onSettingsTap,
    this.isRobotConnected = true,
    this.voiceTip,
    this.faceExpression,
    this.onStopRobotTap,
  });

  @override
  Widget build(BuildContext context) {
    return LandscapeScaffold(
      title: "Accueil HIAR",
      showBack: true,
      onBack: onBack,
      onStopRobotTap: onStopRobotTap,
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: voiceTip ?? "Dites « Orientation », « Renseignements » ou « Consultation »",
      faceExpression: faceExpression,
      onMicTap: onMicTap,
      onSettingsTap: onSettingsTap,
      isRobotConnected: isRobotConnected,
      body: HiarSceneBody(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 1. Bandeau d'accueil
            HiarHeroCard(
              padding: const EdgeInsets.symmetric(horizontal: HiarSpace.xl, vertical: HiarSpace.lg),
              child: Row(
                children: [
                  const HiarIconBox(Icons.health_and_safety_outlined, onDark: true, size: 48),
                  const SizedBox(width: HiarSpace.lg),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text("Assistant hospitalier",
                            style: HiarTypography.caption.copyWith(color: Colors.white70)),
                        const SizedBox(height: 2),
                        Text("Comment puis-je vous aider ?",
                            style: HiarTypography.title.copyWith(color: Colors.white)),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.16),
                      borderRadius: HiarRadius.pillAll,
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.mic_rounded, color: HiarColors.cyanSoft, size: 14),
                        const SizedBox(width: 4),
                        Text("Voix active", style: HiarTypography.chip.copyWith(color: Colors.white)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: HiarSpace.lg),

            // 2. Les trois services
            LayoutBuilder(
              builder: (context, constraints) {
                final bool threeCols = constraints.maxWidth >= 480;
                final tiles = [
                  _HomeServiceTile(
                    title: "Orientation",
                    subtitle: "Pharmacie, labo, radio et accueil",
                    voiceHint: "Orientation",
                    icon: Icons.navigation_outlined,
                    accentColor: HiarColors.azur,
                    onTap: onOpenOrientation,
                  ),
                  _HomeServiceTile(
                    title: "Renseignements",
                    subtitle: "Fiches santé et prévention OMS",
                    voiceHint: "Renseignements",
                    icon: Icons.menu_book_outlined,
                    accentColor: HiarColors.emerald,
                    onTap: onOpenInformation,
                  ),
                  _HomeServiceTile(
                    title: "Consultation",
                    subtitle: "Constantes et ticket médecin",
                    voiceHint: "Consultation",
                    icon: Icons.calendar_today_outlined,
                    accentColor: HiarColors.slateTealStart,
                    highlighted: true,
                    onTap: onOpenConsultation,
                  ),
                ];

                if (threeCols) {
                  return IntrinsicHeight(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        for (int i = 0; i < tiles.length; i++) ...[
                          if (i > 0) const SizedBox(width: HiarSpace.lg),
                          Expanded(child: tiles[i]),
                        ],
                      ],
                    ),
                  );
                }
                return Column(
                  children: [
                    for (int i = 0; i < tiles.length; i++) ...[
                      if (i > 0) const SizedBox(height: HiarSpace.md),
                      tiles[i],
                    ],
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _HomeServiceTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final String voiceHint;
  final IconData icon;
  final Color accentColor;
  final bool highlighted;
  final VoidCallback onTap;

  const _HomeServiceTile({
    required this.title,
    required this.subtitle,
    required this.voiceHint,
    required this.icon,
    required this.accentColor,
    this.highlighted = false,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return HiarGlassCard(
      highlighted: highlighted,
      padding: const EdgeInsets.all(HiarSpace.lg),
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              HiarIconBox(icon, color: accentColor, size: 52),
              Icon(Icons.arrow_forward_ios_rounded, size: 16, color: HiarColors.text2.withOpacity(0.6)),
            ],
          ),
          const SizedBox(height: HiarSpace.lg),
          Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: HiarTypography.heading.copyWith(fontSize: 19)),
          const SizedBox(height: HiarSpace.xs),
          Text(subtitle, maxLines: 2, overflow: TextOverflow.ellipsis, style: HiarTypography.subtitle),
          const SizedBox(height: HiarSpace.lg),
          HiarVoiceChip(voiceHint),
        ],
      ),
    );
  }
}
