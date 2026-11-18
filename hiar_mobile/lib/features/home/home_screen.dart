import 'package:flutter/material.dart';
import '../../ui/components/hiar_surfaces.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/theme/hiar_colors.dart';

class HomeScreen extends StatelessWidget {
  final VoidCallback onOpenOrientation;
  final VoidCallback onOpenInformation;
  final VoidCallback onOpenConsultation;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;
  final VoidCallback? onSettingsTap;
  final bool isRobotConnected;
  final String? voiceTip;
  final String? faceExpression;

  const HomeScreen({
    super.key,
    required this.onOpenOrientation,
    required this.onOpenInformation,
    required this.onOpenConsultation,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Touchez le micro ou parlez",
    this.recognizedText,
    this.onMicTap,
    this.onSettingsTap,
    this.isRobotConnected = true,
    this.voiceTip,
    this.faceExpression,
  });

  @override
  Widget build(BuildContext context) {
    return LandscapeScaffold(
      title: "Accueil HIAR",
      showBack: false,
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: voiceTip ?? "Dites « Orientation », « Renseignements » ou « Consultation »",
      faceExpression: faceExpression,
      onMicTap: onMicTap,
      onSettingsTap: onSettingsTap,
      isRobotConnected: isRobotConnected,
      body: Center(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 680),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 1. Carte Héros sombre Ardoise → Sarcelle (façon bandeau rendez-vous de UI_style.jpeg)
                HiarHeroCard(
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                  child: Row(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.16),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(color: Colors.white.withOpacity(0.24)),
                        ),
                        child: const Icon(Icons.health_and_safety_outlined, color: Colors.white, size: 24),
                      ),
                      const SizedBox(width: 14),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              "Assistant hospitalier",
                              style: TextStyle(
                                fontSize: 11.5,
                                color: Colors.white70,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            SizedBox(height: 2),
                            Text(
                              "Comment puis-je vous aider ?",
                              style: TextStyle(
                                fontSize: 18.5,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                letterSpacing: -0.3,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.16),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.mic, color: HiarColors.cyanSoft, size: 14),
                            SizedBox(width: 4),
                            Text(
                              "Voix active",
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),

                // 2. Tuiles verre dégradé (façon Pharmacy / My Queue / Schedule)
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
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (int i = 0; i < tiles.length; i++) ...[
                            if (i > 0) const SizedBox(width: 12),
                            Expanded(child: tiles[i]),
                          ],
                        ],
                      );
                    }

                    return Column(
                      children: [
                        for (int i = 0; i < tiles.length; i++) ...[
                          if (i > 0) const SizedBox(height: 10),
                          tiles[i],
                        ],
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
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
      padding: const EdgeInsets.all(14),
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: [
                    BoxShadow(
                      color: accentColor.withOpacity(0.14),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
                child: Icon(icon, color: accentColor, size: 22),
              ),
              Icon(Icons.arrow_forward_ios_rounded, size: 14, color: HiarColors.text2.withOpacity(0.6)),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: HiarColors.marine,
              letterSpacing: -0.2,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            subtitle,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 11.5,
              height: 1.3,
              color: HiarColors.text2,
            ),
          ),
          const SizedBox(height: 10),
          HiarPastelBadge(
            label: "« $voiceHint »",
            icon: Icons.mic,
          ),
        ],
      ),
    );
  }
}
