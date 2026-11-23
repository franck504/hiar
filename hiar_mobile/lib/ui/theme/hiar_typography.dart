import 'package:flutter/material.dart';
import 'hiar_colors.dart';

/// Échelle typographique HIAR — 7 niveaux, utilisés par TOUS les écrans.
///
/// (Avant : 19 tailles différentes, de 10 à 34 px, choisies écran par écran.)
class HiarTypography {
  HiarTypography._();

  /// 34 — « Bonjour ! », numéro de ticket.
  static const TextStyle display = TextStyle(
    fontSize: 34, fontWeight: FontWeight.w800, color: HiarColors.marine, letterSpacing: -0.6, height: 1.15,
  );

  /// 22 — titre d'écran, titre de carte héros.
  static const TextStyle title = TextStyle(
    fontSize: 22, fontWeight: FontWeight.w800, color: HiarColors.marine, letterSpacing: -0.4, height: 1.2,
  );

  /// 17 — titre de tuile / de carte.
  static const TextStyle heading = TextStyle(
    fontSize: 17, fontWeight: FontWeight.w700, color: HiarColors.marine, letterSpacing: -0.2, height: 1.25,
  );

  /// 15 — texte courant, libellé de bouton, saisie.
  static const TextStyle body = TextStyle(
    fontSize: 15, fontWeight: FontWeight.w500, color: HiarColors.marine, height: 1.4,
  );

  /// 13 — sous-titre, description.
  static const TextStyle subtitle = TextStyle(
    fontSize: 13, fontWeight: FontWeight.w400, color: HiarColors.text2, height: 1.35,
  );

  /// 12 — légende, état, consigne vocale.
  static const TextStyle caption = TextStyle(
    fontSize: 12, fontWeight: FontWeight.w600, color: HiarColors.text2, height: 1.3,
  );

  /// 11.5 — puces et badges.
  static const TextStyle chip = TextStyle(
    fontSize: 11.5, fontWeight: FontWeight.w700, color: HiarColors.azurDark, letterSpacing: 0.1,
  );

  // Alias historiques (compatibilité)
  static const TextStyle screenTitle = title;
  static const TextStyle cardTitle = heading;
  static const TextStyle bodySecondary = subtitle;
  static const TextStyle button = TextStyle(fontSize: 15, fontWeight: FontWeight.w700, letterSpacing: 0.1);
  static const TextStyle voiceTip = caption;
  static const TextStyle voiceStatus = TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: HiarColors.marine);
}
