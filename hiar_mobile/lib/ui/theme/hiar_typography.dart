import 'package:flutter/material.dart';
import 'hiar_colors.dart';

/// Typographie officielle HIAR V4
class HiarTypography {
  HiarTypography._();

  static const TextStyle screenTitle = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w800,
    color: HiarColors.marine,
    letterSpacing: -0.5,
  );

  static const TextStyle cardTitle = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    color: HiarColors.marine,
  );

  static const TextStyle body = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w400,
    color: HiarColors.marine,
    height: 1.45,
  );

  static const TextStyle bodySecondary = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: HiarColors.text2,
  );

  static const TextStyle button = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.2,
  );

  static const TextStyle voiceTip = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: HiarColors.text2,
  );

  static const TextStyle voiceStatus = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w500,
    color: HiarColors.cyanSoft,
  );
}
