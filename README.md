# Hospital Assistant Robot

## Projet de Master 2

Robot assistant autonome destiné à améliorer l'accueil et l'orientation des patients et visiteurs au sein d'un établissement hospitalier.

## Objectif

Le robot permet notamment de :

- accueillir et orienter les patients et visiteurs ;
- fournir des informations sur les différents services ;
- accompagner l'utilisateur vers une destination ;
- mesurer certains signes vitaux de base ;
- recueillir l'avis des utilisateurs ;
- interagir avec l'utilisateur via un écran tactile.

## Technologies prévues

- ROS 2 Humble
- Python
- Raspberry Pi
- ESP32
- Capteurs
- Écran tactile
- Navigation robotique
- Impression 3D

## Statut

🚧 Projet en cours de développement.

## Auteur

Cecilia RAZAKAHARISOA

## Checkpoint technique — Adaptation matérielle du firmware ESP32

### État au 04 novembre 2026

**Référence stable**
- `HIAR_ESP32_V08_stable.ino` : dernier firmware testé et vérifié.
- V0.8 est conservé sans modification.
- Son brochage et ses entrées IR numériques ne correspondent pas au nouveau câblage.

**Nouvelle version de développement**
- Fichier : `firmware/esp32/HIAR_ESP32_adaptation_materielle_dev/HIAR_ESP32_adaptation_materielle_dev.ino`
- Créé à partir d'une copie de V0.8.
- Aucun téléversement ni test physique de cette adaptation effectué à ce stade.

### Nouveau brochage matériel

| Fonction | GPIO ESP32 |
|---|---:|
| L298N ENA | 25 |
| L298N IN1 | 26 |
| L298N IN2 | 27 |
| L298N IN3 | 14 |
| L298N IN4 | 18 |
| L298N ENB | 19 |
| IR gauche analogique AO | 32 |
| IR droit analogique AO | 33 |
| HC-SR04 TRIG | 13 |
| HC-SR04 ECHO | 34 |
| DS18B20 DATA | 4 |
| MAX30102 SDA | 21 |
| MAX30102 SCL | 22 |

### Intégration ROS 2

Le nœud `esp32_interface` utilise :
- Liaison série à 115200 bauds.
- Commandes moteurs : `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`.
- Distance : `DIST,<cm>`.
- Infrarouges : `IR,LEFT,0/1` et `IR,RIGHT,0/1`.
- États IR attendus par la navigation : `1 = CLEAR`, `0 = OBSTACLE`.

Les capteurs IR analogiques devront être calibrés sur le matériel, puis convertis en états binaires compatibles avec ROS 2.

### Travaux restant à réaliser

- Adapter le firmware au nouveau brochage.
- Développer la lecture analogique et la calibration des deux IR.
- Vérifier la mesure ultrasonique et les sécurités moteurs.
- Intégrer les signes vitaux DS18B20 et MAX30102 dans le protocole série commun.
- Vérifier la compatibilité du protocole avec `esp32_interface`.
- Compiler avec Arduino IDE.
- Effectuer les essais matériels progressifs, puis l'intégration ROS 2.

### Points de vigilance

- Ne pas téléverser V0.8 avec le nouveau câblage.
- Vérifier la résistance pull-up du DS18B20 sur GPIO4.
- Conserver une protection contre les obstacles et une commande STOP prioritaire.
- Ne pas considérer la compilation ou les tests logiciels comme une preuve de fonctionnement physique.
- L'alimentation 12 V des moteurs reste déconnectée pendant la préparation.

**Statut :** adaptation matérielle en développement, dérivée de V0.8. La version officielle V0.9 reste à identifier.
