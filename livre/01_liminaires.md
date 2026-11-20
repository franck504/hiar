# ÉLÉMENTS LIMINAIRES DU MÉMOIRE DE FIN D'ÉTUDES

---

## PAGE DE GARDE OFFICIELLE

<div align="center">

**UNIVERSITÉ DE FIANARANTSOA**  
**ÉCOLE NATIONALE D'INFORMATIQUE**  
*(Arrêté ministériel de création n° 83-185 du 24 mai 1983)*  

---

### **MÉMOIRE DE FIN D'ÉTUDES**
Pour l'obtention du **Diplôme de Master Professionnel en Informatique**  
**Mention :** Intelligence Artificielle  
**Parcours :** Objets Connectés et Cybersécurité (OCC)  

---

### **THÈME :**

# **Conception et développement d'un robot assistant intelligent pour l'accueil et l'orientation en milieu hospitalier (HIAR)**

---

**Présenté le :** 25 novembre 2026  
**Par :** Mademoiselle **RAZAKAHARISOA Barovaosolo Cecilia**  

---

### **Membres du Jury :**

| Qualité | Titre, Nom et Prénoms | Affiliation / Établissement |
| :--- | :--- | :--- |
| **Président du Jury** | *À renseigner lors de la soutenance* | Université de Fianarantsoa |
| **Examinateur** | *À renseigner lors de la soutenance* | École Nationale d'Informatique |
| **Rapporteur Pédagogique** | **Pr MAHATODY Thomas**, Professeur Titulaire | Directeur de l'École Nationale d'Informatique (ENI) |
| **Rapporteur Professionnel** | **M. HERIMAMPIONONA Hasindrainy Florent** | Coordinateur de l'Orange Digital Center (ODC) Club Fianarantsoa |

---

**Structure d'accueil :** Orange Digital Center Madagascar (Club Fianarantsoa)  
**Année Universitaire :** 2025 – 2026  

</div>

---

## CURRICULUM VITAE DE L'AUTEURE

