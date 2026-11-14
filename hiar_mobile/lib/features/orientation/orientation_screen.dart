import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/components/action_button.dart';
import '../../ui/rail/voice_rail.dart';

class OrientationScreen extends StatelessWidget {
  final Function(String destination, String label) onDestinationSelected;
  final VoidCallback onBack;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;

  final bool isRobotConnected;

  const OrientationScreen({
    super.key,
    required this.onDestinationSelected,
    required this.onBack,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Où souhaitez-vous aller ?",
    this.recognizedText,
    this.onMicTap,
    this.isRobotConnected = true,
  });

  @override
  Widget build(BuildContext context) {
    return LandscapeScaffold(
      title: "Orientation",
      onBack: onBack,
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: "Dites : « Pharmacie », « Laboratoire » ou « Réception »",
      onMicTap: onMicTap,
      isRobotConnected: isRobotConnected,
      body: Center(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 620),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ActionButton(
                  label: "Pharmacie",
                  subtitle: "Médicaments et ordonnances",
                  icon: Icons.local_pharmacy_outlined,
                  voiceHint: "Pharmacie",
                  onTap: () => onDestinationSelected("PHARMACY", "Pharmacie"),
                ),
                const SizedBox(height: 12),
                ActionButton(
                  label: "Laboratoire",
                  subtitle: "Analyses médicales et prélèvements",
                  icon: Icons.biotech_outlined,
                  voiceHint: "Laboratoire",
                  onTap: () => onDestinationSelected("LABORATORY", "Laboratoire"),
                ),
                const SizedBox(height: 12),
                ActionButton(
                  label: "Réception",
                  subtitle: "Accueil général et admissions",
                  icon: Icons.meeting_room_outlined,
                  voiceHint: "Réception",
                  onTap: () => onDestinationSelected("RECEPTION", "Réception"),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
