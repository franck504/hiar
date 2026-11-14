import 'dart:convert';
import 'package:flutter/services.dart';
import 'action_model.dart';

class ActionRegistry {
  final Map<String, HiarAction> _actions = {};
  bool _loaded = false;

  bool get isLoaded => _loaded;
  List<HiarAction> get allActions => _actions.values.toList();

  Future<void> load() async {
    if (_loaded) return;
    final jsonString = await rootBundle.loadString('assets/registry/actions.v1.json');
    final data = json.decode(jsonString) as Map<String, dynamic>;
    final actionsList = data['actions'] as List<dynamic>;

    for (final item in actionsList) {
      final action = HiarAction.fromJson(item as Map<String, dynamic>);
      _actions[action.id] = action;
    }
    _loaded = true;
  }

  HiarAction? getAction(String id) => _actions[id];

  List<HiarAction> getAvailableActions(String currentScope) {
    return _actions.values.where((a) => a.isAvailableIn(currentScope)).toList();
  }

  /// Recherche simple d'une action à partir d'une phrase reconnue
  HiarActionMatch? matchPhrase(String rawPhrase, String currentScope) {
    final cleaned = rawPhrase.trim().toLowerCase();
    if (cleaned.isEmpty) return null;

    final available = getAvailableActions(currentScope);

    // Priorité aux actions de risque R3 (comme robot.stop)
    available.sort((a, b) {
      if (a.risk == ActionRisk.r3 && b.risk != ActionRisk.r3) return -1;
      if (b.risk == ActionRisk.r3 && a.risk != ActionRisk.r3) return 1;
      return 0;
    });

    for (final action in available) {
      final voice = action.voiceFr;
      if (voice is List) {
        for (final phrase in voice) {
          final target = phrase.toString().toLowerCase();
          if (cleaned == target || cleaned.contains(target)) {
            return HiarActionMatch(action: action, rawPhrase: rawPhrase);
          }
        }
      } else if (voice is Map<String, dynamic>) {
        // Ex: {'PHARMACY': ['pharmacie', ...]}
        for (final entry in voice.entries) {
          final argValue = entry.key;
          final phrases = entry.value as List<dynamic>;
          for (final phrase in phrases) {
            final target = phrase.toString().toLowerCase();
            if (cleaned == target || cleaned.contains(target)) {
              return HiarActionMatch(
                action: action,
                rawPhrase: rawPhrase,
                args: {'destination': argValue, 'topic': argValue, 'reason': argValue, 'category': argValue},
              );
            }
          }
        }
      }
    }
    return null;
  }
}

class HiarActionMatch {
  final HiarAction action;
  final String rawPhrase;
  final Map<String, dynamic> args;

  HiarActionMatch({
    required this.action,
    required this.rawPhrase,
    this.args = const {},
  });
}
