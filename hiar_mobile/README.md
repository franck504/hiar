# HIAR Mobile — Application Kiosk Tactile & Vocale (Flutter)

Application mobile kiosk pour le robot assistant hospitalier **HIAR (Hospital Assistant Robot)**.  
Conçue en **Flutter / Dart**, elle tourne sur tablette ou smartphone monté en mode paysage sur le buste du robot et offre une double interface bimodal : tactile haute visibilité et commande vocale naturelle continue en français.

---

## 🌟 Fonctionnalités Clés

- **Mode Kiosk Paysage (1440x720)** : Interface immersive plein écran sans barre système encombrante (`SystemChrome.setEnabledSystemUIMode(immersiveSticky)`).
- **Dialogue Vocal Bimodal Continu** :
  - Écoute continue en français (`speech_to_text`) avec indicateur d'ondes sonores animées.
  - Synthèse vocale naturelle (`flutter_tts`) sans délai.
  - Filtre anti-écho matériel et logiciel pour éviter les faux déclenchements et l'effet Larsen.
- **Orientation & Guidage Hospitalier** :
  - Sélection tactile ou vocale (Pharmacie, Laboratoire, Réception, Radiologie).
  - Écran de suivi de mission avec progression en temps réel.
  - Bouton d'arrêt d'urgence permanent rouge (« **Stop** ») et commandes de reprise (« **Reprendre** », « **Terminer** »).
- **Renseignements Sanitaires (Prévention OMS)** :
  - Fiches informatives interactives (Paludisme, Hygiène des mains, Vaccination, Nutrition, Santé mentale).
- **Consultation & Constantes Biomédicales** :
  - Prise de rendez-vous en 6 étapes.
  - Acquisition des signes vitaux en liaison directe avec l'ESP32 (DS18B20 pour la température, MAX30102 pour le pouls et la SpO2).
  - **Zéro valeur fictive** : constantes initialisées à `null` (affichage `"—"` tant qu'aucune vraie mesure n'est validée par les capteurs).
- **Configuration IP Dynamique** :
  - Boîte de dialogue accessible depuis l'icône ⚙️ sur l'accueil pour changer l'IP du serveur sans recompiler l'application. Persistance via `SharedPreferences`.

---

## 📁 Structure du Projet

```text
hiar_mobile/
├── android/                  # Configuration native Android, permissions micro & réseau
├── assets/
│   ├── branding/             # Icône launcher officielle (robot + croix médicale)
│   └── icons/                # Icônes vectorielles et assets visuels
├── lib/
│   ├── main.dart             # Point d'entrée de l'application
│   ├── core/
│   │   ├── net/              # Client WebSocket (HubClient) avec reconnexion automatique
│   │   └── protocol/         # Modèle des trames ServerInstruction et UserAction
│   ├── features/
│   │   ├── splash/           # Écran de veille et animation d'accueil
│   │   ├── home/             # Menu principal des 3 grands services
│   │   ├── orientation/      # Parcours de guidage physique et arrêt d'urgence
│   │   ├── information/      # Fiches sanitaires OMS
│   │   └── consultation/     # Parcours médical, ticket et signes vitaux réels
│   └── ui/
│       ├── components/       # Scaffold paysage réutilisable, boutons d'action
│       ├── rail/             # Volet latéral vocal interactif (VoiceRail)
│       └── theme/            # Charte graphique hospitalière (HiarColors)
└── test/
    ├── widget_test.dart      # Test de lancement sur le SplashScreen
    └── consultation_vitals_test.dart # Tests unitaires de la chaîne des signes vitaux
```

---

## 🚀 Démarrage et Développement

### Prérequis
- Flutter SDK (>= 3.0.0)
- Android SDK (API 21+)
- Appareil Android connecté en USB (débogage USB activé) ou émulateur paysage

### Lancement avec port USB redirigé
```bash
# 1. Rediriger le port 5000 du serveur WebSocket
adb reverse tcp:5000 tcp:5000

# 2. Lancer l'application
flutter run
```

### Vérification et Tests
```bash
# Analyse statique du code (0 avertissement)
flutter analyze

# Exécution des tests unitaires et de widgets
flutter test
```

---

## 📦 Génération de l'APK de Production

Pour installer définitivement l'application sur le robot sans dépendance de développement :

```bash
flutter build apk --release
```

Le fichier APK compilé est généré dans :  
`build/app/outputs/flutter-apk/app-release.apk`
