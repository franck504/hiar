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
      {'key': 'HIV', 'title': 'VIH / SIDA', 'hint': 'VIH', 'desc': 'Prévention, transmission et dépistage'},
      {'key': 'MALARIA', 'title': 'Paludisme', 'hint': 'Paludisme', 'desc': 'Transmission par moustiques, symptômes'},
      {'key': 'DIABETES', 'title': 'Diabète', 'hint': 'Diabète', 'desc': 'Glycémie, dépistage et précautions'},
      {'key': 'HYPERTENSION', 'title': 'Hypertension', 'hint': 'Hypertension', 'desc': 'Pression artérielle et suivi médical'},
      {'key': 'TUBERCULOSIS', 'title': 'Tuberculose', 'hint': 'Tuberculose', 'desc': 'Transmission par l’air et prise en charge'},
      {'key': 'MENSTRUAL_HEALTH', 'title': 'Santé menstruelle', 'hint': 'Règles', 'desc': 'Manifestations, hygiène et suivi'},
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
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 3.2,
            ),
            itemCount: topics.length,
            itemBuilder: (context, index) {
              final t = topics[index];
              return ActionButton(
                label: t['title']!,
                subtitle: t['desc']!,
                icon: Icons.article_outlined,
                voiceHint: t['hint']!,
                onTap: () => onSelectTopic(t['key']!, t['title']!),
              );
            },
          ),
        ),
      ),
    );
  }
}
