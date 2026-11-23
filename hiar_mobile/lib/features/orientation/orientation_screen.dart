import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/components/action_button.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/components/hiar_kit.dart';
import '../../ui/theme/hiar_tokens.dart';


class OrientationScreen extends StatelessWidget {
  final Function(String destination, String label) onDestinationSelected;
  final VoidCallback onBack;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;
  final VoidCallback? onSettingsTap;
  final bool isRobotConnected;
  final String? faceExpression;
  final VoidCallback? onStopRobotTap;

  const OrientationScreen({
    super.key,
    required this.onDestinationSelected,
    required this.onBack,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Où souhaitez-vous aller ?",
    this.recognizedText,
    this.onMicTap,
    this.onSettingsTap,
    this.isRobotConnected = true,
    this.faceExpression,
    this.onStopRobotTap,
  });

  @override
  Widget build(BuildContext context) {
    final destinations = [
      (
        key: "PHARMACY",
        label: "Pharmacie",
        subtitle: "Médicaments et ordonnances",
        hint: "Pharmacie",
        icon: Icons.local_pharmacy_outlined,
      ),
      (
        key: "LABORATORY",
        label: "Laboratoire",
        subtitle: "Analyses médicales et prélèvements",
        hint: "Laboratoire",
        icon: Icons.biotech_outlined,
      ),
      (
        key: "RADIOLOGY",
        label: "Radiologie",
        subtitle: "Radio, scanner et imagerie",
        hint: "Radiologie",
        icon: Icons.medical_information_outlined,
      ),
      (
        key: "RECEPTION",
        label: "Réception",
        subtitle: "Accueil général et admissions",
        hint: "Réception",
        icon: Icons.meeting_room_outlined,
      ),
    ];

    return LandscapeScaffold(
      title: "Orientation",
      onBack: onBack,
      onStopRobotTap: onStopRobotTap,
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: "Dites : « Pharmacie », « Laboratoire », « Radiologie » ou « Réception »",
      faceExpression: faceExpression,
      onMicTap: onMicTap,
      onSettingsTap: onSettingsTap,
      isRobotConnected: isRobotConnected,
      body: HiarSceneBody(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const HiarSceneIntro(
              badge: "Guidage autonome",
              icon: Icons.navigation_outlined,
              text: "Choisissez un service pour être accompagné par le robot",
            ),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final twoCols = constraints.maxWidth >= 460;
                    if (!twoCols) {
                      return Column(
                        children: [
                          for (int i = 0; i < destinations.length; i++) ...[
                            if (i > 0) const SizedBox(height: 10),
                            ActionButton(
                              label: destinations[i].label,
                              subtitle: destinations[i].subtitle,
                              icon: destinations[i].icon,
                              voiceHint: destinations[i].hint,
                              onTap: () => onDestinationSelected(destinations[i].key, destinations[i].label),
                            ),
                          ],
                        ],
                      );
                    }
                    return Column(
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: ActionButton(
                                label: destinations[0].label,
                                subtitle: destinations[0].subtitle,
                                icon: destinations[0].icon,
                                voiceHint: destinations[0].hint,
                                onTap: () => onDestinationSelected(destinations[0].key, destinations[0].label),
                              ),
                            ),
                            const SizedBox(width: HiarSpace.lg),
                            Expanded(
                              child: ActionButton(
                                label: destinations[1].label,
                                subtitle: destinations[1].subtitle,
                                icon: destinations[1].icon,
                                voiceHint: destinations[1].hint,
                                onTap: () => onDestinationSelected(destinations[1].key, destinations[1].label),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: HiarSpace.lg),
                        Row(
                          children: [
                            Expanded(
                              child: ActionButton(
                                label: destinations[2].label,
                                subtitle: destinations[2].subtitle,
                                icon: destinations[2].icon,
                                voiceHint: destinations[2].hint,
                                onTap: () => onDestinationSelected(destinations[2].key, destinations[2].label),
                              ),
                            ),
                            const SizedBox(width: HiarSpace.lg),
                            Expanded(
                              child: ActionButton(
                                label: destinations[3].label,
                                subtitle: destinations[3].subtitle,
                                icon: destinations[3].icon,
                                voiceHint: destinations[3].hint,
                                onTap: () => onDestinationSelected(destinations[3].key, destinations[3].label),
                              ),
                            ),
                          ],
                        ),
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
