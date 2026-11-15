import 'package:flutter/material.dart';
import '../../ui/theme/hiar_colors.dart';

class SplashScreen extends StatelessWidget {
  final VoidCallback onStart;

  const SplashScreen({super.key, required this.onStart});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: false,
      backgroundColor: HiarColors.marine,
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onStart,
        child: SizedBox.expand(
          child: Center(
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Visage du robot HIAR grand format
                  Container(
                    width: 140,
                    height: 104,
                    decoration: BoxDecoration(
                      color: const Color(0xFF102F55),
                      borderRadius: BorderRadius.circular(36),
                      border: Border.all(color: HiarColors.cyan, width: 5),
                      boxShadow: [
                        BoxShadow(
                          color: HiarColors.cyan.withOpacity(0.3),
                          blurRadius: 24,
                          spreadRadius: 3,
                        ),
                      ],
                    ),
                    child: Center(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            width: 18,
                            height: 26,
                            decoration: BoxDecoration(
                              color: HiarColors.cyanSoft,
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          const SizedBox(width: 28),
                          Container(
                            width: 18,
                            height: 26,
                            decoration: BoxDecoration(
                              color: HiarColors.cyanSoft,
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    "Bonjour !",
                    style: TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    "Touchez l’écran ou dites « Commencer »",
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w500,
                      color: HiarColors.cyanSoft,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
