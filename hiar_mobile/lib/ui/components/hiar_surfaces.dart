import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

/// Arrière-plan atmosphérique Néo-Clinique : dégradé bleu glacier → menthe douce
/// agrémenté d'une discrète trame de points (halftone dots) dans le haut.
class HiarAtmosphericBackground extends StatelessWidget {
  final Widget child;
  final bool showHalftone;

  const HiarAtmosphericBackground({
    super.key,
    required this.child,
    this.showHalftone = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            HiarColors.iceTop,
            HiarColors.mintSoft,
            HiarColors.canvasBottom,
          ],
          stops: [0.0, 0.48, 1.0],
        ),
      ),
      child: showHalftone
          ? CustomPaint(
              painter: _HalftoneDotsPainter(),
              child: child,
            )
          : child,
    );
  }
}

class _HalftoneDotsPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..style = PaintingStyle.fill;
    const double spacing = 14.0;
    final double maxX = size.width;
    final double maxY = math.min(size.height * 0.55, 220.0);

    for (double y = 10; y < maxY; y += spacing) {
      final verticalFade = 1.0 - (y / maxY);
      for (double x = 10; x < maxX; x += spacing) {
        final horizontalWeight = 0.35 + 0.65 * (x / math.max(1.0, maxX));
        final alpha = (0.14 * verticalFade * horizontalWeight).clamp(0.0, 0.16);
        if (alpha < 0.015) continue;
        paint.color = HiarColors.azur.withOpacity(alpha);
        canvas.drawCircle(Offset(x, y), 1.4, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Carte héros sombre à fort contraste : dégradé Ardoise profonde → Sarcelle.
class HiarHeroCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;

  const HiarHeroCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
    this.borderRadius = 20,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [
            HiarColors.slateTealStart,
            HiarColors.slateTealEnd,
          ],
        ),
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: [
          BoxShadow(
            color: HiarColors.slateTealStart.withOpacity(0.22),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }
}

/// Tuile « verre dégradé » façon Pharmacy / My Queue / Schedule.
class HiarGlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final bool highlighted;
  final VoidCallback? onTap;

  const HiarGlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(14),
    this.borderRadius = 20,
    this.highlighted = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final box = AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      padding: padding,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: highlighted
              ? const [Color(0xFFD6E9FF), Colors.white]
              : const [HiarColors.glassMintTop, HiarColors.glassWhiteBottom],
        ),
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(
          color: highlighted ? HiarColors.azur : Colors.white.withOpacity(0.9),
          width: highlighted ? 2.0 : 1.3,
        ),
        boxShadow: [
          BoxShadow(
            color: HiarColors.slateTealStart.withOpacity(highlighted ? 0.14 : 0.08),
            blurRadius: highlighted ? 14 : 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: child,
    );

    if (onTap == null) return box;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(borderRadius),
        onTap: onTap,
        child: box,
      ),
    );
  }
}

/// Bouton circulaire lumineux flottant (blanc, sarcelle foncé ou alerte rouge).
class HiarCircularButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  final double size;
  final double iconSize;
  final bool isPrimary;
  final bool isDestructive;
  final String? tooltip;
  final Widget? childOverride;

  const HiarCircularButton({
    super.key,
    required this.icon,
    this.onTap,
    this.size = 46,
    this.iconSize = 22,
    this.isPrimary = false,
    this.isDestructive = false,
    this.tooltip,
    this.childOverride,
  });

  @override
  Widget build(BuildContext context) {
    final Gradient? grad = isPrimary
        ? const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [HiarColors.slateTealStart, HiarColors.slateTealEnd],
          )
        : (isDestructive
            ? const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFFEF4444), Color(0xFFB91C1C)],
              )
            : null);

    final btn = Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: grad == null ? Colors.white : null,
            gradient: grad,
            border: Border.all(
              color: grad == null
                  ? Colors.white.withOpacity(0.95)
                  : Colors.white.withOpacity(0.25),
              width: 1.2,
            ),
            boxShadow: [
              BoxShadow(
                color: (isDestructive
                        ? HiarColors.err
                        : (isPrimary ? HiarColors.slateTealStart : HiarColors.marine))
                    .withOpacity(grad == null ? 0.10 : 0.28),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Center(
            child: childOverride ??
                Icon(
                  icon,
                  size: iconSize,
                  color: grad == null ? HiarColors.marine : Colors.white,
                ),
          ),
        ),
      ),
    );

    if (tooltip != null) {
      return Tooltip(message: tooltip!, child: btn);
    }
    return btn;
  }
}

