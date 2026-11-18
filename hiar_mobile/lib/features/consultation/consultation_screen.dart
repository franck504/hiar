import 'dart:async';
import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/components/action_button.dart';
import '../../ui/components/vitals_tutorial_player.dart';
import '../../ui/rail/voice_rail.dart';
import '../../ui/theme/hiar_colors.dart';

class ConsultationScreen extends StatefulWidget {
  final int initialStep;
  final Map<String, dynamic> dynamicFields;
  final VoiceState voiceState;
  final String voiceStatus;
  final String? recognizedText;
  final String? voiceTip;
  final VoidCallback? onMicTap;
  final VoidCallback? onSettingsTap;
  final bool isRobotConnected;
  final ValueChanged<int>? onStepChanged;
  final VoidCallback? onRequestMeasure;
  final ValueChanged<Map<String, dynamic>>? onConfirmAppointment;
  final VoidCallback onCancel;
  final VoidCallback onFinish;

  const ConsultationScreen({
    super.key,
    this.initialStep = 1,
    this.dynamicFields = const {},
    this.voiceState = VoiceState.idle,
    this.voiceStatus = "J'écoute en continu…",
    this.recognizedText,
    this.voiceTip,
    this.onMicTap,
    this.onSettingsTap,
    this.isRobotConnected = true,
    this.onStepChanged,
    this.onRequestMeasure,
    this.onConfirmAppointment,
    required this.onCancel,
    required this.onFinish,
  });

  @override
  State<ConsultationScreen> createState() => _ConsultationScreenState();
}

class _ConsultationScreenState extends State<ConsultationScreen> {
  int _currentStep = 1;

  // Données du formulaire
  String? _selectedReason = 'consultation_generale';
  String? _selectedDoctor = 'A';
  String? _selectedPeriod = 'MAT';
  final _nameController = TextEditingController(text: "Jean Dupont");
  final _phoneController = TextEditingController(text: "0341234567");

  // Signes vitaux dynamiques (mis à jour par le Raspberry Pi 4 / ROS 2 / ESP32)
  bool _vitalsRunning = false;
  bool _vitalsSuccess = false;
  String? _vitalsError;
  Timer? _vitalsTimeoutTimer;
  double? _temperatureC;
  int? _heartRateBpm;
  int? _spo2Percent;
  int _tutorialIndex = 0;

  // Ticket généré
  String? _ticketLabel;
  bool _isSubmitting = false;
  String? _submitError;

  @override
  void initState() {
    super.initState();
    _currentStep = widget.initialStep;
    final hour = DateTime.now().hour;
    if (hour >= 12) {
      _selectedDoctor = 'B';
      _selectedPeriod = 'AM';
    } else {
      _selectedDoctor = 'A';
      _selectedPeriod = 'MAT';
    }
    _syncFields();
  }

