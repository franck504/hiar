import 'package:flutter/material.dart';

/// Jetons de couleur officiels HIAR — Direction « Soft Medical Glassmorphism » (Néo-Clinique)
class HiarColors {
  HiarColors._();

  // Palette principale (conservée + harmonisée Néo-Clinique)
  static const Color marine = Color(0xFF102A3A);
  static const Color azur = Color(0xFF17827F); // Sarcelle médical moderne
  static const Color azurDark = Color(0xFF116366);
  static const Color azurSoft = Color(0xFFDDF4F1);
  static const Color brume = Color(0xFFF1F8FC);
  static const Color card = Color(0xFFFFFFFF);
  static const Color text1 = Color(0xFF102A3A);
  static const Color text2 = Color(0xFF566B7A);
  static const Color border = Color(0xFFD6E7F0);

  // Dégradés atmosphériques & verre (inspirés UI_style.jpeg)
  static const Color iceTop = Color(0xFFD6EEFF);
  static const Color mintSoft = Color(0xFFDDF6F0);
  static const Color canvasBottom = Color(0xFFF6FBFE);

  // Carte héros sombre Ardoise → Sarcelle
  static const Color slateTealStart = Color(0xFF283E47);
  static const Color slateTealEnd = Color(0xFF17827F);

  // Tuiles verre dégradé (haut menthe translucide → bas blanc pur)
  static const Color glassMintTop = Color(0xBFD2F1EB);
  static const Color glassWhiteBottom = Color(0xFAFFFFFF);

  // Accents émeraude / badges santé
  static const Color emerald = Color(0xFF16A37F);
  static const Color emeraldPastel = Color(0xFFDDF6EE);

  // Éléments vocaux et visage robot
  static const Color cyan = Color(0xFF20C9E8);
  static const Color cyanSoft = Color(0xFF6EF0FF);

  // Pastilles d'état
  static const Color ok = Color(0xFF15803D);
  static const Color okBg = Color(0xFFDCFCE7);

  static const Color wait = Color(0xFFB45309);
  static const Color waitBg = Color(0xFFFEF3C7);

  static const Color err = Color(0xFFDC2626);
  static const Color errBg = Color(0xFFFEE2E2);
}