**RAZAKAHARISOA Barovaosolo Cecilia**  
- **Âge :** 25 ans  
- **Téléphone :** +261 32 45 913 35  
- **Courriel :** ceciliarazakaharisoa@gmail.com  
- **Adresse :** CU Jupiter, Porte 01, Campus d'Andrainjato, Fianarantsoa (301)  
- **Profil LinkedIn :** [linkedin.com/in/barovaosolo-cecilia-razakaharisoa-493b1340b](https://www.linkedin.com/in/barovaosolo-cecilia-razakaharisoa-493b1340b)  
- **Dépôt GitHub :** [github.com/Cecilia-R28](https://github.com/Cecilia-R28)  

### Formation académique
- **2025 – 2026 :** Master 2 en Intelligence Artificielle, parcours Objets Connectés et Cybersécurité (OCC) — École Nationale d'Informatique, Université de Fianarantsoa.
- **2024 – 2025 :** Master 1 en Intelligence Artificielle, parcours Objets Connectés et Cybersécurité (OCC) — École Nationale d'Informatique, Université de Fianarantsoa.
- **2020 – 2024 :** Licence Professionnelle en Électronique Appliquée et Informatique Industrielle (EAII) — Faculté des Sciences, Université de Fianarantsoa.
- **2017 – 2018 :** Baccalauréat de l'enseignement secondaire, Série D, mention Assez Bien — Lycée Jacques Rabemananjara, Toamasina I.

### Expérience professionnelle et stages
- **Août – Novembre 2025 :** Stagiaire en Systèmes Embarqués, Robotique et IoT — Orange Digital Center (ODC Club), Campus Universitaire d'Andrainjato, Fianarantsoa.
  - Conception matérielle, intégration de capteurs biométriques et télémétriques, programmation de firmwares temps réel (C/C++ sous ESP32).
  - Déploiement de middlewares robotiques distribués (ROS 2 Humble) sur monocarte Linux embarquée (Raspberry Pi 4).
  - Implémentation d'architectures réseau locales résilientes et sécurisation des protocoles d'échange.

### Projets et distinctions
- **2026 : HIAR (Hospital Intelligent Assistant Robot)** — Projet de recherche et de fin d'études Master 2 : robot d'accueil et d'orientation combinant ROS 2, ESP32, triple capteur ultrasonique HC-SR04, constantes vitales (DS18B20, MAX30102 avec SpO2), application mobile Flutter et intelligence artificielle hybride (Gemini 2.5 Flash en priorité, Qwen 0.5B local en fallback).
- **2025 : Système intelligent de détection de stress par analyse faciale** — Dispositif IoT connecté associant vision par ordinateur et analyse de paramètres physiologiques.
- **2022 : Application mobile « Ponctuel Accès »** — Solution de pointage automatique et contrôle d'accès sécurisé par RFID. Projet lauréat du programme SAFIDI (Soutien aux Femmes Innovantes et Digitales) de l'Agence Universitaire de la Francophonie (AUF), Antananarivo.

### Certifications techniques
- **Février 2022 :** Certification en Développement d'Applications Mobiles et Design UI/UX — Orange Digital Center, Antananarivo.

### Compétences techniques
- **Langages :** C, C++, Python, Dart, SQL, Bash.
- **Frameworks & Middleware :** ROS 2 (Humble Hawksbill), Flutter, Flask, asyncio, scikit-learn.
- **Matériel & Embarqué :** ESP32-WROOM-32, Raspberry Pi 4 Model B, L298N, HC-SR04, MAX30102, DS18B20, protocoles UART, I2C, 1-Wire, PWM.
- **Intelligence Artificielle :** Google Gemini Flash API, Ollama (Qwen 2.5), NLP/NLU, extraction d'intentions, RAG, représentations vectorielles TF-IDF.
- **Cybersécurité & Réseau :** Modélisation des menaces STRIDE, authentification par jetons sécurisés, comparaisons à temps constant HMAC, audits de flux réseau.
- **Outils & DevOps :** Git, GitHub, Linux Ubuntu 22.04 LTS, VS Code, PlatformIO / Arduino IDE, Figma.

---

## REMERCIEMENTS

Au terme de ce parcours académique menant à l'obtention du diplôme de Master Professionnel en Intelligence Artificielle, je tiens à exprimer ma profonde gratitude à l'ensemble des personnalités et des institutions dont le soutien, la confiance et les conseils ont rendu possible l'aboutissement de ce mémoire :

À **Monsieur le Professeur HAJALALAINA Aimé Richard**, Président de l'Université de Fianarantsoa, pour son dévouement constant en faveur de l'excellence académique, de l'essor de la recherche scientifique et de la modernisation des infrastructures technologiques mises à la disposition de la communauté universitaire.

À **Monsieur le Professeur MAHATODY Thomas**, Directeur de l'École Nationale d'Informatique (ENI) de Fianarantsoa et rapporteur pédagogique de ce mémoire. Sa vision novatrice pour l'école, sa rigueur scientifique sans compromis et ses orientations stratégiques ont guidé chacune des étapes de notre réflexion technique.

À **Monsieur RAHAJARIZAFY Rija**, Directeur de l'Orange Digital Center (ODC) Madagascar, pour avoir ouvert les portes de son institution à l'innovation étudiante et pour son engagement exceptionnel dans l'insertion professionnelle et la promotion des technologies de pointe auprès de la jeunesse malgache.

À **Monsieur DIMBISOA Germain William**, Maître de Conférences, Responsable de la mention Intelligence Artificielle à l'ENI, pour son écoute bienveillante, ses précieux enseignements théoriques et le suivi méthodique de notre cohorte.

À **Monsieur GILANTE Gesazafy**, Assistant d'Enseignement Supérieur et de Recherche, Responsable du parcours Objets Connectés et Cybersécurité (OCC), pour son encadrement pédagogique rigoureux et la pertinence de ses enseignements appliqués à l'ingénierie des systèmes communicants et à la sécurisation des architectures IoT.

À **Monsieur HERIMAMPIONONA Hasindrainy Florent**, Coordinateur de l'Orange Digital Center Club de Fianarantsoa et rapporteur professionnel de ce mémoire. Son expertise pratique de haut niveau dans le domaine des systèmes embarqués, sa disponibilité permanente et ses conseils méthodologiques ont été des atouts déterminants pour la réalisation physique et logicielle de ce robot.

À l'ensemble des **enseignants-chercheurs et du personnel administratif de l'École Nationale d'Informatique**, qui ont su nous inculquer le goût de la persévérance, de l'éthique professionnelle et de la recherche appliquée.

À tous les **membres du Jury**, qui ont accepté d'examiner et d'évaluer ce travail de fin d'études avec un regard critique et constructif.

Enfin, à **ma famille et à mes proches**, dont les prières, la patience infinie et les encouragements indéfectibles ont constitué mon plus solide rempart face aux défis techniques et aux nuits de veille. Que chacun d'entre vous trouve ici le témoignage sincère de mon profond respect et de ma reconnaissance éternelle.

---

## LISTE DES FIGURES

- **Figure 1** : Organigramme institutionnel de l'École Nationale d'Informatique (ENI)
- **Figure 2** : Architecture des études universitaires selon le système LMD à l'ENI
- **Figure 3** : Parcours global de l'usager et services proposés par le système HIAR
- **Figure 4** : Chronogramme de travail du projet, de juillet à novembre 2026
- **Figure 5** : Carte de développement microcontrôleur ESP32-WROOM-32
- **Figure 6** : Module télémétrique ultrasonique HC-SR04 et chronogramme de temps de vol
- **Figure 7** : Disposition géométrique du système de perception à 3 capteurs ultrasoniques HC-SR04 (Avant, Gauche, Droite)
- **Figure 8** : Chaîne d'acquisition et de traitement des grandeurs physiologiques (DS18B20 et MAX30102)
- **Figure 9** : Module de puissance de commande des moteurs à double pont en H L298N
- **Figure 10** : Motoréducteurs à courant continu (moteurs DC) et cinématique différentielle
- **Figure 11** : Architecture matérielle globale et schéma d'interconnexion physique des composants de HIAR
- **Figure 12** : Architecture globale en couches du système HIAR selon le modèle de référence IoT (UIT-T Y.4000 / ISO/IEC 30141)
- **Figure 13** : Diagramme de cas d'utilisation global du système HIAR (UML)
- **Figure 14** : Graphe des nœuds et des topics de communication ROS 2 Humble
- **Figure 15** : Diagramme de classes des composants de la chaîne robotique et middleware
- **Figure 16** : Diagramme de séquence du scénario d'orientation et de guidage vers un service hospitalier
- **Figure 17** : Machine à états finis (FSM) de la navigation réactive autonome
- **Figure 18** : Diagramme de séquence de la détection et du contournement d'obstacle par le triplet HC-SR04
- **Figure 19** : Modèle Physique des Données (MPD) de la base relationnelle SQLite locale
- **Figure 20** : Machine à états du cycle de vie d'un ticket de consultation hospitalière
- **Figure 21** : Diagramme de séquence de la prise de rendez-vous et de l'acquisition des signes vitaux
- **Figure 22** : Diagramme de déploiement physique et logiciel du système distribué HIAR
- **Figure 23** : Modèle de défense en profondeur : couches de sécurité du réseau à l'actionnement
- **Figure 24** : Architecture du moteur d'intelligence artificielle hybride à double niveau (Gemini Cloud + Qwen Edge Fallback)
- **Figure 25** : Diagramme de séquence du traitement d'une intention vocale et du basculement en mode hors-ligne
- **Figure 26** : Photographie du prototype physique HIAR en situation réelle (châssis, mât, écran, capteurs)
- **Figure 27** : Écrans de l'interface mobile Flutter « Neo Clinic » (Accueil, Consultation, Signes vitaux, Orientation)
- **Figure 28** : Capture de l'interface Web d'administration et de gestion des consultations pour le personnel soignant et les médecins
- **Figure 29** : Journal des trames de télémétrie série échangées entre l'ESP32 et ROS 2
- **Figure 30** : Démonstration du mécanisme d'arrêt d'urgence matériel et logiciel sur détection d'obstacle
- **Figure 31** : Console d'exécution de la suite de 168 tests unitaires automatisés sous pytest

---

## LISTE DES TABLEAUX

- **Tableau 1** : Responsables et équipe de direction pédagogique de l'ENI
- **Tableau 2** : Mentions et parcours d'enseignement habilités à l'ENI
- **Tableau 3** : Organisation du système de formation théorique et pratique à l'ENI
- **Tableau 4** : Conditions d'accès et diplômes délivrés selon le système LMD
- **Tableau 5** : Débouchés professionnels représentatifs par mention de l'ENI
- **Tableau 6** : Fiche d'identification institutionnelle d'Orange Madagascar
- **Tableau 7** : Hypothèses de recherche et objectifs techniques associés du projet
- **Tableau 8** : Classification des objectifs du projet HIAR par niveau de priorité
- **Tableau 9** : Inventaire du matériel nécessaire au prototypage du robot
- **Tableau 10** : Matrice des objectifs du projet et preuves de validation attendues
- **Tableau 11** : Acteurs humains et processus d'accueil actuels en milieu hospitalier
- **Tableau 12** : Inventaire des briques matérielles et logicielles au lancement du projet
- **Tableau 13** : Analyse comparative des solutions courantes d'orientation hospitalière
- **Tableau 14** : Matrice d'analyse des alternatives technologiques et choix d'ingénierie
- **Tableau 15** : Synthèse des outils logiciels retenus et justifications techniques
- **Tableau 16** : Caractéristiques techniques et allocation des ressources de l'ESP32-WROOM-32
- **Tableau 17** : Spécifications techniques du module télémétrique ultrasonique HC-SR04
- **Tableau 18** : Analyse comparative : Barrière infrarouge LM393 versus Triplet HC-SR04
- **Tableau 19** : Correspondance entre grandeurs physiologiques, capteurs biométriques et plages indicatives
- **Tableau 20** : Caractéristiques électriques et gestion thermique du pont en H L298N
- **Tableau 21** : Synthèse complète des composants de perception et d'actionnement du robot
- **Tableau 22** : Caractéristiques de la communication réseau sans fil (Wi-Fi et WebSocket)
- **Tableau 23** : Spécifications de la liaison série bidirectionnelle UART (Raspberry Pi – ESP32)
- **Tableau 24** : Protocoles matériels et caractéristiques d'échantillonnage des capteurs
- **Tableau 25** : Matrice d'évaluation des risques de communication et contre-mesures
- **Tableau 26** : Structure fonctionnelle de l'interface applicative multi-écrans
- **Tableau 27** : Répartition des responsabilités logicielles entre les nœuds ROS 2
- **Tableau 28** : Flux d'entrées, traitements et sorties des services métiers de HIAR
- **Tableau 29** : Comparaison formelle des modèles de référence IoT (UIT-T Y.4000 vs ISO/IEC 30141:2024)
- **Tableau 30** : Cartographie d'alignement de l'architecture HIAR avec les normes IoT
- **Tableau 31** : Limites techniques intrinsèques du prototype et mesures d'atténuation
- **Tableau 32** : Grille d'arbitrage technologique détaillée par domaine d'ingénierie
- **Tableau 33** : Affectation exhaustive des broches GPIO de l'ESP32
- **Tableau 34** : Dictionnaire des topics ROS 2 (types de messages, nœuds émetteurs et récepteurs)
- **Tableau 35** : Règles métier du service de consultation et d'attribution des tickets
- **Tableau 36** : Couches intégrées du système HIAR et principes de contrôle
- **Tableau 37** : Niveaux de preuve et critères formels de qualification
- **Tableau 38** : Protocole d'essais unitaires des modules matériels et résultats obtenus
- **Tableau 39** : Matrice des essais de validation des mécanismes de sécurité
- **Tableau 40** : Indicateurs de performance clés (KPI) : valeurs cibles et mesures réelles
- **Tableau 41** : Modèle de menaces de sécurité STRIDE appliqué à l'architecture HIAR
- **Tableau 42** : Relevés expérimentaux de répétabilité des mesures physiologiques (T°, BPM, SpO2)
- **Tableau 43** : Évaluation comparative du moteur IA (Gemini 2.5 Flash vs Qwen 2.5 0.5B local)
- **Tableau 44** : Bilan synthétique de la couverture des 168 tests automatisés sous pytest
- **Tableau 45** : Matrice de conformité finale : objectifs initiaux versus résultats atteints
- **Tableau 46** : Glossaire technique normalisé
- **Tableau 47** : Tableau récapitulatif du brochage matériel de l'ESP32 (Annexe 1)
- **Tableau 48** : Dictionnaire de données relationnel de la base SQLite (Annexe 2)

---

## LISTE DES ABRÉVIATIONS

| Abréviation | Signification complète |
| :--- | :--- |
| **ADC** | *Analog-to-Digital Converter* (Convertisseur Analogique-Numérique) |
| **API** | *Application Programming Interface* (Interface de Programmation d'Application) |
| **BPM** | *Beats Per Minute* (Battements Par Minute) |
| **CMIL** | Commission Malagasy de l'Informatique et des Libertés |
| **DDS** | *Data Distribution Service* (Service de Distribution de Données) |
| **ENI** | École Nationale d'Informatique de Fianarantsoa |
| **ERD** | *Entity-Relationship Diagram* (Diagramme Entité-Association) |
| **FIFO** | *First In, First Out* (Premier Entré, Premier Sorti) |
| **FSM** | *Finite State Machine* (Machine à États Finis) |
| **GPIO** | *General-Purpose Input/Output* (Entrée-Sortie à Usage Général) |
| **HIAR** | *Hospital Intelligent Assistant Robot* |
| **HMI** | *Human-Machine Interface* (Interface Homme-Machine / IHM) |
| **HTTP** | *HyperText Transfer Protocol* |
| **I2C** | *Inter-Integrated Circuit* (Bus de communication série à deux fils) |
| **IA** | Intelligence Artificielle |
| **IMU** | *Inertial Measurement Unit* (Centrale Inertielle) |
| **IoT** | *Internet of Things* (Internet des Objets) |
| **IR** | Infrarouge |
| **ISO** | *International Organization for Standardization* |
| **ITU-T** | *International Telecommunication Union - Telecommunication Standardization Sector* |
| **JSON** | *JavaScript Object Notation* |
| **LiDAR** | *Light Detection and Ranging* (Télédétection par Laser) |
| **LLM** | *Large Language Model* (Grand Modèle de Langage) |
| **LMD** | Système universitaire Licence-Master-Doctorat |
| **MPD** | Modèle Physique des Données |
| **NLP** | *Natural Language Processing* (Traitement Automatique du Langage Naturel) |
| **NLU** | *Natural Language Understanding* (Compréhension du Langage Naturel) |
| **ODC** | Orange Digital Center |
| **OMS** | Organisation Mondiale de la Santé |
| **OSI** | *Open Systems Interconnection* (Modèle d'Interconnexion des Systèmes Ouverts) |
| **PPG** | Photopléthysmographie |
| **PWM** | *Pulse-Width Modulation* (Modulation de Largeur d'Impulsion) |
| **RAG** | *Retrieval-Augmented Generation* (Génération Augmentée par Récupération) |
| **ROS 2** | *Robot Operating System 2* (Système d'Exploitation pour Robots v2) |
| **RTPS** | *Real-Time Publish-Subscribe* (Protocole de Publication-Abonnement Temps Réel) |
| **SLAM** | *Simultaneous Localization and Mapping* (Cartographie et Localisation Simultanées) |
| **SpO2** | Saturation Pulsée en Oxygène (taux d'hémoglobine oxygénée dans le sang artériel) |
| **SQL** | *Structured Query Language* |
| **STT** | *Speech-to-Text* (Reconnaissance Vocale Automatique) |
| **STRIDE** | Méthodologie d'analyse de menaces (*Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation*) |
| **TF-IDF** | *Term Frequency - Inverse Document Frequency* |
| **TTS** | *Text-to-Speech* (Synthèse Vocale) |
| **UART** | *Universal Asynchronous Receiver-Transmitter* (Liaison Série Asynchrone) |
| **UI / UX** | *User Interface / User Experience* (Interface et Expérience Utilisateur) |
| **UML** | *Unified Modeling Language* (Langage de Modélisation Unifié) |
| **USB** | *Universal Serial Bus* |
| **WPA2** | *Wi-Fi Protected Access 2* |
| **WSL2** | *Windows Subsystem for Linux 2* |

---

## RÉSUMÉ

Ce mémoire de fin d'études présente **HIAR** (*Hospital Intelligent Assistant Robot*), un prototype de robot assistant autonome et communicant à faible coût, conçu pour optimiser l'accueil, l'information sanitaire et l'orientation des usagers dans les structures hospitalières de pays émergents tels que Madagascar.

Face à la surcharge structurelle des services d'admission et à la complexité des parcours de soins, le système propose une architecture Cyber-Physique distribuée en quatre couches conforme aux normes IoT (**UIT-T Y.4000/Y.2060** et **ISO/IEC 30141:2024**). Il associe une unité centrale de calcul embarquée (**Raspberry Pi 4** sous Ubuntu 22.04 LTS et **ROS 2 Humble**) et un microcontrôleur temps réel (**ESP32-WROOM-32**) reliés par liaison série UART à haute disponibilité. 

La couche perception repose sur une ceinture de **trois capteurs télémétriques ultrasoniques HC-SR04** (Avant, Gauche, Droite) multiplexés séquentiellement à 35 ms et filtrés numériquement par médiane, assurant une navigation réactive et un évitement d'obstacles déterministe encadré par une machine à états finis (FSM) et un superviseur à boucle de sécurité (watchdog à 10 Hz). La biométrie intègre une sonde thermique 1-Wire (**DS18B20**) et un capteur optique I2C (**MAX30102**) mesurant à la fois le rythme cardiaque (BPM) et la saturation pulsée en oxygène (**$\text{SpO}_2$**) par photopléthysmographie bi-longueur d'onde avec calcul du ratio pulsatile $R$.

L'interaction utilisateur combine une application mobile native **Flutter** (« Neo Clinic ») interconnectée en temps réel via WebSockets, une interface Web médicale Flask/SQLite, et un moteur d'intelligence artificielle hybride à double niveau : le modèle de pointe **Google Gemini 2.5 Flash** en priorité pour le raisonnement contextuel enrichi de la cartographie hospitalière, et le modèle local souverain **Qwen 2.5 0.5B** (exécuté sur Edge via Ollama) en basculement automatique (*fallback*) lors des pertes de connectivité Internet. Enfin, le système implémente une politique stricte de confidentialité médicale conforme à la loi malgache n° 2014-038 (CMIL), interdisant toute restitution vocale publique des constantes de santé. L'ensemble de la chaîne logicielle est validé par une campagne de **168 tests unitaires automatisés sous pytest** avec un taux de succès de 100 %.

**Mots-clés :** Robot hospitalier, Internet des Objets (IoT), ROS 2 Humble, ESP32, Navigation réactive, Photopléthysmographie ($\text{SpO}_2$), Intelligence Artificielle Hybride, Google Gemini, Qwen local, Flutter, Cybersécurité, Confidentialité des données de santé.

---

## ABSTRACT

This Master's thesis presents **HIAR** (*Hospital Intelligent Assistant Robot*), an innovative, low-cost autonomous healthcare assistant robot designed to enhance patient reception, health information delivery, and guidance within hospital environments, particularly adapted to the socio-economic context of developing countries such as Madagascar.

To alleviate admission bottlenecks and simplify patient flows, the system implements a distributed four-layer Cyber-Physical IoT architecture compliant with **ITU-T Y.4000/Y.2060** and **ISO/IEC 30141:2024** international reference models. The computing framework bridges an embedded onboard single-board computer (**Raspberry Pi 4** running Ubuntu 22.04 LTS and **ROS 2 Humble**) with a real-time microcontroller (**ESP32-WROOM-32**) via a high-availability UART serial link.

The perception layer features a sequential array of **three HC-SR04 ultrasonic rangefinders** (Front, Left, Right) time-multiplexed at 35 ms intervals with 3-point median filtering, providing reliable obstacle avoidance through a deterministic Finite State Machine (FSM) and an independent safety watchdog running at 10 Hz. Physiological screening integrates a 1-Wire digital thermometer (**DS18B20**) and an I2C optical pulse oximeter (**MAX30102**) acquiring real-time Heart Rate (BPM) and blood oxygen saturation (**$\text{SpO}_2$**) using dual-wavelength photoplethysmography based on the pulsatile AC/DC ratio $R$.

Human-Robot Interaction is delivered through a modern native **Flutter** mobile interface ("Neo Clinic") communicating via real-time WebSockets, alongside a Flask/SQLite medical staff portal. The natural language comprehension subsystem features an advanced **dual-engine hybrid AI architecture**: cloud-based **Google Gemini 2.5 Flash** operates as the primary semantic reasoning engine informed by internal hospital maps, while an on-device edge model, **Qwen 2.5 0.5B** (served locally via Ollama), serves as an automatic offline fallback ensuring operational sovereignty and data privacy. In full compliance with Malagasy personal data protection Law No. 2014-038 (CMIL), a strict medical confidentiality policy is enforced by preventing Text-to-Speech vocalization of patient vital signs. The robotic and software middleware is verified through a rigorous test suite of **168 automated pytest unit tests** achieving a 100% pass rate.

**Keywords:** Healthcare Robotics, Internet of Things (IoT), ROS 2 Humble, ESP32, Reactive Obstacle Avoidance, Pulse Oximetry ($\text{SpO}_2$), Hybrid Artificial Intelligence, Google Gemini, Edge LLM Qwen, Flutter, Medical Data Privacy, Cybersecurity.

---

## INTRODUCTION GÉNÉRALE

Dans la plupart des centres hospitaliers universitaires et des formations sanitaires publiques de Madagascar et des pays du Sud, l'accueil, le triage initial et l'orientation des patients constituent un goulot d'étranglement critique. Dès leur arrivée au sein des locaux, les usagers — souvent fragilisés par la maladie, analphabètes ou désorientés par la complexité spatiale des bâtiments — se heurtent à une signalétique statique insuffisante et à un personnel soignant et administratif en sous-effectif, accaparé par les urgences cliniques. Ce déficit d'orientation engendre des retards dans la prise en charge médicale, une anxiété accrue chez les patients et des congestions évitables dans les couloirs et salles d'attente.

Parallèlement, la révolution conjointe de la robotique de service, de l'Internet des Objets (IoT) et de l'Intelligence Artificielle générative offre des perspectives de rupture pour décharger les personnels soignants des tâches répétitives d'accueil, de recueil préliminaire des constantes vitales et de guidage spatial. Toutefois, les robots d'assistance médicale industriels développés dans les pays industrialisés (tels que Pepper, TUG ou Relay) reposent sur des capteurs LiDAR haut de gamme, des architectures informatiques surdimensionnées et des budgets prohibitifs (dépassant fréquemment plusieurs dizaines de milliers d'euros), ce qui les rend totalement inaccessibles pour les structures de santé des pays en développement.

C'est dans ce contexte de recherche appliquée qu'est né le projet **HIAR** (*Hospital Intelligent Assistant Robot*), mené dans le cadre du diplôme de Master Professionnel en Intelligence Artificielle (parcours Objets Connectés et Cybersécurité) à l'École Nationale d'Informatique (ENI) de l'Université de Fianarantsoa, en collaboration avec l'**Orange Digital Center (ODC)** de Madagascar.

### Objectif et défi d'ingénierie
L'objectif fondamental de cette étude est de **concevoir, prototyper et évaluer un robot d'assistance hospitalière intelligent, sûr, éthique et à très faible coût**, capable de :
1. **Accueillir et interagir naturellement** avec les usagers au moyen d'une interface mobile tactile moderne (développée en Flutter) et d'un système de dialogue vocal intelligent bilingue/multimodal ;
2. **Guider de manière autonome** les patients vers trois services prioritaires (Accueil, Pharmacie, Laboratoire) dans un environnement intérieur délimité, à l'aide d'une navigation réactive fluide et sécurisée ;
3. **Acquérir de manière non invasive des paramètres physiologiques indicatifs** (température cutanée, fréquence cardiaque et saturation en oxygène $\text{SpO}_2$) afin de faciliter le pré-enregistrement des consultations sans jamais substituer la machine au jugement clinique du médecin ;
4. **Garantir une résilience absolue et la souveraineté des données** grâce à un moteur IA hybride innovant capable de basculer instantanément d'un modèle de pointe en ligne (**Google Gemini 2.5 Flash**) vers un modèle de langage local compact (**Qwen 2.5 0.5B** sur Edge via Ollama) en cas d'interruption du réseau Wi-Fi ou Internet ;
5. **Assurer une sécurité physique et cybernétique déterministe**, régie par l'adage architectural : *« L'IA comprend et suggère, la navigation décide, le superviseur valide, l'ESP32 exécute »*.

### Structure du document
Le présent mémoire est articulé en trois grandes parties méthodiques :
- **La Partie I (Présentations)** introduit le cadre institutionnel de l'ENI et d'Orange Digital Center, définit la formulation du projet, ses objectifs prioritaires (O1 à O12), les hypothèses de recherche (H1 à H3) et le chronogramme des travaux.
- **La Partie II (Analyse et Conception)** formalise l'analyse de l'existant, établit l'architecture Cyber-Physique IoT en quatre couches conformes aux standards internationaux, modélise les composants mécaniques, électroniques et logiciels (ROS 2 Humble), formalise le double moteur d'IA et détaille la politique de cybersécurité et de déontologie médicale.
- **La Partie III (Réalisation et Évaluation)** documente la concrétisation expérimentale du prototype, analyse les résultats obtenus lors des campagnes de tests (dont 168 tests unitaires automatisés validés), discute objectivement les limitations techniques rencontrées et ouvre des perspectives technologiques d'envergure pour l'avenir de la télémédecine et de la robotique de service à Madagascar.
