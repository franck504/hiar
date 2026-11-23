/// Médecins de la consultation HIAR.
///
/// Les codes A–D restent les identifiants stables (base de données, tickets « B-AM-3 ») ; les patients
/// voient et prononcent le prénom. Même ordre, mêmes prénoms et mêmes périodes que
/// `consultation_catalog.py` (dialogue vocal) et `consultation_sessions_store.py` (interface web) :
/// un test Python vérifie l'accord des trois.
class DoctorInfo {
  final String code;
  final String name;
  final String period; // 'MAT' | 'AM'

  const DoctorInfo(this.code, this.name, this.period);

  /// Libellé affiché : « Dr Raissa ».
  String get label => 'Dr $name';
}

class DoctorCatalog {
  DoctorCatalog._();

  static const List<DoctorInfo> doctors = [
    DoctorInfo('A', 'Raissa', 'MAT'),
    DoctorInfo('B', 'Bell', 'AM'),
    DoctorInfo('C', 'Pierrot', 'MAT'),
    DoctorInfo('D', 'Alice', 'AM'),
  ];

  static DoctorInfo? byCode(String? code) {
    if (code == null) return null;
    for (final d in doctors) {
      if (d.code == code.toUpperCase()) return d;
    }
    return null;
  }

  /// « Dr Raissa », ou « Médecin » si aucun n'est choisi.
  static String label(String? code) => byCode(code)?.label ?? 'Médecin';

  static String periodName(String? period) =>
      period == 'MAT' ? 'Matin' : (period == 'AM' ? 'Après-midi' : 'Créneau non choisi');

  static String hours(String? period) =>
      period == 'MAT' ? '08 h 00 – 12 h 00' : (period == 'AM' ? '13 h 00 – 18 h 00' : '');

  /// Noms à dire, dans l'ordre : matin d'abord.
  static List<String> get spokenNames => doctors.map((d) => d.name).toList();
}
