# DOSSIER TECHNIQUE DU PROJET HIAR — V4
## Hospital Intelligent Assistant Robot
### Application mobile Android (paysage) avec interaction vocale native hors ligne

**Version :** V4 — révision 2 (14 novembre 2026) : décisions de l'auteur intégrées (section 1.5)
**Remplace :** Dossier_HIAR_V3 (les parties non modifiées de la V3 restent valables ; elles sont rappelées en section 2.3)
**Destinataire principal :** un agent IA de développement qui implémentera le code. Ce dossier est donc écrit comme une spécification : chaque décision est tranchée, chaque contrat est explicite, chaque point incertain est marqué.
**Sources de cette V4 :** Dossier_HIAR_V3 + audit du code (archive `hiar_audit_20261114.tgz`, 122 fichiers) + consignes de l'auteur du projet.

---

# 0. COMMENT LIRE ET UTILISER CE DOSSIER

## 0.1. Trois niveaux de certitude (à respecter dans tout le code et la documentation)

| Marqueur | Sens |
|---|---|
| **[CODE]** | Constaté en lisant le code de l'archive d'audit du 14/11/2026. Ne prouve pas le fonctionnement physique. |
| **[V4]** | Décision de conception de cette version. À implémenter. |
| **[À VÉRIFIER]** | Hypothèse ou donnée externe (modèle, version de paquet, taille, performance) à confirmer par un essai avant de s'y engager. |

Règle héritée de la V3 : ne jamais déclarer « fonctionnel » une chaîne qui n'a pas été observée de bout en bout sur le matériel. Un test automatisé qui passe n'est pas une preuve de comportement physique.

## 0.2. Règles impératives pour l'agent codeur

