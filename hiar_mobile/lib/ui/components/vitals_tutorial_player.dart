import 'dart:async';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../theme/hiar_colors.dart';

/// Description d'un tutoriel vidéo de prise de signe vital.
class VitalsTutorialItem {
  final String id;
  final String shortLabel;
  final String title;
  final String sensorTag;
  final String instruction;
  final String assetPath;
  final IconData icon;
  final Color accentColor;

  const VitalsTutorialItem({
    required this.id,
    required this.shortLabel,
    required this.title,
    required this.sensorTag,
    required this.instruction,
    required this.assetPath,
    required this.icon,
    required this.accentColor,
  });
}

/// Les deux vidéos tutorielles embarquées pour l'étape des signes vitaux.
const List<VitalsTutorialItem> kVitalsTutorials = [
  VitalsTutorialItem(
    id: 'temperature',
    shortLabel: 'Température',
    title: 'Prise de température',
    sensorTag: 'Sonde DS18B20',
    instruction: 'Tenez la sonde métallique dans votre main et restez immobile.',
    assetPath: 'assets/videos/bmp_animation.mp4',
    icon: Icons.thermostat,
    accentColor: HiarColors.azur,
  ),
  VitalsTutorialItem(
    id: 'spo2',
    shortLabel: 'Pouls & SpO2',
    title: 'Pouls et oxygénation (SpO2)',
    sensorTag: 'Capteur MAX30102',
    instruction: 'Posez délicatement votre index sur le capteur lumineux sans appuyer fort.',
    assetPath: 'assets/videos/spo2_animation.mp4',
    icon: Icons.favorite,
    accentColor: HiarColors.cyan,
  ),
];

/// Lecteur vidéo tutoriel en boucle (muet) affiché avant et pendant la mesure
/// des constantes vitales afin de guider visuellement le patient.
class VitalsTutorialPlayer extends StatefulWidget {
  final bool isMeasuring;
  final bool isCompleted;
  final int initialIndex;
  final VoidCallback? onStartMeasure;
  final bool allowFullscreenButton;
  final bool enableVideoPlayback;

  const VitalsTutorialPlayer({
    super.key,
    this.isMeasuring = false,
    this.isCompleted = false,
    this.initialIndex = 0,
    this.onStartMeasure,
    this.allowFullscreenButton = true,
    this.enableVideoPlayback = true,
  });

  @override
  State<VitalsTutorialPlayer> createState() => _VitalsTutorialPlayerState();
}

class _VitalsTutorialPlayerState extends State<VitalsTutorialPlayer> {
  late int _activeIndex;
  VideoPlayerController? _controller;
  bool _isVideoReady = false;
  bool _videoFailed = false;
  Timer? _autoSwitchTimer;
  int _loadGeneration = 0;

  VitalsTutorialItem get _currentItem => kVitalsTutorials[_activeIndex];

  @override
  void initState() {
    super.initState();
    _activeIndex = widget.initialIndex.clamp(0, kVitalsTutorials.length - 1);
    _loadCurrentVideo();
    _startAutoSwitchTimer();
  }

