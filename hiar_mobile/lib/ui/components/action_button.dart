import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';
import '../theme/hiar_tokens.dart';
import '../theme/hiar_typography.dart';
import 'hiar_kit.dart';

/// Bouton d'action standard HIAR — Tuile verre dégradé façon UI_style.jpeg
/// avec badge de parité vocale en pilule pastel.
class ActionButton extends StatelessWidget {
  final String label;
  final String? subtitle;
  final IconData? icon;
  final String? voiceHint;
  final VoidCallback? onTap;
  final bool isPrimary;
  final bool isDestructive;
  final bool isSelected;
  final bool isHighlightedByVoice;

  const ActionButton({
    super.key,
    required this.label,
    this.subtitle,
    this.icon,
    this.voiceHint,
    this.onTap,
    this.isPrimary = false,
    this.isDestructive = false,
    this.isSelected = false,
    this.isHighlightedByVoice = false,
  });

  @override
  Widget build(BuildContext context) {
    final bool isPrimaryOrDestructive = isPrimary || isDestructive;
    final bool isActive = isSelected || isHighlightedByVoice;

    Gradient gradient;
    Color foregroundColor;
    Border border;
    List<BoxShadow> shadows;

    if (isDestructive) {
      gradient = const LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [Color(0xFFDC2626), Color(0xFFB91C1C)],
      );
      foregroundColor = Colors.white;
      border = Border.all(color: Colors.white.withOpacity(0.25), width: 1.2);
      shadows = [
        BoxShadow(
          color: HiarColors.err.withOpacity(0.26),
          blurRadius: 14,
          offset: const Offset(0, 5),
        ),
      ];
    } else if (isPrimary) {
      gradient = HiarGradients.heroDark;
      foregroundColor = Colors.white;
      border = Border.all(color: Colors.white.withOpacity(0.24), width: 1.2);
      shadows = HiarShadows.floating;
    } else if (isActive) {
      gradient = HiarGradients.medicalCard;
      foregroundColor = HiarColors.textPrimary;
      border = Border.all(color: HiarColors.secondary, width: 1.8);
      shadows = HiarShadows.floating;
    } else {
      gradient = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [HiarColors.surfaceSoft, HiarColors.surface],
      );
      foregroundColor = HiarColors.textPrimary;
      border = Border.all(color: Colors.white.withOpacity(0.75), width: 1.3);
      shadows = HiarShadows.card;
    }

    final onDark = isPrimaryOrDestructive;
    final titleStyle = HiarTypography.heading.copyWith(color: foregroundColor);
    final subtitleStyle = HiarTypography.subtitle.copyWith(
      color: onDark ? Colors.white70 : HiarColors.text2,
    );

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: HiarRadius.lgAll,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          constraints: const BoxConstraints(minHeight: HiarSize.tileMinHeight),
          padding: const EdgeInsets.symmetric(horizontal: HiarSpace.lg, vertical: HiarSpace.md),
          decoration: BoxDecoration(
            gradient: gradient,
            borderRadius: HiarRadius.lgAll,
            border: border,
            boxShadow: shadows,
          ),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isCompact = constraints.maxWidth < 280;
              final texts = Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: titleStyle),
                  if (subtitle != null) ...[
                    const SizedBox(height: 3),
                    Text(subtitle!, maxLines: 2, overflow: TextOverflow.ellipsis, style: subtitleStyle),
                  ],
                ],
              );

              if (isCompact) {
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        if (icon != null) HiarIconBox(icon!, size: 36, onDark: onDark) else const SizedBox.shrink(),
                        if (voiceHint != null) Flexible(child: HiarVoiceChip(voiceHint!, onDark: onDark)),
                      ],
                    ),
                    const SizedBox(height: HiarSpace.sm),
                    texts,
                  ],
                );
              }

              // Disposition unique : icône à gauche · textes · commande vocale à droite
              return Row(
                children: [
                  if (icon != null) ...[
                    HiarIconBox(icon!, onDark: onDark),
                    const SizedBox(width: HiarSpace.md),
                  ],
                  Expanded(child: texts),
                  if (isSelected && !onDark) ...[
                    const SizedBox(width: HiarSpace.sm),
                    const Icon(Icons.check_circle_rounded, color: HiarColors.secondary, size: 22),
                  ],
                  if (voiceHint != null) ...[
                    const SizedBox(width: HiarSpace.sm),
                    HiarVoiceChip(voiceHint!, onDark: onDark),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
