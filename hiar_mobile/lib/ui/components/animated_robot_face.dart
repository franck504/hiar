import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

/// Expressions faciales animées du robot HIAR.
enum RobotFaceExpression {
  idle,
  listening,
  thinking,
  speaking,
  happy,
  emergency,
}

/// Convertit une chaîne `face_expression` venant du serveur en [RobotFaceExpression].
RobotFaceExpression parseRobotFaceExpression(String? raw, {RobotFaceExpression fallback = RobotFaceExpression.idle}) {
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
      return RobotFaceExpression.idle;
    default:
      return fallback;
  }
}

/// Visage animé du robot HIAR :
/// - Clignement périodique naturel des yeux
/// - Mouvement fluide du regard (yeux qui bougent selon l'état)
/// - Sourire animé (parle, sourit, réfléchit ou alerte)
/// - Inclinaison douce et flottement de la tête
/// - Halo de chargement orbital en mode `thinking`
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
    // Inclinaison douce de la tête + mouvement du regard (cycle continu 4.6 s)
    _ambientCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 4600),
    )..repeat();

    // Animation bouche parlante / balayage rapide en réflexion (650 ms)
    _speakCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 650),
    )..repeat(reverse: true);

    // Clignement naturel des paupières (160 ms aller-retour)
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
            ? HiarColors.emerald
            : (isThinking ? HiarColors.cyan : HiarColors.cyanSoft));

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
          tiltRad = 0.085 * math.sin(phase * 1.5); // ~5° curieux
          floatY = -2.0 * math.sin(phase * 2.0);
        } else if (isListening) {
          tiltRad = 0.065 * math.sin(phase); // inclinaison attentive
          floatY = -1.8 * math.sin(phase);
        } else if (isSpeaking) {
          tiltRad = 0.05 * math.sin(phase * 2.0);
          floatY = -2.4 * speakPhase;
        } else if (isHappy) {
          tiltRad = 0.075 * math.sin(phase * 1.5);
          floatY = -2.2 * math.sin(phase * 2.0);
        } else {
          tiltRad = 0.045 * math.sin(phase);
          floatY = -1.6 * math.sin(phase);
        }

        // 2. Déplacement horizontal/vertical du regard (yeux qui bougent)
        double lookX = 0.0;
        double lookY = 0.0;
        if (isThinking) {
          lookX = math.sin(phase * 2.0) * 1.0; // scan gauche ↔ droite
          lookY = -0.35;
        } else if (isListening) {
          lookX = math.sin(phase) * 0.35;
          lookY = 0.0;
        } else if (isEmergency) {
          lookX = 0.0;
          lookY = 0.0;
        } else {
          lookX = math.sin(phase) * 0.7;
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
                // Halo lumineux doux derrière la tête
                Container(
                  width: widget.width + 10,
                  height: widget.height + 10,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(radius + 5),
                    boxShadow: [
                      BoxShadow(
                        color: glowColor.withOpacity(isThinking || isListening ? 0.38 : 0.20),
                        blurRadius: isThinking || isListening ? 18 : 12,
                        spreadRadius: isThinking ? 1.5 : 0.5,
                      ),
                    ],
                  ),
                ),

                // Boîtier de tête HIAR (dégradé Ardoise → Sarcelle + reflet verre)
                Container(
                  width: widget.width,
                  height: widget.height,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: isEmergency
                          ? const [Color(0xFF4C1414), Color(0xFF7F1D1D)]
                          : const [Color(0xFF163242), Color(0xFF135E63)],
                    ),
                    borderRadius: BorderRadius.circular(radius),
                    border: Border.all(
                      color: glowColor.withOpacity(0.85),
                      width: widget.width > 100 ? 3.5 : 2.2,
                    ),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(radius - 2),
                    child: CustomPaint(
                      painter: _RobotFacePainter(
                        expression: widget.expression,
                        lookX: lookX,
                        lookY: lookY,
                        blink: blink,
                        speakPhase: speakPhase,
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
  final double lookX;
  final double lookY;
  final double blink;
  final double speakPhase;
  final double spinnerPhase;
  final bool showLoadingRing;
  final Color glowColor;

  _RobotFacePainter({
    required this.expression,
    required this.lookX,
    required this.lookY,
    required this.blink,
    required this.speakPhase,
    required this.spinnerPhase,
    required this.showLoadingRing,
    required this.glowColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // 1. Reflet verre doux en haut de la visière
    final sheenPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Colors.white.withOpacity(0.18),
          Colors.white.withOpacity(0.0),
        ],
      ).createShader(Rect.fromLTWH(0, 0, w, h * 0.45));
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h * 0.45), sheenPaint);

    final Color featureColor = expression == RobotFaceExpression.emergency
        ? const Color(0xFFFFB4B4)
        : HiarColors.cyanSoft;

    final eyePaint = Paint()
      ..color = featureColor
      ..style = PaintingStyle.fill;

    // Décalage du regard
    final double dx = lookX * (w * 0.055);
    final double dy = lookY * (h * 0.055);

    final double eyeY = h * 0.39 + dy;
    final double leftEyeX = w * 0.33 + dx;
    final double rightEyeX = w * 0.67 + dx;
    final double eyeW = w * 0.135;
    final double fullEyeH = h * 0.24;
    final double currentEyeH = math.max(h * 0.035, fullEyeH * (1.0 - blink * 0.88));

    // 2. Yeux (selon expression)
    if (expression == RobotFaceExpression.happy && blink < 0.5) {
      // Yeux souriants en arcs heureux ^ ^
      final arcPaint = Paint()
        ..color = featureColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(2.2, h * 0.065)
        ..strokeCap = StrokeCap.round;

      for (final cx in [leftEyeX, rightEyeX]) {
        final rect = Rect.fromCenter(center: Offset(cx, eyeY + 2), width: eyeW * 1.15, height: fullEyeH * 0.85);
        canvas.drawArc(rect, math.pi * 1.12, math.pi * 0.76, false, arcPaint);
      }
    } else if (expression == RobotFaceExpression.emergency) {
      // Yeux plissés d'alerte
      for (final cx in [leftEyeX, rightEyeX]) {
        final rect = RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(cx, eyeY), width: eyeW * 1.1, height: fullEyeH * 0.48),
          Radius.circular(eyeW * 0.35),
        );
        canvas.drawRRect(rect, eyePaint);
      }
    } else {
      // Yeux expressifs arrondis avec petit reflet blanc
      final double scaleY = expression == RobotFaceExpression.listening ? 1.12 : 1.0;
      final double finalH = currentEyeH * scaleY;
      for (final cx in [leftEyeX, rightEyeX]) {
        final rect = RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(cx, eyeY), width: eyeW, height: finalH),
          Radius.circular(eyeW * 0.45),
        );
        canvas.drawRRect(rect, eyePaint);

        if (blink < 0.35) {
          final glintPaint = Paint()..color = Colors.white.withOpacity(0.85);
          canvas.drawCircle(
            Offset(cx - eyeW * 0.18, eyeY - finalH * 0.22),
            math.max(1.2, eyeW * 0.16),
            glintPaint,
          );
        }
      }
    }

    // 3. Sourire / Bouche animée
    final mouthPaint = Paint()
      ..color = featureColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(2.0, h * 0.055)
      ..strokeCap = StrokeCap.round;

    final double mouthY = h * 0.70 + dy * 0.35;
    final double mouthHalfW = w * 0.15;

    if (expression == RobotFaceExpression.emergency) {
      // Bouche droite / inquiète
      final path = Path()
        ..moveTo(w * 0.5 - mouthHalfW * 0.8, mouthY + h * 0.04)
        ..quadraticBezierTo(w * 0.5, mouthY - h * 0.03, w * 0.5 + mouthHalfW * 0.8, mouthY + h * 0.04);
      canvas.drawPath(path, mouthPaint);
    } else if (expression == RobotFaceExpression.thinking) {
      // 3 petits points animés de chargement sous les yeux
      final dotPaint = Paint()..style = PaintingStyle.fill;
      for (int i = 0; i < 3; i++) {
        final wave = math.sin((spinnerPhase * 2 * math.pi * 2.0) - i * 0.9);
        final lift = wave > 0 ? -wave * h * 0.055 : 0.0;
        final alpha = (0.45 + 0.55 * ((wave + 1) / 2)).clamp(0.35, 1.0);
        dotPaint.color = featureColor.withOpacity(alpha);
        final cx = w * (0.38 + i * 0.12);
        canvas.drawCircle(Offset(cx, mouthY + lift), math.max(2.0, w * 0.03), dotPaint);
      }
    } else if (expression == RobotFaceExpression.speaking) {
      // Bouche qui s'ouvre et sourit au rythme de la voix
      final double openH = h * (0.04 + 0.11 * speakPhase);
      final mouthRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(w * 0.5, mouthY), width: mouthHalfW * 1.45, height: openH),
        Radius.circular(openH),
      );
      final fillPaint = Paint()
        ..color = featureColor.withOpacity(0.92)
        ..style = PaintingStyle.fill;
      canvas.drawRRect(mouthRect, fillPaint);
    } else {
      // Sourire doux (plus large en mode happy ou listening)
      final double curveDepth = expression == RobotFaceExpression.happy
          ? h * 0.14
          : (expression == RobotFaceExpression.listening ? h * 0.10 : h * 0.085);
      final double halfW = expression == RobotFaceExpression.happy
          ? mouthHalfW * 1.25
          : mouthHalfW;
      final path = Path()
        ..moveTo(w * 0.5 - halfW, mouthY - curveDepth * 0.25)
        ..quadraticBezierTo(w * 0.5, mouthY + curveDepth, w * 0.5 + halfW, mouthY - curveDepth * 0.25);
      canvas.drawPath(path, mouthPaint);
    }

    // 4. Ligne de progression subtile tout en bas en mode réflexion / chargement
    if (showLoadingRing) {
      final barY = h - 3.0;
      final trackPaint = Paint()
        ..color = Colors.white.withOpacity(0.14)
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(w * 0.12, barY), Offset(w * 0.88, barY), trackPaint);

      final sweepW = w * 0.28;
      final startX = w * 0.12 + (w * 0.76 - sweepW) * ((math.sin(spinnerPhase * 2 * math.pi * 1.5) + 1) / 2);
      final activePaint = Paint()
        ..color = glowColor
        ..strokeWidth = 2.8
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(startX, barY), Offset(startX + sweepW, barY), activePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _RobotFacePainter oldDelegate) => true;
}
