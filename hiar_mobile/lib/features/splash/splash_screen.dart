import 'package:flutter/material.dart';
import '../../ui/theme/hiar_colors.dart';

class SplashScreen extends StatelessWidget {
  final VoidCallback onStart;

  const SplashScreen({super.key, required this.onStart});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: HiarColors.marine,
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onStart,
        child: SizedBox.expand(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Visage du robot HIAR grand format
              Container(
                width: 170,
                height: 130,
                decoration: BoxDecoration(
                  color: const Color(0xFF102F55),
                  borderRadius: BorderRadius.circular(42),
                  border: Border.all(color: HiarColors.cyan, width: 6),
                  boxShadow: [
                    BoxShadow(
                      color: HiarColors.cyan.withOpacity(0.3),
                      blurRadius: 30,
                      spreadRadius: 4,
                    ),
                  ],
                ),
                child: Center(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: 22,
                        height: 32,
                        decoration: BoxDecoration(
                          color: HiarColors.cyanSoft,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      const SizedBox(width: 34),
                      Container(
                        width: 22,
                        height: 32,
                        decoration: BoxDecoration(
                          color: HiarColors.cyanSoft,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 28),
              const Text(
                "Bonjour !",
                style: TextStyle(
                  fontSize: 36,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                "Touchez l’écran ou dites « Commencer »",
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w500,
                  color: HiarColors.cyanSoft,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
