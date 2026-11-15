import 'package:flutter/material.dart';
import '../../ui/components/landscape_scaffold.dart';
import '../../ui/components/action_button.dart';
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

  // Signes vitaux dynamiques (mis à jour par le Raspberry Pi 4 / ROS 2)
  bool _vitalsRunning = false;
  double? _temperatureC;
  int? _heartRateBpm;
  int? _spo2Percent;

  // Ticket généré
  String? _ticketLabel;

  @override
  void initState() {
    super.initState();
    _currentStep = widget.initialStep;
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
    }
    if (fields.containsKey('selected_reason') && fields['selected_reason'] != null) {
      _selectedReason = fields['selected_reason'].toString();
    }
    if (fields.containsKey('vitals_state')) {
      final state = fields['vitals_state'].toString();
      _vitalsRunning = state == 'measuring';
      if (state == 'reset' || state == 'cleared') {
        _temperatureC = null;
        _heartRateBpm = null;
        _spo2Percent = null;
      }
    }
  }

  void _nextStep() {
    setState(() {
      if (_currentStep < 5) {
        _currentStep++;
      } else {
        // Confirmation finale -> Génération du ticket
        _ticketLabel = "$_selectedDoctor-$_selectedPeriod-3";
        _currentStep = 6;
      }
    });
    widget.onStepChanged?.call(_currentStep);
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
              onPressed: _nextStep,
              child: Text(
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

  // Étape 4 : Signes vitaux dynamiques
  Widget _buildVitalsStep() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 620),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Température
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: HiarColors.border),
              ),
              child: Row(
                children: [
                  const Icon(Icons.thermostat, color: HiarColors.azur, size: 28),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text("Température corporelle", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                        Text("Capteur DS18B20 (ID: temperature)", style: TextStyle(color: HiarColors.text2, fontSize: 11)),
                      ],
                    ),
                  ),
                  Text(
                    _temperatureC != null ? "${_temperatureC!.toStringAsFixed(1)} °C" : "—",
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 17, color: HiarColors.ok),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            // Fréquence cardiaque
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: HiarColors.border),
              ),
              child: Row(
                children: [
                  const Icon(Icons.favorite, color: HiarColors.err, size: 28),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text("Fréquence cardiaque", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                        Text("Capteur MAX30102 (ID: heart_rate)", style: TextStyle(color: HiarColors.text2, fontSize: 11)),
                      ],
                    ),
                  ),
                  Text(
                    _heartRateBpm != null ? "$_heartRateBpm BPM" : "—",
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 17, color: HiarColors.ok),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            // Oxygénation SpO2
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: HiarColors.border),
              ),
              child: Row(
                children: [
                  const Icon(Icons.air, color: HiarColors.cyan, size: 28),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text("Oxygénation sanguine (SpO2)", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                        Text("Capteur MAX30102 (ID: spo2)", style: TextStyle(color: HiarColors.text2, fontSize: 11)),
                      ],
                    ),
                  ),
                  Text(
                    _spo2Percent != null ? "$_spo2Percent %" : "—",
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 17, color: HiarColors.ok),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              ),
              icon: _vitalsRunning
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.sensors, size: 20),
              label: Text(
                _vitalsRunning ? "Mesure des capteurs en cours…" : "Lancer une nouvelle mesure (🎤 « Mesurer »)",
                style: const TextStyle(fontSize: 13),
              ),
              onPressed: () {
                setState(() => _vitalsRunning = true);
                widget.onRequestMeasure?.call();
                Future.delayed(const Duration(seconds: 3), () {
                  if (mounted) setState(() => _vitalsRunning = false);
                });
              },
            ),
          ],
        ),
      ),
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
