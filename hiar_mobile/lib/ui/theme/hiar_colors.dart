import 'package:flutter/material.dart';

/// Jetons de couleur officiels HIAR — Base BLEU médical « Soft Medical Glassmorphism »
class HiarColors {
  HiarColors._();

  // Palette principale BLEUE
  static const Color marine = Color(0xFF0B2545);
  static const Color azur = Color(0xFF1A73E8); // Bleu médical principal
  static const Color azurDark = Color(0xFF1254B3);
  static const Color azurSoft = Color(0xFFDCEBFF);
  static const Color brume = Color(0xFFF2F7FF);
  static const Color card = Color(0xFFFFFFFF);
  static const Color text1 = Color(0xFF0B2545);
  static const Color text2 = Color(0xFF51657D);
  static const Color border = Color(0xFFD2E2F5);

  // Dégradés atmosphériques & verre bleu glacier
  static const Color iceTop = Color(0xFFCFE6FF);
  static const Color mintSoft = Color(0xFFE3F0FF);
  static const Color canvasBottom = Color(0xFFF6FAFF);

  // Carte héros sombre Bleu marine → Bleu azur
  static const Color slateTealStart = Color(0xFF0D2B52);
  static const Color slateTealEnd = Color(0xFF1A6FD8);

  // Tuiles verre dégradé (haut bleu glacier translucide → bas blanc pur)
  static const Color glassMintTop = Color(0xC4CFE6FF);
  static const Color glassWhiteBottom = Color(0xFAFFFFFF);

  // Accents bleus & badges pastel
  static const Color emerald = Color(0xFF1A73E8);
  static const Color emeraldPastel = Color(0xFFDCEBFF);

  // Éléments vocaux, visage robot & croix jaune médicale
  static const Color cyan = Color(0xFF28B8F6);
  static const Color cyanSoft = Color(0xFF7AE5FF);
  static const Color robotCrossYellow = Color(0xFFFFD43B);

  // Pastilles d'état sémantiques
  static const Color ok = Color(0xFF15803D);
  static const Color okBg = Color(0xFFDCFCE7);

  static const Color wait = Color(0xFFB45309);
  static const Color waitBg = Color(0xFFFEF3C7);

  static const Color err = Color(0xFFDC2626);
  static const Color errBg = Color(0xFFFEE2E2);
}
