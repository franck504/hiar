import 'package:flutter/material.dart';
import '../../ui/components/animated_robot_face.dart';
import '../../ui/components/hiar_surfaces.dart';
import '../../ui/theme/hiar_colors.dart';
import '../../ui/components/hiar_kit.dart';
import '../../ui/theme/hiar_tokens.dart';
import '../../ui/theme/hiar_typography.dart';


class SplashScreen extends StatelessWidget {
  final VoidCallback onStart;

  const SplashScreen({super.key, required this.onStart});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: false,
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onStart,
        child: Container(
          decoration: const BoxDecoration(
            gradient: RadialGradient(
              center: Alignment(0.0, -0.1),
              radius: 1.15,
              colors: [
                Color(0xFFFFFFFF),
                Color(0xFFF7FBFE),
                Color(0xFFEAF4FB),
              ],
              stops: [0.0, 0.55, 1.0],
            ),
          ),
          child: SizedBox.expand(
            child: Center(
              child: SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Séquence logo HIAR : neutre yeux grands ouverts → curieux tête inclinée → sourire enthousiaste yeux fermés
                    const AnimatedRobotFace(
                      playIntroSequence: true,
                      width: 196,
                      height: 146,
                    ),
                    const SizedBox(height: 14),
                    const HiarPastelBadge(
                      label: "Assistant Hospitalier HIAR",
                      icon: Icons.medical_services_outlined,
                    ),
                    const SizedBox(height: 10),
                    const SizedBox(height: HiarSpace.sm),
                    const Text("Bonjour !", style: HiarTypography.display),
                    const SizedBox(height: HiarSpace.sm),
                    Text(
                      "Touchez l’écran ou dites « Commencer »",
                      style: HiarTypography.body.copyWith(color: HiarColors.text2),
                    ),
                    const SizedBox(height: HiarSpace.xl),
                    HiarButton.primary(
                      label: "Commencer",
                      icon: Icons.touch_app_rounded,
                      onPressed: onStart,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
