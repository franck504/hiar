import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

/// Expressions faciales animées du robot HIAR.
enum RobotFaceExpression {
  idle,      // Repos → bouche fermée calme
  listening, // Écoute active → léger sourire attentif
  thinking,  // Attente / chargement vocal → bouche pensive + barre de chargement
  speaking,  // Parole TTS → bouche animée multi-syllabes
  happy,     // Accueil / confirmation / succès → grand sourire radieux + yeux heureux
  emergency, // Arrêt / erreur → bouche inquiète + yeux d'alerte
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

/// Visage animé du robot HIAR (base bleue) :
/// - Petite croix médicale jaune sur le front qui bouge avec la tête et pulse doucement
/// - Clignement périodique naturel des yeux
/// - Mouvement fluide du regard (yeux qui bougent selon l'état)
/// - Formes de bouche variées selon le contexte : fermée, sourire, parle (syllabes), réflexion, alerte
/// - Inclinaison douce et flottement de la tête
class AnimatedRobotFace extends StatefulWidget {
  final RobotFaceExpression expression;
  final double width;
  final double height;
  final bool showLoadingRing;

  const AnimatedRobotFace({
    super.key,
    this.expression = RobotFaceExpression.idle,
    this.width = 76,
    this.height = 58,
    this.showLoadingRing = false,
  });

  @override
  State<AnimatedRobotFace> createState() => _AnimatedRobotFaceState();
}

class _AnimatedRobotFaceState extends State<AnimatedRobotFace>
    with TickerProviderStateMixin {
  late final AnimationController _ambientCtrl;
  late final AnimationController _speakCtrl;
  late final AnimationController _blinkCtrl;
  Timer? _blinkTimer;

  @override
  void initState() {
    super.initState();
    // Inclinaison douce de la tête + mouvement du regard + pulsation croix jaune (4.6 s)
    _ambientCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 4600),
    )..repeat();

