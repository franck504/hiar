/// Respelling phonétique pour la synthèse vocale (TTS).
///
/// Le moteur TTS Android est réglé en `fr-FR` et il n'existe pas de voix malgache.
/// Il lit donc les noms malgaches avec les règles du français : « h » muet, « s » entre
/// deux voyelles prononcé « z », mot en MAJUSCULES parfois épelé lettre par lettre…
///
/// Cette table réécrit ces mots **uniquement pour la parole**. Le texte affiché, les logs
/// et la détection d'écho (anti-larsen) continuent d'utiliser le texte d'origine.
///
/// Pour ajuster une prononciation : modifier la 2e colonne ci-dessous (rechargement à chaud
/// suffisant) et réécouter. Toute règle doit produire un texte qu'elle ne re-capture pas
/// elle-même (voir le test d'idempotence).
class TtsPronunciation {
  TtsPronunciation._();

  static final List<_Rule> _rules = [
    // Razakaharisoa  ->  /ra-za-ka-ha-ri-soa/ (soa ≈ « soua », s sourd : « ss »).
    // Variantes : tout en majuscules, casse mixte, ou nom coupé « Razaka Harisoa ».
    //   Alternatives à essayer si le rendu n'est pas assez net :
    //     'Ra za ka ha ri soua'   (syllabes détachées, un peu hachées)
    //     'Razakarissoua'         (sans le « h » aspiré, plus fluide)
    _Rule(RegExp(r'razaka[\s\-]*harisoa', caseSensitive: false), 'Razakaharissoua'),

    // Prénom : l'accent aide le moteur français à lire « sé-si-lia » et non « ke-ki-lia ».
    _Rule(RegExp(r'\bcecilia\b', caseSensitive: false), 'Cécilia'),
  ];

  /// Retourne le texte à envoyer au moteur TTS (identique si aucun mot à corriger).
  static String apply(String text) {
    var spoken = text;
    for (final rule in _rules) {
      spoken = spoken.replaceAll(rule.pattern, rule.replacement);
    }
    return spoken;
  }
}

class _Rule {
  final RegExp pattern;
  final String replacement;
  const _Rule(this.pattern, this.replacement);
}
