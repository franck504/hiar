import 'package:flutter/material.dart';
import '../../ui/components/hiar_surfaces.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/components/hiar_kit.dart';
import '../../ui/theme/hiar_tokens.dart';
import '../../ui/theme/hiar_typography.dart';

class InformationScreen extends StatefulWidget {
  final Function(String topicKey, String topicTitle) onSelectTopic;
  final VoidCallback onBack;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;
  final VoidCallback? onSettingsTap;
  final bool isRobotConnected;
  final String? faceExpression;
  final VoidCallback? onStopRobotTap;

  const InformationScreen({
    super.key,
    required this.onSelectTopic,
    required this.onBack,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Choisissez un thème de santé",
    this.recognizedText,
    this.onMicTap,
    this.onSettingsTap,
    this.isRobotConnected = true,
    this.faceExpression,
    this.onStopRobotTap,
  });

  @override
  State<InformationScreen> createState() => _InformationScreenState();
}

class _InformationScreenState extends State<InformationScreen> {
  String _selectedFilter = 'all';

  static const _topics = [
    (
      key: 'HIV',
      title: 'VIH / SIDA',
      hint: 'VIH',
      category: 'prevention',
      tag: 'Prévention',
      desc: 'Prévention, transmission et dépistage',
      icon: Icons.healing_outlined,
    ),
    (
      key: 'MALARIA',
      title: 'Paludisme',
      hint: 'Paludisme',
      category: 'prevention',
      tag: 'Prévention',
      desc: 'Transmission par moustiques et symptômes',
      icon: Icons.pest_control_outlined,
    ),
    (
      key: 'DIABETES',
      title: 'Diabète',
      hint: 'Diabète',
      category: 'chronique',
      tag: 'Suivi',
      desc: 'Glycémie, dépistage et précautions',
      icon: Icons.bloodtype_outlined,
    ),
    (
      key: 'HYPERTENSION',
      title: 'Hypertension',
      hint: 'Hypertension',
      category: 'chronique',
      tag: 'Suivi',
      desc: 'Pression artérielle et suivi médical',
      icon: Icons.favorite_outline,
    ),
    (
      key: 'TUBERCULOSIS',
      title: 'Tuberculose',
      hint: 'Tuberculose',
      category: 'prevention',
      tag: 'Prévention',
      desc: 'Transmission par l’air et prise en charge',
      icon: Icons.air_outlined,
    ),
    (
      key: 'MENSTRUAL_HEALTH',
      title: 'Santé menstruelle',
      hint: 'Règles',
      category: 'prevention',
      tag: 'Bien-être',
      desc: 'Manifestations, hygiène et suivi',
      icon: Icons.water_drop_outlined,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final filtered = _selectedFilter == 'all'
        ? _topics
        : _topics.where((t) => t.category == _selectedFilter).toList();

    return LandscapeScaffold(
      title: "Renseignements santé",
      onBack: widget.onBack,
      onStopRobotTap: widget.onStopRobotTap,
      voiceState: widget.voiceState,
      voiceStatus: widget.voiceStatus,
      recognizedText: widget.recognizedText,
      voiceTip: "Dites un thème : « VIH », « Paludisme », « Diabète »…",
      faceExpression: widget.faceExpression,
      onMicTap: widget.onMicTap,
      onSettingsTap: widget.onSettingsTap,
      isRobotConnected: widget.isRobotConnected,
      body: HiarSceneBody(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Filtres
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  HiarPillTab(
                    label: "Toutes les fiches",
                    countBadge: _topics.length,
                    selected: _selectedFilter == 'all',
                    onTap: () => setState(() => _selectedFilter = 'all'),
                  ),
                  const SizedBox(width: HiarSpace.sm),
                  HiarPillTab(
                    label: "Prévention",
                    selected: _selectedFilter == 'prevention',
                    onTap: () => setState(() => _selectedFilter = 'prevention'),
                  ),
                  const SizedBox(width: HiarSpace.sm),
                  HiarPillTab(
                    label: "Maladies chroniques",
                    selected: _selectedFilter == 'chronique',
                    onTap: () => setState(() => _selectedFilter = 'chronique'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: HiarSpace.lg),

            // Fiches : hauteur fixe (plus de cartes étirées par un ratio)
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: HiarSpace.lg,
                mainAxisSpacing: HiarSpace.lg,
                mainAxisExtent: 118,
              ),
              itemCount: filtered.length,
              itemBuilder: (context, index) {
                final t = filtered[index];
                return _HealthArticleCard(
                  title: t.title,
                  description: t.desc,
                  tag: t.tag,
                  voiceHint: t.hint,
                  icon: t.icon,
                  onTap: () => widget.onSelectTopic(t.key, t.title),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _HealthArticleCard extends StatelessWidget {
  final String title;
  final String description;
  final String tag;
  final String voiceHint;
  final IconData icon;
  final VoidCallback onTap;

  const _HealthArticleCard({
    required this.title,
    required this.description,
    required this.tag,
    required this.voiceHint,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return HiarGlassCard(
      onTap: onTap,
      padding: const EdgeInsets.all(HiarSpace.lg),
      child: Row(
        children: [
          HiarIconBox(icon, size: 52),
          const SizedBox(width: HiarSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: HiarTypography.heading),
                const SizedBox(height: 2),
                Text(description, maxLines: 1, overflow: TextOverflow.ellipsis, style: HiarTypography.subtitle),
                const SizedBox(height: HiarSpace.sm),
                Row(
                  children: [
                    Flexible(child: HiarPastelBadge(label: "OMS · $tag")),
                    const SizedBox(width: HiarSpace.sm),
                    Flexible(child: HiarVoiceChip(voiceHint)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
