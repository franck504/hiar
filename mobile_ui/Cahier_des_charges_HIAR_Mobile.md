# CAHIER DES CHARGES — APPLICATION MOBILE HIAR
## Application Android (paysage) avec interaction vocale hors ligne et bus WebSocket

**Version :** 1.0 — 14 novembre 2026
**Projet :** HIAR — Hospital Intelligent Assistant Robot
**Documents liés :** `Dossier_HIAR_V4.md` (rév. 2, le « pourquoi » et l'architecture) · `hiar_contract_v1.json` (le contrat machine) · `contract_validate.py` (vérificateur du contrat)
**Destinataire :** agent IA de développement (puis recette par l'auteur du projet)

---

# 0. OBJET ET MODE D'EMPLOI

## 0.1. But

Ce cahier des charges définit **tout ce qu'il faut livrer** pour l'application mobile, et surtout **comment garantir que, une fois l'application réalisée, elle communique correctement du premier coup** avec le Raspberry Pi (REST, WebSocket, ROS 2 relayé).

La garantie repose sur quatre mécanismes (chapitre 5) :

1. **Un contrat unique** (`hiar_contract_v1.json`) : enveloppe, 27 topics et leurs charges utiles, 41 actions et leurs arguments, 9 endpoints REST, droits par rôle, limites. Les deux côtés (application, serveur) en dérivent leurs modèles et leurs tests.
2. **Des vecteurs de test** inclus dans le contrat (61 vérifications, dont des cas **invalides** qui doivent être refusés). `contract_validate.py` les contrôle.
3. **Deux outils de compatibilité** à produire : un *hub simulé* pour développer l'application sans le Pi, et un *client de conformité* pour valider le vrai hub.
4. **Une matrice d'intégration** et une **procédure du jour J** (chapitre 9) qui prouvent la compatibilité de bout en bout.

## 0.2. Ordre de précédence

`hiar_contract_v1.json` > ce cahier des charges > `Dossier_HIAR_V4.md` > Dossier V3. Si deux documents se contredisent, on applique le plus haut et on **signale** l'écart à l'auteur (on ne le corrige pas en silence).

## 0.3. Mots-clés

**DOIT** : obligatoire, vérifié en recette. **DEVRAIT** : attendu sauf raison documentée. **PEUT** : facultatif. Chaque exigence porte un identifiant (`FUN-…`, `VOX-…`, `INT-…`) repris dans la matrice de traçabilité (annexe F).

## 0.4. Règles intangibles (rappel du Dossier V4, section 0.2)

1. L'**interface Web est gelée** : ni `templates/`, ni `static/`, ni routes existantes ne changent.
2. **Aucune commande moteur** n'est émise par l'application ni par le hub. Deux effets robotiques seulement : demande d'orientation validée (`POST /api/request`) et `STOP` (`POST /api/navigation/cancel`).
3. **Un seul point d'entrée pour toute action** : l'`ActionDispatcher`.
4. **Dire la vérité** : aucun message ne prétend qu'une action robotique est acceptée avant le statut `RUNNING` ; jamais « arrivé ».
5. **Aucun secret** dans le dépôt, l'APK ou les journaux. **Aucune donnée personnelle** persistée sur l'appareil.
6. Aucun flash de l'ESP32, aucune modification de `robot_supervisor.py` ni de `navigation_decision_node.py`.
7. Français uniquement (malgache = perspective, mais le champ `lang` est présent partout).

---

# 1. LIVRABLES

| # | Livrable | Contenu | Vérification |
|---|---|---|---|
| L1 | Projet Flutter `hiar_mobile/` | Code source, arborescence du Dossier V4 §5.1 | Compile (`flutter build apk --release`) sans avertissement bloquant |
| L2 | APK de démonstration signé | `hiar-mobile-<version>.apk` (signature de débogage acceptée pour la démonstration) | Installation et lancement sur le Xiaomi Mi CC9 Pro |
| L3 | Hub WebSocket serveur | Paquet `web_interface/hub/` + montage `/ws` + blueprint `mobile_api.py` (N1 à N5) | Tests pytest verts ; client de conformité vert |
| L4 | Registre vocal | `voice_fr.yaml` + générateur → `actions.v1.json` (embarqué dans l'application) | Tests T7, T8 |
| L5 | **Hub simulé** | `tools/mock_hub.py` | Permet de lancer l'application sans Pi (5.6) |
| L6 | **Client de conformité** | `tools/hub_conformance.py` | Rapport CT-01 à CT-14 vert sur le vrai hub (5.7) |
| L7 | Contrat et validateur | `hiar_contract_v1.json`, `contract_validate.py` (fournis, à ne modifier que par l'auteur) | `contract_validate.py` retourne 0 |
| L8 | Rapport de benchmark voix | `docs/voice_benchmark.md` (Dossier V4 §13.2) sur l'appareil réel | Chiffres présents, décision de modèles consignée |
| L9 | Documentation | `README_MOBILE.md` (installation, MIUI, provisionnement des modèles, réglages), `docs/INTEGRATION.md` (procédure jour J), journal des décisions | Relecture par l'auteur |
| L10 | Preuves de recette | Journaux, captures, `docs/recette.md` rempli (annexe E) | Chaque exigence marquée « vérifiée » avec sa preuve |

**Hors livrable** : toute modification du Web, du firmware, de la navigation, du Supervisor ; interfaces personnel/médecin ; iOS ; portrait ; malgache.

---

# 2. ENVIRONNEMENT ET CONFIGURATION TECHNIQUE

## 2.1. Cible

| Réf | Exigence | Vérification |
|---|---|---|
| ENV-01 | `minSdk 29` (Android 10), `targetSdk` = dernier niveau stable accepté par la chaîne de build **[À VÉRIFIER]**, architecture `arm64-v8a` seulement | `build.gradle` ; APK installé |
| ENV-02 | Appareil de référence : **Xiaomi Mi CC9 Pro** (M1910F4E), 6 Go, Android 10, MIUI 12.0.4. Tout critère de performance est mesuré dessus | Rapport L8 |
| ENV-03 | Version de Flutter/Dart **figée** dans le dépôt (`.fvmrc` ou `pubspec.yaml: environment`) après le spike ; dépendances **épinglées** (pas de `^` sur les paquets audio et sherpa-onnx) | `pubspec.lock` versionné |
| ENV-04 | Orientation : `android:screenOrientation="sensorLandscape"` **et** `SystemChrome.setPreferredOrientations([landscapeLeft, landscapeRight])` | Rotation de l'appareil en portrait : l'application reste en paysage |
| ENV-05 | Mode immersif collant, écran toujours allumé | Observation pendant 10 min |

## 2.2. Manifeste Android (extrait normatif)

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
  <uses-permission android:name="android.permission.RECORD_AUDIO"/>
  <uses-permission android:name="android.permission.INTERNET"/>
  <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
  <uses-permission android:name="android.permission.CHANGE_NETWORK_STATE"/>
  <uses-permission android:name="android.permission.WAKE_LOCK"/>
  <application
      android:networkSecurityConfig="@xml/network_security_config"
      android:usesCleartextTraffic="false"
      android:allowBackup="false" ...>
    <activity android:screenOrientation="sensorLandscape" android:launchMode="singleTask" .../>
  </application>
</manifest>
```

`res/xml/network_security_config.xml` — trafic en clair **uniquement** vers le Pi :

```xml
<network-security-config>
  <base-config cleartextTrafficPermitted="false"/>
  <domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="false">10.42.0.1</domain>
  </domain-config>
</network-security-config>
```

`allowBackup="false"` est obligatoire (aucune donnée sur l'appareil ne doit être sauvegardée dans un compte).

## 2.3. Canal natif Kotlin (liaison au réseau Wi-Fi)

| Réf | Exigence |
|---|---|
| ENV-06 | Un canal de plateforme `hiar/net` expose `bindToWifi()` : trouver le réseau `TRANSPORT_WIFI` via `ConnectivityManager`, appeler `bindProcessToNetwork(network)` ; retourner `{bound: bool, ssid?: string}`. Appelé au démarrage et à chaque reconnexion |
| ENV-07 | Si aucun Wi-Fi n'est disponible : état « hors réseau », pas de plantage, le mode local reste actif |
| ENV-08 | Vérification : appareil avec données mobiles **activées** et Wi-Fi `HIAR-DEMO` (sans Internet) → l'application joint `10.42.0.1` |

## 2.4. Dépendances candidates (à épingler après le spike WP1)

| Besoin | Candidat | Remarque |
|---|---|---|
| État | `flutter_riverpod` | — |
| Navigation | `go_router` | — |
| REST | `dio` | annulation et délais |
| WebSocket | `web_socket_channel` | client de protocole maison (5.2) |
| Moteur vocal | `sherpa_onnx` | VAD + STT + TTS **[À VÉRIFIER : version, support Android arm64]** |
| Micro | `record` | PCM16 16 kHz mono, `echoCancel`, `noiseSuppress`, `autoGain` ; repli : canal natif `AudioRecord` source `VOICE_COMMUNICATION` |
| Lecture PCM | `flutter_pcm_sound` ou `flutter_soloud` | à choisir au spike : latence d'arrêt ≤ 150 ms |
| Écran allumé | `wakelock_plus` | — |
| Secret d'appareil | `flutter_secure_storage` | jeton du hub |
| Réglages | `shared_preferences` | adresse serveur, volume, vitesse |
| QR code | `qr_flutter` | lien « Source OMS » |
| Identifiants | `uuid` (v7) ou `ulid` | le contrat accepte toute chaîne de 1 à 64 caractères |
| Tests | `flutter_test`, `mocktail`, `json_schema` (ou équivalent) | validation contre le contrat |

Aucun paquet n'appelle un service en ligne. Aucune télémétrie tierce.

---

# 3. EXIGENCES FONCTIONNELLES

Le détail des maquettes est au Dossier V4 §9.6 ; le catalogue d'actions au §6.3. Les tableaux ci-dessous fixent les critères de vérification.

## 3.1. Démarrage et veille

| Réf | Exigence | Vérification |
|---|---|---|
| FUN-01 | Au lancement : contrôle des modèles (`ModelManager`), de la permission micro, de la liaison réseau, du registre ; affichage de la veille en ≤ 6 s si tout est prêt | Mesure sur appareil |
| FUN-02 | Veille : robot animé, « Touchez l'écran pour commencer », micro **fermé** | Visuel |
| FUN-03 | Modèle obligatoire absent → écran `/provision` (progression, reprise, SHA-256) ; refus de la voix, tactile utilisable | Retirer un modèle puis lancer |
| FUN-04 | Permission micro refusée → écran d'explication, mode tactile seul, aucune boucle de demande | Refuser la permission |
| FUN-05 | Retour à la veille après 90 s d'inactivité (180 s en consultation), avec avertissement vocal et visuel 20 s avant ; **toute donnée saisie est effacée** | Chronométrer |

## 3.2. Accueil et navigation

| Réf | Exigence | Vérification |
|---|---|---|
| FUN-10 | Accueil : 3 cartes (Orientation, Renseignements, Consultation) ; chaque carte appelle une action de registre | Test T2 |
| FUN-11 | « Retour » toujours en haut à gauche de la scène, même effet partout (un niveau) | Revue visuelle de tous les écrans |
| FUN-12 | Aucun écran de menu ne défile verticalement dans 640 × 360 dp | Widget tests à cette taille |

## 3.3. Orientation

| Réf | Exigence | Vérification |
|---|---|---|
| FUN-20 | 3 destinations : PHARMACY, LABORATORY, RECEPTION (libellé « Réception ») | — |
| FUN-21 | Sélection → **feuille de confirmation obligatoire** (voix **et** toucher), délai 10 s, annulation silencieuse à l'échéance | Test de scénario |
| FUN-22 | Confirmation → `POST /api/request` `{"category":"ORIENTATION","item":"<DEST>"}` ; **aucune** autre émission robotique | Journal du serveur |
| FUN-23 | Écran de mission relié à `robot/mission/status` : « Demande envoyée… » → « En route » (`RUNNING`) → « Mission terminée » (`MISSION_TIMEOUT`) ou « Arrêté » ; refus explicites pour `START_REJECTED:*` et `REQUEST_REJECTED:*` ; message dédié pour `BLOCKED` | Hub simulé, 6 cas |
| FUN-24 | Sans statut sous 4 s : « Le robot n'a pas répondu », sans prétendre quoi que ce soit | Hub simulé muet |
| FUN-25 | Bouton **ARRÊT** (rouge, ≥ 96 dp de haut) visible dès l'envoi de la demande et pendant toute mission ; → `POST /api/navigation/cancel` ; sans réponse HTTP sous 2 s : message « L'arrêt n'est pas confirmé » + une nouvelle tentative | Réseau coupé |
| FUN-26 | Jamais le mot « arrivé » dans aucun texte (vérifié par test de recherche dans les fichiers de traduction) | Test automatique |

## 3.4. Renseignements

| Réf | Exigence | Vérification |
|---|---|---|
| FUN-30 | 6 fiches (HIV, MALARIA, DIABETES, HYPERTENSION, TUBERCULOSIS, MENSTRUAL_HEALTH) lues depuis `GET /api/catalog` ; copie embarquée en repli | Pi éteint : les 6 fiches s'affichent |
| FUN-31 | Fiche structurée en sections (sommaire à gauche, une section à la fois), bandeau d'avertissement permanent (texte `disclaimer` du serveur) | Visuel |
| FUN-32 | Lecture à voix haute : tout, une section, pause/reprise, suivant/précédent ; surlignage phrase par phrase | Scénario 8.6 du Dossier V4 |
| FUN-33 | Source OMS : texte + QR code ; **aucun navigateur ouvert** | Appui sur « Source » |
| FUN-34 | **Aucune** requête `POST /api/request` pour consulter une fiche | Journal du serveur |

## 3.5. Consultation

| Réf | Exigence | Vérification |
|---|---|---|
| FUN-40 | Parcours : motif → session → coordonnées → mesures → vérification → ticket, avec stepper « n sur 5 » | — |
| FUN-41 | Étape 2 : `GET /api/consultation/sessions?date=<aujourd'hui, fuseau Indian/Antananarivo>` ; seules les sessions ouvertes sont proposées ; « n en attente » affiché | Hub/serveur simulé |
| FUN-42 | Étape 3 : nom (≤ 120 car.), téléphone (≥ 8 chiffres côté client ; format malgache 10 chiffres `0xxxxxxxxx` ou `+261…`) ; saisie au clavier **ou** dictée avec lecture-confirmation | Tests de validation |
| FUN-43 | Étape 4 (facultative) : `POST /api/vitals/acquire`, attente jusqu'à 35 s avec compte à rebours ; affichage seulement des valeurs reçues ; **pas de carte SpO₂** ; `spo2_percent` envoyé à `null` | Cas `valide`, `indisponible` |
| FUN-44 | Étape 5 : récapitulatif lu à voix haute ; un seul bouton principal « Confirmer » | — |
| FUN-45 | Confirmation → `POST /api/consultation/appointments` avec les champs du contrat ; anti double-envoi (bouton désactivé tant que la réponse n'est pas arrivée) | Double appui rapide |
| FUN-46 | Erreurs : 400 `invalid_phone`, 409 `duplicate_phone`, 409 `slot_taken`, session fermée, délai réseau → messages de la table 10.2 du Dossier V4, affichés **et** lus, retour à l'étape concernée **sans perte de saisie** | Serveur simulé |
| FUN-47 | Ticket : `ticket_label` (ex. `A-MAT-3`) en 72 sp, lu à voix haute, retour automatique à l'accueil après 60 s | — |
| FUN-48 | Annulation à tout moment : efface les données et revient à l'accueil | — |

## 3.6. Signes vitaux (règles)

Valeurs indicatives, non diagnostiques. Plages de plausibilité du serveur : température 25–45 °C, fréquence cardiaque 40–200 bpm entière. Une valeur absente reste « — » avec la raison fournie ; **jamais de valeur inventée** (FUN-43).

## 3.7. Réglages et diagnostic (écran caché, appui long 5 s sur le logo)

| Réf | Exigence |
|---|---|
| FUN-50 | Adresse du serveur (défaut `10.42.0.1:5000`), jeton d'appareil (saisi, stocké chiffré), identifiant d'appareil |
| FUN-51 | Volume et vitesse de la voix (valeur minimale de volume imposée) ; mode d'écoute (session mains libres / appui) |
| FUN-52 | État des modèles (nom, version, SHA-256), du hub (connecté, latence), de ROS 2 (`robot/link`), du registre (hash) |
| FUN-53 | Bouton « Tester la voix » et « Tester la liaison » (envoie un `ping`, affiche l'aller-retour) |
| FUN-54 | Journal de diagnostic sans données personnelles (200 Ko max, tournant) |
| FUN-55 | Protégé par un code administrateur (PIN local) ; hors voix |

---

# 4. EXIGENCES VOCALES

Architecture, machine à états et règles d'arbitrage : Dossier V4 §8. Ici, les exigences vérifiables.

| Réf | Exigence | Vérification |
|---|---|---|
| VOX-01 | Audio d'entrée : PCM16, 16 kHz, mono ; source `VOICE_COMMUNICATION` avec annulation d'écho, réduction de bruit, contrôle de gain **demandés** ; absence de support = journalisée, demi-duplex conservé | Journal de diagnostic |
| VOX-02 | **Aucun audio n'est enregistré, mis en cache ni transmis** | Inspection du disque et du réseau (capture) |
| VOX-03 | STT et TTS fonctionnent **sans réseau** (Wi-Fi coupé, données mobiles coupées) | Essai en mode avion |
| VOX-04 | Les composants vocaux communiquent **uniquement par le bus** (pas d'appel direct entre eux) | Revue de code ; test avec faux bus |
| VOX-05 | Orchestrateur conforme au tableau de transitions du Dossier V4 §8.2 (un test par ligne) | Tests unitaires |
| VOX-06 | Règles d'arbitrage A1 à A12 (Dossier V4 §8.3), chacune avec au moins un test | Tests unitaires |
| VOX-07 | Mot de niveau R3 (« stop », « arrête ») détecté sur `voice/stt/partial` sans attendre la fin de phrase | Test avec flux simulé |
| VOX-08 | Barge-in : synthèse coupée ≤ 150 ms après détection de parole forte (priorité ≤ 2) | Mesure |
| VOX-09 | Découpage de la synthèse par phrase, pré-synthèse de la suivante, événements `sentence` | Test + mesure |
| VOX-10 | Normalisation et correspondance : pipeline du Dossier V4 §6.7 ; seuils 0,90 / 0,75 ; `NumberParser` testé sur ≥ 30 numéros `03x` | Tests unitaires |
| VOX-11 | Ambiguïtés : règles du Dossier V4 §6.4 (« accueil », « stop », « oui » hors confirmation, médecin sans période…) | Tests unitaires |
| VOX-12 | Dictée : lecture-confirmation obligatoire avant d'accepter un nom ou un téléphone ; téléphone validé comme le serveur (`normalize_phone`) | Tests |
| VOX-13 | Pendant une mission : seuil 0,92, seules `robot.stop`, `voice.stop_speaking`, `voice.repeat`, `app.help` acceptées | Tests |
| VOX-14 | Budgets de performance du Dossier V4 §4.3 respectés sur l'appareil de référence | Rapport L8 |
| VOX-15 | Modes dégradés du Dossier V4 §8.8 (STT/TTS/micro/hub/ROS) : un test par ligne | Tests |
| VOX-16 | Repli TTS système Android si le moteur sherpa échoue, sinon texte seul + messages critiques plein écran | Simuler l'échec |

---

# 5. EXIGENCES D'INTEROPÉRABILITÉ (le cœur du cahier des charges)

## 5.1. Principes

| Réf | Principe |
|---|---|
| INT-01 | **Le contrat fait loi.** Les modèles Dart (enveloppe, charges utiles, arguments d'actions, réponses REST) sont écrits **à partir de** `hiar_contract_v1.json`. Un test charge le fichier, valide chaque vecteur avec les modèles Dart et échoue au moindre écart |
| INT-02 | **Lecteur tolérant, émetteur strict.** À la réception : ignorer les champs inconnus, ignorer les topics inconnus (journaliser), ne jamais planter sur un message mal formé (le journaliser, envoyer `nack`/`error` si QoS 1). À l'émission : produire exactement le contrat, sans champ supplémentaire |
| INT-03 | **Négociation de version** : l'application envoie `v:1` ; si le hub répond `unsupported_version`, afficher « Application et robot incompatibles » (pas de boucle de reconnexion) |
| INT-04 | **Rien n'est supposé** : toute valeur robot affichée provient d'un message reçu, jamais d'un calcul local |
| INT-05 | **Horloges** : `ts` informatif ; l'ordre se fait par `seq` pour un même émetteur ; l'application n'utilise jamais `ts` pour décider |

## 5.2. Client WebSocket (`HubClient`)

| Réf | Exigence | Vérification |
|---|---|---|
| INT-10 | URL `ws://<hôte>:<port>/ws`, sous-protocole `hiar.v1` ; hôte et port issus des réglages | Hub simulé |
| INT-11 | Poignée de main : `hello` (`device_id`, `role:"kiosk"`, `app_version`, `registry_hash`, `last_seq`, `token`) → attendre `welcome` (délai 3 s) ; avant `welcome`, rien d'autre n'est émis | CT-01 |
| INT-12 | `ping` toutes les 5 s ; liaison perdue après 2 `pong` manqués (≈ 11 s) | Hub simulé muet |
| INT-13 | Reconnexion exponentielle 0,5 → 1 → 2 → 4 → 8 s (plafond) avec gigue ±20 % ; à la reconnexion : `hello` avec `last_seq`, rejeu, réabonnements, republication de `ui/state` | Couper/rétablir le Wi-Fi |
| INT-14 | `seq` strictement croissant par session émettrice ; `id` unique par message | Test |
| INT-15 | **QoS 1** : attendre `ack` (`corr` = `id`) ; renvoyer après 1,5 s, 3 essais, puis échec remonté à l'appelant. **QoS 0** : aucun ack | Hub simulé qui perd des acks |
| INT-16 | **Déduplication** à la réception : cache des 512 derniers `id` ; un message déjà vu est acquitté mais pas retraité | Envoyer deux fois le même `id` |
| INT-17 | File d'envoi hors ligne : QoS 1 uniquement, ≤ 100 messages, péremption 30 s ; **jamais** de file pour une action robotique (`orientation.confirm`, `robot.stop`) : échec immédiat visible | Couper le réseau puis confirmer |
| INT-18 | Contre-pression : tampon > 256 Ko → on abandonne d'abord le QoS 0 ; `voice/stt/partial` limité à 10 msg/s ; au plus 50 msg/s au total ; message ≤ 64 Ko | Test de charge |
| INT-19 | Abonnements à la connexion : `voice/#`, `ui/#`, `robot/#`, `vitals/#`, `sys/#` (selon les droits `granted`) ; recevoir les messages **rétentionnés** (`ui/state`, `robot/*`, `vitals/state`, `sys/config`, `voice/stt/state`, `voice/tts/state`) | CT-03 |
| INT-20 | Pont par topic selon le mode du contrat (`local` / `out` / `in` / `both`) ; un topic `local` ne sort **jamais** de l'application | Capture réseau |
| INT-21 | Fermeture propre : `bye` ; reprise possible dans les 60 s sans perte (rejeu) | CT-06 |
| INT-22 | Droits : l'application (`kiosk`) **ne publie jamais** sur `robot/#` ni `vitals/result` ; elle traite `forbidden_topic` comme un bogue (journal + bandeau de diagnostic) | Test + CT-08 |

## 5.3. Client REST (`ApiClient`)

| Réf | Exigence | Vérification |
|---|---|---|
| INT-30 | Base `http://<hôte>:<port>` ; en-tête `Content-Type: application/json` ; corps JSON UTF-8 | — |
| INT-31 | Délais : connexion 3 s ; réponse 8 s ; **`/api/vitals/acquire` : 40 s** ; annulable par l'utilisateur (abandon côté client) | Serveur lent simulé |
| INT-32 | Pas de reprise automatique d'une écriture : `POST /api/request`, `POST /api/consultation/appointments` ne sont **jamais** rejoués sans action de l'utilisateur ; `POST /api/navigation/cancel` peut être rejoué une fois (idempotent) | Test |
| INT-33 | Chaque réponse est validée contre le schéma REST du contrat ; réponse hors contrat → erreur « réponse inattendue » (journalisée), jamais d'affichage de succès | Hub/serveur simulé avec réponses invalides |
| INT-34 | Table de traduction code HTTP / `code` métier → message (Dossier V4 §10.2), unique et testée | Tests |
| INT-35 | `GET /api/catalog` et `GET /api/voice/registry` au démarrage et au retour à l'accueil ; mise en cache sur disque ; si le `hash` diffère de celui embarqué, remplacer **seulement entre deux parcours**, jamais au milieu | Test |
| INT-36 | `GET /api/health` appelé toutes les 30 s à l'accueil pour la pastille de liaison (en plus de `robot/link`) | — |
| INT-37 | Date d'inscription = date du jour en fuseau `Indian/Antananarivo`, indépendante du fuseau de l'appareil | Appareil réglé sur un autre fuseau |

## 5.4. Registre et actions

| Réf | Exigence | Vérification |
|---|---|---|
| INT-40 | L'application embarque `assets/registry/actions.v1.json` ; au démarrage, comparer son `hash` à celui du serveur (`welcome.registry_hash`) | CT-02 |
| INT-41 | Les `action_id` émis dans `ui/action/request` et `voice/intent/resolved` sont ceux de `action_args` du contrat ; arguments validés par le schéma de l'action **avant** exécution | Tests T5 |
| INT-42 | `ui/state` publié à chaque affichage d'écran (rétentionné) : `screen`, `epoch`, `actions`, `dynamic`, `mission_active`, `sensitive_fields` ; `epoch` incrémenté à chaque changement d'écran | Test T6 |
| INT-43 | Une action serveur (`ui/action/request` d'origine `server`, rôle `service`) traverse **le même dispatcher** et les mêmes confirmations ; une action R2 d'origine `server` **exige** la confirmation locale (jamais d'orientation lancée à distance sans confirmation sur l'appareil) | Test |
| INT-44 | `voice/intent/suggest` reçu = simple suggestion : passe par le dispatcher ; si le contexte (`epoch`) a changé, ignorée | Test |
| INT-45 | `voice/tts/request` reçu du hub : respecte `priority`, `interrupt`, `ttl_ms` ; une demande périmée n'est jamais lue ; `sensitive:true` jamais journalisée | Tests |

## 5.5. Statuts robot : correspondance affichage

| Statut reçu | Affichage et voix |
|---|---|
| `robot/hmi/status` `VALIDATED` | (interne) demande validée par ROS 2 |
| `robot/hmi/status` `REJECTED` + `reason` | « Le robot a refusé la demande. » + motif lisible ; fin de mission |
| `robot/mission/status` `REQUEST_RECEIVED` | « Demande reçue. » |
| … `RUNNING` | « En route. Dites stop pour m'arrêter. » (**seul** statut qui autorise « en route ») |
| … `START_REJECTED:SENSORS_NOT_READY` | « Je ne peux pas partir : mes capteurs ne sont pas prêts. » |
| … `START_REJECTED:MISSION_ACTIVE` / `REQUEST_REJECTED:MISSION_ACTIVE` | « Je suis déjà en déplacement. » |
| … `START_REJECTED:NO_DESTINATION` | « Je n'ai pas de destination. » |
| … `BLOCKED` | « Je suis bloqué, je m'arrête. » |
| … `MISSION_TIMEOUT` | « Mon déplacement de démonstration est terminé. » |
| … `IDLE` (après STOP) | « Je m'arrête. » |
| `robot/safety` `OBSTACLE` | « Obstacle détecté. Je m'arrête. » (priorité TTS 0) |
| `robot/link` `ros_bridge:"down"` | « Le robot n'est pas disponible pour le moment. » ; orientation désactivée |

Un statut inconnu est journalisé et **ignoré** (jamais de message de succès par défaut).

## 5.6. Hub simulé (`tools/mock_hub.py`, livrable L5)

Serveur WebSocket Python (bibliothèque `websockets` ou `flask-sock`) qui implémente le **contrat** : poignée de main, `ping/pong`, `ack` QoS 1, rétention, rejeu, droits par rôle, limites. Il lit `hiar_contract_v1.json` pour valider **tout** ce qu'il reçoit et **tout** ce qu'il émet.

| Option de lancement | Effet |
|---|---|
| `--scenario nominal` | Rejoue l'orientation Pharmacie : `REQUEST_RECEIVED` → `RUNNING` → `MISSION_TIMEOUT` |
| `--scenario refuse` | `START_REJECTED:SENSORS_NOT_READY` |
| `--scenario blocked` / `obstacle` / `silent` | `BLOCKED` ; `robot/safety OBSTACLE` ; aucun statut (test des 4 s) |
| `--scenario ros-down` | `robot/link ros_bridge:"down"` |
| `--drop-acks N` | Perd N acks (test de renvoi QoS 1) |
| `--disconnect-after S` | Coupe la connexion après S secondes (test de reconnexion et rejeu) |
| `--service` | Un faux service externe publie `voice/tts/request` et `voice/intent/suggest` |
| `--strict` | Quitte en erreur si l'application émet un message hors contrat |

Il accompagne un **faux serveur REST** (mêmes scénarios : 201, 400, 409, 503, vitaux `valide`/`indisponible`/lent). Avec ces deux outils, **l'application se développe et se teste entièrement sans le Raspberry Pi**.

## 5.7. Client de conformité du vrai hub (`tools/hub_conformance.py`, livrable L6)

Joue la partie « application » contre le **vrai** hub (et le vrai serveur Flask) et produit un rapport. Tous les cas doivent être verts avant l'intégration.

| Cas | Vérifie |
|---|---|
| CT-01 | `hello` valide → `welcome` conforme au contrat ; `hello` sans jeton ou jeton faux → `auth_failed` et fermeture |
| CT-02 | `welcome.registry_hash` = `hash` de `GET /api/voice/registry` ; `registry_stale` correct |
| CT-03 | Abonnement à `robot/#` : réception des messages rétentionnés à l'abonnement |
| CT-04 | Publication `voice/stt/final` (QoS 1) → `ack` ; renvoi du même `id` → pas de double traitement |
| CT-05 | `v:2` → `error unsupported_version` |
| CT-06 | Déconnexion brutale puis `hello` avec `last_seq` → rejeu des QoS 1 manqués, sans doublon |
| CT-07 | Message > 64 Ko → `too_large` ; > 50 msg/s → `rate_limited` |
| CT-08 | `kiosk` publie sur `robot/mission/status` → `forbidden_topic` (et rien ne sort vers ROS 2) |
| CT-09 | Charge utile invalide (ex. `conf: 1.4`) → `bad_payload` (nack) |
| CT-10 | Action `orientation.confirm` via REST `POST /api/request` : le message arrive sur `/hmi/request` (observé avec `ros2 topic echo`) et les statuts reviennent en `robot/mission/status` |
| CT-11 | `robot.stop` → `/navigation/command` = `STOP` |
| CT-12 | `ping`/`pong` et fermeture après 2 `pong` manqués côté client simulé |
| CT-13 | Champ `sensitive:true` : absent du journal `hiar_hub.log` et jamais livré à un `monitor` |
| CT-14 | `GET /api/catalog` : 6 fiches structurées, `hash` stable ; `GET /api/health` conforme au schéma |

Chaque réponse est validée par `contract_validate.py` (mêmes schémas). Le rapport est joint à la recette.

---

# 6. EXIGENCES DE CONTRAT CÔTÉ SERVEUR (ce que le Pi doit offrir)

Ces points conditionnent la compatibilité ; ils sont réalisés en nouveaux modules, sans toucher au Web (Dossier V4 §10.3).

| Réf | Exigence | Vérification |
|---|---|---|
| SRV-01 | `/ws` (flask-sock) dans le **même processus** que Flask ; un seul nœud ROS 2 `hmi_bridge` (réutiliser `RosBridge`) | `ros2 node list` : un seul `hmi_bridge` |
| SRV-02 | Hub conforme au contrat : enveloppe, QoS 1/ack, rétention, anneau de rejeu de 256, droits par rôle, limites | CT-01 à CT-09 |
| SRV-03 | Relais ROS 2 → topics selon la table du Dossier V4 §7.7 (`/hmi/status`, `/navigation/status`, `/esp32/status` filtré `SAFETY,*`, `/sensors/obstacle` sur `CLEAR→OBSTACLE`, `/robot/status`) ; abonnements **en lecture seule** | Simulation puis ROS 2 réel |
| SRV-04 | Les seules sorties hub → ROS 2 sont `RosBridge.publish()` (orientation validée) et `RosBridge.cancel_navigation()` | Revue de code ; CT-08 |
| SRV-05 | `GET /api/catalog`, `GET /api/voice/registry`, `GET /api/health`, `GET /models/manifest.json` conformes aux schémas REST du contrat | CT-14 |
| SRV-06 | Variables d'environnement : `HIAR_DEVICE_TOKEN` (jeton d'appareil, distinct des jetons du personnel et des médecins), `HIAR_DEVICE_ALLOWLIST` (liste d'`device_id`), `HIAR_HUB_LOG` (chemin du journal). **Aucune valeur par défaut secrète** ; hub refusant de démarrer sans jeton | Démarrage sans variable |
| SRV-07 | Journal `hiar_hub.log` rotatif 7 jours, sans charge utile `voice/stt/*` ni contenu `sensitive` | CT-13 |
| SRV-08 | M1 : `hmi_request_node.py` accepte `TUBERCULOSIS` et `MENSTRUAL_HEALTH` ; test de cohérence catalogue ↔ validateur | Test T8 |
| SRV-09 | Tous les tests Web existants (142) passent **sans modification** ; `git diff` sur `templates/` et `static/` vide | CI |
| SRV-10 | Seule modification autorisée de `app.py` : enregistrement du blueprint et du montage `/ws` (quelques lignes ajoutées, aucune route existante modifiée) | `git diff app.py` |

---

# 7. EXIGENCES NON FONCTIONNELLES

| Réf | Exigence | Vérification |
|---|---|---|
| QUA-01 | Performances : budgets du Dossier V4 §4.3 | Rapport L8 |
| QUA-02 | Mémoire ≤ 700 Mo avec VAD, STT et TTS chargés ; pas de fuite sur 30 min de parcours répétés | Profil mémoire |
| QUA-03 | Stabilité : 2 h de fonctionnement continu (veille ↔ parcours) sans plantage, sans arrêt par MIUI | Essai d'endurance |
| QUA-04 | Accessibilité : cibles ≥ 56 dp, texte courant ≥ 18 sp, contraste ≥ 4,5:1, état jamais porté par la seule couleur, `Semantics.identifier` = id d'action | Widget tests + revue |
| QUA-05 | Internationalisation : **aucune** chaîne en dur ; fichiers ARB `fr` ; un test échoue si un littéral français apparaît dans `lib/features/**` | Test automatique |
| QUA-06 | Qualité de code : `flutter analyze` sans erreur ni avertissement ; règles `flutter_lints` + règle interdisant les contrôles bruts hors `ActionButton` | CI |
| QUA-07 | Couverture : ≥ 80 % sur `domain/`, `voice/` (hors adaptateurs sherpa), `core/` | `flutter test --coverage` |
| QUA-08 | Journalisation : niveaux ; jamais de nom, téléphone, texte dicté, jeton | Test de fuite (recherche dans les journaux après un parcours) |
| QUA-09 | Robustesse : message JSON invalide, déconnexion en plein envoi, réponse HTTP tronquée → aucun plantage | Tests de fuzz simples |
| QUA-10 | Sécurité : jeton d'appareil en stockage chiffré ; `allowBackup=false` ; aucune permission hors 2.2 ; aucun trafic hors `10.42.0.1` (ou l'hôte configuré) | `adb shell dumpsys`, capture réseau |

---

# 8. TESTS

## 8.1. Niveaux

| Niveau | Contenu minimal |
|---|---|
| Unitaires | Normaliseur, `NumberParser`, `Matcher`, politique d'ambiguïté, machine à états vocale, `TtsQueue`, `HubClient` (QoS, dédup, reconnexion, rejeu, file), `ApiClient` (délais, traductions d'erreurs) |
| Contrat | Les 61 vecteurs du contrat validés **par les modèles Dart** ; générer et comparer le registre embarqué (T7) |
| Widgets | Chaque écran et chaque état d'erreur à 640 × 360 et 851 × 393 dp ; absence de défilement des menus |
| Parité | T1 à T8 (Dossier V4 §13.3) |
| Scénarios | Les 11 scénarios du Dossier V4 §8.5–8.6 contre le hub simulé et le faux REST |
| Conformité serveur | CT-01 à CT-14 contre le vrai hub |
| Intégration sans moteurs | Matrice 9.2, Pi réel, **moteurs non alimentés** |
| Appareil | Endurance, mémoire, latences, MIUI |
| Physique | Seulement après accord écrit de l'auteur |

## 8.2. Commandes de vérification attendues (à fournir dans `README_MOBILE.md`)

```bash
# Contrat
python3 -I contract_validate.py hiar_contract_v1.json
# Application
flutter analyze && flutter test --coverage
# Hub simulé + application (développement sans Pi)
python3 tools/mock_hub.py --scenario nominal --strict
# Serveur : tests existants + nouveaux
cd web_interface && python3 -m pytest tests hub/tests -q
# Conformité du vrai hub
python3 tools/hub_conformance.py --host 10.42.0.1 --port 5000 --token "$HIAR_DEVICE_TOKEN"
```

---

# 9. INTÉGRATION : « COMPATIBLE DÈS LA PREMIÈRE FOIS »

## 9.1. Procédure du jour J (dans l'ordre ; ne pas passer à l'étape suivante si une étape échoue)

| # | Étape | Résultat attendu observable |
|---|---|---|
| 1 | `contract_validate.py` | `OK : contrat 1.0.0 conforme` |
| 2 | Tests Web existants (142) | Tous verts (hors les 2 échecs déjà connus de l'archive, à documenter) |
| 3 | Tests `hub/` + client de conformité sur un serveur lancé **sans ROS 2** | CT-01 à CT-09, CT-12 à CT-14 verts |
| 4 | Lancer ROS 2 (`hiar_robot.launch.py`), moteurs **non alimentés** | 5 nœuds présents (`ros2 node list`) |
| 5 | CT-10 et CT-11 | `/hmi/request` et `/navigation/command` observés avec `ros2 topic echo` |
| 6 | Installer l'APK sur le Xiaomi ; régler MIUI (batterie, démarrage auto, données mobiles coupées) ; saisir l'adresse et le jeton | Pastille de liaison verte |
| 7 | Poignée de main réelle | Journal du hub : connexion `kiosk`, registre identique, rétention reçue |
| 8 | Parcours 1 : Renseignements, 6 fiches, lecture à voix haute | Aucun `POST /api/request` dans les journaux serveur |
| 9 | Parcours 2 : Consultation complète par la voix | Ticket `A-MAT-n` ; ligne créée dans la base **de test** |
| 10 | Parcours 3 : Orientation (moteurs non alimentés) | `/hmi/request`, `VALIDATED`, `RUNNING`, `MISSION_TIMEOUT` visibles dans l'application |
| 11 | ARRÊT pendant la mission, au toucher puis à la voix | `STOP` sur `/navigation/command` en < 1,5 s |
| 12 | Coupure du Wi-Fi 20 s puis retour | Reconnexion ≤ 15 s, rejeu sans doublon, voix locale intacte hors ligne |
| 13 | Pi redémarré pendant que l'application tourne | Retour à l'état connecté sans action de l'utilisateur |

Toute étape non conforme est consignée avec journal et capture dans `docs/recette.md`.

## 9.2. Matrice d'intégration (conditions × parcours)

Chaque cellule est un test ; « ✓ » = doit réussir, « D » = doit se dégrader comme décrit (Dossier V4 §8.8).

| Condition | Fiches | Consultation | Orientation | ARRÊT | Voix locale |
|---|---|---|---|---|---|
| Tout nominal | ✓ | ✓ | ✓ | ✓ | ✓ |
| Hub injoignable, REST joignable | ✓ (cache/serveur) | ✓ | D (désactivée, expliquée) | D | ✓ |
| Pi injoignable | ✓ (cache) | D (désactivée) | D | D (message « non confirmé ») | ✓ |
| ROS 2 arrêté, Flask actif | ✓ | ✓ (sans vitaux) | D (« robot indisponible ») | D | ✓ |
| Capteurs robot non prêts | ✓ | ✓ (vitaux indisponibles) | D (`SENSORS_NOT_READY`) | ✓ | ✓ |
| Wi-Fi coupé puis rétabli en cours de parcours | ✓ | ✓ sans perte de saisie | D puis ✓ | ✓ | ✓ |
| Modèle STT absent | ✓ | ✓ | ✓ | ✓ | D (tactile seul) |
| Micro refusé | ✓ | ✓ | ✓ | ✓ | D |
| Registre serveur plus récent | ✓ | ✓ | ✓ | ✓ | ✓ (rechargé entre parcours) |
| Version de protocole inconnue | ✓ | ✓ | D | D | ✓ |

---

# 10. LIVRAISON, RECETTE, PLANNING

## 10.1. Définition de « terminé » (toutes cases obligatoires)

- [ ] `contract_validate.py` vert et **modèles Dart validés contre les vecteurs**.
- [ ] Parité T1 à T8 verte.
- [ ] CT-01 à CT-14 verts sur le vrai hub.
- [ ] Les 13 étapes du jour J exécutées et documentées.
- [ ] Matrice 9.2 entièrement renseignée.
- [ ] `flutter analyze` propre, couverture ≥ 80 % des couches cibles.
- [ ] Budgets de performance mesurés sur le Xiaomi et consignés.
- [ ] Aucun fichier Web modifié ; 142 tests Web identiques.
- [ ] Aucun secret, aucune donnée personnelle dans le dépôt, l'APK, les journaux.
- [ ] Limites déclarées dans la documentation : « stop » vocal ≠ arrêt d'urgence ; pas de notion d'arrivée ; mission bornée à 8 s côté ROS 2 ; mesures non diagnostiques ; comportement physique de la mission **non validé** tant que l'auteur ne l'a pas observé.

## 10.2. Lots (rappel, détail au Dossier V4 §14)

WP0 hygiène → WP1 spike voix (Xiaomi) → WP2 contrats serveur → WP3 hub → WP4 squelette app → WP5 registre et dispatcher → WP6 moteur vocal → WP7 écrans → WP8 intégration sans moteurs (procédure 9.1) → WP9 essais physiques (accord écrit de l'auteur).

Ordre de construction recommandé pour la compatibilité : **contrat → hub simulé → application contre le simulé → serveur réel → conformité → intégration**. Le serveur réel et l'application ne se rencontrent qu'une fois chacun conforme au contrat de son côté ; la rencontre devient alors une simple vérification.

## 10.3. Risques et parades

| Risque | Parade |
|---|---|
| Version de `sherpa_onnx` sans support Android complet ou VAD/TTS manquants | Spike WP1 en premier ; interface `SttEngine`/`TtsEngine` pour changer de moteur ; repli TTS système |
| MIUI tue l'application ou coupe le micro | Réglages 4.7 du Dossier V4 ; test d'endurance QUA-03 |
| Trafic détourné vers les données mobiles | ENV-06 à ENV-08 |
| Dérive entre le contrat et le code | INT-01 (modèles dérivés, tests de vecteurs) ; CI qui échoue |
| Écho (le robot s'entend) | Demi-duplex A1 systématique, quelle que soit l'annulation d'écho matérielle |
| Dictée de noms peu fiable | Clavier toujours disponible ; retrait de la dictée du nom si échec au benchmark (Dossier V4 §13.2) |
| Statuts ROS 2 inattendus | Statut inconnu ignoré et journalisé (5.5) ; jamais de succès par défaut |
| Mouvement non voulu | Confirmation R2 voix **et** toucher, jetons de contexte `epoch`, seuils en mission |

---

# ANNEXES

## Annexe A. Contenu du contrat `hiar_contract_v1.json`

| Clé | Contenu |
|---|---|
| `limits` | taille max, heartbeat, délais d'ack, tailles de caches, débits |
| `roles` | `kiosk`, `service`, `monitor` |
| `envelope` | schéma JSON de l'enveloppe, avec champs obligatoires selon `type` |
| `topics` | pour chacun des 27 topics : `mode`, `qos`, `retain`, `publishers`, `subscribers`, schéma de charge utile |
| `action_args` | schéma des arguments de chacune des 41 actions ; `action_risk_overrides` : R1/R2/R3 |
| `rest` | requêtes et réponses (par code HTTP) des 9 endpoints |
| `permissions` | topics publiables / abonnables par rôle |
| `vectors` | 36 messages (valides **et invalides**), 9 jeux d'arguments, 10 droits |

Règle de modification : tout changement du contrat s'accompagne d'un incrément de `contract_version` (mineur si compatible, majeur sinon), de la mise à jour des vecteurs et d'une exécution verte de `contract_validate.py`, **côté application et côté serveur dans le même changement**.

## Annexe B. Variables et paramètres de configuration

| Clé | Côté | Défaut | Rôle |
|---|---|---|---|
| `server.host` / `server.port` | App | `10.42.0.1` / `5000` | Cible réseau |
| `device.id` | App | généré au provisionnement (`tab-01`) | Identité |
| `device.token` | App (stockage chiffré) | saisi | Authentification hub |
| `voice.threshold.command` | App | 0,90 (0,92 en mission) | Seuil d'acceptation |
| `voice.threshold.confirm` | App | 0,75 | Seuil de demande de confirmation |
| `voice.listen.mode` | App | `session` | `session` ou `push` |
| `idle.timeout.s` | App | 90 / 180 | Veille |
| `HIAR_DEVICE_TOKEN` | Serveur | **aucun** | Jeton d'appareil |
| `HIAR_DEVICE_ALLOWLIST` | Serveur | vide = refus | Appareils autorisés |
| `HIAR_HUB_LOG` | Serveur | `~/hiar_logs/hiar_hub.log` | Journal du hub |

## Annexe C. Codes d'erreur

Protocole : `unsupported_version`, `auth_failed`, `forbidden_topic`, `too_large`, `rate_limited`, `bad_payload`, `unknown_topic`, `internal`. Résultat d'action (`ui/action/result.code`) : `stale`, `busy`, `unavailable`, `forbidden`, `network`, `server`, `rejected`, `timeout`.

## Annexe D. Manifeste des modèles (`GET /models/manifest.json`)

Champs par fichier : `role` (`vad`, `stt_command`, `stt_dictation`, `tts`), `name`, `path`, `bytes`, `sha256` (64 hexadécimaux), `required`. L'application active un modèle seulement si la taille et le SHA-256 correspondent.

## Annexe E. Gabarit de procès-verbal de recette (`docs/recette.md`)

| Réf exigence | Critère | Résultat (✓/✗/D) | Preuve (journal, capture, mesure) | Date | Testeur |
|---|---|---|---|---|---|
| FUN-21 | Confirmation d'orientation obligatoire | | | | |
| … | … | | | | |

Une exigence sans preuve n'est pas « vérifiée ».

## Annexe F. Traçabilité

| Domaine | Exigences | Source de détail |
|---|---|---|
| Environnement | ENV-01 à ENV-08 | Chap. 2 ; Dossier V4 §4.1, §4.7, §12.2 |
| Fonctionnel | FUN-01 à FUN-55 | Chap. 3 ; Dossier V4 §6, §9.6, §10 |
| Vocal | VOX-01 à VOX-16 | Chap. 4 ; Dossier V4 §6.7, §8 |
| Interopérabilité | INT-01 à INT-45 | Chap. 5 ; contrat JSON ; Dossier V4 §7 |
| Serveur | SRV-01 à SRV-10 | Chap. 6 ; Dossier V4 §7.7, §10.3 |
| Qualité | QUA-01 à QUA-10 | Chap. 7 |
| Tests | CT-01 à CT-14, T1 à T8, matrice 9.2 | Chap. 5.7, 8, 9 ; Dossier V4 §13.3 |
