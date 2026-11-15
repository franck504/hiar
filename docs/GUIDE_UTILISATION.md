# Guide d'Utilisation — Robot Assistant Hospitalier (HIAR)

Bienvenue dans le guide complet d'utilisation du système **HIAR (Hospital Assistant Robot)**. Ce document détaille l'architecture, la configuration réseau, le démarrage et l'ensemble des scénarios d'interaction (tactiles et vocaux) entre les patients, le personnel et le robot.

---

## Sommaire

1. [Vue d'ensemble du système](#1-vue-densemble-du-système)
2. [Architecture technique](#2-architecture-technique)
3. [Démarrage rapide](#3-démarrage-rapide)
4. [Configuration de l'adresse IP (Sans recompilation)](#4-configuration-de-ladresse-ip-sans-recompilation)
5. [Parcours et Scénarios d'Utilisation](#5-parcours-et-scénarios-dutilisation)
   - [Écran de Veille (Splash Screen)](#51-écran-de-veille-splash-screen)
   - [Écran Principal des Services (Accueil)](#52-écran-principal-des-services-accueil)
   - [Orientation & Accompagnement (Guidage)](#53-orientation--accompagnement-guidage)
   - [Arrêt d'urgence et Reprise](#54-arrêt-durgence-et-reprise)
   - [Fiches de Renseignements & Prévention OMS](#55-fiches-de-renseignements--prévention-oms)
   - [Consultation Médicale & Prise de Constantes Vitales](#56-consultation-médicale--prise-de-constantes-vitales)
6. [Lexique des Commandes Vocales](#6-lexique-des-commandes-vocales)
7. [Filtres Audio & Sécurités Anti-Écho](#7-filtres-audio--sécurités-anti-écho)
8. [Résolution des Problèmes (FAQ)](#8-résolution-des-problèmes-faq)

---

## 1. Vue d'ensemble du système

Le projet **HIAR** est un robot d'assistance autonome destiné aux établissements hospitaliers pour fluidifier l'accueil, orienter les patients vers les bons services, dispenser des conseils de santé préventive et assister la prise de constantes vitales avant consultation.

### Rôles majeurs du robot :
* **Accueil bimodal (Voix + Tactile)** : Dialogue naturel en français couplé à une interface tactile haute lisibilité.
* **Guidage physique autonome** : Accompagnement des usagers vers la Pharmacie, le Laboratoire d'analyses, la Réception ou la Radiologie.
* **Sécurité hospitalière** : Bouton d'arrêt d'urgence tactile et vocal permanent (« *Stop* »), avec reprise contrôlée (« *Reprendre* »).
* **Santé publique** : Diffusion de repères et recommandations sanitaires conformes à l'OMS (paludisme, hygiène, vaccination, etc.).
* **Pré-consultation** : Acquisition des signes vitaux (température, pouls, SpO2) et délivrance de ticket patient.

---

## 2. Architecture technique

```
 +-------------------------------------------------------+
 |        SMARTPHONE / TABLETTE DU ROBOT (Android)       |
 |                                                       |
 |   +-----------------------------------------------+   |
 |   |          HIAR Mobile (Flutter Kiosk)          |   |
 |   |  - Interface tactile paysage (1440x720)       |   |
 |   |  - Reconnaissance vocale continue (STT)       |   |
 |   |  - Synthèse vocale fluide (TTS)               |   |
 |   |  - Configuration IP dynamique (Persistance)   |   |
 |   +-----------------------------------------------+   |
 +--------------------------▲----------------------------+
                            │ WebSocket JSON (Port 5000)
                            ▼
 +-------------------------------------------------------+
 |           CERVEAU CENTRAL (Raspberry Pi 4 / PC)       |
 |                                                       |
 |   +-----------------------------------------------+   |
 |   |      HMI WebSocket Bridge (Python / asyncio)  |   |
 |   |  - Analyseur d'intentions vocales (NLP)       |   |
 |   |  - Moteur d'instructions unifié (JSON)        |   |
 |   |  - Anti-doublons & Anti-rebond vocal          |   |
 |   +-----------------------------------------------+   |
 |                          ▲                            |
 |                          │ ROS 2 Humble Topics        |
 |                          ▼                            |
 |   +-----------------------------------------------+   |
 |   |  Nœuds ROS 2 : Navigation, Superviseur,       |   |
 |   |  Interface ESP32 Série, Base de Données       |   |
 |   +-----------------------------------------------+   |
 +-------------------------------------------------------+
```

---

## 3. Démarrage rapide

### Étape 1 : Démarrer le serveur central (Pont WebSocket ROS 2)
Sur la machine hôte (Raspberry Pi ou PC de contrôle) :
```bash
# Se placer à la racine du projet
cd /chemin/vers/hospital_assistant_robot

# Démarrer le pont WebSocket
PYTHONPATH=src/hospital_robot python3 src/hospital_robot/hospital_robot/hmi_websocket_bridge_node.py
```
Le serveur démarre et écoute sur `ws://0.0.0.0:5000/ws`.

---

### Étape 2 : Établir la liaison réseau avec le mobile

Deux modes de connexion sont possibles :

#### Mode A — Câble USB (Idéal pour le banc de test et développement) :
```bash
# Redirige le port 5000 du téléphone vers la machine hôte
adb reverse tcp:5000 tcp:5000
```
Dans l'application, l'adresse par défaut `127.0.0.1:5000` fonctionne alors directement.

#### Mode B — Réseau Wi-Fi local (Idéal en conditions réelles sur le robot) :
1. Connectez le smartphone et la machine hôte au même réseau Wi-Fi local.
2. Notez l'adresse IP de votre machine hôte (ex : `192.168.1.45` via `ip a` ou `ifconfig`).
3. Dans l'application mobile, ouvrez les paramètres (icône ⚙️) et renseignez cette IP.

---

### Étape 3 : Lancer l'application mobile HIAR

* **Directement sur le téléphone** : Touchez l'icône **HIAR** (tête de robot avec écusson médical) sur l'écran d'accueil du smartphone.
* **Ou via la console de développement** :
  ```bash
  cd hiar_mobile
  flutter run
  ```

---

## 4. Configuration de l'adresse IP (Sans recompilation)

Pour permettre à n'importe quel collègue d'utiliser la même version de l'application sur différents réseaux sans avoir à recompiler :

1. Sur l'écran d'accueil, repérez le voyant d'état du robot en haut à droite.
2. Touchez l'icône **Paramètres ⚙️** située juste à côté du statut.
3. Une fenêtre modale compacte s'affiche :
   * Saisissez l'adresse IP du serveur (ex : `192.168.0.105` ou `10.42.0.1`).
   * Vérifiez le port (par défaut : `5000`).
4. Touchez **« Enregistrer & Reconnecter »**.
5. L'application enregistre immédiatement la nouvelle IP dans le stockage sécurisé (`SharedPreferences`) et se reconnecte au serveur sans redémarrage.

---

## 5. Parcours et Scénarios d'Utilisation

### 5.1 Écran de Veille (Splash Screen)
* **Objectif** : Attirer l'attention du patient avec une animation douce du visage du robot et un statut clair.
* **Action tactile** : Appuyez sur le bouton principal **« COMMENCER L'EXPÉRIENCE »**.
* **Action vocale** : Dites simplement « *Bonjour* », « *Commencer* » ou « *Démarrer* ».
* **Comportement** : Le robot salue chaleureusement l'utilisateur et ouvre le menu principal.

---

### 5.2 Écran Principal des Services (Accueil)
L'écran présente les 3 services majeurs :
1. **Orientation** : Accompagnement physique dans l'hôpital.
2. **Renseignements** : Fiches sanitaires et prévention OMS.
3. **Consultation** : Prise de rendez-vous et ticket patient.

L'utilisateur peut à tout moment choisir un service tactilement ou en disant son nom à voix haute.

---

### 5.3 Orientation & Accompagnement (Guidage)
* **Sélection directe de destination** :
  * Tactile : Touchez la carte souhaitée (**Pharmacie**, **Laboratoire**, **Réception**, **Radiologie**).
  * Vocal : Dites « *Emmène-moi à la pharmacie* » ou « *Je cherche le laboratoire* ».
* **Guidage direct sans friction** : Aucune popup superflue ne bloque le parcours. Le robot annonce vocalement :
  > *« Très bien, suivez-moi vers la Pharmacie. »*
* L'écran bascule immédiatement en mode **Mission**, affichant :
  * Le nom de la destination.
  * La jauge de progression.
  * L'expression animée du robot.

---

### 5.4 Arrêt d'urgence et Reprise

La sécurité des personnes en milieu hospitalier est prioritaire :

1. **Arrêter le robot** :
   * Appuyez sur le grand bouton rouge **ARRÊTER LE ROBOT**.
   * Ou prononcez à tout instant : « ***Stop !*** », « *Arrête-toi !* » ou « *Pause* ».
   * Le robot s'arrête instantanément, diffuse un avertissement vocal et affiche une alerte visuelle rouge.

2. **Reprendre le guidage** :
   * Dès l'arrêt, deux options dédiées apparaissent à l'écran :
     * Bouton vert : **Reprendre le guidage (🎤 « Reprendre »)**.
     * Bouton contour : **Terminer la mission (🎤 « Terminer »)**.
   * Prononcez « *Reprendre* » ou touchez le bouton vert : le robot confirme vocalement et repart en toute sécurité.

3. **Terminer la mission** :
   * Touchez « Terminer la mission » ou dites « *Terminer* » / « *On est arrivé* » : le robot remercie le patient et retourne au menu d'accueil.

---

### 5.5 Fiches de Renseignements & Prévention OMS
* Fiches intégrées conformes aux directives de l'Organisation Mondiale de la Santé :
  * **Paludisme (Malaria)** : Symptômes, diagnostic précoce et moustiquaires imprégnées.
  * **Hygiène des mains** : Procédure de lavage et réduction des infections nosocomiales.
  * **Vaccination** : Calendrier vaccinal et protection collective.
  * **Nutrition** : Alimentation équilibrée, hydratation et prévention des carences.
  * **Santé mentale** : Gestion du stress et soutien psychologique.
* Accompagné d'une synthèse vocale explicative à chaque fiche sélectionnée.

---

### 5.6 Consultation Médicale & Prise de Constantes Vitales
Parcours guidé en 6 étapes :
1. Accueil et présentation de la consultation.
2. Choix du motif (Suivi médical, Consultation générale, Bilan).
3. Consignes de mesure des signes vitaux.
4. Acquisition capteurs (Température corporelle, Fréquence cardiaque, Saturation SpO2).
5. Récapitulatif visuel des mesures.
6. Impression / Affichage du ticket de consultation (ex : `Ticket A-MAT-3`).

---

## 6. Lexique des Commandes Vocales

Le robot comprend le langage naturel. Voici les principales phrases reconnues :

| Catégorie | Phrases types reconnues | Action déclenchée |
|---|---|---|
| **Salutations** | « Bonjour », « Salut », « Coucou », « Hello » | Salue et invite à choisir un service |
| **Orientation** | « Emmène-moi à la pharmacie »<br>« Où sont les médicaments ? »<br>« Direction le laboratoire »<br>« Je cherche l'accueil » | Démarre le guidage physique vers la destination |
| **Arrêt d'urgence** | « **Stop** », « Arrête », « Arrête-toi », « Pause », « Danger » | Arrêt immédiat des moteurs et passage en sécurité |
| **Reprise** | « **Reprendre** », « Reprends », « Repartir », « En route » | Reprise de la marche après un arrêt |
| **Fin de mission** | « **Terminer** », « C'est bon », « On est arrivé », « Fini » | Clôture la mission et retourne à l'accueil |
| **Navigation** | « Accueil », « Menu », « Retour », « Revenir au début » | Ouvre l'écran d'accueil général |
| **Renseignements** | « Fiches de santé », « Renseignements », « Paludisme », « Hygiène » | Ouvre la fiche d'information demandée |
| **Consultation** | « Je veux voir un médecin », « Prendre rendez-vous », « Consultation » | Lance le parcours de consultation |
| **Constantes** | « Prendre ma température », « Mesurer mes constantes », « Pouls » | Déclenche l'acquisition des capteurs |
| **Étapes** | « Suivant », « Continuer », « Étape suivante », « Précédent » | Navigue dans les étapes de consultation |

---

## 7. Filtres Audio & Sécurités Anti-Écho

Pour garantir un confort d'écoute optimal et éviter les bugs classiques des assistants vocaux :

1. **Suppression du double écho vocal** :
   * Le protocole déduplique automatiquement les instructions WebSocket pour empêcher le robot de répéter deux fois la même phrase (« *bonjour bonjour* »).
2. **Isolation microphone pendant l'élocution (Anti-Larsen)** :
   * Dès que le robot parle via son haut-parleur, le microphone est immédiatement désactivé (`speech.cancel()`), vidant le tampon audio.
   * Tout texte capté pendant ou dans la seconde suivant la parole du robot est comparé à la phrase prononcée : s'il s'agit d'un écho acoustique du haut-parleur, il est rejeté silencieusement.
3. **Délai de garde matériel** :
   * Un délai de 800 ms est appliqué à la fin de chaque élocution avant de réactiver le microphone pour laisser le temps aux réverbérations de la pièce de s'éteindre.

---

## 8. Résolution des Problèmes (FAQ)

### Le voyant indique « Déconnecté » (Rouge) :
1. Vérifiez que le script Python `hmi_websocket_bridge_node.py` est bien en cours d'exécution.
2. Si vous êtes connecté par câble USB, vérifiez que la commande suivante a été exécutée :
   ```bash
   adb reverse tcp:5000 tcp:5000
   ```
3. Si vous êtes en Wi-Fi, appuyez sur l'icône ⚙️ sur l'écran d'accueil et confirmez que l'IP renseignée correspond bien à l'adresse IP locale de votre machine (ex: `192.168.0.x`).

### La voix ne répond pas ou ne s'active pas :
1. Vérifiez que la permission **Microphone** est accordée à l'application HIAR dans les paramètres Android.
2. Assurez-vous que le volume multimédia du smartphone est monté au maximum.
3. En cas de blocage d'Android Speech, touchez simplement l'icône microphone sur la gauche de l'écran pour relancer l'écoute.

### Comment compiler une version Release finale (APK) ?
Pour distribuer l'application à installer sur n'importe quel smartphone Android :
```bash
cd hiar_mobile
flutter build apk --release
```
Le fichier APK autonome généré sera disponible dans :
`hiar_mobile/build/app/outputs/flutter-apk/app-release.apk`
