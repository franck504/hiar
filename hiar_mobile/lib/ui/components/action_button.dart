import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

/// Bouton d'action standard HIAR avec badge de parité vocale
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
    Color backgroundColor;
    Color foregroundColor;
    Border? border;

    if (isDestructive) {
      backgroundColor = HiarColors.err;
      foregroundColor = Colors.white;
    } else if (isPrimary) {
      backgroundColor = HiarColors.azur;
      foregroundColor = Colors.white;
    } else if (isSelected || isHighlightedByVoice) {
      backgroundColor = HiarColors.azurSoft;
      foregroundColor = HiarColors.marine;
      border = Border.all(color: HiarColors.azur, width: 2.5);
    } else {
      backgroundColor = Colors.white;
      foregroundColor = HiarColors.marine;
      border = Border.all(color: HiarColors.border, width: 1.5);
    }

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          constraints: const BoxConstraints(minHeight: 52),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: backgroundColor,
            borderRadius: BorderRadius.circular(16),
            border: border,
            boxShadow: isPrimary || isDestructive
                ? [
                    BoxShadow(
                      color: (isDestructive ? HiarColors.err : HiarColors.azur).withOpacity(0.3),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    )
                  ]
                : [
                    const BoxShadow(
                      color: Colors.black12,
                      blurRadius: 4,
                      offset: Offset(0, 2),
                    )
                  ],
          ),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isCompact = constraints.maxWidth < 280;
              final isPrimaryOrDestructive = isPrimary || isDestructive;

              if (isCompact) {
                // Disposition compacte (cartes en grille 2 colonnes) : pas de compression horizontale
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        if (icon != null)
                          _buildIcon(isPrimaryOrDestructive, size: 30, iconSize: 18)
                        else
                          const SizedBox.shrink(),
                        if (voiceHint != null)
                          Flexible(child: _buildVoiceBadge(isPrimaryOrDestructive)),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: foregroundColor,
                      ),
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        subtitle!,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 11,
                          height: 1.25,
                          color: isPrimaryOrDestructive ? Colors.white70 : HiarColors.text2,
                        ),
                      ),
                    ],
                  ],
                );
              }

              // Disposition large (liste en colonne unique ou écran d'accueil)
              return Row(
                children: [
                  if (icon != null) ...[
                    _buildIcon(isPrimaryOrDestructive, size: 38, iconSize: 22),
                    const SizedBox(width: 10),
                  ],
                  Expanded(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: foregroundColor,
                          ),
                        ),
                        if (subtitle != null) ...[
                          const SizedBox(height: 1),
                          Text(
                            subtitle!,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 12,
                              color: isPrimaryOrDestructive ? Colors.white70 : HiarColors.text2,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (voiceHint != null) ...[
                    const SizedBox(width: 8),
                    _buildVoiceBadge(isPrimaryOrDestructive),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildIcon(bool isPrimaryOrDestructive, {required double size, required double iconSize}) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: isPrimaryOrDestructive
            ? Colors.white.withOpacity(0.2)
            : HiarColors.azurSoft,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(
        icon,
        size: iconSize,
        color: isPrimaryOrDestructive ? Colors.white : HiarColors.azur,
      ),
    );
  }

  Widget _buildVoiceBadge(bool isPrimaryOrDestructive) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: isPrimaryOrDestructive
            ? Colors.white.withOpacity(0.2)
            : HiarColors.brume,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isPrimaryOrDestructive ? Colors.white24 : HiarColors.border,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.mic,
            size: 12,
            color: isPrimaryOrDestructive ? Colors.white70 : HiarColors.azur,
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              "« $voiceHint »",
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: isPrimaryOrDestructive ? Colors.white : HiarColors.marine,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
