import 'package:flutter/material.dart';

/// Système de design HIAR — échelles uniques d'espacement, de rayons et de tailles.
///
/// Règle : aucun écran ne doit inventer sa propre valeur. Si une valeur manque, on l'ajoute ici.
class HiarSpace {
  HiarSpace._();
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
}

class HiarRadius {
  HiarRadius._();
  static const double sm = 12; // boîtes d'icône, champs secondaires
  static const double md = 16; // cartes d'information, champs de saisie
  static const double lg = 20; // tuiles de choix, cartes principales
  static const double pill = 999; // boutons, puces, onglets

  static BorderRadius get smAll => BorderRadius.circular(sm);
  static BorderRadius get mdAll => BorderRadius.circular(md);
  static BorderRadius get lgAll => BorderRadius.circular(lg);
  static BorderRadius get pillAll => BorderRadius.circular(pill);
}

class HiarSize {
  HiarSize._();
  /// Cible tactile minimale d'un kiosque (doigt, personne âgée, gants) : 56 dp.
  static const double touch = 56;
  static const double touchCompact = 44;
  static const double iconBox = 44;
  static const double tileMinHeight = 76;
  /// Largeur maximale du contenu de la scène (1440 x 720 moins le rail vocal de 248 dp).
  static const double contentMax = 880;
  static const double contentNarrow = 640;
}