    // Animation de parole (syllabes rapides ~780 ms)
    _speakCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 780),
    )..repeat();

    // Clignement naturel des paupières
    _blinkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 110),
    );

    _scheduleBlinkLoop();
  }

  void _scheduleBlinkLoop() {
    _blinkTimer?.cancel();
    _blinkTimer = Timer.periodic(const Duration(milliseconds: 3400), (_) {
      if (!mounted) return;
      if (widget.expression == RobotFaceExpression.emergency) return;
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
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool isThinking =
        widget.expression == RobotFaceExpression.thinking || widget.showLoadingRing;
    final bool isEmergency = widget.expression == RobotFaceExpression.emergency;
    final bool isHappy = widget.expression == RobotFaceExpression.happy;
    final bool isSpeaking = widget.expression == RobotFaceExpression.speaking;
    final bool isListening = widget.expression == RobotFaceExpression.listening;

    final Color glowColor = isEmergency
        ? HiarColors.err
        : (isHappy
            ? HiarColors.cyanSoft
            : (isThinking ? HiarColors.cyan : HiarColors.azur));

    return AnimatedBuilder(
      animation: Listenable.merge([_ambientCtrl, _speakCtrl, _blinkCtrl]),
      builder: (context, _) {
        final double phase = _ambientCtrl.value * 2 * math.pi;
        final double speakPhase = _speakCtrl.value;
        final double blink = _blinkCtrl.value;

        // 1. Inclinaison de la tête (radians) + léger flottement vertical
        double tiltRad;
        double floatY;
        if (isEmergency) {
          tiltRad = 0.0;
          floatY = 0.0;
        } else if (isThinking) {
          tiltRad = 0.09 * math.sin(phase * 1.5);
          floatY = -2.0 * math.sin(phase * 2.0);
        } else if (isListening) {
          tiltRad = 0.068 * math.sin(phase);
          floatY = -1.8 * math.sin(phase);
        } else if (isSpeaking) {
          tiltRad = 0.055 * math.sin(phase * 2.0);
          floatY = -2.2 * math.sin(speakPhase * math.pi).abs();
        } else if (isHappy) {
          tiltRad = 0.08 * math.sin(phase * 1.5);
          floatY = -2.4 * math.sin(phase * 2.0);
        } else {
          tiltRad = 0.045 * math.sin(phase);
          floatY = -1.6 * math.sin(phase);
        }

        // 2. Déplacement horizontal/vertical du regard (yeux qui bougent)
        double lookX = 0.0;
        double lookY = 0.0;
        if (isThinking) {
          lookX = math.sin(phase * 2.0) * 1.0;
          lookY = -0.3;
        } else if (isListening) {
          lookX = math.sin(phase) * 0.35;
          lookY = 0.0;
        } else if (isEmergency) {
          lookX = 0.0;
          lookY = 0.0;
        } else {
          lookX = math.sin(phase) * 0.72;
          lookY = math.cos(phase * 2.0) * 0.25;
        }

        final double radius = widget.height * 0.32;

        return Transform.translate(
          offset: Offset(0, floatY),
          child: Transform.rotate(
            angle: tiltRad,
            child: Stack(
              alignment: Alignment.center,
              clipBehavior: Clip.none,
              children: [
                // Halo lumineux bleu derrière la tête
                Container(
                  width: widget.width + 10,
                  height: widget.height + 10,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(radius + 5),
                    boxShadow: [
                      BoxShadow(
                        color: glowColor.withOpacity(isThinking || isListening ? 0.42 : 0.24),
                        blurRadius: isThinking || isListening ? 18 : 13,
                        spreadRadius: isThinking ? 1.5 : 0.5,
                      ),
                    ],
                  ),
                ),

                // Boîtier de tête HIAR BLEU médical + reflet verre
                Container(
                  width: widget.width,
                  height: widget.height,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: isEmergency
                          ? const [Color(0xFF4C1414), Color(0xFF8A1C1C)]
                          : const [HiarColors.textPrimary, HiarColors.secondaryDark, HiarColors.secondary],
                    ),
                    borderRadius: BorderRadius.circular(radius),
                    border: Border.all(
                      color: (isEmergency ? HiarColors.err : HiarColors.cyan).withOpacity(0.9),
                      width: widget.width > 100 ? 3.5 : 2.2,
                    ),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(radius - 2),
                    child: CustomPaint(
                      painter: _RobotFacePainter(
                        expression: widget.expression,
                        mouthShape: mouthShapeForExpression(widget.expression),
                        lookX: lookX,
                        lookY: lookY,
                        blink: blink,
                        speakPhase: speakPhase,
                        ambientPhase: phase,
                        spinnerPhase: _ambientCtrl.value,
                        showLoadingRing: isThinking,
                        glowColor: glowColor,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _RobotFacePainter extends CustomPainter {
  final RobotFaceExpression expression;
  final RobotMouthShape mouthShape;
  final double lookX;
  final double lookY;
  final double blink;
  final double speakPhase;
  final double ambientPhase;
  final double spinnerPhase;
  final bool showLoadingRing;
  final Color glowColor;

  _RobotFacePainter({
    required this.expression,
    required this.mouthShape,
    required this.lookX,
    required this.lookY,
    required this.blink,
    required this.speakPhase,
    required this.ambientPhase,
    required this.spinnerPhase,
    required this.showLoadingRing,
    required this.glowColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // 1. Reflet verre doux en haut de la visière bleue
    final sheenPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Colors.white.withOpacity(0.20),
          Colors.white.withOpacity(0.0),
        ],
      ).createShader(Rect.fromLTWH(0, 0, w, h * 0.45));
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h * 0.45), sheenPaint);

    // 2. Petite croix médicale JAUNE sur le front qui bouge (parallaxe + oscillation douce + pulsation)
    _paintYellowForeheadCross(canvas, w, h);

    final Color featureColor = expression == RobotFaceExpression.emergency
        ? const Color(0xFFFFB4B4)
        : HiarColors.cyanSoft;

    final eyePaint = Paint()
      ..color = featureColor
      ..style = PaintingStyle.fill;

    // Décalage du regard
    final double dx = lookX * (w * 0.055);
    final double dy = lookY * (h * 0.05);

    // Yeux abaissés légèrement pour laisser un beau front à la croix jaune
    final double eyeY = h * 0.46 + dy;
    final double leftEyeX = w * 0.32 + dx;
    final double rightEyeX = w * 0.68 + dx;
    final double eyeW = w * 0.135;
    final double fullEyeH = h * 0.22;
    final double currentEyeH = math.max(h * 0.032, fullEyeH * (1.0 - blink * 0.88));

    // 3. Yeux (selon expression)
    if (expression == RobotFaceExpression.happy && blink < 0.5) {
      final arcPaint = Paint()
        ..color = featureColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(2.2, h * 0.062)
        ..strokeCap = StrokeCap.round;

      for (final cx in [leftEyeX, rightEyeX]) {
        final rect = Rect.fromCenter(
          center: Offset(cx, eyeY + 2),
          width: eyeW * 1.15,
          height: fullEyeH * 0.85,
        );
        canvas.drawArc(rect, math.pi * 1.12, math.pi * 0.76, false, arcPaint);
      }
    } else if (expression == RobotFaceExpression.emergency) {
      for (final cx in [leftEyeX, rightEyeX]) {
        final rect = RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(cx, eyeY), width: eyeW * 1.12, height: fullEyeH * 0.46),
          Radius.circular(eyeW * 0.35),
        );
        canvas.drawRRect(rect, eyePaint);
      }
    } else {
      final double scaleY = expression == RobotFaceExpression.listening ? 1.12 : 1.0;
      final double finalH = currentEyeH * scaleY;
      for (final cx in [leftEyeX, rightEyeX]) {
        final rect = RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(cx, eyeY), width: eyeW, height: finalH),
          Radius.circular(eyeW * 0.45),
        );
        canvas.drawRRect(rect, eyePaint);

        if (blink < 0.35) {
          final glintPaint = Paint()..color = Colors.white.withOpacity(0.88);
          canvas.drawCircle(
            Offset(cx - eyeW * 0.18, eyeY - finalH * 0.22),
            math.max(1.2, eyeW * 0.16),
            glintPaint,
          );
        }
      }
    }

    // 4. Bouche conditionnée selon les cas (fermée, sourire, parle, réflexion, alerte)
    _paintMouth(canvas, w, h, dx, dy, featureColor);

    // 5. Barre de progression subtile tout en bas en mode réflexion / chargement
    if (showLoadingRing) {
      final barY = h - 3.0;
      final trackPaint = Paint()
        ..color = Colors.white.withOpacity(0.16)
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(w * 0.12, barY), Offset(w * 0.88, barY), trackPaint);

      final sweepW = w * 0.28;
      final startX = w * 0.12 +
          (w * 0.76 - sweepW) * ((math.sin(spinnerPhase * 2 * math.pi * 1.5) + 1) / 2);
      final activePaint = Paint()
        ..color = HiarColors.robotCrossYellow
        ..strokeWidth = 2.8
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(startX, barY), Offset(startX + sweepW, barY), activePaint);
    }
  }

  /// Dessine la petite croix médicale JAUNE sur le front du robot (mobile + pulsation).
  void _paintYellowForeheadCross(Canvas canvas, double w, double h) {
    final double cx = w * 0.5 + lookX * (w * 0.028) + math.sin(ambientPhase * 1.5) * (w * 0.012);
    final double cy = h * 0.175 + math.cos(ambientPhase * 2.0) * (h * 0.015);
    final double pulse = 1.0 + 0.10 * math.sin(ambientPhase * 2.0);
    final double armLen = math.max(5.5, h * 0.145) * pulse;
    final double armThick = math.max(2.1, armLen * 0.36);

    // Halo doré doux
    final haloPaint = Paint()
      ..color = HiarColors.robotCrossYellow.withOpacity(0.32)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
    canvas.drawCircle(Offset(cx, cy), armLen * 0.72, haloPaint);

    // Rotation très subtile de la croix jaune lors du mouvement de tête
    canvas.save();
    canvas.translate(cx, cy);
    canvas.rotate(0.08 * math.sin(ambientPhase * 1.5));

    final crossPaint = Paint()
      ..color = HiarColors.robotCrossYellow
      ..style = PaintingStyle.fill;

    // Barre verticale
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset.zero, width: armThick, height: armLen),
        Radius.circular(armThick * 0.35),
      ),
      crossPaint,
    );
    // Barre horizontale
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset.zero, width: armLen, height: armThick),
        Radius.circular(armThick * 0.35),
      ),
      crossPaint,
    );
    canvas.restore();
  }

  /// Dessine les différentes formes de bouche selon le contexte.
  void _paintMouth(
    Canvas canvas,
    double w,
    double h,
    double dx,
    double dy,
    Color featureColor,
  ) {
    final double mouthCx = w * 0.5 + dx * 0.35;
    final double mouthY = h * 0.75 + dy * 0.3;
    final double mouthHalfW = w * 0.145;

    final strokePaint = Paint()
      ..color = featureColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(2.0, h * 0.052)
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final fillPaint = Paint()
      ..color = featureColor.withOpacity(0.92)
      ..style = PaintingStyle.fill;

    switch (mouthShape) {
      case RobotMouthShape.closed:
        // 1. BOUCHE FERMÉE (repos / neutre) : ligne horizontale douce fermée
        canvas.drawLine(
          Offset(mouthCx - mouthHalfW * 0.85, mouthY),
          Offset(mouthCx + mouthHalfW * 0.85, mouthY),
          strokePaint,
        );
        break;

      case RobotMouthShape.gentleSmile:
        // 2. SOURIRE DOUX ATTENTIF (en écoute)
        final path = Path()
          ..moveTo(mouthCx - mouthHalfW, mouthY - h * 0.025)
          ..quadraticBezierTo(mouthCx, mouthY + h * 0.095, mouthCx + mouthHalfW, mouthY - h * 0.025);
        canvas.drawPath(path, strokePaint);
        break;

      case RobotMouthShape.bigSmile:
        // 3. GRAND SOURIRE OUVERT RADIEUX (happy / accueil / ticket confirmé)
        final double smileW = mouthHalfW * 1.32;
        final double depth = h * 0.145;
        final smilePath = Path()
          ..moveTo(mouthCx - smileW, mouthY - depth * 0.25)
          ..quadraticBezierTo(mouthCx, mouthY + depth, mouthCx + smileW, mouthY - depth * 0.25)
          ..close();
        canvas.drawPath(smilePath, fillPaint);
        canvas.drawPath(smilePath, strokePaint..strokeWidth = math.max(1.5, h * 0.035));
        break;

      case RobotMouthShape.talking:
        // 4. BOUCHE QUI PARLE (cycle multi-syllabes fluide : O, large D, mi-fermée, ouverte)
        final double t = speakPhase;
        if (t < 0.25) {
          // Syllabe ronde "O"
          final oval = Rect.fromCenter(
            center: Offset(mouthCx, mouthY + h * 0.01),
            width: mouthHalfW * 0.95,
            height: h * 0.14,
          );
          canvas.drawOval(oval, fillPaint);
        } else if (t < 0.55) {
          // Syllabe large ouverte souriante "A / E"
          final double openW = mouthHalfW * 1.25;
          final double openH = h * 0.14;
          final talkPath = Path()
            ..moveTo(mouthCx - openW, mouthY - openH * 0.25)
            ..quadraticBezierTo(mouthCx, mouthY - openH * 0.4, mouthCx + openW, mouthY - openH * 0.25)
            ..quadraticBezierTo(mouthCx, mouthY + openH * 0.95, mouthCx - openW, mouthY - openH * 0.25)
            ..close();
          canvas.drawPath(talkPath, fillPaint);
        } else if (t < 0.78) {
          // Syllabe semi-ouverte "I"
          final rect = RRect.fromRectAndRadius(
            Rect.fromCenter(
              center: Offset(mouthCx, mouthY),
              width: mouthHalfW * 1.35,
              height: h * 0.075,
            ),
            Radius.circular(h * 0.04),
          );
          canvas.drawRRect(rect, fillPaint);
        } else {
          // Micro-pause entre syllabes (presque fermée)
          final path = Path()
            ..moveTo(mouthCx - mouthHalfW * 0.85, mouthY)
            ..quadraticBezierTo(mouthCx, mouthY + h * 0.04, mouthCx + mouthHalfW * 0.85, mouthY);
          canvas.drawPath(path, strokePaint);
        }
        break;

      case RobotMouthShape.thinking:
        // 5. RÉFLEXION / LOADING : petite bouche pensive oscillante + points
        final double shift = math.sin(ambientPhase * 2.0) * (w * 0.025);
        final oval = Rect.fromCenter(
          center: Offset(mouthCx + shift, mouthY + h * 0.01),
          width: mouthHalfW * 0.65,
          height: h * 0.085,
        );
        canvas.drawOval(oval, strokePaint);
        break;

      case RobotMouthShape.alert:
        // 6. ALERTE / ARRÊT D'URGENCE : bouche inquiète inversée
        final path = Path()
          ..moveTo(mouthCx - mouthHalfW * 0.85, mouthY + h * 0.045)
          ..quadraticBezierTo(mouthCx, mouthY - h * 0.05, mouthCx + mouthHalfW * 0.85, mouthY + h * 0.045);
        canvas.drawPath(path, strokePaint);
        break;
    }
  }

  @override
  bool shouldRepaint(covariant _RobotFacePainter oldDelegate) => true;
}
