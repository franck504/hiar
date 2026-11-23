import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiar_mobile/features/consultation/consultation_screen.dart';
import 'package:hiar_mobile/features/consultation/doctors.dart';

/// Parent simulé : il reconstruit l'écran avec la MÊME table de champs, comme `main.dart`
/// le fait à chaque changement d'état vocal (écoute, texte reconnu…).
class _Host extends StatefulWidget {
  final Map<String, dynamic> fields;
  final int initialStep;
  final ValueChanged<int>? onStepChanged;
  final ValueChanged<Map<String, dynamic>>? onFormChanged;
  final GlobalKey<ConsultationScreenState> screenKey;

  const _Host({
    required this.fields,
    required this.initialStep,
    required this.screenKey,
    this.onStepChanged,
    this.onFormChanged,
  });

  @override
  State<_Host> createState() => _HostState();
}

class _HostState extends State<_Host> {
  int step = 1;
  int ticks = 0;

  @override
  void initState() {
    super.initState();
    step = widget.initialStep;
  }

  void goTo(int s) => setState(() => step = s);
  void rebuild() => setState(() => ticks++);

  @override
  Widget build(BuildContext context) => MaterialApp(
        home: ConsultationScreen(
          key: widget.screenKey,
          initialStep: step,
          dynamicFields: widget.fields,
          onStepChanged: widget.onStepChanged,
          onFormChanged: widget.onFormChanged,
          onCancel: () {},
          onFinish: () {},
        ),
      );
}

void main() {
  setUp(() {});

  testWidgets('catalogue : 4 médecins, prénoms reconnaissables, une période chacun', (tester) async {
    expect(DoctorCatalog.doctors.map((d) => '${d.code}:${d.name}:${d.period}').toList(),
        ['A:Raissa:MAT', 'B:Bell:AM', 'C:Pierrot:MAT', 'D:Alice:AM']);
    expect(DoctorCatalog.label('b'), 'Dr Bell');
    expect(DoctorCatalog.label(null), 'Médecin');
    expect(DoctorCatalog.label('Z'), 'Médecin');
  });

  testWidgets('étape 2 : les 4 prénoms sont proposés, plus aucune lettre A/B/C/D', (tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(MaterialApp(
      home: ConsultationScreen(initialStep: 2, onCancel: () {}, onFinish: () {}),
    ));
    for (final label in ['Dr Raissa', 'Dr Bell', 'Dr Pierrot', 'Dr Alice']) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
    expect(find.textContaining('Médecin A'), findsNothing);
    expect(find.textContaining('Médecin B'), findsNothing);
    expect(find.textContaining('Pierrot'), findsWidgets);
    expect(find.textContaining('Dites le prénom du médecin'), findsOneWidget);
  });

  testWidgets('toucher un médecin choisit aussi sa période et prévient le serveur', (tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final reports = <Map<String, dynamic>>[];
    final key = GlobalKey<ConsultationScreenState>();
    await tester.pumpWidget(_Host(
      fields: {}, initialStep: 2, screenKey: key, onFormChanged: reports.add,
    ));

    await tester.tap(find.text('Dr Bell'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(reports, isEmpty, reason: 'anti-rebond : rien avant 350 ms');
    await tester.pump(const Duration(milliseconds: 400));

    expect(reports, hasLength(1));
    expect(reports.single['doctor_code'], 'B');
    expect(reports.single['selected_doctor'], 'B');
    expect(reports.single['period'], 'AM');
    expect(key.currentState!.formSnapshot()['selected_period'], 'AM');
  });

  testWidgets('médecin dicté : appliqué une seule fois, un choix tactile ultérieur n est PAS écrasé',
      (tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final fields = <String, dynamic>{'selected_doctor': 'B', 'selected_period': 'AM'};
    final key = GlobalKey<ConsultationScreenState>();
    final host = _Host(fields: fields, initialStep: 2, screenKey: key);
    await tester.pumpWidget(host);

    expect(key.currentState!.formSnapshot()['doctor_code'], 'B'); // la voix a choisi Bell
    expect(fields.containsKey('selected_doctor'), isFalse, reason: 'champ consommé');

    await tester.tap(find.text('Dr Alice'));                       // le patient préfère Alice au toucher
    await tester.pump();
    expect(key.currentState!.formSnapshot()['doctor_code'], 'D');

    // Le parent se reconstruit (écoute vocale, texte reconnu…) : l'ancienne valeur ne doit pas revenir
    tester.state<_HostState>(find.byType(_Host)).rebuild();
    await tester.pump();
    await tester.pump();
    expect(key.currentState!.formSnapshot()['doctor_code'], 'D');
    expect(key.currentState!.formSnapshot()['period'], 'AM');
  });

  testWidgets('motif dicté + passage à l étape 2 arrivent ensemble : l étape avance sans erreur',
      (tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final fields = <String, dynamic>{};
    final key = GlobalKey<ConsultationScreenState>();
    await tester.pumpWidget(_Host(fields: fields, initialStep: 1, screenKey: key));
    expect(find.text('Étape 1 sur 5'), findsOneWidget);

    // Instruction serveur : { fields: {selected_reason}, instruction_ui: {step: 2} }
    fields['selected_reason'] = 'suivi_medical';
    tester.state<_HostState>(find.byType(_Host)).goTo(2);
    await tester.pump();
    await tester.pump();

    expect(find.text('Étape 2 sur 5'), findsOneWidget);
    expect(find.textContaining('Veuillez choisir un motif'), findsNothing);
  });

  testWidgets('saut d étape refusé (motif absent) : l écran reste, le serveur est prévenu', (tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final reported = <int>[];
    final key = GlobalKey<ConsultationScreenState>();
    await tester.pumpWidget(_Host(fields: {}, initialStep: 1, screenKey: key, onStepChanged: reported.add));

    tester.state<_HostState>(find.byType(_Host)).goTo(2);
    await tester.pump();
    await tester.pump();

    expect(find.text('Étape 1 sur 5'), findsOneWidget);
    expect(find.textContaining('Veuillez choisir un motif'), findsWidgets);
    expect(reported, [1], reason: 'le mobile signale son étape réelle pour que le serveur se recale');
  });

  testWidgets('nom et téléphone dictés remplissent les champs de l étape 3', (tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final fields = <String, dynamic>{'patient_name': 'Jean Dupont', 'patient_phone': '034 12 345 67'};
    final key = GlobalKey<ConsultationScreenState>();
    await tester.pumpWidget(_Host(fields: fields, initialStep: 3, screenKey: key));

    expect(find.widgetWithText(TextField, 'Jean Dupont'), findsOneWidget);
    expect(find.widgetWithText(TextField, '034 12 345 67'), findsOneWidget);
    expect(key.currentState!.formSnapshot()['contact'], '034 12 345 67');
  });

  testWidgets('récapitulatif : le médecin est nommé par son prénom', (tester) async {
    tester.view.physicalSize = const Size(1440, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(MaterialApp(
      home: ConsultationScreen(
        initialStep: 5,
        dynamicFields: {'selected_reason': 'suivi_medical', 'selected_doctor': 'C', 'patient_name': 'Hery'},
        onCancel: () {},
        onFinish: () {},
      ),
    ));
    expect(find.textContaining('Dr Pierrot'), findsOneWidget);
    expect(find.textContaining('Matin'), findsOneWidget);
    expect(find.textContaining('Médecin C'), findsNothing);
  });
}
