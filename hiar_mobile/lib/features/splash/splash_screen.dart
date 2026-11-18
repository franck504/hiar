import 'package:flutter/material.dart';
import '../../ui/components/animated_robot_face.dart';
import '../../ui/components/hiar_surfaces.dart';
import '../../ui/theme/hiar_colors.dart';

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
                    const Text(
                      "Bonjour !",
                      style: TextStyle(
                        fontSize: 34,
                        fontWeight: FontWeight.w800,
                        color: HiarColors.marine,
                        letterSpacing: -0.6,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      "Touchez l’écran ou dites « Commencer »",
                      style: TextStyle(
                        fontSize: 15.5,
                        fontWeight: FontWeight.w500,
                        color: HiarColors.text2,
                      ),
                    ),
                    const SizedBox(height: 18),
                    // Bouton pilule Ardoise → Sarcelle
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 12),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [HiarColors.slateTealStart, HiarColors.slateTealEnd],
                        ),
                        borderRadius: BorderRadius.circular(999),
                        boxShadow: [
                          BoxShadow(
                            color: HiarColors.slateTealStart.withOpacity(0.24),
                            blurRadius: 16,
                            offset: const Offset(0, 6),
                          ),
                        ],
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.touch_app_rounded, color: Colors.white, size: 20),
                          SizedBox(width: 8),
                          Text(
                            "Commencer",
                            style: TextStyle(
                              fontSize: 15.5,
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
            ),
          ),
        ),
      ),
    );
  }
}
