import 'dart:async';
import 'package:flutter/material.dart';

/// Composant de texte défilant horizontalement automatique (effet Marquee).
/// Maintient le texte sur une seule ligne et défile automatiquement si le texte dépasse la largeur disponible.
class AutoScrollText extends StatefulWidget {
  final String text;
  final TextStyle? style;
  final double velocity; // Vitesse en pixels par seconde
  final Duration pauseDuration;

  const AutoScrollText({
    super.key,
    required this.text,
    this.style,
    this.velocity = 35.0,
    this.pauseDuration = const Duration(seconds: 2),
  });

  @override
  State<AutoScrollText> createState() => _AutoScrollTextState();
}

class _AutoScrollTextState extends State<AutoScrollText> {
  final ScrollController _scrollController = ScrollController();
  bool _isScrolling = false;
  Timer? _pauseTimer;
  Completer<bool>? _delayCompleter;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _startScrollLoop());
  }

  @override
  void didUpdateWidget(covariant AutoScrollText oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.text != oldWidget.text) {
      _stopScrolling();
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(0.0);
      }
      WidgetsBinding.instance.addPostFrameCallback((_) => _startScrollLoop());
    }
  }

  Future<bool> _cancellableDelay(Duration duration) {
    _pauseTimer?.cancel();
    final completer = Completer<bool>();
    _delayCompleter = completer;
    _pauseTimer = Timer(duration, () {
      if (!completer.isCompleted) completer.complete(mounted && _isScrolling);
    });
    return completer.future;
  }

  void _stopScrolling() {
    _isScrolling = false;
    _pauseTimer?.cancel();
    _pauseTimer = null;
    if (_delayCompleter != null && !_delayCompleter!.isCompleted) {
      _delayCompleter!.complete(false);
    }
  }

  void _startScrollLoop() async {
    if (!mounted || !_scrollController.hasClients) return;
    final maxScroll = _scrollController.position.maxScrollExtent;
    if (maxScroll <= 0) return;

    _isScrolling = true;

    while (mounted && _isScrolling && _scrollController.hasClients) {
      // Pause de confort au début
      final ok1 = await _cancellableDelay(widget.pauseDuration);
      if (!ok1 || !mounted || !_isScrolling || !_scrollController.hasClients) break;

      final currentMax = _scrollController.position.maxScrollExtent;
      if (currentMax <= 0) break;

      // Durée proportionnelle à la longueur à faire défiler
      final durationMs = ((currentMax / widget.velocity) * 1000).toInt().clamp(1000, 45000);

      try {
        await _scrollController.animateTo(
          currentMax,
          duration: Duration(milliseconds: durationMs),
          curve: Curves.linear,
        );
      } catch (_) {
        break;
      }

      if (!mounted || !_isScrolling || !_scrollController.hasClients) break;
      final ok2 = await _cancellableDelay(widget.pauseDuration);
      if (!ok2 || !mounted || !_isScrolling || !_scrollController.hasClients) break;

      // Retour fluide au point de départ
      try {
        await _scrollController.animateTo(
          0.0,
          duration: const Duration(milliseconds: 600),
          curve: Curves.easeInOut,
        );
      } catch (_) {
        break;
      }
    }
  }

  @override
  void dispose() {
    _stopScrolling();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      controller: _scrollController,
      scrollDirection: Axis.horizontal,
      physics: const NeverScrollableScrollPhysics(),
      child: Text(
        widget.text,
        style: widget.style,
        maxLines: 1,
        softWrap: false,
      ),
    );
  }
}