/// Pilule de sélection / filtre (actif = blanc surélevé, inactif = contour translucide).
class HiarPillTab extends StatelessWidget {
  final String label;
  final int? countBadge;
  final bool selected;
  final VoidCallback? onTap;

  const HiarPillTab({
    super.key,
    required this.label,
    this.countBadge,
    this.selected = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: selected ? Colors.white : Colors.white.withOpacity(0.32),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: selected ? Colors.white : HiarColors.marine.withOpacity(0.18),
              width: 1.1,
            ),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: HiarColors.slateTealStart.withOpacity(0.10),
                      blurRadius: 10,
                      offset: const Offset(0, 3),
                    ),
                  ]
                : null,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                  color: HiarColors.marine,
                ),
              ),
              if (countBadge != null) ...[
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                  decoration: const BoxDecoration(
                    color: HiarColors.emerald,
                    shape: BoxShape.circle,
                  ),
                  child: Text(
                    '$countBadge',
                    style: const TextStyle(
                      fontSize: 10.5,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Badge pastel vert menthe (façon pastille « Article » de UI_style.jpeg).
class HiarPastelBadge extends StatelessWidget {
  final String label;
  final IconData? icon;
  final Color backgroundColor;
  final Color textColor;

  const HiarPastelBadge({
    super.key,
    required this.label,
    this.icon,
    this.backgroundColor = HiarColors.emeraldPastel,
    this.textColor = HiarColors.azurDark,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3.5),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: textColor),
            const SizedBox(width: 4),
          ],
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w700,
                color: textColor,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Carte Ticket façon « Reçu médical » à bord inférieur festonné
/// sortant d'une fente d'imprimante en haut (style panneau droit de UI_style.jpeg).
class HiarReceiptCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;

  const HiarReceiptCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.fromLTRB(20, 18, 20, 26),
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Fente d'imprimante en haut
        Container(
          height: 10,
          margin: const EdgeInsets.symmetric(horizontal: 6),
          decoration: BoxDecoration(
            color: const Color(0xFF9AC5DC),
            borderRadius: BorderRadius.circular(999),
            boxShadow: [
              BoxShadow(
                color: HiarColors.marine.withOpacity(0.16),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
        ),
        // Papier du reçu qui sort sous la fente avec bord inférieur dentelé
        Transform.translate(
          offset: const Offset(0, -4),
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              boxShadow: [
                BoxShadow(
                  color: HiarColors.slateTealStart.withOpacity(0.14),
                  blurRadius: 18,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: ClipPath(
              clipper: _ScallopedBottomClipper(),
              child: Container(
                width: double.infinity,
                decoration: const BoxDecoration(
                  color: Colors.white,
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Color(0xFFEAF3F9),
                      Colors.white,
                      Colors.white,
                    ],
                    stops: [0.0, 0.06, 1.0],
                  ),
                ),
                padding: padding,
                child: child,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _ScallopedBottomClipper extends CustomClipper<Path> {
  @override
  Path getClip(Size size) {
    const double waveHeight = 8.0;
    const int waveCount = 14;
    final double waveWidth = size.width / waveCount;

    final path = Path()
      ..moveTo(0, 0)
      ..lineTo(size.width, 0)
      ..lineTo(size.width, size.height - waveHeight);

    for (int i = waveCount; i > 0; i--) {
      final double endX = (i - 1) * waveWidth;
      final double midX = endX + waveWidth / 2;
      path.quadraticBezierTo(
        midX,
        i.isEven ? size.height : size.height - waveHeight * 1.45,
        endX,
        size.height - waveHeight * 0.5,
      );
    }

    path.close();
    return path;
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> oldClipper) => false;
}