  @override
  void didUpdateWidget(covariant ConsultationScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialStep != oldWidget.initialStep && widget.initialStep != _currentStep) {
      setState(() {
        _currentStep = widget.initialStep;
      });
    }
    _syncFields();
  }

  @override
  void dispose() {
    _vitalsTimeoutTimer?.cancel();
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  void _syncFields() {
    final fields = widget.dynamicFields;
    if (fields.containsKey('temperature')) {
      final val = fields['temperature'];
      if (val == null) {
        _temperatureC = null;
      } else {
        final raw = val.toString().split(' ').first.trim();
        if (raw == '--' || raw == '—' || raw.toUpperCase() == 'NA') {
          _temperatureC = null;
        } else {
          _temperatureC = double.tryParse(raw) ?? _temperatureC;
        }
      }
    }
    if (fields.containsKey('heart_rate')) {
      final val = fields['heart_rate'];
      if (val == null) {
        _heartRateBpm = null;
      } else {
        final raw = val.toString().split(' ').first.trim();
        if (raw == '--' || raw == '—' || raw.toUpperCase() == 'NA') {
          _heartRateBpm = null;
        } else {
          _heartRateBpm = int.tryParse(raw) ?? _heartRateBpm;
        }
      }
    }
    if (fields.containsKey('spo2')) {
      final val = fields['spo2'];
      if (val == null) {
        _spo2Percent = null;
      } else {
        final raw = val.toString().split(' ').first.trim();
        if (raw == '--' || raw == '—' || raw.toUpperCase() == 'NA') {
          _spo2Percent = null;
        } else {
          _spo2Percent = int.tryParse(raw) ?? _spo2Percent;
        }
      }
    }
    if (fields.containsKey('patient_name') && fields['patient_name'] != null) {
      _nameController.text = fields['patient_name'].toString();
    }
    if (fields.containsKey('patient_phone') && fields['patient_phone'] != null) {
      _phoneController.text = fields['patient_phone'].toString();
    }
    if (fields.containsKey('ticket_label') && fields['ticket_label'] != null) {
      _ticketLabel = fields['ticket_label'].toString();
      _isSubmitting = false;
      _submitError = null;
      _currentStep = 6;
    }
    if (fields.containsKey('booking_error') && fields['booking_error'] != null) {
      _submitError = fields['booking_error'].toString();
      _isSubmitting = false;
    }
    if (fields.containsKey('selected_reason') && fields['selected_reason'] != null) {
      _selectedReason = fields['selected_reason'].toString();
    }
    if (fields.containsKey('vitals_state')) {
      final state = fields['vitals_state'].toString();
      if (state == 'measuring') {
        _vitalsRunning = true;
        _vitalsError = null;
        _vitalsSuccess = false;
      } else if (state == 'done') {
        _vitalsRunning = false;
        _vitalsTimeoutTimer?.cancel();
        _vitalsSuccess = true;
        _vitalsError = null;
      } else if (state == 'error') {
        _vitalsRunning = false;
        _vitalsTimeoutTimer?.cancel();
        _vitalsSuccess = false;
        _vitalsError = fields['vitals_error']?.toString() ??
            "Mesure interrompue ou capteur non détecté. Veuillez replacer votre doigt.";
      } else if (state == 'reset' || state == 'cleared') {
        _vitalsRunning = false;
        _vitalsTimeoutTimer?.cancel();
        _temperatureC = null;
        _heartRateBpm = null;
        _spo2Percent = null;
        _vitalsSuccess = false;
        _vitalsError = null;
      }
    }
  }

  void _startVitalsMeasurement() {
    setState(() {
      _vitalsRunning = true;
      _vitalsSuccess = false;
      _vitalsError = null;
      _temperatureC = null;
      _heartRateBpm = null;
      _spo2Percent = null;
    });

    widget.onRequestMeasure?.call();

    // Timeout de sécurité de 35s (en phase avec le timeout de 32s de l'ESP32)
    _vitalsTimeoutTimer?.cancel();
    _vitalsTimeoutTimer = Timer(const Duration(seconds: 35), () {
      if (mounted && _vitalsRunning) {
        setState(() {
          _vitalsRunning = false;
          _vitalsError = "Délai d'attente dépassé. Vérifiez la connexion du capteur ESP32.";
        });
      }
    });
  }

  void _nextStep() {
    if (_currentStep < 5) {
      setState(() {
        _currentStep++;
        _submitError = null;
      });
      widget.onStepChanged?.call(_currentStep);
    } else {
      // Confirmation finale -> Envoi au serveur pour enregistrement réel en base SQLite
      _confirmAndBook();
    }
  }

  void _confirmAndBook() {
    setState(() {
      _isSubmitting = true;
      _submitError = null;
    });

    final payload = {
      'patient_name': _nameController.text.trim().isEmpty ? 'Jean Dupont' : _nameController.text.trim(),
      'contact': _phoneController.text.trim().isEmpty ? '0341234567' : _phoneController.text.trim(),
      'reason_code': _selectedReason ?? 'consultation_generale',
      'doctor_code': _selectedDoctor ?? 'A',
      'period': _selectedPeriod ?? 'MAT',
      'temperature_c': _temperatureC,
      'heart_rate_bpm': _heartRateBpm,
      'spo2_percent': _spo2Percent,
    };

    if (widget.onConfirmAppointment != null) {
      widget.onConfirmAppointment!(payload);
    } else {
      setState(() {
        _ticketLabel = "$_selectedDoctor-$_selectedPeriod-1";
        _currentStep = 6;
        _isSubmitting = false;
      });
      widget.onStepChanged?.call(6);
    }
  }

  void _prevStep() {
    setState(() {
      if (_currentStep > 1) {
        _currentStep--;
        widget.onStepChanged?.call(_currentStep);
      } else {
        widget.onCancel();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_currentStep == 6) {
      return _buildTicketScreen();
    }

    final titles = {
      1: "Motif de consultation",
      2: "Médecin et période",
      3: "Vos coordonnées",
      4: "Signes vitaux (facultatifs)",
      5: "Vérification et confirmation",
    };

    final defaultTips = {
      1: "Dites : « Générale », « Suivi » ou « Annuler »",
      2: "Dites : « Médecin A », « Médecin B » ou « Suivant »",
      3: "Dites : « Continuer » ou « Précédent »",
      4: "Dites : « Mesurer », « Suivant » ou « Passer »",
      5: "Dites : « Confirmer » ou « Annuler »",
    };

    return LandscapeScaffold(
      title: titles[_currentStep] ?? "Consultation",
      step: "Étape $_currentStep sur 5",
      onBack: _prevStep,
      voiceState: widget.voiceState,
      voiceStatus: widget.voiceStatus,
      recognizedText: widget.recognizedText,
      voiceTip: widget.voiceTip ?? defaultTips[_currentStep],
      onMicTap: widget.onMicTap,
      onSettingsTap: widget.onSettingsTap,
      isRobotConnected: widget.isRobotConnected,
      body: _buildStepContent(),
      bottomBar: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Flexible(
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                side: const BorderSide(color: HiarColors.border),
              ),
              onPressed: widget.onCancel,
              child: const Text(
                "Annuler (🎤 « Annuler »)",
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: HiarColors.text2),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Flexible(
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: HiarColors.azur,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: _isSubmitting ? null : _nextStep,
              child: _isSubmitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                    )
                  : Text(
                      _currentStep == 5 ? "Confirmer (🎤 « Confirmer »)" : "Continuer (🎤 « Suivant »)",
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStepContent() {
    Widget content;
    switch (_currentStep) {
      case 1:
        content = _buildReasonStep();
        break;
      case 2:
        content = _buildDoctorStep();
        break;
      case 3:
        content = _buildContactStep();
        break;
      case 4:
        content = _buildVitalsStep();
        break;
      case 5:
        content = _buildReviewStep();
        break;
      default:
        content = const SizedBox.shrink();
    }
    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      child: content,
    );
  }

  // Étape 1 : Motif
  Widget _buildReasonStep() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ActionButton(
              label: "Consultation générale",
              subtitle: "Premier avis ou consultation médicale courante",
              voiceHint: "Générale",
              isSelected: _selectedReason == 'consultation_generale',
              onTap: () => setState(() => _selectedReason = 'consultation_generale'),
            ),
            const SizedBox(height: 12),
            ActionButton(
              label: "Suivi médical",
              subtitle: "Visite de contrôle ou renouvellement d'ordonnance",
              voiceHint: "Suivi",
              isSelected: _selectedReason == 'suivi_medical',
              onTap: () => setState(() => _selectedReason = 'suivi_medical'),
            ),
            const SizedBox(height: 12),
            ActionButton(
              label: "Autre motif",
              subtitle: "Certificat, avis spécifique ou orientation",
              voiceHint: "Autre",
              isSelected: _selectedReason == 'autre_motif',
              onTap: () => setState(() => _selectedReason = 'autre_motif'),
            ),
          ],
        ),
      ),
    );
  }

  // Étape 2 : Médecin et Période
  Widget _buildDoctorStep() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 620),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                Expanded(
                  child: ActionButton(
                    label: "Médecin A (Matin)",
                    subtitle: "08 h 00 – 12 h 00",
                    voiceHint: "Médecin A",
                    isSelected: _selectedDoctor == 'A' && _selectedPeriod == 'MAT',
                    onTap: () => setState(() {
                      _selectedDoctor = 'A';
                      _selectedPeriod = 'MAT';
                    }),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ActionButton(
                    label: "Médecin B (Après-midi)",
                    subtitle: "13 h 00 – 18 h 00",
                    voiceHint: "Médecin B",
                    isSelected: _selectedDoctor == 'B' && _selectedPeriod == 'AM',
                    onTap: () => setState(() {
                      _selectedDoctor = 'B';
                      _selectedPeriod = 'AM';
                    }),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ActionButton(
                    label: "Médecin C (Matin)",
                    subtitle: "08 h 00 – 12 h 00",
                    voiceHint: "Médecin C",
                    isSelected: _selectedDoctor == 'C' && _selectedPeriod == 'MAT',
                    onTap: () => setState(() {
                      _selectedDoctor = 'C';
                      _selectedPeriod = 'MAT';
                    }),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ActionButton(
                    label: "Médecin D (Après-midi)",
                    subtitle: "13 h 00 – 18 h 00",
                    voiceHint: "Médecin D",
                    isSelected: _selectedDoctor == 'D' && _selectedPeriod == 'AM',
                    onTap: () => setState(() {
                      _selectedDoctor = 'D';
                      _selectedPeriod = 'AM';
                    }),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // Étape 3 : Coordonnées
  Widget _buildContactStep() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 500),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: _nameController,
              decoration: InputDecoration(
                labelText: "Nom complet du patient",
                hintText: "Ex : Jean Dupont",
                prefixIcon: const Icon(Icons.person_outline),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              decoration: InputDecoration(
                labelText: "Numéro de téléphone",
                hintText: "Ex : 034 12 345 67",
                prefixIcon: const Icon(Icons.phone_outlined),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // Étape 4 : Signes vitaux dynamiques + tutoriels vidéo embarqués
  Widget _buildVitalsStep() {
    final bool hasMeasured = _temperatureC != null || _heartRateBpm != null || _spo2Percent != null;

    final tutorialWidget = VitalsTutorialPlayer(
      initialIndex: _tutorialIndex,
      isMeasuring: _vitalsRunning,
      isCompleted: _vitalsSuccess || hasMeasured,
      onStartMeasure: _vitalsRunning ? null : _startVitalsMeasurement,
    );

    final vitalsControlsColumn = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Bandeau d'état logique de la mesure
        _buildVitalsStatusBanner(),
        const SizedBox(height: 8),

        // Température (clic → affiche le tutoriel sonde DS18B20)
        _buildVitalCard(
          icon: Icons.thermostat,
          iconColor: HiarColors.azur,
          title: "Température corporelle",
          subtitle: "Sonde DS18B20 · Tenez dans la main",
          valueText: _temperatureC != null ? "${_temperatureC!.toStringAsFixed(1)} °C" : "—",
          isMeasuring: _vitalsRunning,
          isMeasured: _temperatureC != null,
          onTap: () => setState(() => _tutorialIndex = 0),
        ),
        const SizedBox(height: 6),

        // Fréquence cardiaque (clic → affiche le tutoriel capteur MAX30102)
        _buildVitalCard(
          icon: Icons.favorite,
          iconColor: HiarColors.err,
          title: "Fréquence cardiaque",
          subtitle: "Capteur MAX30102 · Posez l'index",
          valueText: _heartRateBpm != null ? "$_heartRateBpm BPM" : "—",
          isMeasuring: _vitalsRunning,
          isMeasured: _heartRateBpm != null,
          onTap: () => setState(() => _tutorialIndex = 1),
        ),
        const SizedBox(height: 6),

        // Oxygénation SpO2 (clic → affiche le tutoriel capteur MAX30102)
        _buildVitalCard(
          icon: Icons.air,
          iconColor: HiarColors.cyan,
          title: "Oxygénation sanguine (SpO2)",
          subtitle: "Capteur MAX30102 · Posez l'index",
          valueText: _spo2Percent != null ? "$_spo2Percent %" : "—",
          isMeasuring: _vitalsRunning,
          isMeasured: _spo2Percent != null,
          onTap: () => setState(() => _tutorialIndex = 1),
        ),
        const SizedBox(height: 10),

        // Bouton de déclenchement logique
        Center(
          child: _vitalsRunning
              ? Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: HiarColors.azur.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: HiarColors.azur.withOpacity(0.3)),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: HiarColors.azur),
                      ),
                      SizedBox(width: 8),
                      Flexible(
                        child: Text(
                          "Mesure en cours (restez immobile)…",
                          style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: HiarColors.azur),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                )
              : (!hasMeasured && _vitalsError == null)
                  ? ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: HiarColors.azur,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: const Icon(Icons.sensors, size: 18),
                      label: const Text(
                        "Démarrer la mesure des constantes (🎤 « Mesurer »)",
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700),
                      ),
                      onPressed: _startVitalsMeasurement,
                    )
                  : OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: const Icon(Icons.refresh, size: 17),
                      label: Text(
                        _vitalsError != null ? "Réessayer la mesure" : "Reprendre la mesure (🎤 « Mesurer »)",
                        style: const TextStyle(fontSize: 12.5),
                      ),
                      onPressed: _startVitalsMeasurement,
                    ),
        ),

        const SizedBox(height: 6),
        const Text(
          "La prise de constantes est facultative pour la consultation.",
          textAlign: TextAlign.center,
          style: TextStyle(color: HiarColors.text2, fontSize: 11, fontStyle: FontStyle.italic),
        ),
      ],
    );

    return LayoutBuilder(
      builder: (context, constraints) {
        final bool sideBySide = constraints.maxWidth >= 520;
        if (sideBySide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(flex: 48, child: tutorialWidget),
              const SizedBox(width: 14),
              Expanded(flex: 52, child: vitalsControlsColumn),
            ],
          );
        }
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                tutorialWidget,
                const SizedBox(height: 10),
                vitalsControlsColumn,
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildVitalsStatusBanner() {
    if (_vitalsRunning) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: HiarColors.cyanSoft.withOpacity(0.15),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: HiarColors.cyan.withOpacity(0.4)),
        ),
        child: const Column(
          children: [
            Row(
              children: [
                Icon(Icons.sensors, size: 18, color: HiarColors.azur),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    "Lecture des capteurs ESP32 en cours… Veuillez rester immobile.",
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: HiarColors.marine),
                  ),
                ),
              ],
            ),
            SizedBox(height: 6),
            LinearProgressIndicator(
              minHeight: 2.5,
              backgroundColor: Colors.white,
              valueColor: AlwaysStoppedAnimation<Color>(HiarColors.azur),
            ),
          ],
        ),
      );
    } else if (_vitalsSuccess || (_temperatureC != null || _heartRateBpm != null || _spo2Percent != null)) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: HiarColors.ok.withOpacity(0.12),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: HiarColors.ok.withOpacity(0.4)),
        ),
        child: const Row(
          children: [
            Icon(Icons.check_circle_outline, size: 18, color: HiarColors.ok),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                "Constantes enregistrées avec succès. Vous pouvez continuer vers le récapitulatif.",
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: HiarColors.marine),
              ),
            ),
          ],
        ),
      );
    } else if (_vitalsError != null) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: HiarColors.err.withOpacity(0.12),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: HiarColors.err.withOpacity(0.4)),
        ),
        child: Row(
          children: [
            const Icon(Icons.warning_amber_rounded, size: 18, color: HiarColors.err),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                _vitalsError!,
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: HiarColors.err),
              ),
            ),
          ],
        ),
      );
    } else {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: HiarColors.border),
        ),
        child: const Row(
          children: [
            Icon(Icons.info_outline, size: 18, color: HiarColors.azur),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                "Suivez le guide vidéo puis appuyez sur « Démarrer la mesure ».",
                style: TextStyle(fontSize: 12, color: HiarColors.text2),
              ),
            ),
          ],
        ),
      );
    }
  }

  Widget _buildVitalCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required String valueText,
    required bool isMeasuring,
    required bool isMeasured,
    VoidCallback? onTap,
  }) {
    final card = Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isMeasured
              ? HiarColors.ok.withOpacity(0.5)
              : (isMeasuring ? HiarColors.azur.withOpacity(0.5) : HiarColors.border),
        ),
      ),
      child: Row(
        children: [
          Icon(icon, color: iconColor, size: 26),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                Text(subtitle, style: const TextStyle(color: HiarColors.text2, fontSize: 11)),
              ],
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isMeasuring && !isMeasured) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  margin: const EdgeInsets.only(right: 8),
                  decoration: BoxDecoration(
                    color: HiarColors.azur.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text(
                    "Lecture…",
                    style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: HiarColors.azur),
                  ),
                ),
              ],
              Text(
                valueText,
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                  color: isMeasured ? HiarColors.ok : HiarColors.text2,
                ),
              ),
            ],
          ),
        ],
      ),
    );
    if (onTap == null) return card;
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: onTap,
      child: card,
    );
  }

  // Étape 5 : Récapitulatif
  Widget _buildReviewStep() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: HiarColors.border),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("Récapitulatif de votre rendez-vous", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              const Divider(height: 14, thickness: 1),
              if (_submitError != null) ...[
                Container(
                  padding: const EdgeInsets.all(8),
                  margin: const EdgeInsets.only(bottom: 10),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.red.shade200),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: Colors.red, size: 18),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _submitError!,
                          style: const TextStyle(color: Colors.red, fontSize: 13, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              _buildReviewRow("Patient :", _nameController.text),
              _buildReviewRow("Téléphone :", _phoneController.text),
              _buildReviewRow("Motif :", _selectedReason == 'consultation_generale' ? 'Consultation générale' : 'Suivi médical'),
              _buildReviewRow("Médecin :", "Médecin $_selectedDoctor (${_selectedPeriod == 'MAT' ? 'Matin' : 'Après-midi'})"),
              if (_temperatureC != null) _buildReviewRow("Température :", "${_temperatureC!.toStringAsFixed(1)} °C"),
              if (_heartRateBpm != null) _buildReviewRow("Pouls :", "$_heartRateBpm BPM"),
              if (_spo2Percent != null) _buildReviewRow("SpO2 :", "$_spo2Percent %"),
              if (_temperatureC == null && _heartRateBpm == null && _spo2Percent == null)
                _buildReviewRow("Constantes :", "Non mesurées"),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildReviewRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2.5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: HiarColors.text2, fontSize: 14)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        ],
      ),
    );
  }

  // Écran Ticket final
  Widget _buildTicketScreen() {
    return LandscapeScaffold(
      title: "Rendez-vous confirmé",
      showBack: false,
      voiceState: widget.voiceState,
      voiceStatus: widget.voiceStatus,
      recognizedText: widget.recognizedText,
      voiceTip: "Dites : « Terminer » ou « Accueil »",
      onMicTap: widget.onMicTap,
      onSettingsTap: widget.onSettingsTap,
      isRobotConnected: widget.isRobotConnected,
      body: Center(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: HiarColors.border),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.check_circle_outline, color: HiarColors.ok, size: 44),
                  const SizedBox(height: 8),
                  const Text(
                    "Votre numéro de passage :",
                    style: TextStyle(fontSize: 15, color: HiarColors.text2),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _ticketLabel ?? "A-MAT-1",
                    style: const TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.w900,
                      color: HiarColors.azur,
                      letterSpacing: 2,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    "Patient : ${_nameController.text}",
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: HiarColors.azur,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      onPressed: widget.onFinish,
                      child: const Text("Terminer (🎤 « Terminer »)", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
