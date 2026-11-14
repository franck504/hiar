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
          child: Row(
            children: [
              if (icon != null) ...[
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: isPrimary || isDestructive
                        ? Colors.white.withOpacity(0.2)
                        : HiarColors.azurSoft,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    icon,
                    size: 22,
                    color: isPrimary || isDestructive ? Colors.white : HiarColors.azur,
                  ),
                ),
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
                          color: isPrimary || isDestructive ? Colors.white70 : HiarColors.text2,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (voiceHint != null) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: isPrimary || isDestructive
                        ? Colors.white.withOpacity(0.2)
                        : HiarColors.brume,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isPrimary || isDestructive ? Colors.white24 : HiarColors.border,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.mic,
                        size: 13,
                        color: isPrimary || isDestructive ? Colors.white70 : HiarColors.azur,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        "« $voiceHint »",
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: isPrimary || isDestructive ? Colors.white : HiarColors.marine,
                        ),
                      ),
                    ],
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
