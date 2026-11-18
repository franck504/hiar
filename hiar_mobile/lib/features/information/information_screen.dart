import 'package:flutter/material.dart';
import '../../ui/components/hiar_surfaces.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/theme/hiar_colors.dart';

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
      voiceState: widget.voiceState,
      voiceStatus: widget.voiceStatus,
      recognizedText: widget.recognizedText,
      voiceTip: "Dites un thème : « VIH », « Paludisme », « Diabète »…",
      faceExpression: widget.faceExpression,
      onMicTap: widget.onMicTap,
      onSettingsTap: widget.onSettingsTap,
      isRobotConnected: widget.isRobotConnected,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Onglets pilules façon « General 4 / Obstetrician » de UI_style.jpeg
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
                    const SizedBox(width: 8),
                    HiarPillTab(
                      label: "Prévention",
                      selected: _selectedFilter == 'prevention',
                      onTap: () => setState(() => _selectedFilter = 'prevention'),
                    ),
                    const SizedBox(width: 8),
                    HiarPillTab(
                      label: "Maladies chroniques",
                      selected: _selectedFilter == 'chronique',
                      onTap: () => setState(() => _selectedFilter = 'chronique'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // Grille de cartes façon « Health Tips / Protect Your Health »
              Expanded(
                child: GridView.builder(
                  physics: const BouncingScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 10,
                    childAspectRatio: 2.15,
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
              ),
            ],
          ),
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
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Colors.white, Color(0xFFF3FAFD)],
            ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white, width: 1.4),
            boxShadow: [
              BoxShadow(
                color: HiarColors.slateTealStart.withOpacity(0.08),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            children: [
              // Vignette illustrée arrondie à gauche
              Container(
                width: 56,
                height: double.infinity,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [HiarColors.iceTop, HiarColors.emeraldPastel],
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: HiarColors.azur, size: 28),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: HiarPastelBadge(label: "OMS · $tag"),
                        ),
                        const SizedBox(width: 6),
                        const Icon(Icons.mic, size: 12, color: HiarColors.emerald),
                        const SizedBox(width: 2),
                        Flexible(
                          child: Text(
                            "« $voiceHint »",
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 10.5,
                              fontWeight: FontWeight.w700,
                              color: HiarColors.text2,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 5),
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: HiarColors.marine,
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      description,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 11.5,
                        height: 1.25,
                        color: HiarColors.text2,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
