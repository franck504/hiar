# Décision technique — Fusion du firmware ESP32 HIAR

**Date :** 10 novembre 2026  
**Statut :** Autorisation accordée pour la création d'une nouvelle version fusionnée.

## 1. Objectif

Créer un firmware ESP32 intégré réunissant :
- Le firmware de navigation HIAR V0.8 : moteurs, HC-SR04, capteurs IR, mode autonome et sécurités.
- Le firmware de signes vitaux : DS18B20 et MAX30102.
- Le protocole série attendu par ROS2 : MEASURE, READY, STATE, RESULT et ERROR.

## 2. Préservation obligatoire

Les deux fichiers sources doivent rester strictement intacts :
- firmware/esp32/HIAR_ESP32_adaptation_materielle_dev/HIAR_ESP32_adaptation_materielle_dev.ino
- firmware/esp32/HIAR_VITALS_ESP32_test/HIAR_VITALS_ESP32_test.ino

La fusion sera réalisée dans un nouveau dossier et un nouveau fichier .ino.

## 3. Exigences techniques

- DS18B20 : GPIO23.
- MAX30102 : SDA GPIO21, SCL GPIO22.
- Acquisition non bloquante vis-à-vis de la boucle de sécurité moteur.
- STOP conserve toujours sa fonction d'arrêt des moteurs.
- L'annulation d'une mesure utilise une commande distincte.
- SpO2 reste non implémenté et renvoyé comme NA.
- Aucune suppression des sécurités de navigation.

## 4. Limite de l'autorisation

L'autorisation porte uniquement sur la création et les vérifications logicielles de la nouvelle version.

**Aucun flash sur l'ESP32 n'est autorisé sans accord explicite supplémentaire.**

## 5. État des preuves

- Analyse des deux firmwares : effectuée.
- Compatibilité des broches : vérifiée sur les fichiers examinés.
- Fusion : à réaliser.
- Compilation : à vérifier.
- Tests matériels : non effectués.
