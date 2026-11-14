import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/components/action_button.dart';
import '../../ui/rail/voice_rail.dart';

class InformationScreen extends StatelessWidget {
  final Function(String topicKey, String topicTitle) onSelectTopic;
  final VoidCallback onBack;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;
  final bool isRobotConnected;

  const InformationScreen({
    super.key,
    required this.onSelectTopic,
    required this.onBack,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Choisissez un thème de santé",
    this.recognizedText,
    this.onMicTap,
    this.isRobotConnected = true,
  });

  @override
  Widget build(BuildContext context) {
    final topics = [
      {
        'key': 'HIV',
        'title': 'VIH / SIDA',
        'hint': 'VIH',
        'desc': 'Prévention, transmission et dépistage',
        'icon': Icons.healing_outlined,
      },
      {
        'key': 'MALARIA',
        'title': 'Paludisme',
        'hint': 'Paludisme',
        'desc': 'Transmission par moustiques, symptômes',
        'icon': Icons.pest_control_outlined,
      },
      {
        'key': 'DIABETES',
        'title': 'Diabète',
        'hint': 'Diabète',
        'desc': 'Glycémie, dépistage et précautions',
        'icon': Icons.bloodtype_outlined,
      },
      {
        'key': 'HYPERTENSION',
        'title': 'Hypertension',
        'hint': 'Hypertension',
        'desc': 'Pression artérielle et suivi médical',
        'icon': Icons.favorite_outline,
      },
      {
        'key': 'TUBERCULOSIS',
        'title': 'Tuberculose',
        'hint': 'Tuberculose',
        'desc': 'Transmission par l’air et prise en charge',
        'icon': Icons.air_outlined,
      },
      {
        'key': 'MENSTRUAL_HEALTH',
        'title': 'Santé menstruelle',
        'hint': 'Règles',
        'desc': 'Manifestations, hygiène et suivi',
        'icon': Icons.water_drop_outlined,
      },
    ];

    return LandscapeScaffold(
      title: "Renseignements santé",
      onBack: onBack,
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: "Dites un thème : « VIH », « Paludisme », « Diabète »…",
      onMicTap: onMicTap,
      isRobotConnected: isRobotConnected,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: GridView.builder(
            physics: const BouncingScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
              childAspectRatio: 1.95,
            ),
            itemCount: topics.length,
            itemBuilder: (context, index) {
              final t = topics[index];
              return ActionButton(
                label: t['title'] as String,
                subtitle: t['desc'] as String,
                icon: t['icon'] as IconData,
                voiceHint: t['hint'] as String,
                onTap: () => onSelectTopic(t['key'] as String, t['title'] as String),
              );
            },
          ),
        ),
      ),
    );
  }
}
