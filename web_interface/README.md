# HIAR : Interface Web Administrative & Espace Personnel (/staff)

Interface Web d'administration et de supervision du robot HIAR.
Elle fournit un tableau de bord pour le personnel soignant (`/staff`) permettant de visualiser la file d'attente des rendez-vous et l'état des consultations.

> **Note :** L'interface tactile principale embarquée sur le robot est désormais l'application mobile Flutter Kiosk native (`hiar_mobile/`), connectée en WebSocket temps réel à ROS 2.

## Contenu

- `catalog.py` : catalogue des catégories, actions, destinations et fiches d'information (source unique).
- `requests_model.py` : modèle des demandes structurées.
- `app.py` : serveur Flask (page d'accueil, espace `/staff` et routes API `/api/appointments`).
- `templates/`, `static/` : vues d'accueil et tableau de bord soignant.
- `tests/` : tests unitaires pytest.

## Lancer

    cd web_interface
    python3 app.py

Prérequis : `sudo apt install -y python3-flask python3-pytest`.  
Ouvrir ensuite http://localhost:5000 sur le poste.

## Tests

    cd web_interface
    python3 -m pytest tests -v

## Demandes structurées

    {"category": "ORIENTATION", "destination": "PHARMACY"}
    {"category": "CONSULTATION", "action": "APPOINTMENT"}
    {"category": "INFORMATION", "topic": "HIV"}

Destinations du MVP : PHARMACY, LABORATORY, RECEPTION, RADIOLOGY.
