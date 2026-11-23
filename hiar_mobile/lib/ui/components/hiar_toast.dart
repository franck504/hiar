import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

/// Notification éphémère HIAR.
///
/// Remplace le SnackBar Material par défaut (pleine largeur, collé en bas) qui masquait
/// les boutons d'action de la scène (Suivant, Valider, Reprendre, Terminer…).
/// Ici la notification est :
///  - étroite (≈ largeur du rail vocal) et ancrée en bas à gauche, au-dessus du rail
///    (zone sans bouton d'action : les commandes de la scène sont à droite) ;
///  - unique : une nouvelle notification remplace la précédente (pas de file d'attente) ;
///  - dédoublonnée : le même message répété en moins de 1,5 s est ignoré
///    (appuis répétés sur STOP) ;
///  - courte (2,5 s par défaut) et jamais bloquante.
class HiarToast {
  HiarToast._();

  /// Largeur de la notification (rail vocal = 248 dp, moins les marges).
  static const double width = 224;
  static const double _edge = 12;
  static const Duration _dedupe = Duration(milliseconds: 1500);

  static String? _lastMessage;
  static DateTime? _lastShownAt;

  /// Réinitialise l'anti-doublon (tests).
  static void resetForTests() {
    _lastMessage = null;
    _lastShownAt = null;
  }

  /// Marge d'un SnackBar flottant ancré en bas à gauche pour un écran de [screenWidth] dp.
  static EdgeInsets marginFor(double screenWidth) {
    final right = (screenWidth - _edge - width).clamp(_edge, double.infinity).toDouble();
    return EdgeInsets.fromLTRB(_edge, 0, right, _edge);
  }

  static void show({
    required ScaffoldMessengerState? messenger,
    required double screenWidth,
    required String message,
    Color background = HiarColors.marine,
    Duration duration = const Duration(milliseconds: 2500),
  }) {
    if (messenger == null) return;

    final now = DateTime.now();
    if (_lastMessage == message &&
        _lastShownAt != null &&
        now.difference(_lastShownAt!) < _dedupe) {
      return;
    }
    _lastMessage = message;
    _lastShownAt = now;

    // removeCurrentSnackBar (sans animation) : la nouvelle notification remplace aussitôt
    // l'ancienne, rien ne reste en file d'attente.
    messenger
      ..removeCurrentSnackBar()
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          behavior: SnackBarBehavior.floating,
          margin: marginFor(screenWidth),
          backgroundColor: background,
          duration: duration,
          dismissDirection: DismissDirection.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          content: Text(
            message,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
        ),
      );
  }
}
