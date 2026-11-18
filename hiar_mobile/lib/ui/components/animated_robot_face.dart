import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

/// Expressions faciales animées du robot HIAR.
enum RobotFaceExpression {
  idle,      // Veille neutre → yeux grands ouverts + bouche fermée
  listening, // Écoute attentive / curieux → inclinaison + léger sourire
  thinking,  // Attente / chargement vocal → regard qui balaie + bouche pensive + barre
  speaking,  // Parole TTS → bouche animée multi-syllabes
  happy,     // Sourire enthousiaste & serein → yeux fermés en arcs + grand sourire + joues
  emergency, // Alerte / arrêt → yeux plissés rouge-corail + bouche inquiète
}

/// Forme explicite de bouche dérivée de [RobotFaceExpression].
enum RobotMouthShape {
  closed,
  gentleSmile,
  bigSmile,
  talking,
  thinking,
  alert,
}

/// Associe chaque expression faciale à sa forme de bouche correspondante.
RobotMouthShape mouthShapeForExpression(RobotFaceExpression expression) {
  switch (expression) {
    case RobotFaceExpression.idle:
      return RobotMouthShape.closed;
    case RobotFaceExpression.listening:
      return RobotMouthShape.gentleSmile;
    case RobotFaceExpression.happy:
      return RobotMouthShape.bigSmile;
    case RobotFaceExpression.speaking:
      return RobotMouthShape.talking;
    case RobotFaceExpression.thinking:
      return RobotMouthShape.thinking;
    case RobotFaceExpression.emergency:
      return RobotMouthShape.alert;
  }
}

/// Convertit une chaîne `face_expression` venant du serveur en [RobotFaceExpression].
RobotFaceExpression parseRobotFaceExpression(
  String? raw, {
  RobotFaceExpression fallback = RobotFaceExpression.idle,
}) {
  switch ((raw ?? '').toLowerCase().trim()) {
    case 'happy':
    case 'smile':
      return RobotFaceExpression.happy;
    case 'speaking':
    case 'talk':
      return RobotFaceExpression.speaking;
    case 'thinking':
    case 'loading':
      return RobotFaceExpression.thinking;
    case 'listening':
    case 'curious':
      return RobotFaceExpression.listening;
    case 'emergency':
    case 'alert':
    case 'stop':
      return RobotFaceExpression.emergency;
    case 'neutral':
    case 'idle':
    case 'closed':
      return RobotFaceExpression.idle;
    default:
      return fallback;
  }
}

/// Visage animé officiel du robot HIAR (inspiré de hiar_animated_logo_splash_screen.html) :
/// - Coque céramique blanche 3D + oreilles acoustiques latérales + visière verre sombre
/// - Petite croix médicale JAUNE sur le front qui bouge avec la tête et pulse doucement
/// - Morphing continu Bézier des yeux (ronds ouverts avec reflets → arcs fermés souriants)
/// - 6 formes de bouche conditionnées selon l'état (fermée, sourire, parle, réflexion, alerte)
/// - Mode [playIntroSequence] pour le Splash Screen :
///     1. (0s – 2s) Neutre : yeux grands ouverts sans réaction, bouche fermée, micro-clignement
///     2. (2s – 4s) Curieux : inclinaison de la tête (~13°) comme s'il vous avait repéré
///     3. (4s – 6s) Sourire enthousiaste & serein : yeux fermés en arcs + grand sourire + joues
///     4. (6s – 9.5s) Maintien serein avec respiration douce puis boucle fluide
class AnimatedRobotFace extends StatefulWidget {
  final RobotFaceExpression expression;
  final double width;
  final double height;
  final bool showLoadingRing;
  final bool playIntroSequence;

  const AnimatedRobotFace({
    super.key,
    this.expression = RobotFaceExpression.idle,
    this.width = 92,
    this.height = 70,
    this.showLoadingRing = false,
    this.playIntroSequence = false,
  });

  @override
  State<AnimatedRobotFace> createState() => _AnimatedRobotFaceState();
}

