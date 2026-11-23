import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';
import '../theme/hiar_tokens.dart';
import '../theme/hiar_typography.dart';

/// Puce « commande vocale » unique de l'application : 🎤 « Suivant ».
///
/// Remplace les trois conventions qui coexistaient (emoji dans le libellé, puce à droite,
/// texte nu à côté d'une icône).
class HiarVoiceChip extends StatelessWidget {
  final String hint;
  final bool onDark;

  const HiarVoiceChip(this.hint, {super.key, this.onDark = false});

  @override
  Widget build(BuildContext context) {
    final fg = onDark ? Colors.white : HiarColors.azurDark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: onDark ? Colors.white.withOpacity(0.18) : HiarColors.emeraldPastel,
        borderRadius: HiarRadius.pillAll,
        border: onDark ? null : Border.all(color: HiarColors.emerald.withOpacity(0.18)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.mic_rounded, size: 13, color: onDark ? Colors.white : HiarColors.emerald),
          const SizedBox(width: 3),
          Flexible(
            child: Text(
              '« $hint »',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: HiarTypography.chip.copyWith(color: fg),
            ),
          ),
        ],
      ),
    );
  }
}

/// Boîte d'icône carrée arrondie (tuiles, cartes, en-têtes).
class HiarIconBox extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double size;
  final bool onDark;

  const HiarIconBox(
    this.icon, {
    super.key,
    this.color = HiarColors.azur,
    this.size = HiarSize.iconBox,
    this.onDark = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: onDark ? Colors.white.withOpacity(0.16) : Colors.white,
        borderRadius: HiarRadius.smAll,
        border: Border.all(color: onDark ? Colors.white.withOpacity(0.24) : color.withOpacity(0.14)),
        boxShadow: onDark
            ? null
            : [BoxShadow(color: color.withOpacity(0.12), blurRadius: 8, offset: const Offset(0, 3))],
      ),
      child: Icon(icon, size: size * 0.52, color: onDark ? Colors.white : color),
    );
  }
}

enum HiarButtonVariant { primary, secondary, danger, success }

/// Bouton unique de l'application : même hauteur, même forme pilule, même place pour la commande vocale.
class HiarButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final String? voiceHint;
  final VoidCallback? onPressed;
  final HiarButtonVariant variant;
  final bool expand;
  final bool compact;
  final bool loading;

  const HiarButton({
    super.key,
    required this.label,
    this.icon,
    this.voiceHint,
    this.onPressed,
    this.variant = HiarButtonVariant.primary,
    this.expand = false,
    this.compact = false,
    this.loading = false,
  });

  const HiarButton.primary({
    super.key,
    required this.label,
    this.icon,
    this.voiceHint,
    this.onPressed,
    this.expand = false,
    this.compact = false,
    this.loading = false,
  }) : variant = HiarButtonVariant.primary;

  const HiarButton.secondary({
    super.key,
    required this.label,
    this.icon,
    this.voiceHint,
    this.onPressed,
    this.expand = false,
    this.compact = false,
    this.loading = false,
  }) : variant = HiarButtonVariant.secondary;

  const HiarButton.danger({
    super.key,
    required this.label,
    this.icon,
    this.voiceHint,
    this.onPressed,
    this.expand = false,
    this.compact = false,
    this.loading = false,
  }) : variant = HiarButtonVariant.danger;

  const HiarButton.success({
    super.key,
    required this.label,
    this.icon,
    this.voiceHint,
    this.onPressed,
    this.expand = false,
    this.compact = false,
    this.loading = false,
  }) : variant = HiarButtonVariant.success;

  @override
  Widget build(BuildContext context) {
    final Color bg;
    final Color fg;
    final bool filled = variant != HiarButtonVariant.secondary;
    switch (variant) {
      case HiarButtonVariant.primary:
        bg = HiarColors.secondary;
        fg = Colors.white;
        break;
      case HiarButtonVariant.danger:
        bg = HiarColors.err;
        fg = Colors.white;
        break;
      case HiarButtonVariant.success:
        bg = HiarColors.success;
        fg = Colors.white;
        break;
      case HiarButtonVariant.secondary:
        bg = Colors.white;
        fg = HiarColors.marine;
        break;
    }
    final disabled = onPressed == null || loading;
    final height = compact ? HiarSize.touchCompact : HiarSize.touch;

    Widget row(bool withChip) => Row(
            mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (icon != null) ...[
                Icon(icon, size: compact ? 18 : 21, color: fg),
                const SizedBox(width: HiarSpace.sm),
              ],
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: HiarTypography.button.copyWith(
                    color: fg,
                    fontSize: compact ? 13 : 15,
                    fontWeight: compact ? FontWeight.w800 : FontWeight.w700,
                    letterSpacing: compact ? 0.5 : 0.1,
                  ),
                ),
              ),
              if (withChip) ...[
                const SizedBox(width: HiarSpace.sm),
                HiarVoiceChip(voiceHint!, onDark: filled),
              ],
            ],
          );

    final content = loading
        ? SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: fg, strokeWidth: 2.2))
        : (voiceHint == null || compact)
            ? row(false)
            // Écran étroit : on retire la puce plutôt que de tronquer le libellé
            : LayoutBuilder(
                builder: (context, c) => row(!c.hasBoundedWidth || c.maxWidth >= 230),
              );

    return Opacity(
      opacity: disabled && !loading ? 0.55 : 1,
      child: Material(
        color: bg,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: HiarRadius.pillAll,
          side: filled ? BorderSide.none : const BorderSide(color: HiarColors.border, width: 1.4),
        ),
        clipBehavior: Clip.antiAlias,
        shadowColor: Colors.transparent,
        child: InkWell(
          onTap: disabled ? null : onPressed,
          child: Container(
            height: height,
            width: expand ? double.infinity : null,
            padding: EdgeInsets.symmetric(horizontal: compact ? HiarSpace.lg : HiarSpace.xl),
            decoration: BoxDecoration(
              boxShadow: filled && !disabled
                  ? [BoxShadow(color: bg.withOpacity(0.22), blurRadius: 14, offset: const Offset(0, 5))]
                  : null,
            ),
            // Pas d'`alignment` : il étirerait le bouton sur toute la largeur disponible (ex. dans un Center)
            child: expand ? Center(child: content) : content,
          ),
        ),
      ),
    );
  }
}

/// Corps de scène commun : contenu centré, largeur maximale identique, défilement si nécessaire.
class HiarSceneBody extends StatelessWidget {
  final Widget child;
  final double maxWidth;

  const HiarSceneBody({super.key, required this.child, this.maxWidth = HiarSize.contentMax});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: Center(
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth),
              child: child,
            ),
          ),
        ),
      ),
    );
  }
}

/// Ligne d'introduction d'une scène : badge + phrase d'aide.
class HiarSceneIntro extends StatelessWidget {
  final String badge;
  final IconData icon;
  final String text;

  const HiarSceneIntro({super.key, required this.badge, required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: HiarSpace.md),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(color: HiarColors.emeraldPastel, borderRadius: HiarRadius.pillAll),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 14, color: HiarColors.azurDark),
                const SizedBox(width: 5),
                Text(badge, style: HiarTypography.chip),
              ],
            ),
          ),
          const SizedBox(width: HiarSpace.md),
          Expanded(
            child: Text(text, maxLines: 1, overflow: TextOverflow.ellipsis, style: HiarTypography.subtitle),
          ),
        ],
      ),
    );
  }
}
