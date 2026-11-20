import 'package:flutter/material.dart';

/// Charte graphique officielle HIAR — Palette Médicale Pastel / Cyan / Teal
/// Répartition : 60 % fonds clairs (#D9ECFB / #F4F8FB) · 30 % surfaces blanches (#FFFFFF) · 10 % accents (#2C7777 / #82DFF7 / #2B8F83)
class HiarColors {
  HiarColors._();

  // 1. Palette principale
  static const Color primary = Color(0xFF82DFF7);       // Cyan lumineux
  static const Color primaryLight = Color(0xFFD9ECFB);  // Bleu ciel clair
  static const Color primarySoft = Color(0xFFC4E7FA);   // Bleu pastel
  static const Color secondary = Color(0xFF0B4F7C);     // Bleu médical HIAR officiel (tête robot)
  static const Color secondaryLight = Color(0xFF7BBCE3);// Bleu doux
  static const Color secondaryDark = Color(0xFF083B5E); // Deep Blue
  static const Color accent = Color(0xFF9ADFF7);        // Cyan pastel
  static const Color success = Color(0xFF2B8F83);       // Vert médical
  static const Color mint = Color(0xFFECFFF9);          // Vert menthe
  static const Color mintMid = Color(0xFFC8F1E7);       // Vert menthe médian (gradient C)

  // 2. Couleurs secondaires & surfaces
  static const Color surface = Color(0xFFFFFFFF);       // Blanc pur
  static const Color offWhite = Color(0xFFFCFDFE);      // Blanc cassé très lumineux
  static const Color background = Color(0xFFFAFDFE);    // Fond ultra-clair blanc glacé
  static const Color surfaceSoft = Color(0xFFE7F2F9);   // Bleu très pâle
  static const Color cyanPale = Color(0xFFD0F0FB);      // Cyan pâle (badges / barres)
  static const Color turquoisePale = Color(0xFFB3E3F1); // Turquoise pâle (gradient B)
  static const Color turquoiseLight = Color(0xFF9DCFCF);// Vert turquoise clair (gradient B)

  // 3. Textes & éléments fonctionnels
  static const Color textPrimary = Color(0xFF19313A);   // Dark Navy
  static const Color textSecondary = Color(0xFF32545D); // Bleu gris foncé
  static const Color slateBlue = Color(0xFF526B7D);     // Labels
  static const Color textMuted = Color(0xFF8AA6A7);     // Gris turquoise
  static const Color border = Color(0xFFD0E5EF);        // Bordures légères
  static const Color divider = Color(0xFFE6EEF2);       // Séparateurs
  static const Color shadow = Color(0xFF0B4F7C);        // Ombres bleues HIAR

  // Alias historiques HIAR (compatibilité complète dans toute l'app)
  static const Color marine = textPrimary;
  static const Color azur = secondary;
  static const Color azurDark = secondaryDark;
  static const Color azurSoft = surfaceSoft;
  static const Color brume = background;
  static const Color card = surface;
  static const Color text1 = textPrimary;
  static const Color text2 = textSecondary;

  static const Color iceTop = primaryLight;
  static const Color mintSoft = primarySoft;
  static const Color canvasBottom = background;

  static const Color slateTealStart = textPrimary;
  static const Color slateTealEnd = secondary;

  static const Color glassMintTop = Color(0xCCE7F2F9);
  static const Color glassWhiteBottom = Color(0xFAFFFFFF);

  static const Color emerald = success;
  static const Color emeraldPastel = mint;

  // Éléments vocaux, visage robot & croix jaune médicale
  static const Color cyan = primary;
  static const Color cyanSoft = accent;
  static const Color robotCrossYellow = Color(0xFFFFD43B);

  // Pastilles d'état sémantiques
  static const Color ok = success;
  static const Color okBg = mint;

  static const Color wait = Color(0xFFB45309);
  static const Color waitBg = Color(0xFFFEF3C7);

  static const Color err = Color(0xFFDC2626);
  static const Color errBg = Color(0xFFFEE2E2);

  /// ColorScheme Material 3 aligné sur la charte officielle
  static ColorScheme get colorScheme => ColorScheme.fromSeed(
        seedColor: secondary,
        primary: secondary,
        onPrimary: Colors.white,
        secondary: primary,
        onSecondary: textPrimary,
        surface: surface,
        onSurface: textPrimary,
        error: err,
        onError: Colors.white,
      );
}

/// Dégradés officiels de la charte HIAR
class HiarGradients {
  HiarGradients._();

  /// A. Background principal lumineux (très blanc avec touche bleu pastel douce)
  static const LinearGradient mainBackground = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFFFFFFFF),
      Color(0xFFF8FBFE),
      Color(0xFFECF5FC),
    ],
    stops: [0.0, 0.58, 1.0],
  );

  /// A (plein éclat, pour splash / en-têtes) : #D9ECFB → #C4E7FA → #82DFF7
  static const LinearGradient mainVibrant = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      HiarColors.primaryLight,
      HiarColors.primarySoft,
      HiarColors.primary,
    ],
    stops: [0.0, 0.45, 1.0],
  );

  /// B. Dégradé turquoise / vert : #B3E3F1 → #A7D6DA → #9DCFCF
  static const LinearGradient tealSoft = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      HiarColors.turquoisePale,
      HiarColors.secondaryLight,
      HiarColors.turquoiseLight,
    ],
    stops: [0.0, 0.5, 1.0],
  );

  /// C. Dégradé de cartes médicales : Mint → Cyan (#ECFFF9 → #C8F1E7 → #82DFF7)
  static const LinearGradient medicalCard = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      HiarColors.mint,
      HiarColors.mintMid,
      HiarColors.cyanPale,
    ],
    stops: [0.0, 0.55, 1.0],
  );

  /// D. Carte héros contrastée : Dark Navy → Deep Teal → Teal médical
  static const LinearGradient heroDark = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      HiarColors.textPrimary,
      HiarColors.secondaryDark,
      HiarColors.secondary,
    ],
    stops: [0.0, 0.45, 1.0],
  );
}

/// Ombres douces officielles : rgba(11, 79, 124, 0.10 / 0.14)
class HiarShadows {
  HiarShadows._();

  static final List<BoxShadow> card = [
    BoxShadow(
      color: const Color(0xFF0B4F7C).withOpacity(0.10),
      blurRadius: 24,
      offset: const Offset(0, 8),
    ),
  ];

  static final List<BoxShadow> floating = [
    BoxShadow(
      color: const Color(0xFF0B4F7C).withOpacity(0.14),
      blurRadius: 30,
      offset: const Offset(0, 12),
    ),
  ];

  static final List<BoxShadow> softButton = [
    BoxShadow(
      color: const Color(0xFF0B4F7C).withOpacity(0.10),
      blurRadius: 12,
      offset: const Offset(0, 4),
    ),
  ];
}