  @override
  void didUpdateWidget(covariant VitalsTutorialPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialIndex != oldWidget.initialIndex) {
      final target = widget.initialIndex.clamp(0, kVitalsTutorials.length - 1);
      if (target != _activeIndex) {
        _selectTab(target, resetTimer: true);
      }
    }
  }

  @override
  void dispose() {
    _autoSwitchTimer?.cancel();
    _disposeController();
    super.dispose();
  }

  void _startAutoSwitchTimer() {
    _autoSwitchTimer?.cancel();
    // Chaque vidéo dure 10 secondes : on alterne automatiquement les deux gestes
    _autoSwitchTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      if (!mounted) return;
      _selectTab((_activeIndex + 1) % kVitalsTutorials.length, resetTimer: false);
    });
  }

  void _selectTab(int index, {bool resetTimer = true}) {
    if (index == _activeIndex) return;
    setState(() {
      _activeIndex = index;
    });
    _loadCurrentVideo();
    if (resetTimer) {
      _startAutoSwitchTimer();
    }
  }

  Future<void> _disposeController() async {
    final old = _controller;
    _controller = null;
    if (old != null) {
      try {
        await old.pause();
        await old.dispose();
      } catch (_) {
        // Ignorer les erreurs de nettoyage en environnement de test
      }
    }
  }

  Future<void> _loadCurrentVideo() async {
    final gen = ++_loadGeneration;
    await _disposeController();
    if (!mounted) return;

    setState(() {
      _isVideoReady = false;
      _videoFailed = false;
    });

    if (!widget.enableVideoPlayback) {
      return;
    }

    try {
      final ctrl = VideoPlayerController.asset(
        _currentItem.assetPath,
        videoPlayerOptions: VideoPlayerOptions(mixWithOthers: true),
      );
      _controller = ctrl;
      await ctrl.initialize();
      if (!mounted || gen != _loadGeneration) {
        await ctrl.dispose();
        return;
      }
      // Toujours muet pour ne pas perturber la voix TTS ni le micro STT du robot
      await ctrl.setVolume(0.0);
      await ctrl.setLooping(true);
      await ctrl.play();
      if (mounted && gen == _loadGeneration) {
        setState(() {
          _isVideoReady = true;
          _videoFailed = false;
        });
      }
    } catch (_) {
      if (mounted && gen == _loadGeneration) {
        setState(() {
          _isVideoReady = false;
          _videoFailed = true;
        });
      }
    }
  }

  Future<void> _openFullscreenGuide() async {
    // Mettre en pause le petit lecteur pendant que la fenêtre agrandie joue
    try {
      await _controller?.pause();
    } catch (_) {}
    _autoSwitchTimer?.cancel();

    if (!mounted) return;
    await showDialog<void>(
      context: context,
      barrierDismissible: true,
      builder: (ctx) => _VitalsTutorialDialog(
        initialIndex: _activeIndex,
        isMeasuring: widget.isMeasuring,
        isCompleted: widget.isCompleted,
        enableVideoPlayback: widget.enableVideoPlayback,
        onStartMeasure: widget.onStartMeasure == null
            ? null
            : () {
                Navigator.of(ctx).pop();
                widget.onStartMeasure?.call();
              },
      ),
    );

    if (!mounted) return;
    try {
      await _controller?.play();
    } catch (_) {}
    _startAutoSwitchTimer();
  }

  @override
  Widget build(BuildContext context) {
    final item = _currentItem;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: widget.isMeasuring
              ? HiarColors.azur.withOpacity(0.55)
              : (widget.isCompleted ? HiarColors.ok.withOpacity(0.45) : HiarColors.border),
          width: widget.isMeasuring ? 1.5 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: HiarColors.marine.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // En-tête : sélecteur des 2 tutoriels + bouton agrandir
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 8, 6),
            child: Row(
              children: [
                Expanded(
                  child: Row(
                    children: List.generate(kVitalsTutorials.length, (i) {
                      final tab = kVitalsTutorials[i];
                      final selected = i == _activeIndex;
                      return Expanded(
                        child: Padding(
                          padding: EdgeInsets.only(right: i == 0 ? 6 : 0),
                          child: InkWell(
                            borderRadius: BorderRadius.circular(8),
                            onTap: () => _selectTab(i),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 180),
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                              decoration: BoxDecoration(
                                color: selected ? tab.accentColor : HiarColors.brume,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    tab.icon,
                                    size: 14,
                                    color: selected ? Colors.white : HiarColors.text2,
                                  ),
                                  const SizedBox(width: 4),
                                  Flexible(
                                    child: Text(
                                      tab.shortLabel,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w700,
                                        color: selected ? Colors.white : HiarColors.text2,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      );
                    }),
                  ),
                ),
                if (widget.allowFullscreenButton) ...[
                  const SizedBox(width: 4),
                  Tooltip(
                    message: 'Agrandir le guide vidéo',
                    child: InkWell(
                      borderRadius: BorderRadius.circular(8),
                      onTap: _openFullscreenGuide,
                      child: Container(
                        padding: const EdgeInsets.all(5),
                        decoration: BoxDecoration(
                          color: HiarColors.brume,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.open_in_full, size: 15, color: HiarColors.marine),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),

          // Zone vidéo 16:9 avec badges d'état
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: AspectRatio(
                aspectRatio: 16 / 9,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (_isVideoReady && _controller != null)
                      FittedBox(
                        fit: BoxFit.cover,
                        child: SizedBox(
                          width: _controller!.value.size.width > 0
                              ? _controller!.value.size.width
                              : 1280,
                          height: _controller!.value.size.height > 0
                              ? _controller!.value.size.height
                              : 720,
                          child: VideoPlayer(_controller!),
                        ),
                      )
                    else
                      _buildFallbackPreview(item),

                    // Badge supérieur gauche (étape / état)
                    Positioned(
                      top: 6,
                      left: 6,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: (widget.isMeasuring
                                  ? HiarColors.azur
                                  : (widget.isCompleted ? HiarColors.ok : HiarColors.marine))
                              .withOpacity(0.86),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              widget.isMeasuring
                                  ? Icons.sensors
                                  : (widget.isCompleted ? Icons.check_circle : Icons.play_circle_outline),
                              size: 12,
                              color: Colors.white,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              widget.isMeasuring
                                  ? 'Suivez ce geste'
                                  : (widget.isCompleted ? 'Mesure terminée' : 'Tutoriel · ${item.sensorTag}'),
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Indicateurs de pagination en bas à droite
                    Positioned(
                      bottom: 6,
                      right: 8,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: List.generate(kVitalsTutorials.length, (i) {
                          final active = i == _activeIndex;
                          return AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            margin: const EdgeInsets.only(left: 4),
                            width: active ? 16 : 6,
                            height: 6,
                            decoration: BoxDecoration(
                              color: active ? Colors.white : Colors.white.withOpacity(0.5),
                              borderRadius: BorderRadius.circular(4),
                            ),
                          );
                        }),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Légende pédagogique sous la vidéo
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 7, 10, 9),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(item.icon, size: 16, color: item.accentColor),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    item.instruction,
                    style: const TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: HiarColors.marine,
                      height: 1.25,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFallbackPreview(VitalsTutorialItem item) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            item.accentColor.withOpacity(0.14),
            HiarColors.brume,
          ],
        ),
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: item.accentColor.withOpacity(0.2),
                    blurRadius: 10,
                  ),
                ],
              ),
              child: Icon(item.icon, size: 28, color: item.accentColor),
            ),
            const SizedBox(height: 6),
            Text(
              item.title,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: HiarColors.marine,
              ),
            ),
            if (!_videoFailed && widget.enableVideoPlayback)
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: HiarColors.azur),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Fenêtre agrandie du guide vidéo avant ou pendant la mesure.
class _VitalsTutorialDialog extends StatelessWidget {
  final int initialIndex;
  final bool isMeasuring;
  final bool isCompleted;
  final bool enableVideoPlayback;
  final VoidCallback? onStartMeasure;

  const _VitalsTutorialDialog({
    required this.initialIndex,
    required this.isMeasuring,
    required this.isCompleted,
    required this.enableVideoPlayback,
    this.onStartMeasure,
  });

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final dialogWidth = (screenWidth * 0.68).clamp(360.0, 620.0);

    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      child: SizedBox(
        width: dialogWidth,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(14),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Icon(Icons.ondemand_video_rounded, color: HiarColors.azur, size: 22),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'Comment placer les capteurs',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: HiarColors.marine,
                      ),
                    ),
                  ),
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close, color: HiarColors.text2),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              VitalsTutorialPlayer(
                initialIndex: initialIndex,
                isMeasuring: isMeasuring,
                isCompleted: isCompleted,
                allowFullscreenButton: false,
                enableVideoPlayback: enableVideoPlayback,
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Fermer'),
                  ),
                  if (!isMeasuring && onStartMeasure != null) ...[
                    const SizedBox(width: 8),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: HiarColors.azur,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      onPressed: onStartMeasure,
                      icon: const Icon(Icons.sensors, size: 18),
                      label: const Text("J'ai compris, démarrer"),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