class _AnimatedRobotFaceState extends State<AnimatedRobotFace>
    with TickerProviderStateMixin {
  late final AnimationController _ambientCtrl;
  late final AnimationController _speakCtrl;
  late final AnimationController _blinkCtrl;
  late final AnimationController _introCtrl;
  Timer? _blinkTimer;

  @override
  void initState() {
    super.initState();
    _ambientCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 4600),
    )..repeat();

    _speakCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 780),
    )..repeat();

    _blinkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 110),
    );

    // Cycle intro Splash Screen : 10 secondes (Neutre 0–2s → Curieux 2–4s → Sourire serein 4–9s → Transition douce)
    _introCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 10000),
    );
    if (widget.playIntroSequence) {
      _introCtrl.repeat();
    }

    _scheduleBlinkLoop();
  }

  @override
  void didUpdateWidget(covariant AnimatedRobotFace oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.playIntroSequence && !_introCtrl.isAnimating) {
      _introCtrl.repeat();
    } else if (!widget.playIntroSequence && _introCtrl.isAnimating) {
      _introCtrl.stop();
    }
  }

  void _scheduleBlinkLoop() {
    _blinkTimer?.cancel();
    _blinkTimer = Timer.periodic(const Duration(milliseconds: 3400), (_) {
      if (!mounted) return;
      if (widget.playIntroSequence) return; // L'intro gère son propre clignement
      if (widget.expression == RobotFaceExpression.emergency ||
          widget.expression == RobotFaceExpression.happy) {
        return;
      }
      _blinkCtrl.forward().then((_) {
        if (mounted) _blinkCtrl.reverse();
      });
    });
  }

  @override
  void dispose() {
    _blinkTimer?.cancel();
    _ambientCtrl.dispose();
    _speakCtrl.dispose();
    _blinkCtrl.dispose();
    _introCtrl.dispose();
    super.dispose();
  }

  double _clamp01(double v) => v.clamp(0.0, 1.0);

  double _easeInOutCubic(double t) {
    final c = _clamp01(t);
    return c < 0.5 ? 4 * c * c * c : 1 - math.pow(-2 * c + 2, 3) / 2.0;
  }

  double _easeOutBack(double t, {double s = 1.25}) {
    final c = _clamp01(t);
    final c3 = s + 1.0;
    return 1.0 + c3 * math.pow(c - 1.0, 3) + s * math.pow(c - 1.0, 2);
  }

  double _window(double timeSec, double start, double end, {bool back = false}) {
    if (timeSec <= start) return 0.0;
    if (timeSec >= end) return 1.0;
    final norm = (timeSec - start) / (end - start);
    return back ? _easeOutBack(norm) : _easeInOutCubic(norm);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([_ambientCtrl, _speakCtrl, _blinkCtrl, _introCtrl]),
      builder: (context, _) {
        final double phase = _ambientCtrl.value * 2 * math.pi;
        final double speakPhase = _speakCtrl.value;

        double tiltDeg = 0.0;
        double floatY = 0.0;
        double lookX = 0.0;
        double lookY = 0.0;
        double blink = _blinkCtrl.value;
        double curiosity = 0.0;
        double happyMorph = 0.0;
        double cheekOpacity = 0.0;
        RobotMouthShape mouthShape = mouthShapeForExpression(widget.expression);
        bool isEmergency = widget.expression == RobotFaceExpression.emergency;
        bool isThinking =
            widget.expression == RobotFaceExpression.thinking || widget.showLoadingRing;

        if (widget.playIntroSequence) {
          // Séquence fidèle à hiar_animated_logo_splash_screen.html (10 s en boucle douce)
          final double t = _introCtrl.value * 10.0;

          // Scène 1 (0–2s) : neutre, yeux grands ouverts + micro-clignement à 1.15s
          if (t > 1.05 && t < 1.32) {
            blink = math.sin(((t - 1.05) / 0.27) * math.pi);
          } else {
            blink = 0.0;
          }

          // Scène 2 (2–4s) : curiosité & inclinaison (~13.2°) comme s'il vous avait repéré
          final cIn = _window(t, 1.95, 2.85, back: true);
          final cOut = _window(t, 3.95, 4.75);
          curiosity = (cIn * (1.0 - cOut)).clamp(0.0, 1.15);

          // Scène 3 & 4 (4–8.8s) : sourire enthousiaste, yeux fermés en arcs, serein → retour neutre 8.8–9.8s
          final wIn = _window(t, 4.00, 5.15, back: true);
          final wOut = _window(t, 8.80, 9.75);
          final double welcome = (wIn * (1.0 - wOut)).clamp(0.0, 1.05);

          happyMorph = welcome.clamp(0.0, 1.0);
          cheekOpacity = (happyMorph * 0.95).clamp(0.0, 1.0);

          final double breath = math.sin(t * 2.1) * 2.4;
          floatY = breath - curiosity * 3.0 - happyMorph * 2.5;
          final double gentleSway = math.sin(t * 1.45) * 1.3 * happyMorph;
          tiltDeg = curiosity * 13.2 + happyMorph * 2.2 + gentleSway;
          lookX = curiosity * 0.7 + happyMorph * 0.12;
          lookY = -curiosity * 0.35 - happyMorph * 0.18;

          if (happyMorph > 0.45) {
            mouthShape = RobotMouthShape.bigSmile;
          } else if (curiosity > 0.25) {
            mouthShape = RobotMouthShape.gentleSmile;
          } else {
            mouthShape = RobotMouthShape.closed;
          }
          isEmergency = false;
          isThinking = false;
        } else {
          // Mode interactif dans le VoiceRail selon l'expression active
          switch (widget.expression) {
            case RobotFaceExpression.idle:
              // Neutre calme, yeux ouverts, bouche fermée
              tiltDeg = math.sin(phase) * 2.2;
              floatY = -math.sin(phase) * 1.5;
              lookX = math.sin(phase) * 0.45;
              lookY = math.cos(phase * 2.0) * 0.15;
              happyMorph = 0.0;
              break;
            case RobotFaceExpression.listening:
              // Curieux / à l'écoute : tête inclinée + regard attentif
              curiosity = 0.65;
              tiltDeg = 6.5 + math.sin(phase) * 2.2;
              floatY = -math.sin(phase) * 1.8 - 1.0;
              lookX = math.sin(phase) * 0.35 + 0.2;
              happyMorph = 0.0;
              break;
            case RobotFaceExpression.thinking:
              // Attente réponse vocale : inclinaison curieuse + yeux qui balaient
              curiosity = 0.55;
              tiltDeg = math.sin(phase * 1.5) * 7.0;
              floatY = -math.sin(phase * 2.0) * 1.8;
              lookX = math.sin(phase * 2.0) * 0.95;
              lookY = -0.3;
              happyMorph = 0.0;
              break;
            case RobotFaceExpression.speaking:
              // Parle : bouche multi-syllabes + léger hochement amical
              tiltDeg = math.sin(phase * 2.0) * 3.5;
              floatY = -math.sin(speakPhase * math.pi).abs() * 2.0;
              lookX = math.sin(phase) * 0.25;
              happyMorph = 0.0;
              cheekOpacity = 0.35;
              break;
            case RobotFaceExpression.happy:
              // Sourire enthousiaste & serein : yeux fermés en arcs + grand sourire
              tiltDeg = 2.5 + math.sin(phase * 1.4) * 2.0;
              floatY = -math.sin(phase * 2.0) * 2.0 - 1.5;
              happyMorph = 1.0;
              cheekOpacity = 0.95;
              break;
            case RobotFaceExpression.emergency:
              tiltDeg = 0.0;
              floatY = 0.0;
              happyMorph = 0.0;
              break;
          }
        }

        return SizedBox(
          width: widget.width,
          height: widget.height,
          child: Transform.translate(
            offset: Offset(0, floatY),
            child: Transform.rotate(
              angle: tiltDeg * math.pi / 180.0,
              child: CustomPaint(
                painter: _HiarCeramicRobotPainter(
                  expression: widget.expression,
                  mouthShape: mouthShape,
                  lookX: lookX,
                  lookY: lookY,
                  blink: blink,
                  curiosity: curiosity,
                  happyMorph: happyMorph,
                  cheekOpacity: cheekOpacity,
                  speakPhase: speakPhase,
                  ambientPhase: phase,
                  spinnerPhase: _ambientCtrl.value,
                  isEmergency: isEmergency,
                  showLoadingRing: isThinking,
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _HiarCeramicRobotPainter extends CustomPainter {
  final RobotFaceExpression expression;
  final RobotMouthShape mouthShape;
  final double lookX;
  final double lookY;
  final double blink;
  final double curiosity;
  final double happyMorph;
  final double cheekOpacity;
  final double speakPhase;
  final double ambientPhase;
  final double spinnerPhase;
  final bool isEmergency;
  final bool showLoadingRing;

  _HiarCeramicRobotPainter({
    required this.expression,
    required this.mouthShape,
    required this.lookX,
    required this.lookY,
    required this.blink,
    required this.curiosity,
    required this.happyMorph,
    required this.cheekOpacity,
    required this.speakPhase,
    required this.ambientPhase,
    required this.spinnerPhase,
    required this.isEmergency,
    required this.showLoadingRing,
  });

  double _lerp(double a, double b, double t) => a + (b - a) * t;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final cx = w * 0.5;
    final cy = h * 0.52;

    // Proportions inspirées de la coque céramique 524×396 + oreilles du HTML
    final double shellW = w * 0.84;
    final double shellH = h * 0.80;
    final double shellR = shellH * 0.45;
    final Rect shellRect = Rect.fromCenter(center: Offset(cx, cy), width: shellW, height: shellH);

    // Parallaxe 3D subtile
    final double faceShiftX = lookX * (shellW * 0.032);
    final double faceShiftY = lookY * (shellH * 0.025);
    final double earParallaxX = -faceShiftX * 0.35;

    // 1. Ombre portée douce sous la tête
    final shadowPaint = Paint()
      ..color = HiarColors.shadow.withOpacity(0.14)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawRRect(
      RRect.fromRectAndRadius(shellRect.shift(const Offset(0, 4)), Radius.circular(shellR)),
      shadowPaint,
    );

    // 2. Oreilles acoustiques latérales (avec accent teal/cyan HIAR)
    _paintEars(canvas, shellRect, earParallaxX, -faceShiftY * 0.3);

    // 3. Coque céramique blanche 3D
    final shellPaint = Paint()
      ..shader = const RadialGradient(
        center: Alignment(-0.12, -0.42),
        radius: 1.05,
        colors: [
          Color(0xFFFFFFFF),
          Color(0xFFF6FAFD),
          Color(0xFFE3EEF6),
          Color(0xFFCBDCEB),
        ],
        stops: [0.0, 0.58, 0.86, 1.0],
      ).createShader(shellRect);

    final RRect shellRRect = RRect.fromRectAndRadius(shellRect, Radius.circular(shellR));
    canvas.drawRRect(shellRRect, shellPaint);

    // Bordure satinée de la coque
    canvas.drawRRect(
      shellRRect,
      Paint()
        ..color = HiarColors.border
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1.2, w * 0.012),
    );

    // Reflet spéculaire 3D doux sur le haut du crâne
    final highlightRect = Rect.fromCenter(
      center: Offset(cx, shellRect.top + shellH * 0.14),
      width: shellW * 0.56,
      height: shellH * 0.16,
    );
    canvas.drawOval(
      highlightRect,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Colors.white.withOpacity(0.95), Colors.white.withOpacity(0.0)],
        ).createShader(highlightRect),
    );

    // 4. Petite croix médicale JAUNE sur le front qui bouge avec la tête + pulsation
    _paintYellowForeheadCross(canvas, cx, shellRect.top + shellH * 0.115, shellW, shellH);

    // 5. Cadre satiné + Visière en verre sombre profond
    final double visorW = shellW * 0.82;
    final double visorH = shellH * 0.63;
    final double visorR = visorH * 0.44;
    final Rect visorRect = Rect.fromCenter(
      center: Offset(cx, cy + shellH * 0.055),
      width: visorW,
      height: visorH,
    );
    final RRect visorFrame = RRect.fromRectAndRadius(
      visorRect.inflate(math.max(1.8, w * 0.015)),
      Radius.circular(visorR + 2),
    );
    canvas.drawRRect(visorFrame, Paint()..color = const Color(0xFFDCE8F2));

    final RRect visorRRect = RRect.fromRectAndRadius(visorRect, Radius.circular(visorR));
    final visorPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0.0, -0.3),
        radius: 0.95,
        colors: isEmergency
            ? const [Color(0xFF471515), Color(0xFF230A0A), Color(0xFF120505)]
            : const [Color(0xFF15324B), Color(0xFF0B1C2E), Color(0xFF06101B)],
        stops: const [0.0, 0.55, 1.0],
      ).createShader(visorRect);
    canvas.drawRRect(visorRRect, visorPaint);

    // Contenu interne de la visière (clippé)
    canvas.save();
    canvas.clipRRect(visorRRect);

    // Reflet vitré diagonal subtil sur la visière
    final sheenPath = Path()
      ..moveTo(visorRect.left, visorRect.top)
      ..lineTo(visorRect.left + visorW * 0.62, visorRect.top)
      ..lineTo(visorRect.left + visorW * 0.36, visorRect.bottom)
      ..lineTo(visorRect.left, visorRect.bottom)
      ..close();
    canvas.drawPath(
      sheenPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white.withOpacity(0.14),
            Colors.white.withOpacity(0.02),
            Colors.transparent,
          ],
        ).createShader(visorRect),
    );

    // 6. Joues lumineuses douces lors du sourire
    if (cheekOpacity > 0.02) {
      final cheekPaint = Paint()
        ..color = const Color(0xFF2DD4BF).withOpacity(0.32 * cheekOpacity)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5);
      final double cheekY = visorRect.center.dy + visorH * 0.21 + faceShiftY;
      canvas.drawOval(
        Rect.fromCenter(
          center: Offset(visorRect.center.dx - visorW * 0.29 + faceShiftX, cheekY),
          width: visorW * 0.17,
          height: visorH * 0.14,
        ),
        cheekPaint,
      );
      canvas.drawOval(
        Rect.fromCenter(
          center: Offset(visorRect.center.dx + visorW * 0.29 + faceShiftX, cheekY),
          width: visorW * 0.17,
          height: visorH * 0.14,
        ),
        cheekPaint,
      );
    }

    // 7. Yeux morphés (ronds grands ouverts → arcs fermés souriants)
    final Color featureColor = isEmergency ? const Color(0xFFFF8A8A) : const Color(0xFF22D3EE);
    final double eyeY = visorRect.center.dy - visorH * 0.06 - happyMorph * (visorH * 0.03) + faceShiftY;
    final double eyeOffset = visorW * 0.22;

    final double baseRx = visorW * 0.082 * (1.0 + curiosity * 0.11);
    final double baseRy = visorH * 0.142 * (1.0 + curiosity * 0.12);

    // Asymétrie attachante pendant la curiosité (exactement comme dans le HTML)
    final double leftRx = baseRx * (1.0 - curiosity * 0.03);
    final double leftRy = math.max(1.8, baseRy * (1.0 - curiosity * 0.03) * (1.0 - blink * 0.88));
    final double rightRx = baseRx * (1.0 + curiosity * 0.05);
    final double rightRy = math.max(1.8, baseRy * (1.0 + curiosity * 0.05) * (1.0 - blink * 0.88));

    _paintMorphedEye(
      canvas,
      Offset(visorRect.center.dx - eyeOffset + faceShiftX, eyeY),
      leftRx,
      leftRy,
      happyMorph,
      featureColor,
    );
    _paintMorphedEye(
      canvas,
      Offset(visorRect.center.dx + eyeOffset + faceShiftX, eyeY),
      rightRx,
      rightRy,
      happyMorph,
      featureColor,
    );

    // 8. Bouche conditionnée selon les cas (fermée, sourire, parle, réflexion, alerte)
    _paintMouth(canvas, visorRect, faceShiftX, faceShiftY, featureColor);

    // 9. Barre de progression subtile en mode réflexion / chargement vocal
    if (showLoadingRing) {
      final double barY = visorRect.bottom - math.max(3.0, visorH * 0.06);
      final double padX = visorW * 0.16;
      canvas.drawLine(
        Offset(visorRect.left + padX, barY),
        Offset(visorRect.right - padX, barY),
        Paint()
          ..color = Colors.white.withOpacity(0.16)
          ..strokeWidth = 2.4
          ..strokeCap = StrokeCap.round,
      );
      final double trackW = visorW - padX * 2;
      final double sweepW = trackW * 0.34;
      final double startX = visorRect.left +
          padX +
          (trackW - sweepW) * ((math.sin(spinnerPhase * 2 * math.pi * 1.5) + 1) / 2);
      canvas.drawLine(
        Offset(startX, barY),
        Offset(startX + sweepW, barY),
        Paint()
          ..color = HiarColors.robotCrossYellow
          ..strokeWidth = 2.8
          ..strokeCap = StrokeCap.round,
      );
    }

    canvas.restore();
  }

  void _paintEars(Canvas canvas, Rect shellRect, double px, double py) {
    final double earW = shellRect.width * 0.085;
    final double earH = shellRect.height * 0.30;
    final double earY = shellRect.center.dy + shellRect.height * 0.02 + py;

    final earPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFF7FBFE), Color(0xFFDCE9F3), Color(0xFFB9D0E2)],
      ).createShader(shellRect);

    final accentPaint = Paint()
      ..color = (isEmergency ? HiarColors.err : HiarColors.secondary).withOpacity(0.85);

    for (final isLeft in [true, false]) {
      final double ex = isLeft
          ? shellRect.left - earW * 0.45 + px
          : shellRect.right + earW * 0.45 + px;
      final earRect = Rect.fromCenter(center: Offset(ex, earY), width: earW, height: earH);
      canvas.drawRRect(
        RRect.fromRectAndRadius(earRect, Radius.circular(earW * 0.5)),
        earPaint,
      );
      final stripRect = Rect.fromCenter(
        center: Offset(ex + (isLeft ? -earW * 0.12 : earW * 0.12), earY),
        width: earW * 0.25,
        height: earH * 0.58,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(stripRect, Radius.circular(earW * 0.15)),
        accentPaint,
      );
    }
  }

  /// Petite croix médicale JAUNE sur le front qui bouge doucement et pulse.
  void _paintYellowForeheadCross(Canvas canvas, double cx, double cy, double shellW, double shellH) {
    final double moveX = lookX * (shellW * 0.018) + math.sin(ambientPhase * 1.5) * (shellW * 0.008);
    final double moveY = math.cos(ambientPhase * 2.0) * (shellH * 0.008);
    final double pulse = 1.0 + 0.09 * math.sin(ambientPhase * 2.0);
    final double armLen = math.max(6.5, shellH * 0.145) * pulse;
    final double armThick = math.max(2.3, armLen * 0.36);

    final Offset center = Offset(cx + moveX, cy + moveY);

    // Halo doré discret
    canvas.drawCircle(
      center,
      armLen * 0.72,
      Paint()
        ..color = HiarColors.robotCrossYellow.withOpacity(0.35)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );

    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(0.08 * math.sin(ambientPhase * 1.5));

    final crossPaint = Paint()
      ..color = HiarColors.robotCrossYellow
      ..style = PaintingStyle.fill;

    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset.zero, width: armThick, height: armLen),
        Radius.circular(armThick * 0.35),
      ),
      crossPaint,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset.zero, width: armLen, height: armThick),
        Radius.circular(armThick * 0.35),
      ),
      crossPaint,
    );
    canvas.restore();
  }

  /// Morphing continu par 4 courbes de Bézier cubiques (port fidèle de buildEyePath du HTML) :
  /// happy = 0 → œil rond grand ouvert lumineux + 2 reflets spéculaires blancs
  /// happy = 1 → arc souriant fermé enthousiaste et serein
  void _paintMorphedEye(
    Canvas canvas,
    Offset center,
    double rx,
    double ry,
    double happy,
    Color color,
  ) {
    canvas.save();
    canvas.translate(center.dx, center.dy);

    if (isEmergency) {
      // Yeux plissés d'alerte
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset.zero, width: rx * 2.1, height: ry * 0.9),
          Radius.circular(rx * 0.45),
        ),
        Paint()..color = color,
      );
      canvas.restore();
      return;
    }

    const double k = 0.55228475;
    final double h = happy.clamp(0.0, 1.0);

    // État ouvert (happy = 0)
    final oL = Offset(-rx, 0);
    final oT = Offset(0, -ry);
    final oR = Offset(rx, 0);
    final oB = Offset(0, ry);

    final oLc1 = Offset(-rx, -ry * k);
    final oTc2 = Offset(-rx * k, -ry);
    final oTc1 = Offset(rx * k, -ry);
    final oRc2 = Offset(rx, -ry * k);
    final oRc1 = Offset(rx, ry * k);
    final oBc2 = Offset(rx * k, ry);
    final oBc1 = Offset(-rx * k, ry);
    final oLc2 = Offset(-rx, ry * k);

    // État souriant fermé (happy = 1 : croissant lumineux courbé vers le haut)
    final double arcW = rx * 1.20;
    final double arcPeakY = -ry * 0.58;
    final double arcBaseY = ry * 0.28;
    final double thick = math.max(2.2, ry * 0.28);

    final hL = Offset(-arcW, arcBaseY);
    final hT = Offset(0, arcPeakY - thick * 0.5);
    final hR = Offset(arcW, arcBaseY);
    final hB = Offset(0, arcPeakY + thick * 0.5);

    final hLc1 = Offset(-arcW * 0.72, arcBaseY - ry * 0.55);
    final hTc2 = Offset(-arcW * 0.45, hT.dy);
    final hTc1 = Offset(arcW * 0.45, hT.dy);
    final hRc2 = Offset(arcW * 0.72, arcBaseY - ry * 0.55);

    final hRc1 = Offset(arcW * 0.68, arcBaseY - ry * 0.35);
    final hBc2 = Offset(arcW * 0.42, hB.dy);
    final hBc1 = Offset(-arcW * 0.42, hB.dy);
    final hLc2 = Offset(-arcW * 0.68, arcBaseY - ry * 0.35);

    Offset mix(Offset a, Offset b) => Offset(_lerp(a.dx, b.dx, h), _lerp(a.dy, b.dy, h));

    final pL = mix(oL, hL);
    final pT = mix(oT, hT);
    final pR = mix(oR, hR);
    final pB = mix(oB, hB);
    final c1 = mix(oLc1, hLc1);
    final c2 = mix(oTc2, hTc2);
    final c3 = mix(oTc1, hTc1);
    final c4 = mix(oRc2, hRc2);
    final c5 = mix(oRc1, hRc1);
    final c6 = mix(oBc2, hBc2);
    final c7 = mix(oBc1, hBc1);
    final c8 = mix(oLc2, hLc2);

    final path = Path()
      ..moveTo(pL.dx, pL.dy)
      ..cubicTo(c1.dx, c1.dy, c2.dx, c2.dy, pT.dx, pT.dy)
      ..cubicTo(c3.dx, c3.dy, c4.dx, c4.dy, pR.dx, pR.dy)
      ..cubicTo(c5.dx, c5.dy, c6.dx, c6.dy, pB.dx, pB.dy)
      ..cubicTo(c7.dx, c7.dy, c8.dx, c8.dy, pL.dx, pL.dy)
      ..close();

    // Lueur cyan douce autour de l'œil
    canvas.drawPath(
      path,
      Paint()
        ..color = color.withOpacity(0.42)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4.5),
    );
    canvas.drawPath(path, Paint()..color = color);
    canvas.drawPath(
      path,
      Paint()
        ..color = const Color(0xFF82DFF7)
        ..style = PaintingStyle.stroke
        ..strokeWidth = _lerp(0.8, 1.8, h),
    );

    // 2 reflets spéculaires blancs dans l'œil ouvert (disparaissent quand l'œil sourit fermé)
    final double catchOpacity = (1.0 - h * 1.45).clamp(0.0, 1.0) * (1.0 - blink);
    if (catchOpacity > 0.05) {
      final double gx = curiosity * rx * 0.18;
      final double gy = -curiosity * ry * 0.12;
      canvas.drawCircle(
        Offset(-rx * 0.30 + gx, -ry * 0.30 + gy),
        math.max(1.2, rx * 0.24),
        Paint()..color = Colors.white.withOpacity(0.92 * catchOpacity),
      );
      canvas.drawCircle(
        Offset(rx * 0.26 + gx * 0.7, ry * 0.26 + gy * 0.7),
        math.max(0.8, rx * 0.11),
        Paint()..color = Colors.white.withOpacity(0.65 * catchOpacity),
      );
    }

    canvas.restore();
  }

  void _paintMouth(
    Canvas canvas,
    Rect visorRect,
    double dx,
    double dy,
    Color featureColor,
  ) {
    final double w = visorRect.width;
    final double h = visorRect.height;
    final double mouthCx = visorRect.center.dx + dx;
    final double mouthY = visorRect.center.dy + h * 0.23 + dy * 0.4;
    final double mouthHalfW = w * 0.105;

    final strokePaint = Paint()
      ..color = featureColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(2.0, h * 0.055)
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final fillPaint = Paint()
      ..color = featureColor.withOpacity(0.92)
      ..style = PaintingStyle.fill;

    switch (mouthShape) {
      case RobotMouthShape.closed:
        // Bouche fermée calme (neutre / veille)
        final double hw = mouthHalfW * (0.65 - curiosity * 0.12);
        canvas.drawLine(
          Offset(mouthCx - hw, mouthY),
          Offset(mouthCx + hw, mouthY),
          strokePaint,
        );
        break;

      case RobotMouthShape.gentleSmile:
        // Petit sourire attentif (écoute / curieux)
        final path = Path()
          ..moveTo(mouthCx - mouthHalfW * 0.9, mouthY - h * 0.015)
          ..quadraticBezierTo(mouthCx, mouthY + h * 0.09, mouthCx + mouthHalfW * 0.9, mouthY - h * 0.015);
        canvas.drawPath(path, strokePaint);
        break;

      case RobotMouthShape.bigSmile:
        // Grand sourire chaleureux & enthousiaste (exactement comme Scène 3 du HTML)
        final double smileW = _lerp(mouthHalfW * 0.65, mouthHalfW * 1.45, happyMorph.clamp(0.5, 1.0));
        final double cornerY = mouthY - h * 0.03;
        final double ctrlY = mouthY + h * 0.16;
        final path = Path()
          ..moveTo(mouthCx - smileW, cornerY)
          ..quadraticBezierTo(mouthCx, ctrlY, mouthCx + smileW, cornerY);
        canvas.drawPath(
          path,
          Paint()
            ..color = featureColor.withOpacity(0.35)
            ..style = PaintingStyle.stroke
            ..strokeWidth = strokePaint.strokeWidth * 2.1
            ..strokeCap = StrokeCap.round
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
        );
        canvas.drawPath(path, strokePaint..strokeWidth = math.max(2.3, h * 0.068));
        break;

      case RobotMouthShape.talking:
        // Bouche animée multi-syllabes (parle : O / large A / semi-ouvert I / micro-pause)
        final double t = speakPhase;
        if (t < 0.25) {
          canvas.drawOval(
            Rect.fromCenter(center: Offset(mouthCx, mouthY), width: mouthHalfW * 0.95, height: h * 0.14),
            fillPaint,
          );
        } else if (t < 0.55) {
          final double openW = mouthHalfW * 1.25;
          final double openH = h * 0.14;
          final talkPath = Path()
            ..moveTo(mouthCx - openW, mouthY - openH * 0.25)
            ..quadraticBezierTo(mouthCx, mouthY - openH * 0.4, mouthCx + openW, mouthY - openH * 0.25)
            ..quadraticBezierTo(mouthCx, mouthY + openH * 0.95, mouthCx - openW, mouthY - openH * 0.25)
            ..close();
          canvas.drawPath(talkPath, fillPaint);
        } else if (t < 0.78) {
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromCenter(center: Offset(mouthCx, mouthY), width: mouthHalfW * 1.32, height: h * 0.075),
              Radius.circular(h * 0.04),
            ),
            fillPaint,
          );
        } else {
          final path = Path()
            ..moveTo(mouthCx - mouthHalfW * 0.8, mouthY)
            ..quadraticBezierTo(mouthCx, mouthY + h * 0.04, mouthCx + mouthHalfW * 0.8, mouthY);
          canvas.drawPath(path, strokePaint);
        }
        break;

      case RobotMouthShape.thinking:
        // Bouche pensive oscillante (réflexion / loading)
        final double shift = math.sin(ambientPhase * 2.0) * (w * 0.025);
        canvas.drawOval(
          Rect.fromCenter(center: Offset(mouthCx + shift, mouthY), width: mouthHalfW * 0.62, height: h * 0.085),
          strokePaint,
        );
        break;

      case RobotMouthShape.alert:
        // Bouche inquiète inversée (arrêt / erreur)
        final path = Path()
          ..moveTo(mouthCx - mouthHalfW * 0.85, mouthY + h * 0.045)
          ..quadraticBezierTo(mouthCx, mouthY - h * 0.05, mouthCx + mouthHalfW * 0.85, mouthY + h * 0.045);
        canvas.drawPath(path, strokePaint);
        break;
    }
  }

  @override
  bool shouldRepaint(covariant _HiarCeramicRobotPainter oldDelegate) => true;
}
