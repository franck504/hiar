enum ActionRisk { r0, r1, r2, r3 }

class HiarAction {
  final String id;
  final List<String> scope;
  final ActionRisk risk;
  final String priority;
  final bool requiresConfirmation;
  final dynamic voiceFr;
  final Map<String, dynamic>? argsSchema;

  const HiarAction({
    required this.id,
    required this.scope,
    required this.risk,
    this.priority = 'normal',
    this.requiresConfirmation = false,
    this.voiceFr,
    this.argsSchema,
  });

  factory HiarAction.fromJson(Map<String, dynamic> json) {
    ActionRisk parseRisk(String? r) {
      switch (r) {
        case 'R1':
          return ActionRisk.r1;
        case 'R2':
          return ActionRisk.r2;
        case 'R3':
          return ActionRisk.r3;
        default:
          return ActionRisk.r0;
      }
    }

    return HiarAction(
      id: json['id'] as String,
      scope: (json['scope'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? ['*'],
      risk: parseRisk(json['risk'] as String?),
      priority: json['priority'] as String? ?? 'normal',
      requiresConfirmation: json['requires_confirmation'] as bool? ?? false,
      voiceFr: json['voice_fr'],
      argsSchema: json['args_schema'] as Map<String, dynamic>?,
    );
  }

  /// Vérifie si l'action est active dans le scope courant
  bool isAvailableIn(String currentScope) {
    if (scope.contains('*')) return true;
    if (scope.contains(currentScope)) return true;
    for (final s in scope) {
      if (s.endsWith('.*')) {
        final prefix = s.substring(0, s.length - 2);
        if (currentScope.startsWith(prefix)) return true;
      }
    }
    return false;
  }
}
