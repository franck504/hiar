import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

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
      gradient = const LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [HiarColors.slateTealStart, HiarColors.slateTealEnd],
      );
      foregroundColor = Colors.white;
      border = Border.all(color: Colors.white.withOpacity(0.22), width: 1.2);
      shadows = [
        BoxShadow(
          color: HiarColors.slateTealStart.withOpacity(0.24),
          blurRadius: 14,
          offset: const Offset(0, 5),
        ),
      ];
    } else if (isActive) {
      gradient = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0xFFD2E7FF), Colors.white],
      );
      foregroundColor = HiarColors.marine;
      border = Border.all(color: HiarColors.azur, width: 2.0);
      shadows = [
        BoxShadow(
          color: HiarColors.azur.withOpacity(0.18),
          blurRadius: 14,
          offset: const Offset(0, 4),
        ),
      ];
    } else {
      gradient = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [HiarColors.glassMintTop, HiarColors.glassWhiteBottom],
      );
      foregroundColor = HiarColors.marine;
      border = Border.all(color: Colors.white.withOpacity(0.92), width: 1.4);
      shadows = [
        BoxShadow(
          color: HiarColors.slateTealStart.withOpacity(0.08),
          blurRadius: 12,
          offset: const Offset(0, 4),
        ),
      ];
    }

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          constraints: const BoxConstraints(minHeight: 54),
          padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 10),
          decoration: BoxDecoration(
            gradient: gradient,
            borderRadius: BorderRadius.circular(20),
            border: border,
            boxShadow: shadows,
          ),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isCompact = constraints.maxWidth < 280;

              if (isCompact) {
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        if (icon != null)
                          _buildIcon(isPrimaryOrDestructive, size: 32, iconSize: 18)
                        else
                          const SizedBox.shrink(),
                        if (voiceHint != null)
                          Flexible(child: _buildVoiceBadge(isPrimaryOrDestructive)),
                      ],
                    ),
                    const SizedBox(height: 7),
                    Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: foregroundColor,
                        letterSpacing: -0.2,
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

              return Row(
                children: [
                  if (icon != null) ...[
                    _buildIcon(isPrimaryOrDestructive, size: 42, iconSize: 22),
                    const SizedBox(width: 12),
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
                            letterSpacing: -0.2,
                          ),
                        ),
                        if (subtitle != null) ...[
                          const SizedBox(height: 2),
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
                    const SizedBox(width: 10),
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
            ? Colors.white.withOpacity(0.18)
            : Colors.white.withOpacity(0.88),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isPrimaryOrDestructive
              ? Colors.white.withOpacity(0.24)
              : HiarColors.azur.withOpacity(0.14),
        ),
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
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: isPrimaryOrDestructive
            ? Colors.white.withOpacity(0.18)
            : HiarColors.emeraldPastel,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.mic,
            size: 12,
            color: isPrimaryOrDestructive ? Colors.white : HiarColors.emerald,
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              "« $voiceHint »",
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: isPrimaryOrDestructive ? Colors.white : HiarColors.azurDark,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