1. **Inspecter avant de modifier.** Lire le fichier concerné et ses tests avant toute modification.
2. **Ne pas toucher** : le firmware ESP32 (aucun flash sans accord explicite), `robot_supervisor.py`, `navigation_decision_node.py` (sauf demande explicite de la section 14), les fichiers `*.bak`, `*.before-*` (ne pas les supprimer sans décision de l'auteur), et **toute l'interface Web : `templates/`, `static/`, pages `/`, `/staff`, `/doctor` (Web gelé, décision de l'auteur, section 1.5)**. Les routes REST existantes ne changent ni de comportement ni de contrat ; les ajouts serveur se font dans de **nouveaux modules** (section 10.3).
3. **Aucune commande moteur** ne doit jamais être émise par l'application mobile ni par le hub WebSocket. Seules deux actions robotiques existent côté application : publier une demande d'orientation validée (`/hmi/request`) et publier `STOP` sur `/navigation/command`. Ce sont les fonctions existantes `RosBridge.publish()` et `RosBridge.cancel_navigation()`.
4. **Un seul point d'entrée pour toute action** : le `ActionDispatcher` (section 6). Aucun bouton, aucune commande vocale n'appelle directement l'API ou la navigation d'écran.
5. **Ne jamais inventer de valeur** : une mesure indisponible reste indisponible (règle V3 §7.6). La SpO₂ n'est pas affichée (règle V3 §1.5).
6. **Ne jamais annoncer qu'une action robotique est acceptée ou exécutée** avant d'en avoir reçu la preuve sur le canal d'état (section 7.6). Les messages vocaux et visuels doivent suivre l'état réel.
7. **Ne pas journaliser de données personnelles** (nom, téléphone, texte dicté) en clair. Voir section 12.
8. **Aucun secret dans le dépôt, les journaux, les archives, ni ce dossier.** Voir section 2.2, constat S1.
9. Travailler **lot par lot** (section 14), avec une définition de « terminé » vérifiable pour chaque lot.

## 0.3. Glossaire minimal

| Terme | Définition |
|---|---|
| STT | Speech-To-Text, reconnaissance vocale |
| TTS | Text-To-Speech, synthèse vocale |
| VAD | Voice Activity Detection, détection de parole |
| Hub | Module serveur WebSocket hébergé sur le Raspberry Pi (nouveau) |
| Bus | Bus d'événements interne à l'application, calqué sur les topics du hub |
| Topic | Canal de publication/abonnement nommé, hiérarchique (`voice/stt/final`) |
| Action | Opération identifiée de l'interface (équivalent d'un bouton). Toute action existe en tactile ET en vocal |
| Registre | Fichier unique décrivant toutes les actions, leurs libellés, leurs phrases vocales et leur niveau de risque |
| Dispatcher | Composant unique qui exécute une action, quelle que soit son origine (tactile, vocale, système) |
| Origine | `touch`, `voice`, `system`, `server` |

---

# 1. CADRAGE V4

## 1.1. Ce que change la V4

La V3 décrit une interface Web consultée depuis un navigateur de smartphone. La V4 ajoute une **application Android native** qui :

1. reprend **toutes** les fonctions patient/visiteur de l'interface Web ;
2. ajoute une **interaction vocale hors ligne** (STT + TTS exécutés sur l'appareil), **en parallèle** de l'écran tactile ;
3. échange ses événements vocaux avec le Raspberry Pi par **WebSocket**, selon un modèle **publication/abonnement par topics** ;
4. propose une **interface repensée** (paysage, bonne UX) tout en gardant **l'identité visuelle** de l'interface Web (couleurs, polices, logo, robot).

## 1.2. Objectifs spécifiques V4

| # | Objectif |
|---|---|
| O1 | Application Android native en **paysage uniquement**, destinée à un smartphone ou une tablette utilisé comme écran tactile du robot |
| O2 | **Parité totale tactile/vocale** : toute action disponible par bouton est exécutable et détectable par la voix, et réciproquement |
| O3 | STT et TTS **100 % hors ligne** sur l'appareil (aucun service cloud) |
| O4 | Communication **WebSocket** par topics entre l'application et le Pi, avec une conception par événements |
| O5 | Interface mobile **de même style et mêmes couleurs** que le Web, mais avec une UX nettement améliorée (le Web n'est pas un modèle à imiter) |
| O6 | Aucune régression de sécurité : la voix n'a **aucune autorité supplémentaire** sur le robot |
| O7 | Fonctionnement dégradé défini quand le Pi ou le réseau est indisponible |

## 1.3. Périmètre

**Dans le périmètre V4**

- Écran d'accueil, menu des 3 catégories (Orientation, Renseignements, Consultation).
- Orientation : Pharmacie, Laboratoire, Réception, avec suivi d'état de mission et arrêt.
- Renseignements : 6 fiches (VIH/SIDA, Paludisme, Diabète, Hypertension, Tuberculose, Santé menstruelle), lecture à voix haute.
- Consultation : parcours en 5 étapes + ticket (motif, session médecin/période, coordonnées, signes vitaux facultatifs, vérification, confirmation, numéro de file).
- Acquisition des signes vitaux (température, fréquence cardiaque) via le robot.
- Interaction vocale complète (écoute, compréhension des commandes, réponses parlées, lecture des fiches).
- Hub WebSocket côté Raspberry Pi et relais d'état ROS 2 → application.

**Hors périmètre V4**

- Interfaces **personnel** (`/staff`) et **médecin** (`/doctor`) : elles **restent dans le Web** (décision confirmée).
- **Toute modification de l'interface Web** (gelée), iOS, portrait. L'application est **uniquement en paysage**.
- SLAM, cartographie, localisation, confirmation d'arrivée.
- Dispositif médical, diagnostic, remplacement du personnel (limites V3 inchangées).
- Langues autres que le français au premier lot (architecture prête pour le malgache, section 4.6).

## 1.4. Hypothèses à valider (marquées dans le texte)

| # | Hypothèse | Impact si fausse |
|---|---|---|
| H1 | **CONFIRMÉE** : staff et médecin restent Web | — |
| H2 | **CORRIGÉE par l'auteur** : l'application mobile est la cible ; c'est le **Web** qui n'est plus touché. Paysage uniquement | — |
| H3 | **CONFIRMÉE** : français seul ; le malgache est une perspective (4.6) | — |
| H4 | **REMPLACÉE par l'appareil réel** (section 4.7) : Xiaomi Mi CC9 Pro, 6 Go de RAM, Android 10 | — |
| H5 | Un seul appareil client à la fois pendant la démonstration (plusieurs clients restent possibles par conception) | Aucun, le hub gère N clients |
| H6 | L'appareil est posé ou fixé sur le robot, utilisé en **kiosque** (écran allumé, une seule application) | Les règles kiosque (section 9.7) deviennent facultatives |


## 1.5. Décisions de l'auteur intégrées (révision 2)

| Réf | Décision | Effet sur ce dossier |
|---|---|---|
| Q1 | Les interfaces personnel et médecin **restent dans le Web** | H1 confirmée ; aucun portage |
| Q2 | Correction d'une faute de frappe : **l'application mobile est le livrable**, c'est **le Web qui n'est plus touché** | Web gelé (règle 0.2-2) ; ajouts serveur uniquement en nouveaux modules ; M2 abandonnée ; défauts du Web (C2, C6, U1 à U12) documentés mais non corrigés. Orientation inchangée : paysage uniquement |
| Q3 | Le malgache est **négligé pour l'instant** : amélioration future | Français seul ; 4.6 devient une perspective ; l'architecture garde le champ `lang` |
| Q5 | Appareil de test : **Xiaomi Mi CC9 Pro**, 6 Go de RAM | Section 4.7 ; modèle de dictée allégé ; consignes MIUI |
| Q6 | Confirmation obligatoire avant **chaque** orientation, y compris au toucher : **oui** | Politique 6.5 confirmée, plus une question ouverte |

Restent sans réponse (valeurs par défaut appliquées) : Q4, Q7, Q8, Q9 (section 15).

---

# 2. ÉTAT RÉEL DU PROJET À LA DATE DE L'AUDIT

Cette section remplace la présomption « le code correspond au dossier ». Chaque écart doit être traité ou accepté explicitement.

## 2.1. Inventaire constaté **[CODE]**

| Domaine | Constat |
|---|---|
| Web | Flask, `app.py` (849 lignes), routes patient, personnel, médecin ; `catalog.py` ; `requests_model.py` ; `ros_bridge.py` ; SQLite (`appointments`, `doctor_sessions`, `hiar_schema_migrations`) |
| Interface Web | `index.html` (une page, écrans empilés), `hmi.js`, `consultation.js`, `hiar-voice.js`, CSS : `hiar-tokens.css`, `hiar-redesign.css` (1 984 lignes), `hmi.css`, etc. |
| Voix Web existante | `hiar-voice.js` : Web Speech API du navigateur (`SpeechRecognition`, `speechSynthesis`), 6 commandes seulement (3 catégories, accueil, répéter, arrêt voix/écoute). **Dépend du navigateur et, sur Android/Chrome, d'un service de reconnaissance généralement en ligne. Ce n'est pas du hors ligne.** |
| ROS 2 | 5 nœuds lancés par `hiar_robot.launch.py` : `esp32_interface`, `obstacle_detector`, `robot_supervisor`, `navigation_decision`, `hmi_request_receiver`. `robot_status` existe dans `setup.py` mais **n'est pas lancé** |
| Firmware | `HIAR_ESP32_V08_stable` (stable, ancien câblage), `HIAR_ESP32_adaptation_materielle_dev` (nouveau câblage), `HIAR_VITALS_ESP32_test`. Le firmware fusionné décrit dans `DECISION_FUSION_FIRMWARE_ESP32.md` **n'est pas présent** dans l'archive |
| Tests | 142 fonctions de test côté Web (13 fichiers), 26 côté ROS 2 (hors fichiers de lint). Dernier état connu : 2 échecs Web enregistrés dans le cache pytest (`test_closed_session_and_expired_cutoff_are_refused`, `test_staff_interface_is_read_only`). Les tests de lint ROS 2 (`flake8`, `pep257`, `copyright`) figurent parmi les échecs enregistrés |

## 2.2. Constats et actions

### Sécurité et hygiène du dépôt

| Réf | Constat **[CODE]** | Gravité | Action |
|---|---|---|---|
| S1 | L'archive d'audit contient `.env` (jeton du personnel) et `web_interface/.doctor-secrets` (jetons des médecins A à D). Ils sont dans `.gitignore`, mais ont été inclus dans l'archive transmise | **Élevée** | Considérer ces jetons comme **compromis** : les régénérer. Ne plus inclure ces fichiers dans une archive. Ce dossier ne reproduit aucun secret |
| S2 | `web_interface/instance/appointments.sqlite3` est dans l'archive : 11 rendez-vous (noms et téléphones de patients) et 40 sessions | Moyenne | Ne pas transmettre de base réelle. Fournir une base de test synthétique pour le développement |
| S3 | Fichiers parasites vides à la racine : `Get-FileHash`, `,heart_rate_bpm=`, `,spo2_percent=NA`, `web_interface/PY`, `web_interface/for` (erreurs de redirection shell) | Faible | Supprimer **avec l'accord de l'auteur** |
| S4 | Nombreux `*.bak`, `*.before-*` dans les sources et les tests | Faible | Conserver le temps de la V4 ; archiver hors dépôt ensuite (décision de l'auteur) |
| S5 | `docs/PROMPTS.md` est vide (0 octet) | Faible | Ne pas supprimer sans décision (règle du checkpoint du 15/10) |

### Écarts fonctionnels et contractuels

| Réf | Constat **[CODE]** | Conséquence | Action V4 |
|---|---|---|---|
| C1 | `catalog.py` contient **6** fiches d'information (VIH, paludisme, diabète, hypertension, **tuberculose, santé menstruelle**). Le validateur ROS 2 `hmi_request_node.py` n'en connaît que **4** | Une demande « Tuberculose » reçoit `ok:true` côté Flask mais est rejetée en silence côté ROS 2 (`REJECTED:UNKNOWN_OR_UNAVAILABLE_ITEM`) | Aligner les deux listes (lot WP2). Ajouter un test de cohérence catalogue ↔ validateur |
| C2 | `POST /api/request` publie **toute** demande sur ROS 2, y compris les fiches d'information, et répond **503** si le pont ROS 2 est inactif | Lire une fiche échoue si ROS 2 est arrêté, alors que l'information est locale | **Le Web est gelé : on ne le corrige pas.** L'application ne passe **pas** par cette route pour les fiches : elle les lit via `GET /api/catalog` (N1), sans ROS 2. La route reste telle quelle |
| C3 | `navigation_decision_node.py` : à la réception d'une demande valide sur `/navigation/request`, il appelle **`start_mission()` automatiquement** (mission bornée à 8 s, `MAX_MISSION_DURATION_S = 8.0`, fin par `MISSION_TIMEOUT`). Le checkpoint du 15/10 disait « ne pas lancer automatiquement START » : **la documentation est périmée** | Une commande vocale mal comprise peut mettre le robot en mouvement | La voix ET le tactile passent par une **confirmation obligatoire** avant toute orientation (section 6.5). Le comportement physique reste **[À VÉRIFIER]** |
| C4 | Aucun retour d'état vers l'interface : le `ok:true` de `/api/request` signifie seulement « publié sur `/hmi/request` ». Les topics `/hmi/status`, `/navigation/status`, `/robot/status`, `/esp32/status` ne sont jamais relus par le Web | L'interface ne peut pas dire si le robot est parti, refusé (`SENSORS_NOT_READY`), ou arrêté | Relais ROS 2 → hub → application (section 7.7) |
| C5 | Aucune notion d'**arrivée** : la mission se termine uniquement par `MISSION_TIMEOUT` après 8 s (pas de localisation) | Dire « nous sommes arrivés » serait faux | Messages V4 : « mission de démonstration terminée », jamais « arrivé » (section 8.7) |
| C6 | `index.html` affiche encore une carte **SpO₂** (« En attente »). La V3 dit que la SpO₂ n'est pas affichée | Incohérence V3 ↔ Web | Web gelé, **non corrigé**. L'application mobile n'affiche **pas** la SpO₂ ; le champ reste envoyé à `null` |
| C7 | `catalog.py` : `VITAL_SIGNS` est `available: False` dans CONSULTATION, mais les signes vitaux existent comme **étape 4** du parcours de consultation | Deux notions pour la même fonction | Ne pas exposer `VITAL_SIGNS` comme action de menu ; c'est une étape du parcours |
| C8 | `/api/vitals/acquire` est **bloquant jusqu'à 35 s** dans la requête HTTP (attente d'un `RESULT`/`ERROR` via `/vitals/result`). Le nœud ROS 2 a un délai de 32 s | L'application doit gérer une attente longue et son annulation | Section 8.6 (scénario vitaux) |
| C9 | `vital_signs.py` (acquisition par port série direct, `HIAR_VITALS_PORT`) coexiste avec l'acquisition par ROS 2 (`ros_bridge.acquire_vitals`) | Deux chemins possibles pour la même mesure ; seul `_build` et `_result` de `vital_signs.py` sont utilisés par `app.py` | Hors périmètre ; ne pas utiliser `vital_signs.acquire()` |
| C10 | Brochage : le checkpoint du 04/11 place le DS18B20 sur **GPIO4** ; la décision de fusion du 10/11 impose **GPIO23** | Incohérence de documentation | À trancher à la fusion du firmware (hors périmètre V4, mentionné pour mémoire) |
| C11 | Serveur : `app.run(host="0.0.0.0", port=5000)` (serveur de développement Werkzeug). Aucun WebSocket. Aucun point de santé (`/api/health`) | Nécessaire pour le hub | Section 10 |
| C12 | `static/hiar-voice.js` utilise `SpeechRecognition` Web et supposait le navigateur | Remplacé dans l'application mobile par STT/TTS natifs ; la page Web reste inchangée | Ne pas modifier la page Web (gelée) |

## 2.3. Ce qui reste valable de la V3 (non répété)

Architecture globale (Smartphone → Wi-Fi HIAR-DEMO → Raspberry Pi 4 → Flask / SQLite / ROS 2 → ESP32), rôles des nœuds ROS 2, protocole série ESP32, contrat `/hmi/request`, règles de sécurité (sections 5.3 et 5.4 de la V3), scénarios de démarrage, d'obstacle et d'échec de communication, règles de gestion des rendez-vous (une réservation par téléphone et par jour, contrôles côté serveur, transactions), principe **« L'IA comprend. La navigation décide du mouvement. Le Supervisor valide. L'ESP32 exécute. »**

Adresses de démonstration inchangées : point d'accès `HIAR-DEMO`, Pi `10.42.0.1`, port `5000`.

---

# 3. ARCHITECTURE GLOBALE V4

## 3.1. Vue d'ensemble

```text
 ┌──────────────────────── APPLICATION ANDROID (Flutter, paysage) ───────────────────────┐
 │                                                                                         │
 │  UI tactile ──┐                                      ┌── STT (sherpa-onnx, hors ligne)  │
 │               ├─► ActionDispatcher ◄─ Interpréteur ◄─┤        micro → VAD → texte      │
 │  Voix ────────┘        │             (grammaire)     └── TTS (sherpa-onnx, hors ligne)  │
 │                        │                                       ▲  haut-parleur          │
 │                        ▼                                       │                        │
 │              ┌────── BUS D'ÉVÉNEMENTS LOCAL (topics) ──────────┴───┐                    │
 │              │   voice/*   ui/*   robot/*   vitals/*   sys/*       │                    │
 │              └──────────────┬──────────────────────────────────────┘                    │
 │                             │  Pont WebSocket (par topic : local / out / in / both)      │
 └─────────────────────────────┼───────────────────────────────────────────────────────────┘
                               │  ws://10.42.0.1:5000/ws        REST : http://10.42.0.1:5000/api/*
                               ▼                                          │
 ┌──────────────────────── RASPBERRY PI 4 (Ubuntu 22.04, ROS 2 Humble) ───┼───────────────┐
 │  HUB WebSocket (nouveau)  ◄──── relais d'état ────  RosBridge ◄────────┘               │
 │   routeur de topics, rétention,     (/hmi/status, /navigation/status, /robot/status,    │
 │   QoS 1, rejeu, droits par rôle      /esp32/status, /sensors/obstacle, /vitals/result)  │
 │                                                                                         │
 │  Flask (REST existant) ── SQLite        ROS 2 : hmi_request_receiver → navigation       │
 │                                         → supervisor → esp32_interface → ESP32          │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
```

## 3.2. Principes d'architecture **[V4]**

| # | Principe |
|---|---|
| P1 | **Local d'abord.** Tout ce qui est voix (VAD, STT, interprétation des commandes, TTS) fonctionne sur l'appareil sans le Pi. Le réseau local enrichit, il n'est pas requis pour comprendre une commande. |
| P2 | **Une action, un chemin.** Tactile, voix, serveur et système produisent la même `ActionRequest`, exécutée par le même `ActionDispatcher`, validée par les mêmes règles que le Web. |
| P3 | **La voix n'a aucun pouvoir propre.** Un texte transcrit ne devient une action que s'il correspond à une entrée du registre, disponible dans le contexte courant, avec le niveau de confirmation requis. |
| P4 | **REST pour les opérations métier, WebSocket pour les événements.** Réservation, créneaux, signes vitaux, orientation : les endpoints REST existants restent la référence testée. Le WebSocket transporte les événements vocaux, les états et les notifications. |
| P5 | **Le serveur ne décide pas du mouvement.** Le hub relaie vers ROS 2 par les deux seules fonctions autorisées (section 0.2, règle 3). |
| P6 | **Dire la vérité.** Les réponses vocales et visuelles reflètent l'état réellement observé (section 7.7), jamais une hypothèse optimiste. |
| P7 | **Dégradation explicite.** Chaque perte (réseau, STT, TTS, ROS 2) a un comportement défini et une annonce à l'utilisateur (section 8.8). |
| P8 | **Registre unique.** Libellés, phrases vocales, risque et effet de chaque action sont décrits une seule fois et servis au Web, à l'application et aux tests. |

## 3.3. Séparation des responsabilités (extension de la V3)

> **La voix transcrit. L'interpréteur propose. Le dispatcher valide. La navigation décide du mouvement. Le Supervisor valide. L'ESP32 exécute.**

Une éventuelle IA côté serveur (classifieur d'intentions de la V3 §8.6, ou futur modèle de langage) est **un fournisseur de suggestions** (`voice/intent/suggest`) : elle n'exécute rien et ses suggestions traversent le même dispatcher, avec les mêmes confirmations.

---

# 4. STACK TECHNIQUE V4 ET CHOIX DES MODÈLES

## 4.1. Application mobile

| Brique | Choix **[V4]** | Raison | Alternative écartée |
|---|---|---|---|
| Framework | **Flutter** (Dart, canal stable) | Une seule base de code, UI très expressive (animations, mise en page paysage), FFI vers C++/ONNX, bonne cible tablette Android | Kotlin + Compose : meilleur contrôle audio natif mais coût de développement plus élevé et moins de réutilisation si iOS un jour |
| Cible | Android 10 (API 29) minimum, ARM64 (`arm64-v8a`) ; appareil de test : section 4.7 | H4 | — |
| Orientation | Paysage forcé : `sensorLandscape` dans le manifeste + `SystemChrome.setPreferredOrientations` | O1 | — |
| État | **Riverpod** (v2) | Testable, adapté à l'injection du bus, du registre et du dispatcher | Bloc (acceptable, ne pas mélanger) |
| Navigation | **go_router** | Routes typées, redirections gardées | — |
| Réseau REST | `dio` | Délais, intercepteurs, annulation (vitaux 35 s) | `http` |
| WebSocket | `web_socket_channel` + client maison (section 7) | Contrôle total de l'enveloppe, QoS 1, reprise | Paquets MQTT : écartés (voir 7.1) |
| Stockage local | `shared_preferences` (réglages), fichiers (modèles, registre, fiches en cache) | Simple | `isar`/`drift` : inutiles (aucune donnée patient stockée sur l'appareil) |
| Audio entrée | `record` (flux PCM16 16 kHz mono, options `echoCancel`, `noiseSuppress`, `autoGain`) **[À VÉRIFIER : version]** | Flux direct vers sherpa-onnx | Appel natif `AudioRecord` via canal Kotlin si `record` ne donne pas l'annulation d'écho voulue |
| Audio sortie | `flutter_pcm_sound` ou `flutter_soloud` (lecture de flux PCM) **[À VÉRIFIER : choisir après le spike WP1]** | Les échantillons synthétisés arrivent par blocs ; il faut pouvoir les jouer au fil de l'eau et les interrompre en < 100 ms | `just_audio` : pensé pour les fichiers, pas pour le flux synthétique |
| Découverte | Adresse fixe `10.42.0.1` par défaut ; mDNS `_hiar._tcp` (paquet `nsd`) en option | Le point d'accès est fixe (V3 §3.1) | — |
| Écran allumé | `wakelock_plus` | Kiosque | — |

## 4.2. Moteur vocal : sherpa-onnx

**[V4]** Un seul runtime pour VAD, STT et TTS : **sherpa-onnx** (paquet Flutter officiel `sherpa_onnx` **[À VÉRIFIER : version et plateformes]**). Avantages : un seul moteur ONNX Runtime embarqué, modèles interchangeables, pas de service externe, API VAD/STT/TTS cohérentes.

| Fonction | Modèle recommandé | Rôle | Taille indicative **[À VÉRIFIER]** |
|---|---|---|---|
| **VAD** | **Silero VAD** (ONNX) | Détecter début/fin de parole, couper la synthèse quand l'utilisateur parle (barge-in) | ~2 Mo |
| **STT commandes** (principal) | **Zipformer transducer en flux continu, français** si disponible dans le catalogue sherpa-onnx ; sinon Whisper (tiny/base) quantifié | Texte partiel en direct, faible latence, **biais lexical (hotwords)** vers les phrases du contexte courant | 50 à 150 Mo |
| **STT dictée** (secondaire, chargé à la demande) | **Whisper small** quantifié int8 ou **Whisper base** ; **Parakeet TDT v3 écarté a priori** (≈ 600 M de paramètres, trop lourd pour un Snapdragon 730G) | Meilleure précision pour un nom, une série de chiffres | 80 à 250 Mo selon le modèle |
| **TTS** (principal) | **Piper (VITS)**, voix française de qualité moyenne (par exemple `fr_FR-siwis-medium`) | Temps réel même sur appareil modeste, 1 modèle = 1 voix | 20 à 70 Mo |
| **TTS** (option qualité) | **Kokoro-82M** quantifié (si la voix française convient) | Plus naturel, plus gourmand | ~80 Mo + |
| Repli système | `TextToSpeech` Android | Aucun modèle à charger ; qualité variable | 0 |

**Pourquoi deux modèles STT.** Les commandes de l'interface forment un vocabulaire fermé (quelques dizaines de phrases) : un modèle en flux continu avec biais lexical est rapide, réactif et suffisant. La dictée d'un nom ou d'un numéro de téléphone est un problème ouvert : on charge un modèle plus précis uniquement pour cette étape, et on propose toujours le clavier tactile comme alternative.

**Règle de décision.** Les noms de modèles ci-dessus sont des **candidats**. Le lot WP1 mesure et tranche (section 13.2). Ne figer aucun modèle avant ce benchmark.

## 4.3. Budgets de performance cibles **[V4]**

| Mesure | Cible | Mesure faite sur |
|---|---|---|
| Fin de parole → texte final | ≤ 700 ms | Xiaomi Mi CC9 Pro (4.7) |
| Fin de parole → réaction visible de l'interface (commande simple) | ≤ 1,2 s | idem |
| Demande TTS → premier son | ≤ 500 ms (première phrase) | idem |
| Arrêt de la synthèse sur « stop » ou toucher | ≤ 150 ms | idem |
| Taux d'erreur sur le jeu de commandes (section 13.2) | ≤ 5 % en environnement calme, ≤ 15 % avec bruit de couloir | corpus enregistré par l'auteur |
| Mémoire vive (STT flux + VAD + TTS chargés) | ≤ 700 Mo | idem |
| Démarrage à froid → prêt à écouter | ≤ 6 s (modèles déjà installés) | idem |

## 4.4. Distribution des modèles **[V4]**

Les modèles ne sont **pas** embarqués dans l'APK.

| Mode | Usage |
|---|---|
| **Pré-chargement par `adb push`** vers le dossier privé de l'application | Développement et démonstration (réseau hospitalier sans Internet) |
| **Téléchargement depuis le Pi** : le hub sert `GET /models/manifest.json` et `/models/<fichier>` (liste, tailles, SHA-256) | Provisionnement d'un nouvel appareil sur le réseau `HIAR-DEMO` sans Internet |

L'application vérifie le SHA-256 avant d'activer un modèle, affiche un écran de provisionnement (progression, reprise), et ne démarre la voix que si les modèles obligatoires sont valides. Sans modèle : mode tactile seul, avec message explicite.

## 4.5. Serveur (Raspberry Pi)

| Brique | Choix **[V4]** | Remarque |
|---|---|---|
| Langage | Python 3 (existant) | — |
| Serveur HTTP | Flask existant, inchangé pour le REST | — |
| WebSocket | **`flask-sock`** (basé sur `simple-websocket`) monté sur la route `/ws`, dans **le même processus** que Flask | Réutilise l'instance unique de `RosBridge` (un seul nœud `hmi_bridge`). Les connexions sont tenues par des threads : suffisant pour 1 à 3 clients **[À VÉRIFIER sur le Pi]** |
| Découplage | La logique du hub vit dans un paquet `web_interface/hub/` **indépendant de Flask**. Si une montée en charge l'exige, elle peut migrer vers un serveur ASGI sans réécrire la logique | — |
| Sécurité réseau | Réseau `HIAR-DEMO` en WPA2, hub limité aux clients authentifiés (section 12) | — |

## 4.6. Perspective : langue malgache (hors V4, décision de l'auteur)

Le dossier est rédigé pour le contexte hospitalier d'Antananarivo (fuseau `Indian/Antananarivo`, numéros `034`/`032`/`033`/`038`). Whisper et les modèles génériques sont faibles en malgache. Pistes **[À VÉRIFIER]** : modèles MMS (Meta) pour la reconnaissance et la synthèse du malgache (licence non commerciale à contrôler), affinage de Whisper small sur un corpus malgache, jeu de commandes restreint. **Conception prête :** tous les topics et le registre portent un champ `lang` (`fr`, plus tard `mg`) ; les libellés d'interface sont dans des fichiers de traduction (ARB) ; le jeu de phrases vocales est par langue. Ajouter une langue ne change ni le protocole ni le dispatcher.



## 4.7. Appareil de test : Xiaomi Mi CC9 Pro (M1910F4E)

Caractéristiques communiquées par l'auteur (capture d'écran) : Xiaomi Mi CC9 Pro (commercialisé aussi sous le nom Mi Note 10), **6 Go de RAM**, processeur huit cœurs jusqu'à 2,2 GHz (Snapdragon 730G), **Android 10**, MIUI Global 12.0.4, correctif de sécurité de janvier 2021.

| Sujet | Conséquence |
|---|---|
| Android 10 = API 29 | C'est exactement le minimum visé (`minSdk 29`). Ne pas utiliser d'API plus récentes sans repli |
| Écran ≈ 2340 × 1080 px | En paysage ≈ **851 × 393 dp** : les maquettes 9.6 (840 × 360 dp) sont calibrées pour lui. Encoche en goutte : respecter les marges de sécurité sur le bord gauche ou droit |
| Snapdragon 730G (milieu de gamme, 2019) | STT de commandes en flux continu et Piper moyenne qualité : **faisables**, à confirmer par mesure. Dictée : Whisper small/base quantifié seulement ; **Parakeet TDT v3 écarté** ; Kokoro à mesurer avant adoption. Budget mémoire 4.3 (≤ 700 Mo) très confortable avec 6 Go |
| Stockage des modèles | Sous Android 10, le dossier privé de l'application sur le stockage externe est accessible par `adb push` sans permission particulière |
| **MIUI 12 : gestion agressive de l'énergie** | Risque d'arrêt de l'application en arrière-plan et de coupure du micro. Mesures : désactiver l'optimisation de batterie pour HIAR, activer le démarrage automatique, verrouiller l'application dans les applications récentes, autoriser le micro en permanence. À consigner dans le manuel d'installation |
| **MIUI et Wi-Fi sans Internet** | Les options de bascule automatique entre Wi-Fi et données mobiles peuvent détourner le trafic. En plus de la liaison au réseau Wi-Fi (12.2), désactiver les données mobiles et les assistants de réseau |
| Épinglage d'écran | Disponible sous MIUI 12 ; à utiliser en kiosque **[À VÉRIFIER]** |
| Correctif de sécurité ancien (2021) | Acceptable pour un démonstrateur sur réseau fermé et sans Internet ; ne pas utiliser l'appareil sur un réseau ouvert |
| Annulation d'écho | Le matériel peut ne pas honorer `VOICE_COMMUNICATION` de la même façon selon MIUI : **tester**, et conserver le demi-duplex (A1) comme sécurité dans tous les cas |

Le lot WP1 s'exécute **sur cet appareil** ; ses mesures font foi.

---

# 5. ARCHITECTURE LOGICIELLE DE L'APPLICATION

## 5.1. Arborescence du projet Flutter **[V4]**

```text
hiar_mobile/
├─ android/                      # manifeste, network_security_config, canal Kotlin (réseau Wi-Fi)
├─ assets/
│  ├─ registry/actions.v1.json   # copie embarquée du registre (repli hors ligne)
│  ├─ content/info_fr.json       # copie embarquée des fiches (repli hors ligne)
│  ├─ fonts/                     # Inter, Plus Jakarta Sans (mêmes fichiers que le Web)
│  └─ brand/                     # logo HIAR, robot (SVG repris de index.html)
├─ lib/
│  ├─ app/                       # bootstrap, thème, routeur, configuration
│  ├─ core/
│  │  ├─ bus/                    # EventBus, Envelope, Topics (constantes), QoS
│  │  ├─ net/                    # ApiClient (REST), HubClient (WebSocket), Discovery
│  │  └─ platform/               # liaison au réseau Wi-Fi, kiosque, permissions
│  ├─ domain/
│  │  ├─ actions/                # ActionRegistry, ActionRequest, ActionDispatcher, Risk
│  │  ├─ intents/                # Normalizer, Matcher, NumberParser, DisambiguationPolicy
│  │  └─ models/                 # Category, Service, InfoSheet, Session, Appointment, Vitals…
│  ├─ voice/
│  │  ├─ voice_orchestrator.dart # machine à états vocale (section 8)
│  │  ├─ audio/                  # AudioIo, AudioFocus, demi-duplex
│  │  ├─ vad/                    # SileroVad
│  │  ├─ stt/                    # SttEngine (interface) + SherpaStt
│  │  ├─ tts/                    # TtsEngine (interface) + SherpaTts + SystemTts (repli) + TtsQueue
│  │  └─ models/                 # ModelManager (inventaire, SHA-256, provisionnement)
│  ├─ features/                  # splash, home, orientation, information, consultation, vitals,
│  │                             # settings (caché), diagnostics (caché)
│  └─ ui/                        # système de design : thème, composants, widgets vocaux
└─ test/                         # unitaires, widgets, parité, protocole, golden
```

Les interfaces `SttEngine` et `TtsEngine` isolent sherpa-onnx : on peut remplacer un moteur (ou le simuler dans les tests) sans toucher au reste.

## 5.2. Flux de contrôle (règle P2)

```text
Bouton (ActionButton)  ──┐
Voix (Matcher)         ──┼─► ActionRequest{id, args, origin, corr, epoch} ─► ActionDispatcher
Serveur (suggestion)   ──┤                                                      │
Système (délai, erreur)──┘                          ┌───────────────────────────┤
                                                    ▼                           ▼
                                      Vérifications (disponible ? risque ?      Exécution :
                                      écran à jour ? occupé ?)                  navigation d'écran,
                                                    │                           REST, WebSocket,
                                                    └─► confirmation si requise  mission, TTS
```

Le dispatcher publie `ui/action/request` à l'entrée et `ui/action/result` à la sortie (section 7.4). Il est le seul composant autorisé à :

- changer d'écran suite à une action ;
- appeler `ApiClient` pour une écriture ou une demande robotique ;
- déclencher la confirmation.

## 5.3. Écrans et routes

| Route | Écran | Remarques |
|---|---|---|
| `/splash` | Accueil / veille | Toucher n'importe où ou dire « commencer » |
| `/home` | Choix du service | 3 services |
| `/orientation` | Choix de la destination | 3 destinations |
| `/orientation/confirm` | Feuille de confirmation | Obligatoire (section 6.5) |
| `/orientation/mission` | Suivi de mission | État réel relayé, bouton ARRÊT |
| `/info` | Liste des 6 fiches | — |
| `/info/:topic` | Fiche | Sections, lecture à voix haute |
| `/consult/:step` | Parcours de consultation (étapes 1 à 5) | Une route par étape pour le retour système |
| `/consult/ticket` | Ticket et numéro de file | Retour automatique à l'accueil |
| `/settings` | Réglages et diagnostic | Caché (appui long de 5 s sur le logo) |
| `/provision` | Installation des modèles vocaux | Affiché si modèle obligatoire absent |

## 5.4. Réglages (écran caché)

Adresse du serveur (défaut `10.42.0.1:5000`), volume et vitesse de la voix, mode micro (appui pour parler / mains libres de session), seuil de confiance (lecture seule en démonstration), état des modèles (version, SHA-256), état du hub (connecté, latence), état de ROS 2 (relayé), journal de diagnostic (sans données personnelles), commande « tester la voix ».

---

# 6. REGISTRE D'ACTIONS : PARITÉ TACTILE / VOCALE

## 6.1. Règle de parité **[V4, impérative]**

> Toute action accessible par un bouton, une carte ou un geste doit exister dans le registre et être exécutable par la voix. Toute action vocale doit avoir un équivalent visible et tactile (sauf les exceptions listées en 6.6).

Conséquences de conception :

1. Un bouton **n'a pas de logique propre** : il s'appelle `ActionButton(actionId: 'orientation.select', args: {...})` et ne fait que demander l'action.
2. Chaque écran publie à son affichage la **liste des actions disponibles** (`ui/state`, section 7.4). La voix ne résout les phrases que contre : les actions globales + les actions de l'écran courant (+ celles de la feuille ouverte, si une feuille est ouverte).
3. Chaque bouton affiche, discrètement, **ce qu'il faut dire** (« Dites : Pharmacie »). L'utilisateur découvre ainsi la voix sans lire de manuel (section 9.5).
4. Un **test de parité automatisé** échoue si un bouton existe sans action de registre, ou si une action n'a pas de phrases vocales (section 13.3).

## 6.2. Structure d'une entrée du registre

```json
{
  "id": "orientation.select",
  "scope": ["orientation.menu", "home"],
  "args": { "destination": ["PHARMACY", "LABORATORY", "RECEPTION"] },
  "risk": "R0",
  "effect": { "type": "screen", "to": "orientation.confirm" },
  "touch": { "control": "destination_card" },
  "label_fr": { "PHARMACY": "Pharmacie", "LABORATORY": "Laboratoire", "RECEPTION": "Réception" },
  "voice_fr": {
    "PHARMACY":   ["pharmacie", "la pharmacie", "médicaments", "je cherche la pharmacie", "emmene moi a la pharmacie"],
    "LABORATORY": ["laboratoire", "labo", "analyses", "prise de sang"],
    "RECEPTION":  ["reception", "la reception", "accueil de l hopital"]
  },
  "feedback_fr": "Vous souhaitez aller à : {label}. Confirmez-vous ?",
  "requires_confirmation": false
}
```

Le registre est produit à partir de `catalog.py` (catégories, destinations, fiches) **plus** un fichier de phrases vocales (`voice_fr.yaml`) maintenu à la main. Le serveur le sert (`GET /api/voice/registry`, section 10) avec un hachage ; l'application embarque une copie pour le repli.

## 6.3. Catalogue complet des actions

Niveaux de risque : **R0** navigation/lecture ; **R1** écriture de données (rendez-vous) ; **R2** mouvement du robot ; **R3** arrêt de sécurité (jamais bloqué, jamais soumis à confirmation).

### Globales (disponibles sur tous les écrans)

| Id | Arguments | Risque | Effet | Phrases types (FR) |
|---|---|---|---|---|
| `app.home` | — | R0 | Retour à `/home` | « menu principal », « écran d'accueil », « retour au menu », « accueil » (voir 6.4 pour l'ambiguïté) |
| `app.back` | — | R0 | Retour au niveau précédent (comportement défini par l'écran) | « retour », « précédent », « revenir » |
| `app.help` | — | R0 | Annonce des commandes disponibles ici (lues depuis `ui/state`) | « aide », « que puis-je dire », « quelles commandes » |
| `voice.read_screen` | — | R0 | Lit le contenu utile de l'écran | « lis l'écran », « qu'est-ce que je peux faire » |
| `voice.repeat` | — | R0 | Répète la dernière phrase prononcée | « répète », « répétez », « pardon ? » |
| `voice.stop_speaking` | — | R0 | Coupe la synthèse | « silence », « tais-toi », « arrête de parler » |
| `voice.mic_off` | — | R0 | Coupe l'écoute | « arrête d'écouter », « coupe le micro » |
| `robot.stop` | — | **R3** | `POST /api/navigation/cancel` → `STOP` sur `/navigation/command` | « stop », « arrête », « arrête-toi », « halte », « arrêt d'urgence » |

### Veille et accueil

| Id | Arguments | Risque | Effet | Phrases types |
|---|---|---|---|---|
| `splash.start` | — | R0 | `/splash` → `/home` | « commencer », « bonjour », « démarrer » |
| `home.open_category` | `category` ∈ ORIENTATION, INFORMATION | R0 | Ouvre le menu | Orientation : « orientation », « m'orienter », « où aller » · Renseignements : « renseignements », « informations », « fiches santé » |
| `consult.start` | — | R0 | Ouvre l'étape 1 de la consultation (accueil → directement le parcours, car la catégorie ne contient qu'un élément exploitable, constat C7) | « consultation », « rendez-vous », « prendre rendez-vous », « voir un médecin » |

### Orientation

| Id | Arguments | Risque | Effet | Phrases types |
|---|---|---|---|---|
| `orientation.select` | `destination` ∈ PHARMACY, LABORATORY, RECEPTION | R0 | Ouvre la feuille de confirmation | « pharmacie », « labo », « réception », « emmène-moi à la pharmacie » (disponible aussi depuis `/home`) |
| `orientation.confirm` | `destination` (mémorisée) | **R2** | `POST /api/request` `{category:"ORIENTATION", item}` puis suivi d'état | « oui », « je confirme », « d'accord », « c'est bon » |
| `orientation.decline` | — | R0 | Ferme la feuille, aucune demande émise | « non », « annuler », « pas maintenant » |
| `mission.dismiss` | — | R0 | Quitte l'écran de suivi une fois la mission terminée ou arrêtée | « fermer », « terminé » |

### Renseignements

| Id | Arguments | Risque | Effet | Phrases types |
|---|---|---|---|---|
| `info.open` | `topic` ∈ HIV, MALARIA, DIABETES, HYPERTENSION, TUBERCULOSIS, MENSTRUAL_HEALTH | R0 | Affiche la fiche (contenu local) | VIH : « vih », « sida » · Paludisme : « paludisme », « malaria » · Diabète : « diabète », « sucre » · Hypertension : « hypertension », « tension » · Tuberculose : « tuberculose », « tb » · Santé menstruelle : « règles », « menstruation », « santé menstruelle » |
| `info.read_all` | — | R0 | Lit toute la fiche à voix haute, section par section | « lis la fiche », « lis tout », « lecture » |
| `info.read_section` | `section` (index ou titre) | R0 | Lit une section | « lis la prévention », « lis les symptômes » |
| `info.next_section` / `info.prev_section` | — | R0 | Section suivante / précédente | « suivant », « section suivante » / « précédent » |
| `info.pause` / `info.resume` | — | R0 | Pause / reprise de la lecture | « pause » / « continue », « reprends » |
| `info.show_source` | — | R0 | Affiche la source OMS (texte et QR code) ; **n'ouvre pas de navigateur** en mode kiosque | « source », « d'où vient cette information » |

### Consultation (parcours en 5 étapes + ticket)

| Id | Étape | Arguments | Risque | Effet | Phrases types |
|---|---|---|---|---|---|
| `consult.reason.select` | 1 | `reason` ∈ consultation_generale, suivi_medical, autre_motif | R0 | Sélectionne le motif | « consultation générale », « suivi médical », « autre motif » |
| `consult.next` | 1–4 | — | R0 | Étape suivante (si valide) | « continuer », « suivant » |
| `consult.session.select` | 2 | `doctor` ∈ A, B, C, D ; `period` ∈ MAT, AM (**uniquement les sessions ouvertes** renvoyées par `GET /api/consultation/sessions`) | R0 | Sélectionne la session | « médecin B ce matin », « docteur A cet après-midi » |
| `consult.field.dictate` | 3 | `field` ∈ name, phone | R0 | Active la dictée (modèle de dictée, section 4.2) | « dicter mon nom », « je donne mon numéro » |
| `consult.field.set` | 3 | `field`, `value` | R0 | Remplit le champ **après lecture-confirmation** (6.5) | « je m'appelle … », « mon numéro est zéro trois quatre … » |
| `consult.field.clear` | 3 | `field` | R0 | Efface le champ | « efface le nom », « recommencer le numéro » |
| `consult.vitals.start` | 4 | — | R0 | `POST /api/vitals/acquire` (attente jusqu'à 35 s) | « lance la mesure », « mesurer » |
| `consult.vitals.skip` | 4 | — | R0 | Passe l'étape (mesures facultatives) | « passer », « continuer sans mesure » |
| `consult.vitals.cancel` | 4 | — | R0 | Abandonne l'attente côté application. **Limite :** n'arrête pas l'acquisition sur l'ESP32, le résultat est ignoré | « annuler la mesure » |
| `consult.review.confirm` | 5 | — | **R1** | `POST /api/consultation/appointments` | « je confirme », « confirmer » |
| `consult.review.modify` | 5 | — | R0 | Retour à l'étape à corriger | « modifier », « corriger » |
| `consult.cancel` | 1–5 | — | R0 | Abandonne le parcours, efface les données saisies | « annuler la consultation », « abandonner » |
| `consult.ticket.read` | ticket | — | R0 | Lit le numéro de file et la session | « quel est mon numéro », « lis mon ticket » |
| `consult.finish` | ticket | — | R0 | Retour à l'accueil | « terminer », « c'est tout » |

### Feuilles et erreurs

| Id | Contexte | Risque | Phrases types |
|---|---|---|---|
| `confirm.yes` / `confirm.no` | Toute feuille de confirmation ouverte (alias contextuels de `orientation.confirm` / `decline`, `consult.review.confirm`, validation d'un champ dicté) | selon l'action sous-jacente | « oui », « non » |
| `error.retry` / `error.dismiss` | Bandeau d'erreur | R0 | « réessayer » / « fermer », « ok » |

## 6.4. Ambiguïtés : la règle « ne jamais deviner »

| Cas | Règle |
|---|---|
| « accueil » seul, sur le menu Orientation (où existe aussi « Réception ») | Question de clarification : « Voulez-vous la réception, ou revenir à l'écran d'accueil ? ». Le libellé vocal de la destination est « réception » ; « accueil » n'est jamais un synonyme de `RECEPTION` |
| « stop » ou « arrête » seul | Si une mission est demandée ou en cours → `robot.stop`. Sinon, si la synthèse parle → `voice.stop_speaking`. Sinon, ignoré |
| « oui » / « non » hors feuille de confirmation | Ignoré (aucune action). Évite qu'un « oui » dit à quelqu'un d'autre ne valide quoi que ce soit |
| « médecin B » avec deux périodes ouvertes | Demander « Le matin ou l'après-midi ? » |
| Deux actions avec des scores proches (écart < 0,08) | Demander « Vous voulez dire X ou Y ? » |
| Score de correspondance entre 0,75 et 0,90 | Répéter ce qui a été compris et demander confirmation, sauf R3 |
| Score < 0,75 | Non résolu : message d'aide + publication de `voice/intent/unresolved` (le serveur peut proposer) |

## 6.5. Politique de confirmation

| Risque | Tactile | Vocal |
|---|---|---|
| R0 | Exécution immédiate | Exécution immédiate si score ≥ 0,90 |
| R1 (écriture) | Écran de vérification (étape 5) puis bouton « Confirmer » | **Même écran.** Seul « je confirme » / « confirmer » valide. « oui » est accepté **uniquement** si la feuille de vérification est au premier plan |
| R2 (mouvement) | **Feuille de confirmation obligatoire** (bouton « Confirmer » distinct, pas de validation au premier toucher sur la carte destination) | **Feuille identique** : l'application dit la destination et demande confirmation. Délai de 10 s, sinon annulation silencieuse. Une seule confirmation valide par feuille |
| R3 (arrêt) | Bouton ARRÊT toujours visible pendant une mission | Reconnu **sur les résultats partiels** (sans attendre la fin de phrase), sans confirmation |

Pour **tout** R2, la confirmation s'applique aussi au tactile : c'est une décision de sûreté liée au constat C3 (démarrage automatique de la mission à la réception de la demande).

**Données dictées (nom, téléphone).** Après dictée : affichage dans le champ, lecture à voix haute (« J'ai compris : zéro trois quatre … , est-ce correct ? »), puis `confirm.yes` pour valider ou `confirm.no` pour recommencer. Le téléphone est validé localement par la même règle que le serveur (`normalize_phone` : 10 chiffres commençant par `0`, ou `+261…`/`261…`) avant d'être accepté.

## 6.6. Exceptions documentées à la parité

| Élément | Pourquoi | Équivalent |
|---|---|---|
| Réactiver le micro (`voice.mic_on`) | On ne peut pas parler à un micro éteint | Bouton micro (toucher) ; toucher la zone vocale |
| Saisie au clavier d'un nom ou d'un numéro | La frappe n'a pas d'équivalent « bouton » | Dictée (`consult.field.dictate`/`set`) |
| Défilement tactile d'un long texte | Geste continu | `info.next_section` / `info.prev_section` / lecture à voix haute |
| Écran caché des réglages | Technique, réservé à l'administrateur | Hors voix (volontairement) |
| Réveil depuis la veille (`splash.start` par la voix) | Micro fermé à la veille pour éviter les déclenchements parasites (9.5) | Toucher l'écran ; réveil vocal optionnel, désactivé par défaut |

## 6.7. Normalisation et correspondance **[V4]**

Pipeline appliqué à chaque texte reconnu, avant correspondance :

1. minuscules, suppression des accents, de la ponctuation, des apostrophes (« l'écran » → « l ecran ») ;
2. suppression des mots de politesse et d'amorce : « s'il vous plaît », « euh », « je voudrais », « pouvez-vous », « je veux », « est-ce que » ;
3. conversion des nombres dits : « zéro trois quatre douze quarante-cinq » → chiffres, avec gestion de « double » / « triple » ; analyseur dédié `NumberParser` testé sur les numéros malgaches ;
4. correspondance par ordre : phrase exacte → motif avec argument (« médecin {lettre} {période} ») → similarité par ensemble de mots (seuils de la section 6.4) ;
5. **portée** : seules les actions disponibles dans le contexte courant participent (section 6.1, point 2) ; cela réduit fortement les confusions.

**Biais du STT.** À chaque changement d'écran, l'application fournit au moteur de reconnaissance la liste des phrases du contexte (mots-clés/hotwords) **[À VÉRIFIER : support du biais lexical selon le modèle retenu]**. Sans support, le biais est remplacé par la correspondance approximative.

---

# 7. BUS D'ÉVÉNEMENTS ET PROTOCOLE WEBSOCKET

## 7.1. Modèle **[V4]**

Un **bus de publication/abonnement par topics**, présent à deux niveaux :

- **local** dans l'application (le `EventBus`) ;
- **distant** sur le Pi (le hub), relié au bus local par un **pont WebSocket**.

Les deux utilisent **les mêmes noms de topics et la même enveloppe**. Chaque topic a un mode de pont :

| Mode | Sens |
|---|---|
| `local` | Reste dans l'application (ex. `voice/vad`, haute fréquence) |
| `out` | Application → hub |
| `in` | Hub → application |
| `both` | Dans les deux sens |

Ainsi, la voix fonctionne identiquement avec ou sans réseau : les composants vocaux s'abonnent et publient sur le bus local, qu'un hub soit joignable ou non (principe P1).

**Pourquoi pas MQTT ?** Un courtier MQTT ajouterait un service à installer et à superviser sur le Pi. Le besoin (quelques clients, quelques dizaines de topics, QoS 1 limité) est couvert par un protocole JSON minimal sur WebSocket, sans dépendance supplémentaire. Les noms de topics sont volontairement compatibles MQTT (séparateur `/`, jokers `+` et `#`) pour une migration future.

## 7.2. Connexion

| Élément | Valeur |
|---|---|
| URL | `ws://10.42.0.1:5000/ws` (réseau `HIAR-DEMO`, WPA2) |
| Sous-protocole | `hiar.v1` |
| Trames | Texte JSON, UTF-8, taille ≤ 64 Ko. Aucune trame binaire dans la V4 (l'audio ne quitte jamais l'appareil) |
| Cycle de vie | `hello` → `welcome` → abonnements → échanges → `bye` |

### Poignée de main

Client → hub :

```json
{ "v": 1, "type": "hello", "device_id": "tab-01", "role": "kiosk",
  "app_version": "0.1.0", "registry_hash": "sha256:…", "last_seq": 1842,
  "token": "<jeton d'appareil>" }
```

Hub → client :

```json
{ "v": 1, "type": "welcome", "session": "s-7f3a", "server_time": 1789398000000,
  "registry_hash": "sha256:…", "registry_stale": false,
  "heartbeat_s": 5, "max_msg_bytes": 65536,
  "granted": { "publish": ["voice/stt/#","voice/tts/control","ui/#","vitals/#","sys/#"],
               "subscribe": ["voice/#","ui/#","robot/#","vitals/#","sys/#"] },
  "replay": 3 }
```

`registry_stale: true` signale à l'application qu'une version plus récente du registre existe sur le serveur (à récupérer par `GET /api/voice/registry`).

## 7.3. Enveloppe

```json
{
  "v": 1,
  "id": "01JD3…",          // identifiant unique du message (ULID)
  "type": "pub",           // pub | sub | unsub | ack | nack | ping | pong | hello | welcome | bye | error
  "topic": "voice/stt/final",
  "ts": 1789398001234,     // millisecondes, horloge de l'émetteur
  "seq": 1843,             // compteur croissant par émetteur et par session
  "corr": "01JD2…",        // corrélation avec une requête ou un énoncé (facultatif)
  "qos": 1,                // 0 = au plus une fois ; 1 = au moins une fois, avec ack
  "retain": false,         // le hub garde la dernière valeur et la rejoue aux nouveaux abonnés
  "payload": { }
}
```

| Règle | Détail |
|---|---|
| QoS 0 | Pour les flux rapides et sans conséquence (`voice/stt/partial`, `voice/vad`, niveaux sonores). Non acquittés, non rejoués |
| QoS 1 | Pour tout ce qui a une conséquence : `voice/stt/final`, `voice/tts/request`, `ui/action/*`, `robot/safety`. Le récepteur répond `ack` (`corr` = `id` reçu). L'émetteur renvoie après 1,5 s, 3 essais maximum, puis `nack` local |
| Déduplication | Le récepteur ignore un `id` déjà traité (cache de 512 `id`) |
| Rétention | Seuls les topics d'état sont rétentionnés (colonne « R » du catalogue) |
| Rejeu | Le hub garde un anneau de 256 messages QoS 1 par session ; à la reconnexion, `last_seq` permet de rejouer ce qui a été manqué |
| Ordre | Garanti par `seq` pour un même émetteur |
| Horloges | `ts` est informatif ; ne jamais s'en servir pour ordonner entre appareils |
| Versions | `v` entier. Le hub refuse une version inconnue par `error` code `unsupported_version` |

## 7.4. Catalogue des topics

Convention : `domaine/sous-domaine/nom`. **Mode** : L local, O out, I in, B both. **R** : rétentionné. **QoS** : 0 ou 1.

### Voix : écoute (STT)

| Topic | Mode | QoS | R | Producteur → consommateurs | Charge utile |
|---|---|---|---|---|---|
| `voice/vad` | L | 0 | | VAD → orchestrateur, visualiseur | `{event:"speech_start"\|"speech_end", level}` |
| `voice/mic/control` | B | 1 | | UI, orchestrateur, serveur → micro | `{cmd:"start"\|"stop"\|"mute"\|"unmute"\|"mode", mode?:"push"\|"session"}` |
| `voice/stt/state` | B | 0 | ✓ | STT → UI, hub | `{state:"idle"\|"listening"\|"hearing"\|"decoding"\|"error", engine, model, lang}` |
| `voice/stt/partial` | B | 0 | | STT → UI (affichage en direct), détecteur d'arrêt, hub | `{utt, text, lang}` |
| `voice/stt/final` | B | 1 | | STT → interpréteur, hub | `{utt, text, lang, conf, duration_ms, engine, model, mode:"command"\|"dictation", sensitive}` |
| `voice/stt/error` | B | 1 | | STT → UI, hub | `{code:"mic_denied"\|"model_missing"\|"engine_crash"\|"no_audio", message}` |

### Voix : parole (TTS)

| Topic | Mode | QoS | R | Producteur → consommateurs | Charge utile |
|---|---|---|---|---|---|
| `voice/tts/request` | B | 1 | | Dispatcher, orchestrateur, **serveur**, services externes → TTS | `{utt, text, lang, voice?, speed?, priority:0..3, interrupt:"none"\|"queue"\|"replace", source, ttl_ms, sensitive?}` |
| `voice/tts/control` | B | 1 | | UI, orchestrateur, serveur → TTS | `{cmd:"stop"\|"pause"\|"resume"\|"repeat", utt?}` |
| `voice/tts/state` | B | 1 | ✓ | TTS → orchestrateur, UI, hub | `{utt, state:"queued"\|"started"\|"sentence"\|"finished"\|"cancelled"\|"error", index?, reason?}` |

### Interprétation

| Topic | Mode | QoS | R | Producteur → consommateurs | Charge utile |
|---|---|---|---|---|---|
| `voice/intent/resolved` | B | 1 | | Interpréteur → dispatcher, hub (audit) | `{utt, action_id, args, score, source:"grammar"\|"server", epoch, needs_confirm}` |
| `voice/intent/unresolved` | B | 1 | | Interpréteur → hub, UI | `{utt, text?, screen, reason:"low_score"\|"out_of_scope"\|"ambiguous", candidates?:[{action_id,score}]}` — `text` absent si `sensitive` |
| `voice/intent/suggest` | I | 1 | | **Serveur** (classifieur/IA) → interpréteur | `{utt, action_id, args, score, rationale?}` — **suggestion seulement** : retraverse le dispatcher (section 3.3) |

### Interface et actions

| Topic | Mode | QoS | R | Producteur → consommateurs | Charge utile |
|---|---|---|---|---|---|
| `ui/state` | B | 1 | ✓ | Écran courant → interpréteur, hub | `{screen, epoch, step?, actions:[ids], dynamic:{…}, sensitive_fields:[…], mission_active}` |
| `ui/action/request` | B | 1 | | Bouton, interpréteur, serveur → dispatcher, hub | `{action_id, args, origin:"touch"\|"voice"\|"system"\|"server", corr, epoch}` |
| `ui/action/result` | B | 1 | | Dispatcher → UI, orchestrateur, hub | `{corr, ok, error?, code?, next_screen?}` |
| `ui/confirm/request` | L | 1 | | Dispatcher → UI, orchestrateur | `{corr, action_id, args, timeout_ms, prompt}` |
| `ui/confirm/answer` | L | 1 | | UI (toucher) ou interpréteur (voix) → dispatcher | `{corr, answer:"yes"\|"no"\|"timeout"}` |

### Robot (relayés depuis ROS 2 par le hub, **lecture seule pour l'application**)

| Topic | Mode | QoS | R | Source ROS 2 | Charge utile |
|---|---|---|---|---|---|
| `robot/hmi/status` | I | 1 | ✓ | `/hmi/status` | `{state:"VALIDATED"\|"REJECTED", category?, item?, reason?}` |
| `robot/mission/status` | I | 1 | ✓ | `/navigation/status` | `{code:"REQUEST_RECEIVED"\|"RUNNING"\|"BLOCKED"\|"IDLE"\|"MISSION_TIMEOUT"\|"REQUEST_REJECTED"\|"START_REJECTED", reason?, destination?}` |
| `robot/safety` | I | 1 | | `/esp32/status` lignes `SAFETY,*` et `/sensors/obstacle` | `{event:"OBSTACLE"\|"TIMEOUT"\|"SENSOR_INVALID", cm?}` |
| `robot/supervisor/status` | I | 0 | ✓ | `/robot/status` (`String`, état courant de commande, ex. `STOP`, `FORWARD`) | `{state}` (valeur brute conservée ; analyse tolérante) |
| `robot/link` | I | 1 | ✓ | État du pont ROS 2 du hub | `{ros_bridge:"up"\|"down", esp32:"unknown"\|"seen"\|"stale", reason?}` |

### Signes vitaux

| Topic | Mode | QoS | R | Producteur | Charge utile |
|---|---|---|---|---|---|
| `vitals/state` | B | 1 | ✓ | Hub (autour de `/api/vitals/acquire`) et application | `{state:"idle"\|"measuring"\|"done"\|"unavailable", started_at?, timeout_s:35}` |
| `vitals/result` | I | 1 | | Hub | `{state, values:{temperature_c, heart_rate_bpm, spo2_percent:null}, reason?}` — **valeurs non diagnostiques** |

### Système

| Topic | Mode | QoS | R | Charge utile |
|---|---|---|---|---|
| `sys/hello`, `sys/ping`, `sys/pong` | (types d'enveloppe, section 7.2) | | | |
| `sys/config` | I | 1 | ✓ | `{registry_hash, tts_defaults, thresholds}` : configuration poussée par le serveur |
| `sys/health` | B | 0 | | `{battery?, cpu?, mem?, models:{stt,tts,vad}}` : télémétrie facultative, jamais de contenu vocal |
| `sys/error` | B | 1 | | `{code, message, topic?}` |

### Droits par rôle

| Rôle | Peut publier | Peut s'abonner |
|---|---|---|
| `kiosk` (application patient) | `voice/stt/#`, `voice/tts/control`, `voice/tts/state`, `voice/intent/resolved\|unresolved`, `voice/mic/control`, `ui/#`, `vitals/state`, `sys/health\|error` | `voice/#`, `ui/#`, `robot/#`, `vitals/#`, `sys/#` |
| `service` (service externe, ex. IA locale) | `voice/tts/request`, `voice/intent/suggest`, `ui/action/request` (origine `server`) | `voice/stt/final`, `voice/intent/unresolved`, `ui/state`, `robot/#` |
| `monitor` (diagnostic, lecture seule) | rien | `#` sauf contenu `sensitive` |

Aucun rôle ne peut publier sur `robot/#`. Ces topics n'existent **que** dans le sens ROS 2 → application.

## 7.5. Fiabilité, reconnexion, heartbeat

| Paramètre | Valeur |
|---|---|
| `ping` client → hub | toutes les 5 s ; `pong` attendu sous 3 s |
| Liaison considérée perdue | 2 `pong` manqués (≈ 11 s) |
| Reconnexion | Délai exponentiel 0,5 → 1 → 2 → 4 → 8 s (plafond), avec gigue ±20 % |
| À la reconnexion | `hello` avec `last_seq` ; rejeu des QoS 1 manqués ; réabonnements ; republication de `ui/state` |
| File d'envoi hors ligne | QoS 1 mis en file (max 100, péremption 30 s) puis abandonnés. **Jamais** de file pour une action robotique : si la liaison est perdue, l'action échoue immédiatement (section 8.8) |
| Contre-pression | Si le tampon d'envoi dépasse 256 Ko, les QoS 0 sont jetés en premier ; `voice/stt/partial` est limité à 10 messages/s |
| Fermeture propre | `bye` ; le hub libère la session après 60 s sans reconnexion |

## 7.6. Codes d'erreur (`type:"error"` ou `sys/error`)

`unsupported_version`, `auth_failed`, `forbidden_topic`, `too_large`, `rate_limited`, `bad_payload`, `unknown_topic`, `internal`. Un `nack` précise `corr` et `code`.

## 7.7. Hub côté Raspberry Pi **[V4]**

### Organisation du code (nouveau paquet, indépendant de Flask)

```text
web_interface/hub/
├─ __init__.py
├─ protocol.py        # enveloppe, validation, constantes de topics, codes d'erreur
├─ router.py          # abonnements, jokers, rétention, anneau de rejeu, QoS 1
├─ session.py         # une session par client, heartbeat, file d'envoi
├─ roles.py           # droits par rôle (section 7.4)
├─ ros_relay.py       # abonnements ROS 2 → topics robot/*, vitals/*
├─ flask_ws.py        # montage flask-sock sur /ws (seul fichier dépendant de Flask)
└─ tests/             # protocole, routeur, droits, relais ROS 2 simulé
```

Contraintes :

- `router.py` et `session.py` n'importent ni Flask ni ROS 2 (testables sans matériel).
- `ros_relay.py` ajoute des **abonnements en lecture** au `RosBridge` existant ; il ne crée aucun éditeur. Les callbacks ROS 2 tournent dans le fil de `rclpy.spin` : ils déposent les messages dans une file thread-safe, consommée par les sessions.
- **Aucun** appel du hub vers ROS 2 en dehors de `RosBridge.publish()` et `RosBridge.cancel_navigation()`, et seulement à la suite d'une `ActionRequest` validée (`orientation.confirm`, `robot.stop`).

### Correspondance ROS 2 → topics

| Topic ROS 2 | Type | Topic hub | Transformation |
|---|---|---|---|
| `/hmi/status` | `String` | `robot/hmi/status` | `VALIDATED:CAT:ITEM` → `{state:"VALIDATED", category, item}` ; `REJECTED:RAISON` → `{state:"REJECTED", reason}` |
| `/navigation/status` | `String` | `robot/mission/status` | `RUNNING`, `BLOCKED`, `IDLE`, `MISSION_TIMEOUT` → `{code}` ; `REQUEST_RECEIVED:DEST` → `{code, destination}` ; `REQUEST_REJECTED:RAISON` et `START_REJECTED:RAISON` → `{code, reason}` |
| `/esp32/status` | `String` | `robot/safety` | uniquement les lignes `SAFETY,OBSTACLE,<cm>`, `SAFETY,TIMEOUT`, `SAFETY,SENSOR_INVALID` ; les `ACK`/`REJECTED` ne sont pas relayés |
| `/sensors/obstacle` | `String` (`CLEAR` ou `OBSTACLE`) **[CODE]** | `robot/safety` | uniquement sur passage `CLEAR` → `OBSTACLE` |
| `/robot/status` | `String` | `robot/supervisor/status` | brut |
| (état du pont) | — | `robot/link` | `up` si `RosBridge.active`, sinon `down` ; `esp32:"stale"` si aucun message capteur depuis 5 s |

### Vérité de l'état (principe P6)

L'application n'affiche **« En route »** qu'après réception de `robot/mission/status` avec `code:"RUNNING"`. Elle affiche un refus clair pour `START_REJECTED:SENSORS_NOT_READY`, `START_REJECTED:MISSION_ACTIVE`, `REQUEST_REJECTED:MISSION_ACTIVE` ou `robot/hmi/status.state == "REJECTED"`. Si aucun statut n'est reçu sous **4 s** après l'émission de la demande, l'application affiche « Le robot n'a pas répondu » et ne prétend rien.

## 7.8. Exemples de messages

**Un énoncé qui devient une action (côté application, bus local puis hub pour l'audit) :**

```json
{"type":"pub","topic":"voice/stt/final","qos":1,"seq":41,"id":"01JD…A",
 "payload":{"utt":"u-118","text":"emmène-moi à la pharmacie","lang":"fr","conf":0.93,
            "duration_ms":1900,"engine":"sherpa-zipformer-fr","mode":"command","sensitive":false}}

{"type":"pub","topic":"voice/intent/resolved","qos":1,"seq":42,"corr":"u-118",
 "payload":{"utt":"u-118","action_id":"orientation.select","args":{"destination":"PHARMACY"},
            "score":0.96,"source":"grammar","epoch":12,"needs_confirm":false}}

{"type":"pub","topic":"ui/action/request","qos":1,"seq":43,"corr":"c-77",
 "payload":{"action_id":"orientation.select","args":{"destination":"PHARMACY"},
            "origin":"voice","corr":"c-77","epoch":12}}
```

**Le serveur demande à l'application de parler (service externe) :**

```json
{"type":"pub","topic":"voice/tts/request","qos":1,"id":"01JD…B",
 "payload":{"utt":"srv-5","text":"Votre rendez-vous est confirmé.","lang":"fr",
            "priority":2,"interrupt":"queue","source":"service:agenda","ttl_ms":15000}}
```

---

# 8. GESTION DES INTERACTIONS PAR ÉVÉNEMENTS

## 8.1. Composants et responsabilités

| Composant | Publie | S'abonne à | Responsabilité unique |
|---|---|---|---|
| `AudioIo` | (interne) | `voice/mic/control` | Posséder le micro et le haut-parleur ; arbitrer le demi-duplex |
| `Vad` | `voice/vad` | flux audio | Détecter début et fin de parole |
| `SttEngine` | `voice/stt/state\|partial\|final\|error` | `voice/vad`, `voice/mic/control` | Transcrire |
| `Interpreter` | `voice/intent/resolved\|unresolved`, `ui/confirm/answer` | `voice/stt/final\|partial`, `ui/state`, `voice/intent/suggest`, `ui/confirm/request` | Transformer un texte en action candidate **sans l'exécuter** |
| `ActionDispatcher` | `ui/action/result`, `ui/confirm/request`, `voice/tts/request` | `ui/action/request`, `ui/confirm/answer`, `voice/intent/resolved` | Valider, confirmer, exécuter une action |
| `TtsEngine` + `TtsQueue` | `voice/tts/state` | `voice/tts/request\|control` | Synthétiser, mettre en file, interrompre |
| `VoiceOrchestrator` | `voice/mic/control`, `voice/tts/control` | tous les états vocaux, `robot/mission/status` | Faire respecter les règles d'arbitrage (8.3) |
| `UiStatePublisher` | `ui/state` | navigation | Annoncer à chaque écran ses actions disponibles |
| `HubClient` | — | topics en mode `out`/`both` | Ponter le bus local avec le hub |

Aucun composant n'appelle directement un autre : ils communiquent **uniquement** par le bus. Cela rend chaque pièce remplaçable et testable avec un faux bus.

## 8.2. Machine à états de l'orchestrateur vocal

États : `Off` (modèles absents ou micro refusé), `Armed` (prêt, micro fermé), `Listening` (micro ouvert, en attente de parole), `Hearing` (parole détectée), `Decoding` (fin de parole, texte final en cours), `Resolving`, `Speaking` (synthèse en cours), `Confirming` (feuille de confirmation ouverte).

| État | Événement | Condition | Nouvel état | Effet (publication) |
|---|---|---|---|---|
| `Off` | modèles prêts et micro autorisé | — | `Armed` | `voice/stt/state=idle` |
| `Armed` | toucher le micro / début de session | mode `push` ou `session` | `Listening` | `voice/mic/control{start}`, `voice/stt/state=listening` |
| `Listening` | `voice/vad speech_start` | TTS inactive | `Hearing` | `voice/stt/state=hearing` |
| `Hearing` | `voice/stt/partial` | contient mot R3 (« stop », « arrête ») | `Resolving` (immédiat) | `ui/action/request{robot.stop}` sans attendre la fin |
| `Hearing` | `voice/vad speech_end` | — | `Decoding` | `voice/stt/state=decoding` |
| `Decoding` | `voice/stt/final` | `text` non vide | `Resolving` | — |
| `Decoding` | `voice/stt/final` | `text` vide ou `conf` < 0,4 | `Listening` | rien (silence = pas de bruit parasite) |
| `Resolving` | résultat de l'interpréteur | score ≥ 0,90, R0 | `Listening` | `ui/action/request` |
| `Resolving` | résultat | `needs_confirm` ou score 0,75–0,90 | `Confirming` | `ui/confirm/request` + `voice/tts/request` (prompt) |
| `Resolving` | résultat | non résolu | `Listening` | `voice/intent/unresolved` + invite brève (au plus 1 fois toutes les 8 s) |
| `Confirming` | « oui » / toucher « Confirmer » | feuille au premier plan | `Listening` | `ui/confirm/answer{yes}` |
| `Confirming` | « non » / toucher « Annuler » / délai 10 s | — | `Listening` | `ui/confirm/answer{no\|timeout}` |
| *tout état* | `voice/tts/state started` | priorité ≥ 1 | `Speaking` | micro en **demi-duplex** (8.3) |
| `Speaking` | `voice/tts/state finished\|cancelled` | file vide | `Listening` | réouverture du micro après 300 ms |
| *tout état* | `voice/stt/error` | `engine_crash` | `Armed` | redémarrage du moteur (1 essai) ; sinon `Off` + message |
| *tout état* | toucher quelconque sur l'écran | — | inchangé | annule la confirmation vocale en attente ; le toucher a priorité |

## 8.3. Règles d'arbitrage

| # | Règle |
|---|---|
| A1 | **Demi-duplex.** Pendant que le TTS parle, le micro n'envoie rien au STT, sauf le détecteur R3 (mots « stop », « arrête ») et le barge-in (A2). Cela évite que le robot s'écoute lui-même. |
| A2 | **Barge-in.** Si le VAD détecte une parole forte (> seuil réglé en usine) pendant un TTS de priorité ≤ 2, la synthèse est coupée dans les 150 ms et l'écoute reprend. Une synthèse de priorité 0 (sécurité) n'est jamais coupée par la parole, seulement par « stop » ou un toucher. |
| A3 | **Priorités TTS.** 0 sécurité (obstacle, arrêt) ; 1 confirmations et invites ; 2 réponses aux actions ; 3 lecture de contenu (fiches). Une priorité plus haute interrompt la plus basse (`interrupt:"replace"`) ; à priorité égale, `queue`. |
| A4 | **Découpage par phrase.** Le texte long est découpé en phrases ; la phrase *n+1* est synthétisée pendant la lecture de la *n*. Chaque phrase émet `voice/tts/state{sentence,index}`, ce qui permet la pause/reprise et « répète la section ». |
| A5 | **Péremption (`ttl_ms`).** Une demande TTS non démarrée dans son `ttl_ms` est jetée. Un message serveur arrivé trop tard n'est jamais lu. |
| A6 | **Contexte périmé (`epoch`).** Chaque changement d'écran incrémente `epoch`. Une `ActionRequest` ou une intention dont l'`epoch` est inférieur à l'`epoch` courant est **rejetée** (`code:"stale"`), sauf R3. Un énoncé dit sur l'écran précédent ne s'exécute pas sur le suivant. |
| A7 | **Occupé.** Pendant l'exécution d'une action (appel réseau en cours), toute autre action non R3 est rejetée (`code:"busy"`), le toucher comme la voix. |
| A8 | **Toucher prioritaire.** Un toucher annule toute confirmation vocale en attente et coupe la synthèse de priorité ≥ 2. |
| A9 | **Déduplication.** Un `voice/stt/final` de même texte dans les 800 ms est ignoré. |
| A10 | **Contenu sensible.** Une charge utile `sensitive:true` n'est jamais persistée, ni journalisée par le hub, ni envoyée à un rôle `monitor`. |
| A11 | **Pendant une mission** (`mission_active`), le seuil d'acceptation vocal monte à 0,92 et seules les actions `robot.stop`, `voice.stop_speaking`, `voice.repeat`, `app.help` sont acceptées : le bruit des moteurs dégrade la reconnaissance et rien d'autre ne doit être déclenché. |
| A12 | **Changement d'écran pendant une lecture de fiche.** La lecture (priorité 3) est annulée ; celle d'une confirmation ou d'une erreur ne l'est pas. |

## 8.4. Délais de référence

| Délai | Valeur |
|---|---|
| Confirmation d'une action R2 | 10 s |
| Attente d'un statut robot après `orientation.confirm` | 4 s |
| Acquisition des signes vitaux | 35 s (REST ; le nœud ROS 2 coupe à 32 s) |
| Relance d'une invite « je n'ai pas compris » | ≥ 8 s entre deux |
| Inactivité avant retour à la veille | 90 s sur les écrans de menu et de fiche ; 180 s dans le parcours de consultation (avec avertissement vocal et visuel 20 s avant) |
| Retour automatique après ticket | 60 s (comportement du Web conservé) |
| Mission (rappel du serveur) | 8 s (constante `MAX_MISSION_DURATION_S` côté ROS 2, à ne pas coder en dur dans l'application) |

## 8.5. Scénario : orientation par la voix (nominal)

```text
Utilisateur : « Emmène-moi à la pharmacie »
  Vad          → voice/vad{speech_start} … {speech_end}
  Stt          → voice/stt/final{ "emmène-moi à la pharmacie", conf 0.93 }
  Interpreter  → voice/intent/resolved{ orientation.select, PHARMACY, 0.96, epoch 12 }
  Dispatcher   → ui/action/request{ orientation.select, origin:voice }   (R0 : exécutée)
               → écran /orientation/confirm   → ui/state{ screen:"orientation.confirm", actions:[orientation.confirm, orientation.decline, robot.stop?] }
               → voice/tts/request{ "Vous souhaitez aller à la pharmacie. Confirmez-vous ?", priority 1 }
  Orchestr.    → état Confirming (délai 10 s)
Utilisateur : « Oui »
  Interpreter  → ui/confirm/answer{ yes }
  Dispatcher   → POST /api/request {ORIENTATION, PHARMACY}  → 200 {published:true}
               → voice/tts/request{ "Je transmets votre demande au robot.", priority 2 }
  Hub (relais) → robot/hmi/status{VALIDATED,ORIENTATION,PHARMACY}
               → robot/mission/status{REQUEST_RECEIVED, PHARMACY}
               → robot/mission/status{RUNNING}
  Dispatcher   → écran /orientation/mission « En route »
               → voice/tts/request{ "Je me mets en route. Dites stop pour m'arrêter.", priority 2 }
  Hub (relais) → robot/mission/status{MISSION_TIMEOUT}   (après ≈ 8 s)
               → écran « Mission de démonstration terminée » + voix correspondante (jamais « arrivé »)
```

## 8.6. Autres scénarios à implémenter et tester

| Scénario | Comportement attendu |
|---|---|
| **Refus par le robot** | `START_REJECTED:SENSORS_NOT_READY` → écran « Je ne peux pas partir : mes capteurs ne sont pas prêts » et même phrase vocale. Aucune mention d'un départ |
| **Pi injoignable pendant la confirmation** | `orientation.confirm` échoue immédiatement (pas de file) : « Je n'arrive pas à joindre le robot. Rien n'a été envoyé. » Rejoint V3 §7.8 |
| **ARRÊT pendant la mission** | « stop » reconnu sur `partial` → `robot.stop` → `POST /api/navigation/cancel` → STOP ; écran « Arrêté ». Le bouton ARRÊT tactile fait la même chose. Si l'application n'obtient pas de réponse HTTP sous 2 s, elle l'affiche (« L'arrêt n'est pas confirmé ») et réessaie une fois |
| **Ambiguïté « accueil »** | Voir 6.4 : question de clarification, aucune action |
| **Lecture d'une fiche et interruption** | « pause » met en pause à la fin de la phrase courante ; « continue » reprend ; « suivant » passe à la section suivante ; toucher « Silence » coupe |
| **Consultation par la voix** | Motif → session → dictée du nom (lecture-confirmation) → dictée du téléphone (lecture-confirmation) → signes vitaux (consigne vocale : « Posez le doigt sur le capteur et restez immobile », compte à rebours 35 s) → vérification lue en entier → « je confirme » → ticket lu : « Votre numéro est A-MAT-3 » |
| **Erreur de réservation** | Les messages du serveur (`duplicate_phone` 409, `slot_taken` 409, `invalid_phone` 400, session fermée) sont affichés **et** lus ; l'utilisateur est ramené à l'étape concernée |
| **Signes vitaux indisponibles** | « Je n'ai pas pu mesurer. Vous pouvez réessayer ou continuer sans mesure. » Aucune valeur inventée |
| **Barge-in** | Pendant une lecture de fiche, l'utilisateur dit « arrête » → synthèse coupée ≤ 150 ms ; l'écoute reprend |
| **Perte du WebSocket** | Bandeau discret « Connexion au robot perdue », reconnexion automatique ; les fonctions locales (voix, fiches en cache, navigation d'écrans) continuent ; orientation et réservation sont désactivées avec explication vocale si demandées |
| **Service externe qui parle** | `voice/tts/request` reçu du hub avec `source:"service:…"` : lu selon la priorité et le `ttl_ms`, journalisé sans contenu |

## 8.7. Textes vocaux de référence (français)

Ton : phrases courtes, vouvoiement, une idée par phrase, jamais de promesse que le robot n'a pas tenue. Les textes vivent dans des fichiers de traduction, pas dans le code.

| Situation | Texte |
|---|---|
| Veille → accueil | « Bonjour et bienvenue ! Que puis-je faire pour vous ? » |
| Choix de service | « Je peux vous orienter, vous informer, ou prendre un rendez-vous. » |
| Non compris | « Je n'ai pas bien compris. Vous pouvez aussi toucher l'écran. » |
| Hors contexte | « Je ne peux pas faire cela ici. Dites : aide. » |
| Mission acceptée | « Je me mets en route. Dites stop pour m'arrêter. » |
| Fin de mission | « Mon déplacement de démonstration est terminé. » |
| Arrêt | « Je m'arrête. » |
| Obstacle | « Obstacle détecté. Je m'arrête. » |
| Avertissement d'inactivité | « Êtes-vous toujours là ? Touchez l'écran pour continuer. » |
| Avertissement fiche | « Ces informations sont générales. Elles ne remplacent pas l'avis d'un professionnel de santé. » (le texte de `INFO_DISCLAIMER` côté serveur fait foi) |

## 8.8. Modes dégradés

| Panne | Comportement |
|---|---|
| Modèle STT absent ou en échec | Mode tactile seul ; bandeau « Voix indisponible » ; la synthèse continue si disponible |
| Modèle TTS absent ou en échec | Repli sur le TTS Android ; sinon texte seul. Les messages critiques (arrêt, obstacle) sont aussi affichés plein écran |
| Micro refusé | Écran d'explication de la permission, mode tactile seul |
| Hub injoignable | Voix locale complète ; fiches depuis le cache ; orientation/réservation/signes vitaux désactivés avec message explicite |
| REST joignable mais ROS 2 inactif (`robot/link` = down ou HTTP 503) | « Le robot n'est pas disponible pour le moment ». Les rendez-vous (SQLite) restent possibles (le Web actuel les traite sans ROS 2) |
| Le serveur renvoie un registre plus récent | Rechargé au prochain retour à l'accueil, jamais au milieu d'un parcours |

---

# 9. INTERFACE ET EXPÉRIENCE UTILISATEUR (UI/UX)

## 9.1. Diagnostic de l'interface Web actuelle (à ne pas reproduire)

Constats issus d'un rendu de la page réelle en paysage (915 × 412) et de la lecture du code.

| # | Constat | Conséquence pour la V4 |
|---|---|---|
| U1 | Les commandes vocales sont **trois boutons-icônes sans libellé** (micro, répéter, carré) dans l'angle supérieur droit, avec un message d'état coupé au bord de l'écran. Aucun état « j'écoute / je réfléchis / je parle » lisible, aucune transcription visible, aucune indication de ce qu'on peut dire | La voix devient un **élément permanent et central** de l'interface (rail vocal, 9.3) |
| U2 | L'icône « carré » (arrêt de la voix) est confondable avec un arrêt du robot | Deux commandes distinctes et nommées : « Silence » (voix) et « ARRÊT » (robot), formes et couleurs différentes |
| U3 | Le contenu flotte dans une carte centrée sur un fond presque vide ; une grande partie de la hauteur utile est perdue, alors que la hauteur est la ressource rare en paysage (≈ 360–412 dp). Un pied de page de copyright occupe de la place en permanence | Mise en page en deux zones, pas de pied de page (mention dans « À propos ») |
| U4 | Les trois tuiles de l'accueil sont **de poids égal**, sans chemin principal, et leur ordre ne suit pas la fréquence d'usage (Consultation en premier) | Hiérarchie claire, ordre : Orientation, Renseignements, Consultation (à valider avec l'auteur) |
| U5 | « Accueil / Réception » : le mot « Accueil » désigne à la fois l'écran d'accueil et la réception | Libellé « Réception » ; règle vocale de la section 6.4 |
| U6 | La confirmation d'orientation est une page de texte (« Je vous accompagne vers : Pharmacie ») dont le bouton « Annuler » **émet un STOP robot** : même mot pour « changer d'avis » et « arrêter le robot en marche » | Séparer : feuille de confirmation (Confirmer / Changer) et écran de mission (ARRÊT) |
| U7 | Aucun retour d'état du robot (parti ? refusé ? arrêté ?) : l'interface affiche toujours le texte de succès (constat C4) | Écran de mission relié aux états réels |
| U8 | Les fiches d'information s'affichent comme un long texte défilant dans l'écran « confirm » ; les titres sont reconnus par une liste codée en dur (`INFO_HEADINGS`), fragile | Fiche structurée en sections, navigation par section, lecture à voix haute, source en QR code |
| U9 | Le parcours de consultation est une colonne unique de boutons pleine largeur empilés (Continuer, Retour, Annuler…) | Parcours en deux colonnes, une action principale, retour toujours au même endroit, stepper visuel |
| U10 | La carte SpO₂ « En attente » reste affichée alors qu'elle n'est pas livrable (constat C6) | Retirée |
| U11 | Cibles tactiles des boutons-icônes d'environ 36 px ; textes secondaires petits | Cibles ≥ 56 dp, texte courant ≥ 18 sp |
| U12 | Chaînes de texte écrites dans le HTML et le JavaScript | Textes externalisés (fichiers ARB), prêts pour le malgache |

**Ce qui est conservé du Web** (identité à reprendre) : palette marine/azur/brume, polices Plus Jakarta Sans et Inter, logo (robot dans un carré arrondi), robot de l'écran d'accueil (visage sur écran sombre, yeux et sourire cyan), tuiles d'icônes sur fond azur clair, pastilles d'état (attente, erreur, succès), ton chaleureux et vouvoiement.

## 9.2. Principes de conception **[V4]**

| # | Principe |
|---|---|
| D1 | **Deux zones.** À gauche, le **rail HIAR** (robot + voix + état), permanent. À droite, la **scène** (le contenu de l'étape). La voix n'est jamais cachée, le contenu dispose de toute la largeur restante |
| D2 | **Une action principale par écran**, visuellement dominante (bouton plein azur). Les actions secondaires sont en contour ou textuelles |
| D3 | **Le retour est toujours au même endroit** (haut gauche de la scène) et fait la même chose partout : revenir d'un niveau |
| D4 | **Cibles ≥ 56 dp**, espacement ≥ 12 dp, texte courant ≥ 18 sp, titres ≥ 28 sp. Les menus tiennent **sans défilement** dans 360 dp de hauteur |
| D5 | **Voix découvrable** : chaque contrôle porte discrètement ce qu'il faut dire (puce « 🎤 Pharmacie » sous forme d'icône micro + mot), activable dans les réglages, affichée par défaut |
| D6 | **Retour immédiat** : tout geste ou ordre vocal produit une réaction visible en moins de 200 ms (état pressé, surbrillance de la carte reconnue), puis le résultat |
| D7 | **L'état du système est lisible d'un coup d'œil** : l'expression du robot et la couleur du rail disent s'il est hors ligne, prêt, à l'écoute, en réflexion, en parole, en mission |
| D8 | **Tolérance** : jamais de perte de saisie en cas de retour ; une erreur dit quoi faire ensuite ; les actions destructrices et robotiques demandent confirmation |
| D9 | **Calme** : pas d'animation décorative en boucle sur les écrans de contenu. Les seules animations continues sont le halo du micro et le clignement du robot. Respect du réglage « réduire les animations » |
| D10 | **Pas de mode sombre** en V4 (kiosque, charte unique) |

## 9.3. Gabarit paysage

Dimensions de référence (en dp, indépendantes de la densité) : fenêtre minimale **640 × 360**, courante **800–915 × 360–412** (smartphone), tablette **1024+ × 600+**. Marges de sécurité (encoche, barres) lues via `MediaQuery.padding`.

```text
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ RAIL (248 dp)               │ SCÈNE (reste)                                   │
 │ ┌─────────────────────────┐ │ ┌─ barre : ← Retour · titre · étape ──────────┐ │
 │ │  Robot (96 dp)          │ │ │                                             │ │
 │ │  expression = état      │ │ │            contenu de l'étape               │ │
 │ ├─────────────────────────┤ │ │                                             │ │
 │ │  Micro (72 dp)          │ │ │                                             │ │
 │ │  libellé d'état         │ │ │                                             │ │
 │ ├─────────────────────────┤ │ ├─────────────────────────────────────────────┤ │
 │ │  « … texte reconnu … »  │ │ │  [ action secondaire ]   [ ACTION PRINCIPALE ]│ │
 │ │  Dites : « pharmacie »  │ │ └─────────────────────────────────────────────┘ │
 │ │  Liaison robot ●        │ │                                                 │
 │ └─────────────────────────┘ │                                                 │
 └──────────────────────────────────────────────────────────────────────────────┘
```

- Rail : largeur fixe 248 dp (232 dp sous 700 dp de largeur), fond **marine** (`#0B2545`) pour détacher la voix du contenu ; la scène reste sur fond **brume** (`#F3F7FB`).
- Scène : cartes blanches, rayon 20 dp, ombre douce (reprise de `--shadow`), marges 24 dp (16 dp en 360 dp de hauteur).
- Barre de scène : 56 dp ; zone d'actions en pied : 72 dp, collée en bas, jamais masquée par le clavier.

## 9.4. Système visuel

### Couleurs (jetons repris du Web, `hiar-tokens.css`)

| Jeton | Valeur | Usage | Contraste vérifié |
|---|---|---|---|
| `marine` | `#0B2545` | Texte principal, rail | 14,3:1 sur brume |
| `azur` | `#1A73C8` | Action principale, icônes | 4,85:1 avec blanc (texte blanc sur bouton) |
| `azur-dark` | `#145A9E` | État pressé | — |
| `brume` | `#F3F7FB` | Fond de scène | — |
| `azur-soft` | `#DCEBFA` | Tuiles d'icônes, sélection | **Ne pas mettre de texte azur dessus** (4,0:1) ; texte marine |
| `text-2` | `#51657D` | Texte secondaire | 5,6:1 sur brume |
| `border` | `#D5E1EE` | Contours | — |
| `wait` / `wait-bg` | `#B45309` / `#FEF3C7` | En attente, confirmation en cours | 4,5:1 |
| `err` / `err-bg` | `#B91C1C` / `#FEE2E2` | Erreur, **bouton ARRÊT** (blanc sur `err` : 6,5:1) | 5,3:1 |
| `ok` / `ok-bg` | `#15803D` / `#DCFCE7` | Succès, mesure valide | 4,6:1 |
| `cyan` / `cyan-soft` | `#20C9E8` / `#55E7FF` | **Uniquement** voix et robot (halo du micro, yeux). Repris du SVG d'accueil | 10,4:1 sur marine |

### Typographie

| Rôle | Police | Taille / graisse |
|---|---|---|
| Titre d'écran | Plus Jakarta Sans | 32 sp / 800 (28 sp en 360 dp de hauteur) |
| Titre de carte | Plus Jakarta Sans | 22 sp / 700 |
| Texte courant | Inter | 18 sp / 400, interligne 1,45 |
| Texte secondaire | Inter | 16 sp / 400 |
| Libellé de bouton | Inter | 20 sp / 600 |
| Puce vocale | Inter | 14 sp / 500 |
| Numéro de ticket | Plus Jakarta Sans | 72 sp / 800 |

**Mise en œuvre des polices.** Flutter ne charge pas le format `.woff2` du Web : convertir les deux polices variables en `.ttf` (outil `fonttools`, conserver l'axe de graisse) et les déclarer dans `pubspec.yaml`, avec `FontVariation('wght', …)` **[À VÉRIFIER : rendu sur l'appareil cible]**. Ne pas dépendre de `google_fonts` (hors ligne).

### Forme et mouvement

Rayons : 20 dp (cartes), 16 dp (boutons), 28 dp (feuilles). Élévation 0–2 (ombres douces). Transitions de 200 ms (axe horizontal entre étapes, fondu entre feuille et scène). Retour tactile : ondulation Material + vibration légère facultative.

## 9.5. Le rail vocal

### États (miroir de la machine à états, section 8.2)

| État | Robot | Micro | Texte du rail | Couleur d'accent |
|---|---|---|---|---|
| Hors ligne (`Off`) | Yeux fermés | Barré, gris | « Voix indisponible » (+ raison) | gris `text-2` |
| Prêt (`Armed`) | Sourire, yeux ouverts | Contour azur | « Touchez pour parler » | azur |
| Écoute (`Listening`) | Yeux attentifs | Halo cyan lent | « Je vous écoute » | cyan |
| Entend (`Hearing`) | Yeux dilatés | Anneau réagissant au niveau sonore | texte partiel en direct, en italique | cyan vif |
| Réflexion (`Decoding/Resolving`) | Regard vers le haut | Trois points | « … » | cyan |
| Parole (`Speaking`) | Bouche animée | Barres d'onde (sortie) + bouton **Silence** | phrase en cours (surlignée par phrase) | azur |
| Confirmation (`Confirming`) | Sourcils levés | Boutons **Oui / Non** | « Dites oui ou non » | `wait` |
| Mission | Regard avant | Micro en mode réduit (A11) | « En route · dites stop » | `err` discret sur le liseré du rail |

### Éléments

- **Bouton micro** 72 dp : touch = basculer l'écoute ; appui long = parler (push-to-talk).
- **Transcription** : 2 lignes, texte reconnu (le dernier énoncé reste 4 s, puis s'efface).
- **Puces « Dites… »** : 2 à 3 exemples contextuels (issus de `ui/state.actions`), la première étant la plus probable.
- **Pastille de liaison** : vert (hub joint, ROS 2 actif), orange (hub joint, ROS 2 inactif), gris (hors réseau). Texte lisible par TalkBack.
- **Indicateur de confidentialité** : « Aucun enregistrement. Reconnaissance sur l'appareil. » accessible depuis l'icône d'information du rail.

### Modes d'écoute **[V4]**

| Mode | Comportement | Par défaut |
|---|---|---|
| **Session mains libres** | Une fois la session commencée (toucher l'écran de veille), le micro reste ouvert, filtré par le VAD et le seuil de confiance. Fermé à la veille et après 90 s d'inactivité | **Oui** |
| Appui pour parler | Micro ouvert seulement pendant l'appui | Réglage |
| Réveil vocal depuis la veille | Reconnaissance d'un seul mot-clé (« bonjour ») à seuil strict | **Désactivé** (déclenchements parasites en milieu hospitalier) |

## 9.6. Écrans (maquettes paysage, 840 × 360 dp indicatifs)

### Veille

```text
┌───────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│            [ robot HIAR animé : clignement, antenne cyan ]                     │
│                              Bonjour !                                        │
│                  Touchez l'écran pour commencer                               │
│                                                       (mic fermé · ● liaison)   │
└───────────────────────────────────────────────────────────────────────────────┘
```

Plein écran sur fond brume dégradé azur-soft (reprise de l'esprit du Web). Aucun rail : la voix n'écoute pas à cet état.

### Accueil

```text
┌─ RAIL ──────────┬─────────────────────────────────────────────────────────────┐
│  (robot)        │  Que souhaitez-vous ?                                       │
│  (micro)        │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │
│  « … »          │ │  ⌖          │ │  ⓘ          │ │  ▦＋        │             │
│  Dites :        │ │ Orientation │ │ Renseigne-  │ │ Consultation│             │
│  🎤 orientation │ │ Pharmacie,  │ │ ments       │ │ Rendez-vous │             │
│                 │ │ labo, récep.│ │ Santé       │ │ du jour     │             │
│                 │ └─────────────┘ └─────────────┘ └─────────────┘             │
└─────────────────┴─────────────────────────────────────────────────────────────┘
```

Trois cartes égales en hauteur (≈ 200 dp), icône 56 dp sur tuile azur-soft, titre 22 sp, sous-titre 16 sp. Phrase d'aide dessous : « Vous pouvez aussi dire : *emmène-moi à la pharmacie* ».

### Orientation : choix de destination

```text
│  ← Retour        Où souhaitez-vous aller ?                                    │
│ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐                │
│ │ ✚  Pharmacie     │ │ ⚗  Laboratoire   │ │ ▥  Réception     │                │
│ │ 🎤 pharmacie     │ │ 🎤 laboratoire   │ │ 🎤 réception     │                │
│ └──────────────────┘ └──────────────────┘ └──────────────────┘                │
```

### Orientation : confirmation (feuille modale, 28 dp de rayon)

```text
│ ┌────────────────────────────────────────────────────────────────────────┐    │
│ │  Aller à la Pharmacie ?                                                │    │
│ │  Le robot va se déplacer. Restez à distance des obstacles.             │    │
│ │  [ Changer de destination ]                       [  ✔ Confirmer  ]    │    │
│ │  Dites : « oui » ou « non »         ⏱ 10 s (anneau décroissant)        │    │
│ └────────────────────────────────────────────────────────────────────────┘    │
```

### Orientation : mission

```text
│  Vers : Pharmacie                           État : ● En route                │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  Mission de démonstration                                            │   │
│  │  Le robot se déplace de façon limitée dans le temps.                 │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│  [                       ■  ARRÊT  (rouge, 96 dp de haut)               ]    │
│  Dites : « stop »                                                            │
```

États affichés (relayés, section 7.7) : *Demande envoyée…* → *En route* (`RUNNING`) → *Mission terminée* (`MISSION_TIMEOUT`) ou *Arrêté* ; ou refus explicite (capteurs non prêts, mission déjà active, robot sans réponse). **Jamais** « arrivé ».

### Renseignements : liste

```text
│  ← Retour       Renseignements santé                                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                               │
│  │ VIH / SIDA │ │ Paludisme  │ │ Diabète    │      6 cartes en 3 × 2        │
│  └────────────┘ └────────────┘ └────────────┘      (hauteur 120 dp,         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐       sans défilement)        │
│  │Hypertension│ │Tuberculose │ │ Santé      │                               │
│  │            │ │            │ │ menstruelle│                               │
│  └────────────┘ └────────────┘ └────────────┘                               │
```

### Renseignements : fiche (lecteur)

```text
│  ← Retour        Paludisme                         [ Source OMS ▣ ]         │
│ ┌──────────────┬───────────────────────────────────────────────────────┐    │
│ │ ● Comprendre │  COMPRENDRE                                           │    │
│ │   Transmiss. │  Le paludisme est une maladie provoquée par un        │    │
│ │   Symptômes  │  parasite transmis principalement par la piqûre d'un  │    │
│ │   Formes gr. │  moustique Anophèle femelle infecté…                  │    │
│ │   Prévention │                                                       │    │
│ │   Quand cons.│                                                       │    │
│ ├──────────────┴───────────────────────────────────────────────────────┤    │
│ │  ⏮    ⏯ Lire cette section    ⏭        Vitesse ▾      Silence ■      │    │
│ └──────────────────────────────────────────────────────────────────────┘    │
│  ⚠ Information générale non diagnostique…  (bandeau fixe, 40 dp)             │
```

À gauche, le sommaire des sections (navigation tactile et vocale) ; à droite, une section à la fois, sans défilement de page entière (défilement interne si la section est longue). La section en cours de lecture est surlignée **phrase par phrase** (événements `voice/tts/state{sentence}`).

### Consultation : parcours

Stepper en haut de la scène (5 pastilles + libellé). Étape 1 : trois cartes de motif. Étape 2 : cartes de sessions (médecin, période, « n en attente ») ; les sessions fermées n'apparaissent pas.

```text
│  ← Retour     ①──②──③──④──⑤       Vos coordonnées                            │
│  Nom complet     [ Rakoto Jean                       ] [ 🎤 Dicter ]          │
│  Téléphone       [ 034 12 345 67                     ] [ 🎤 Dicter ]          │
│  « J'ai compris : zéro trois quatre … Est-ce correct ? »   [ Oui ] [ Non ]    │
│                                                    [ Continuer → ]           │
```

Étape 3 : champs avec dictée, pavé numérique plein écran pour le téléphone en alternative au clavier. Étape 4 :

```text
│  Mesures facultatives, non diagnostiques                                      │
│  ┌──────────────────────┐  ┌──────────────────────┐                           │
│  │ Température          │  │ Fréquence cardiaque  │      Anneau de compte à    │
│  │  36,6 °C   ● Valide  │  │  72 bpm    ● Valide  │      rebours 35 s pendant  │
│  └──────────────────────┘  └──────────────────────┘      la mesure             │
│  [ Passer ]                     [ Lancer la mesure ]      (pas de carte SpO₂)    │
```

Étape 5 : récapitulatif en deux colonnes (motif, session, nom, téléphone, mesures), bouton « Confirmer » unique ; « Modifier » en secondaire ; l'application lit le récapitulatif.

Ticket :

```text
│  Rendez-vous enregistré                                                       │
│        Votre numéro de file                                                   │
│             A-MAT-3                  (72 sp)                                  │
│  Médecin A · Matin · 14 novembre 2026                                         │
│  Retour à l'accueil dans 60 s                              [ Terminer ]       │
```

### Erreur et mode dégradé

Bandeau en haut de la scène (hauteur 48 dp, couleurs `err-bg`/`wait-bg`) avec une phrase et une action (« Réessayer »). La panne n'enlève jamais la navigation : l'utilisateur peut toujours revenir.

## 9.7. Kiosque et accessibilité

| Sujet | Règle |
|---|---|
| Orientation | Paysage forcé (`sensorLandscape`), les deux sens autorisés |
| Écran | Allumé en permanence (`wakelock_plus`), mode immersif collant, barre de navigation masquée |
| Sortie de l'application | Geste retour système désactivé sur `/splash` et `/home` ; sortie réservée à l'administrateur (réglages protégés) |
| Verrouillage d'écran / épinglage | Recommandé (« épinglage d'écran » Android) **[À VÉRIFIER : selon l'appareil]** |
| Volume | Volume de la voix réglable, valeur minimale imposée (jamais muet par accident) |
| TalkBack | Chaque contrôle a un libellé sémantique ; l'identifiant sémantique = identifiant d'action du registre (utile aux tests de parité) |
| Texte agrandi | Supporte jusqu'à × 1,3 sans coupure |
| Contraste | ≥ 4,5:1 pour le texte (tableau 9.4) |
| Daltonisme | L'état n'est jamais porté par la seule couleur (icône ou texte associé) |
| Inactivité | Avertissement vocal et visuel 20 s avant le retour à la veille ; efface toute donnée saisie (section 11) |
| Sans état persistant patient | Rien de ce que saisit un patient ne reste sur l'appareil après la fin du parcours |

---

# 10. CONTRATS API ET MODIFICATIONS DU SERVEUR

## 10.1. Endpoints existants utilisés par l'application **[CODE]**

| Méthode et chemin | Usage dans l'application | Réponses à traiter |
|---|---|---|
| `POST /api/request` | `orientation.confirm` (corps `{"category":"ORIENTATION","item":"PHARMACY"}`) | 200 `{ok, request, title, message, published}` ; 400 (élément inconnu/indisponible) ; 503 (pont ROS 2 non publié) |
| `POST /api/navigation/cancel` | `robot.stop` | 200 `{ok, published, message}` ; 503 |
| `GET /api/consultation/sessions?date=YYYY-MM-DD` | Étape 2 : sessions ouvertes (`doctor_code`, `period`, `waiting_count`) | 200 ; 400 date invalide ; 500 |
| `POST /api/consultation/appointments` | `consult.review.confirm` : `patient_name, contact, reason_code, requested_date, doctor_code, period, temperature_c?, heart_rate_bpm?, spo2_percent?` | 201 `{ok, ticket_number, ticket_label, …}` ; 400 ; 409 `duplicate_phone` / `slot_taken` ; 500 |
| `POST /api/vitals/acquire` | `consult.vitals.start` (bloquant jusqu'à 35 s) | 200 `{ok, state, values, reason, measured_at}`, avec `state` ∈ `valide`, `indisponible`, `en cours` |

Mesures : `temperature_c` ∈ [25, 45], `heart_rate_bpm` entier ∈ [40, 200], `spo2_percent` toujours `null` côté application. Date du jour : fuseau `Indian/Antananarivo`.

**Les endpoints `/api/staff/*` et `/api/doctor/*` ne sont pas utilisés** (hors périmètre).

## 10.2. Mapping erreur → message (affiché et parlé)

| Source | Message (FR) |
|---|---|
| 400 `invalid_phone` | « Ce numéro de téléphone n'est pas valide. Il doit comporter 10 chiffres. » |
| 409 `duplicate_phone` | « Une réservation existe déjà pour ce numéro aujourd'hui. » |
| 409 `slot_taken` | « Cette consultation vient d'être prise. Choisissez-en une autre. » |
| Session fermée ou échéance dépassée (400 côté serveur) | « Cette consultation n'accepte plus d'inscriptions. » |
| 503 sur `/api/request` | « Le robot n'est pas disponible. Rien n'a été envoyé. » |
| Délai réseau | « Le serveur HIAR ne répond pas. Réessayez. » |
| 200 vitaux `indisponible` | « La mesure n'a pas pu être faite. » + `reason` du serveur |

## 10.3. Nouveaux endpoints et modifications **[V4]**

| Réf | Changement | Fichier(s) | Raison |
|---|---|---|---|
| N1 | `GET /api/catalog` : catégories, destinations, fiches d'information **structurées** (liste de sections `{heading, paragraphs[], bullets[]}`, `source`, `source_url`, `disclaimer`) | `app.py`, `catalog.py` | Le mobile n'utilise pas Jinja ; supprime le découpage fragile par titres (U8) |
| N2 | `GET /api/voice/registry` : registre d'actions (section 6) avec `hash` | `app.py`, nouveau `voice_fr.yaml`, génération depuis `catalog.py` | Source unique des phrases vocales |
| N3 | `GET /api/health` : `{version, registry_hash, db:"ok", ros_bridge:"up"\|"down", hub:{clients}}` | `app.py` | Diagnostic, bandeau d'état |
| N4 | `GET /models/manifest.json` et fichiers de modèles | serveur statique | Provisionnement hors Internet (4.4) |
| N5 | `WS /ws` (section 7) | `hub/` | Bus d'événements |
| M1 | Aligner `hmi_request_node.py` sur `catalog.py` : ajouter `TUBERCULOSIS` et `MENSTRUAL_HEALTH` ; test de cohérence catalogue ↔ validateur | `hmi_request_node.py`, test | Constat C1. **Seule modification ROS 2 autorisée par la V4** |
| M2 | ~~Modifier `POST /api/request`~~ **Abandonnée** (Web gelé) : les fiches passent par N1 | — | Constat C2 |
| M3 | Rendre `ROS_BRIDGE` observable (`RosBridge.active`, abonnements d'état en lecture) | `ros_bridge.py` | Relais (7.7) |
| M4 | Ajouter `robot_status` au fichier de lancement **uniquement si** l'auteur le souhaite | `hiar_robot.launch.py` | Constat de la section 2.1 (non lancé) ; question ouverte Q4 |

**Web gelé.** Aucun fichier de `templates/` ni de `static/` n'est modifié ; les routes existantes gardent comportement et contrat ; leurs 142 tests continuent de passer sans changement. N1, N2, N3 et le WebSocket sont réalisés dans de **nouveaux fichiers** (un blueprint `mobile_api.py` et le paquet `hub/`), enregistrés dans `app.py` par quelques lignes d'ajout seulement, sans toucher aux routes. La seule modification hors ajout est M1, côté ROS 2 (hmi_request_node.py), qui n'est pas du Web.

---

# 11. DONNÉES ET JOURNALISATION

## 11.1. Base SQLite

**Aucune modification du schéma** en V4. Tables actuelles **[CODE]** : `appointments` (patient_name, contact, contact_normalized, reason, reason_code, requested_date, requested_time, status, period, doctor, ticket_number, pass_number, slot_id, température/fréquence cardiaque/SpO₂, created_at…), `doctor_sessions` (requested_date, doctor_code, period, is_open, manual_open, opened_at, closed_at), `hiar_schema_migrations`. Le « Journal » conceptuel de la V3 n'est pas une table dans le code ; la V4 le réalise sous forme de **fichier journal** (11.3).

## 11.2. Sur l'appareil

| Donnée | Conservation |
|---|---|
| Saisies d'un patient (nom, téléphone, mesures) | **En mémoire seulement**, effacées à la fin du parcours, à l'annulation ou à la veille. Jamais écrites sur le disque |
| Audio | **Jamais enregistré, jamais transmis** |
| Textes reconnus | En mémoire vive, non persistés ; si `sensitive:true`, non publiés au hub (A10) |
| Modèles vocaux, registre, fiches en cache, réglages | Stockage privé de l'application |
| Journal de diagnostic | Événements techniques sans contenu (codes, durées, scores), tournant, 200 Ko max |

## 11.3. Côté Pi

Fichier `hiar_hub.log` (rotation 7 jours) : connexion/déconnexion, topics publiés (nom, taille, `id`), erreurs, actions R1/R2/R3 avec `action_id` et `origin`. **Pas de charge utile** pour `voice/stt/*` ni de contenu `sensitive`. Ajout au minimum : horodatage (fuseau Antananarivo), appareil, `corr`. Les journaux évitent les données personnelles (règle V3 §9.5.8).

---

# 12. SÉCURITÉ ET SÛRETÉ

## 12.1. La voix et le mouvement du robot

| Risque | Mesure |
|---|---|
| Mauvaise reconnaissance qui déclenche un déplacement | Confirmation obligatoire R2 pour voix **et** tactile ; seuils ; portée contextuelle ; `epoch` (A6) |
| Parole ambiante (couloir, télévision) | Session ouverte uniquement après un toucher ; réveil vocal désactivé ; « oui » ignoré hors confirmation ; seuil renforcé en mission (A11) |
| Bruit des moteurs qui empêche d'entendre « stop » | Bouton ARRÊT tactile permanent ; les protections ESP32 et la durée maximale de mission (8 s) restent la sécurité réelle |
| Faux sentiment de sécurité | **Le « stop » vocal n'est pas un arrêt d'urgence** : il passe par Wi-Fi, Flask, ROS 2 et la navigation. L'arrêt d'urgence réel reste matériel (coupure d'alimentation moteurs). À écrire dans le manuel et la soutenance |
| Mission lancée sans que l'utilisateur le sache | Annonce vocale et visuelle systématique, avec le moyen d'arrêter |
| Annonce mensongère | Messages liés aux états réels uniquement (P6) |
| Contournement du Supervisor | Interdit par conception : le hub n'a aucun éditeur sur `/robot/*` ni `/robot/motor_command` |

## 12.2. Réseau et accès

| Risque | Mesure |
|---|---|
| Client WebSocket non autorisé | Réseau `HIAR-DEMO` en **WPA2** (mot de passe changé) ; jeton d'appareil à la poignée de main (`HIAR_DEVICE_TOKEN` côté serveur, distinct du jeton du personnel) ; liste d'`device_id` autorisés |
| Injection de topics | Droits par rôle (7.4) ; validation de chaque charge utile ; rejet `forbidden_topic` |
| Flood | Limite 50 msg/s par client, 64 Ko par message, `rate_limited` |
| Trafic en clair | `ws://` et `http://` en clair, mais **limités** à `10.42.0.1` par `networkSecurityConfig` Android (pas de `usesCleartextTraffic` global). Amélioration future : `wss://` avec certificat interne |
| Réseau Wi-Fi sans Internet | Android peut router le trafic vers les données mobiles quand le Wi-Fi n'a pas d'accès Internet. **Lier le processus au réseau Wi-Fi** via un petit canal Kotlin (`ConnectivityManager.bindProcessToNetwork`), et désactiver les données mobiles de l'appareil en kiosque |
| Jetons compromis (S1) | Régénérer ; ne plus les mettre dans les archives ; ne pas les coder dans l'APK (le jeton d'appareil est saisi au provisionnement et stocké dans le stockage sécurisé Android) |
| Modèles corrompus ou remplacés | Vérification SHA-256 du manifeste avant activation |
| Données de santé | Fiches générales non diagnostiques, avertissement toujours présent et lu ; mesures « indicatives » ; aucune interprétation clinique |

## 12.3. Permissions Android

`RECORD_AUDIO` (demandée à la première utilisation avec explication), `INTERNET`, `ACCESS_NETWORK_STATE`, `CHANGE_NETWORK_STATE` (liaison au Wi-Fi), `WAKE_LOCK`. Pas de localisation, pas de stockage partagé, pas de service au premier plan en V4 (l'écoute n'a lieu que l'application au premier plan).

---

# 13. TESTS ET CRITÈRES D'ACCEPTATION

## 13.1. Pyramide de tests

| Niveau | Outil | Cible |
|---|---|---|
| Unitaire Dart | `flutter test` | Normaliseur, `NumberParser`, correspondance, politique d'ambiguïté, machine à états vocale, `TtsQueue`, enveloppe et QoS du `HubClient` |
| Widgets | `flutter test` (widget tests) | Chaque écran, états d'erreur, cibles ≥ 56 dp, absence de défilement dans 640 × 360 |
| Parité | Test dédié (13.3) | Registre ↔ interface |
| Protocole | `pytest` côté `hub/` + client Dart contre un hub simulé | Poignée de main, ack, rejeu, droits, limites |
| Serveur | `pytest` existant (142 tests) + nouveaux | Aucune régression ; M1, N1 à N3 |
| Intégration sans moteurs | Pi, ROS 2 réel, **moteurs non alimentés** | Chaîne application → hub → Flask → `/hmi/request` → statuts relayés |
| Essais physiques | Robot, supervision humaine, zone dégagée | Seulement après validation des étapes précédentes |

## 13.2. Évaluation de la voix (lot WP1, avant tout engagement de modèle)

1. **Corpus de commandes** : au moins toutes les phrases du registre (6.3) et leurs variantes, dites par ≥ 5 locuteurs, dans 3 conditions (calme ; bruit de couloir ; robot en mouvement).
2. **Corpus de dictée** : 30 noms malgaches courants et 30 numéros de téléphone `03x xx xxx xx`, dits naturellement.
3. **Mesures** : taux d'erreur de mots, taux de commandes correctement résolues, latence fin de parole → texte, mémoire, température et consommation après 20 minutes.
4. **Décision** : choisir le modèle STT de commandes, le modèle de dictée, la voix TTS. Consigner la décision (date, appareil, résultats) dans un document `docs/voice_benchmark.md`.
5. Si la dictée d'un nom échoue systématiquement, la fonction `consult.field.dictate` pour le **nom** est retirée de la livraison et le clavier reste la seule voie (le téléphone par dictée est conservé s'il atteint le seuil).

Seuils d'acceptation : section 4.3.

## 13.3. Test de parité (automatique, bloquant)

| # | Vérification |
|---|---|
| T1 | Toute action du registre a au moins un contrôle tactile (identifiant sémantique = id d'action) **ou** figure en 6.6 |
| T2 | Tout contrôle interactif de `lib/features/**` est un `ActionButton` ; un contrôle brut (`ElevatedButton`, `InkWell`, etc.) qui n'en dérive pas fait échouer le test (règle de lint personnalisée ou recherche de motifs) |
| T3 | Toute action a ≥ 3 phrases vocales (≥ 5 pour les actions globales et de niveau R2/R3) |
| T4 | **Aucune collision** : deux actions disponibles dans le même écran n'ont jamais la même phrase normalisée |
| T5 | Pour chaque action et chaque phrase, passer l'énoncé simulé au `Matcher` avec le contexte de l'écran donne exactement l'`ActionRequest` du bouton correspondant |
| T6 | Pour chaque écran, `ui/state.actions` est égal à l'ensemble des contrôles visibles et actifs |
| T7 | Le registre embarqué a le même hachage que celui généré depuis `catalog.py` (échec si le catalogue change sans régénération) |
| T8 | Cohérence catalogue ↔ validateur ROS 2 (`hmi_request_node.VALID_REQUESTS`) |

## 13.4. Critères d'acceptation par fonction

| Fonction | Critère observable |
|---|---|
| Orientation par la voix | Dire « emmène-moi à la pharmacie » → feuille de confirmation vocale et visuelle → « oui » → `/hmi/request` reçu et statuts `VALIDATED` puis `RUNNING` visibles dans l'application. Sans « oui », rien n'est publié |
| Arrêt | « stop » pendant la mission → STOP publié sur `/navigation/command` en < 1,5 s ; le bouton ARRÊT donne le même résultat |
| Vérité de l'état | Capteurs non prêts → l'application affiche le refus et ne dit jamais « en route » |
| Fiches | Les 6 fiches s'affichent sans ROS 2 (via N1) ; la lecture à voix haute fonctionne section par section, pause et reprise comprises |
| Consultation | Parcours complet par la voix seule (hors clavier) jusqu'au ticket ; mêmes règles serveur qu'au Web (un téléphone par jour) |
| Signes vitaux | Valeurs affichées seulement si fournies par le robot ; sinon « indisponible » ; jamais de SpO₂ |
| Voix hors ligne | Avec le Wi-Fi coupé, la reconnaissance et la synthèse fonctionnent ; l'application l'indique et désactive orientation et réservation |
| Reconnexion | Coupure puis retour du Wi-Fi : reconnexion automatique en ≤ 15 s, état `ui/state` republié, aucun message QoS 1 perdu ni dupliqué |
| Parité | Les tests T1 à T8 passent |
| Confidentialité | Aucun fichier de l'appareil ni du Pi ne contient de nom, téléphone ou audio après un parcours complet |

---

# 14. PLAN DE RÉALISATION POUR L'AGENT CODEUR

Ordre recommandé. Chaque lot a une définition de « terminé » vérifiable. Ne pas commencer un lot dont les dépendances ne sont pas validées.

| Lot | Contenu | Dépend de | Terminé quand |
|---|---|---|---|
| **WP0** Hygiène | Régénérer les jetons (S1) ; base synthétique de développement (S2) ; décisions de l'auteur sur S3 à S5 ; figer la version de référence du dépôt (commit) | — | Aucun secret ni donnée réelle dans le dépôt de travail ; tests Web exécutés et leur état connu (les 2 échecs de l'archive analysés) |
| **WP1** Spike voix | Prototype Flutter minimal : micro → VAD → STT → texte, texte → TTS → haut-parleur, sur l'appareil cible ; benchmark 13.2 ; choix des paquets audio (4.1) | — | `docs/voice_benchmark.md` rédigé ; latences mesurées ; décision de modèles consignée |
| **WP2** Serveur : contrats | M1, N1, N2, N3 (nouveaux modules uniquement) ; tests T7 et T8 côté serveur | WP0 | Nouveaux tests verts, anciens tests inchangés, aucun fichier Web modifié (vérifiable par `git diff` sur `templates/` et `static/`) |
| **WP3** Hub WebSocket | Paquet `hub/` (protocole, routeur, sessions, rôles), montage `/ws`, journalisation, tests de protocole ; relais ROS 2 (M3) simulé puis réel | WP2 | Tests de protocole verts ; client de test se connecte, s'abonne, reçoit un statut simulé ; reconnexion et rejeu démontrés |
| **WP4** Squelette application | Projet Flutter, thème (9.4), polices, routeur, `EventBus`, `ApiClient`, `HubClient`, liaison réseau Wi-Fi, mode paysage et kiosque | WP1 (choix), WP3 | L'application affiche la veille et l'accueil, se connecte au hub, affiche l'état du lien |
| **WP5** Registre et dispatcher | `ActionRegistry`, `ActionDispatcher`, `Interpreter`, `ActionButton`, `UiStatePublisher`, politique de confirmation | WP2, WP4 | Tests T1 à T6 passent sur les écrans déjà construits |
| **WP6** Moteur vocal | `SttEngine`, `TtsEngine`, `TtsQueue`, `VoiceOrchestrator`, demi-duplex, barge-in, `ModelManager` et écran de provisionnement | WP1, WP4, WP5 | Scénarios 8.5 et 8.6 (hors robot) passent avec un faux serveur ; budgets 4.3 respectés |
| **WP7** Écrans patient | Rail vocal, Orientation (confirmation + mission), Renseignements (lecteur), Consultation (5 étapes + ticket + dictée), erreurs et dégradations | WP5, WP6 | Parcours complets tactile **et** vocal ; wireframes 9.6 respectés ; aucun défilement de page dans 640 × 360 pour les menus |
| **WP8** Intégration sans moteurs | Pi réel, ROS 2 réel, **moteurs non alimentés** : orientation, statuts relayés, refus, ARRÊT, vitaux | WP3, WP7 | Critères 13.4 vérifiés et consignés avec captures et journaux |
| **WP9** Essais physiques et gel | Essais supervisés, zone dégagée, un seul scénario à la fois ; documentation, manuel d'utilisation, mise à jour du checkpoint | WP8 + accord explicite de l'auteur | Résultats consignés ; limites déclarées (stop vocal ≠ arrêt d'urgence, pas d'arrivée) |

**À ne pas faire sans demande explicite** : flasher l'ESP32, modifier `navigation_decision_node.py` ou `robot_supervisor.py`, supprimer des fichiers `*.bak`/`*.before-*`, porter les interfaces personnel/médecin, ajouter des fonctionnalités non décrites ici.

---

# 15. QUESTIONS

## 15.1. Tranchées par l'auteur

Q1 (staff et médecin restent Web), Q2 (application mobile cible, Web gelé, paysage), Q3 (malgache en perspective), Q5 (Xiaomi Mi CC9 Pro, 6 Go), Q6 (confirmation obligatoire avant toute orientation). Voir 1.5.

## 15.2. Encore ouvertes

| # | Question | Par défaut si non tranchée |
|---|---|---|
| Q4 | Lancer le nœud `robot_status` (présent dans `setup.py`, absent du lancement) ? | Non |
| Q7 | Ordre des services à l'accueil : Orientation, Renseignements, Consultation (U4) ? | Oui |
| Q8 | Décision sur les fichiers parasites et `*.bak` (S3, S4) ? | Ne rien supprimer |
| Q9 | Le comportement **physique** de la mission automatique (C3) a-t-il été observé ? Sinon la V4 le traite comme non validé | Non validé |

---

# ANNEXE A. Exemple de registre généré (extrait)

```json
{
  "version": 1,
  "lang": "fr",
  "hash": "sha256:…",
  "generated_from": ["catalog.py", "voice_fr.yaml"],
  "actions": [
    { "id": "robot.stop", "scope": ["*"], "risk": "R3",
      "effect": { "type": "rest", "method": "POST", "path": "/api/navigation/cancel" },
      "touch": { "control": "stop_button" },
      "voice_fr": ["stop", "arrete", "arrete toi", "halte", "arret d urgence"],
      "requires_confirmation": false, "priority": "max" },

    { "id": "orientation.confirm", "scope": ["orientation.confirm"], "risk": "R2",
      "effect": { "type": "rest", "method": "POST", "path": "/api/request",
                  "body": { "category": "ORIENTATION", "item": "{destination}" } },
      "touch": { "control": "confirm_button" },
      "voice_fr": ["oui", "je confirme", "d accord", "c est bon", "confirmer"],
      "requires_confirmation": true, "confirm_prompt_fr": "Vous souhaitez aller à : {label}. Confirmez-vous ?",
      "timeout_ms": 10000 },

    { "id": "info.open", "scope": ["information.menu", "home"], "risk": "R0",
      "args": { "topic": ["HIV","MALARIA","DIABETES","HYPERTENSION","TUBERCULOSIS","MENSTRUAL_HEALTH"] },
      "effect": { "type": "screen", "to": "info.detail" },
      "voice_fr": { "HIV": ["vih","sida","virus du sida"], "MALARIA": ["paludisme","malaria"],
                    "DIABETES": ["diabete","sucre"], "HYPERTENSION": ["hypertension","tension"],
                    "TUBERCULOSIS": ["tuberculose","tb"], "MENSTRUAL_HEALTH": ["regles","menstruation","sante menstruelle"] } }
  ]
}
```

# ANNEXE B. Exemple de `ui/state` publié par un écran

```json
{ "topic": "ui/state", "retain": true, "qos": 1,
  "payload": { "screen": "orientation.menu", "epoch": 12, "mission_active": false,
    "actions": ["app.back","app.home","app.help","voice.read_screen","voice.repeat",
                "orientation.select","robot.stop"],
    "dynamic": { "orientation.select": { "destination": ["PHARMACY","LABORATORY","RECEPTION"] } },
    "sensitive_fields": [] } }
```

# ANNEXE C. Résumé de l'ensemble des topics

`voice/vad` · `voice/mic/control` · `voice/stt/{state,partial,final,error}` · `voice/tts/{request,control,state}` · `voice/intent/{resolved,unresolved,suggest}` · `ui/state` · `ui/action/{request,result}` · `ui/confirm/{request,answer}` · `robot/{hmi/status, mission/status, safety, supervisor/status, link}` · `vitals/{state,result}` · `sys/{config,health,error}`

# ANNEXE D. Ce qui est volontairement laissé ouvert

- Le comportement du nœud `robot_status` s'il est lancé : il publie aussi sur `/robot/status`, ce qui mélangerait deux sources (voir Q4). Le statut `BLOCKED` (toutes directions bloquées) doit recevoir un message vocal dédié lors du WP7 : « Je suis bloqué, je m'arrête. »
- Le choix final des modèles et paquets audio (WP1).
- La navigation avec localisation et la confirmation d'arrivée (hors périmètre du démonstrateur).

---

# CONCLUSION

La V4 de HIAR ajoute un second canal d'interaction, la voix, **sans créer de second chemin vers le robot**. Les trois idées directrices :

1. **Une action, un chemin** : tactile et vocal produisent la même demande, exécutée par le même dispatcher, avec les mêmes confirmations.
2. **Local d'abord, réseau ensuite** : la voix fonctionne hors ligne ; le WebSocket par topics relie l'application au Pi pour les états et les services, sans jamais donner au serveur ou à l'IA l'autorité sur le mouvement.
3. **Dire la vérité** : l'interface et la voix n'annoncent que ce que le robot a effectivement confirmé, et le « stop » vocal n'est jamais présenté comme un arrêt d'urgence.

La séparation de la V3 est conservée et étendue : **la voix transcrit, l'interpréteur propose, le dispatcher valide, la navigation décide, le Supervisor valide, l'ESP32 exécute.**
