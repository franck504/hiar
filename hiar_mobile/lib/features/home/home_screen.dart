import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/components/action_button.dart';
import '../../ui/rail/voice_rail.dart';

class HomeScreen extends StatelessWidget {
  final VoidCallback onOpenOrientation;
  final VoidCallback onOpenInformation;
  final VoidCallback onOpenConsultation;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final VoidCallback? onMicTap;
  final bool isRobotConnected;
  final String? voiceTip;

  const HomeScreen({
    super.key,
    required this.onOpenOrientation,
    required this.onOpenInformation,
    required this.onOpenConsultation,
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "Touchez le micro ou parlez",
    this.recognizedText,
    this.onMicTap,
    this.isRobotConnected = true,
    this.voiceTip,
  });

  @override
  Widget build(BuildContext context) {
    return LandscapeScaffold(
      title: "Choisissez un service",
      showBack: false,
      voiceState: voiceState,
      voiceStatus: voiceStatus,
      recognizedText: recognizedText,
      voiceTip: voiceTip ?? "Dites « Orientation », « Renseignements » ou « Consultation »",
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
                  label: "Orientation",
                  subtitle: "Pharmacie, laboratoire et accueil / réception",
                  icon: Icons.navigation_outlined,
                  voiceHint: "Orientation",
                  onTap: onOpenOrientation,
                ),
                const SizedBox(height: 12),
                ActionButton(
                  label: "Renseignements",
                  subtitle: "Repères de santé publique et prévention (OMS)",
                  icon: Icons.info_outline,
                  voiceHint: "Renseignements",
                  onTap: onOpenInformation,
                ),
                const SizedBox(height: 12),
                ActionButton(
                  label: "Consultation",
                  subtitle: "Prendre un ticket de consultation avec un médecin",
                  icon: Icons.calendar_today_outlined,
                  voiceHint: "Consultation",
                  isPrimary: true,
                  onTap: onOpenConsultation,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
