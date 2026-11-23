# Spécification Officielle du Protocole WebSocket HIAR
**Architecture Client Mobile (HMI) ↔ Serveur Central de Contrôle (Raspberry Pi 4 / ROS 2)**

---

## 1. Principes et Architecture

L'application mobile HIAR est un **périphérique d'interface utilisateur et de voix pur** (I/O périphérique).
* **Entrées :** Le smartphone capte la voix de l'utilisateur en continu via son microphone (STT) et les interactions tactiles sur l'écran, puis les transmet brutes au serveur central via WebSocket.
* **Sorties :** Le serveur central analyse la parole, gère la navigation ROS 2 et commande le smartphone : changement d'écrans, affichage dynamique de données (signes vitaux, télémétrie) et synthèse vocale (TTS).

```
┌────────────────────────────────────────────────────────┐
│                   SMARTPHONE (HMI)                     │
│  - Écoute continue (Microphone / STT)                  │
│  - Écran tactile Paysage (Scène UI + Rail Vocal)       │
│  - Synthèse vocale (Haut-parleur / TTS)                │
└──────────────────────────┬─────────────────────────────┘
                           │
                 WebSocket │ Duplex Intégral
          ws://<IP_SERVEUR>:5000/ws
                           │
┌──────────────────────────▼─────────────────────────────┐
│          SERVEUR CENTRAL (Raspberry Pi 4 / ROS 2)      │
│  - NLU & Classification d'intention vocale             │
│  - Lecture des capteurs physiques (DS18B20, MAX30102)   │
│  - Gestionnaire de mission & Navigation autonome        │
│  - Génération des instructions UI & TTS                │
└────────────────────────────────────────────────────────┘
```

---

## 2. Paramétrage Réseau du Serveur

Pour que l'application mobile se connecte au serveur, le serveur central doit démarrer un serveur WebSocket répondant aux spécifications suivantes :

* **Port d'écoute :** `5000` (par défaut).
* **Chemin URI :** `ws://0.0.0.0:5000/ws` ou `ws://0.0.0.0:5000/`
* **Sous-réseaux supportés :**
  * **Point d'accès Wi-Fi autonome du Raspberry Pi 4 :** `10.42.0.1:5000` *(recommandé sur le robot en milieu hospitalier)*
  * **Réseau Wi-Fi local :** ex: `192.168.0.x:5000`
  * **Câble USB (Développement ADB reverse) :** `127.0.0.1:5000`

---

## 3. Format d'Enveloppe Universel (Envelope Protocol v4)

Tous les paquets échangés sur la liaison WebSocket utilisent un format d'enveloppe JSON uniforme :

```json
{
  "v": 1,
  "type": "pub",
  "ts": 1731628800,
  "topic": "<nom_du_topic>",
  "payload": { ... },
  "qos": 1
}
```

### Types d'enveloppes (`type`)
* `"hello"` : Envoyé par le smartphone lors de la connexion initiale.
* `"welcome"` : Réponse envoyée par le serveur pour valider la connexion.
* `"sub"` : Souscription à un topic (effectuée automatiquement par le smartphone).
* `"pub"` (ou `"publish"`) : Message de publication de données ou d'instruction.
* `"ping"` : Heartbeat émis par le smartphone toutes les 10 secondes.
* `"pong"` : Réponse immédiate envoyée par le serveur pour maintenir le canal actif.

---

## 4. Flux Smartphone ➔ Serveur (Données émises par le smartphone)

### 4.1. `voice/stt/final` — Parole entendue par le microphone
Dès que l'utilisateur prononce une phrase, le smartphone la transcrit et l'émet immédiatement.

```json
{
  "v": 1,
  "type": "pub",
  "topic": "voice/stt/final",
  "ts": 1731628800,
  "payload": {
    "text": "Bonjour, je cherche le laboratoire d'analyses",
    "confidence": 0.95
  }
}
```

### 4.2. `ui/action/request` — Action tactile sur l'écran
Émis lorsque l'utilisateur touche un bouton ou valide un formulaire sur l'écran.

```json
{
  "v": 1,
  "type": "pub",
  "topic": "ui/action/request",
  "ts": 1731628800,
  "payload": {
    "action_id": "orientation.select",
    "args": {
      "destination": "PHARMACY",
      "origin": "touch"
    }
  }
}
```

### 4.3. `ui/state` — Écran actuellement actif sur le smartphone
Émis par le smartphone à chaque transition d'écran pour synchroniser l'état du serveur.

```json
{
  "v": 1,
  "type": "pub",
  "topic": "ui/state",
  "ts": 1731628800,
  "payload": {
    "screen": "mission",
    "actions": ["robot.stop", "mission.dismiss"]
  }
}
```

---

## 5. Flux Serveur ➔ Smartphone (Commandes du serveur central)

### 5.1. `server/instruction` — Le Topic Maître Unifié

C'est **le topic principal**. Il permet au serveur de piloter simultanément la voix, l'interface graphique et les capteurs.

#### Schéma complet du payload :
```json
{
  "origin": "voice",
  "text_to_speak": "D'accord, je vous accompagne à la pharmacie. Suivez-moi.",
  "speech_priority": "normal",
  "instruction_ui": {
    "screen": "mission",
    "destination": "Pharmacie",
    "require_confirmation": false,
    "step": 4,
    "topic": "MALARIA",
    "action": "navigate"
  },
  "value_to_show": {
    "field_id": "temperature",
    "value": 36.8,
    "unit": "°C",
    "label": "Température corporelle",
    "status": "normal"
  },
  "fields": {
    "distance": "15 m",
    "eta": "20 s",
    "heart_rate": 72,
    "spo2": 98
  },
  "voice_hints": ["Stop", "Terminer"],
  "robot_status": {
    "face_expression": "speaking",
    "status_label": "En route vers la Pharmacie"
  }
}
```

> **Note :** Tous les champs sont facultatifs. N'envoyez que les blocs nécessaires à votre action.

---

## 6. Répertoire des Cas d'Usage et Payloads Types

### 6.1. Faire parler le robot uniquement (TTS sans changer l'écran)
```json
{
  "origin": "server",
  "text_to_speak": "Bonjour ! Je suis le robot hospitalier HIAR. Que puis-je faire pour vous ?"
}
```

### 6.2. Guidage vers une destination (Mission d'accompagnement)
> **Règle vitale :** `require_confirmation: false` ou `origin: "voice"` désactive toute pop-up de confirmation. L'écran bascule immédiatement sur la mission.

```json
{
  "origin": "voice",
  "text_to_speak": "Très bien, suivez-moi vers la Pharmacie.",
  "instruction_ui": {
    "screen": "mission",
    "destination": "Pharmacie",
    "require_confirmation": false
  },
  "fields": {
    "destination": "Pharmacie",
    "distance": "15 m",
    "eta": "20 s"
  },
  "voice_hints": ["Stop", "Terminer"],
  "robot_status": {
    "face_expression": "speaking",
    "status_label": "Guidage vers la Pharmacie"
  }
}
```

### 6.3. Rafraîchissement télémétrique en cours de déplacement (ROS 2 Navigation)
Mise à jour en continu de la distance restante et de l'ETA :
```json
{
  "fields": {
    "distance": "8 m",
    "eta": "10 s"
  }
}
```

### 6.4. Mesure dynamique des signes vitaux (Capteurs matériels)
Le serveur lit les capteurs du robot et pousse les valeurs en temps réel.

#### A. Ouverture de l'étape de mesure + consigne vocale :
```json
{
  "origin": "server",
  "text_to_speak": "Veuillez poser votre doigt sur le capteur et rester immobile.",
  "instruction_ui": {
    "screen": "consultation",
    "step": 4
  },
  "value_to_show": {
    "field_id": "vitals_state",
    "value": "measuring"
  }
}
```

#### B. Mise à jour silencieuse des jauges (text_to_speak est null) :
*Pendant la mesure, le robot met à jour l'affichage en direct sans parler.*

* **Température (DS18B20) :**
  ```json
  {
    "text_to_speak": null,
    "value_to_show": {
      "field_id": "temperature",
      "value": 36.8,
      "unit": "°C"
    }
  }
  ```
* **Fréquence cardiaque & Oxygénation (MAX30102) :**
  ```json
  {
    "text_to_speak": null,
    "fields": {
      "heart_rate": 72,
      "spo2": 98
    }
  }
  ```

#### C. Annonce vocale du bilan final :
```json
{
  "origin": "server",
  "text_to_speak": "Mesure terminée. Température 36 degrés 8, rythme cardiaque 72 battements par minute, constantes normales.",
  "value_to_show": {
    "field_id": "vitals_state",
    "value": "done"
  }
}
```

### 6.5. Validation et émission de Ticket de passage
```json
{
  "origin": "voice",
  "text_to_speak": "Votre rendez-vous est validé. Voici votre ticket numéro A-MAT-3.",
  "instruction_ui": {
    "screen": "consultation",
    "step": 6
  },
  "value_to_show": {
    "field_id": "ticket_label",
    "value": "A-MAT-3"
  }
}
```

### 6.6. Affichage d'une fiche de renseignement de santé publique (OMS)
Affiche directement le texte officiel OMS de la thématique demandée :
* Thèmes disponibles : `"MALARIA"`, `"HIV"`, `"DIABETES"`, `"HYPERTENSION"`, `"TUBERCULOSIS"`, `"MENSTRUAL_HEALTH"`.

```json
{
  "origin": "voice",
  "text_to_speak": "Voici les informations de prévention de l'OMS concernant le paludisme.",
  "instruction_ui": {
    "screen": "information",
    "topic": "MALARIA"
  }
}
```

### 6.7. Arrêt d'Urgence Sécurisé
Interrompt immédiatement la parole en cours et fige l'écran en alerte rouge d'arrêt :
```json
{
  "origin": "voice",
  "text_to_speak": "Arrêt d'urgence du robot.",
  "speech_priority": "interrupt",
  "instruction_ui": {
    "screen": "mission",
    "action": "stop",
    "require_confirmation": false
  },
  "value_to_show": {
    "field_id": "mission_state",
    "value": "STOPPED"
  },
  "robot_status": {
    "face_expression": "emergency",
    "status_label": "ROBOT ARRÊTÉ"
  }
}
```

### 6.8. Mise en veille et retour à l'accueil
* **Mise en veille (Splash screen initial) :**
  ```json
  {"instruction_ui": {"screen": "splash"}}
  ```
* **Retour à l'accueil :**
  ```json
  {
    "text_to_speak": "Retour à l'accueil.",
    "instruction_ui": {"screen": "home"}
  }
  ```

---

### 6.9. Consultation vocale guidée (formulaire synchronisé)

Le serveur conduit la prise de rendez-vous et garde la mémoire du formulaire ; le mobile l'applique et la lui renvoie.

* **Serveur ➔ mobile** : `fields` porte les valeurs dictées, appliquées **une seule fois** par l'écran puis retirées
  (sinon une valeur périmée écraserait un choix tactile ultérieur) :
  `selected_reason` (`consultation_generale` | `suivi_medical` | `autre_motif`), `selected_doctor` (`A`–`D`),
  `selected_period` (`MAT` | `AM`), `patient_name`, `patient_phone` (chaîne vide = effacer le champ).
  `instruction_ui.step` fait changer d'étape ; sans `step` ni `action`, l'écran ne bouge pas (simple invite vocale).
* **Mobile ➔ serveur** : `consult.step_changed` transporte `args.fields` (formulaire complet) ; une saisie tactile
  envoie `ui/state` avec `consultation_data` après 350 ms de calme. Les valeurs vides sont ignorées par le serveur.
  Si le mobile refuse un saut d'étape (donnée manquante), il renvoie `consult.step_changed` avec son étape réelle.
* **Doubles annonces évitées** : une étape annoncée par le serveur n'est pas ré-annoncée quand le mobile la confirme
  (fenêtre de 6 s).
* **Codes médecin** : `A`=Raissa, `B`=Bell, `C`=Pierrot, `D`=Alice (matin : A, C ; après-midi : B, D). Les tickets
  gardent le code (`B-AM-3`).
* **Confidentialité** : `ui/state` hors consultation efface le dossier côté serveur ; le mobile efface aussi nom,
  téléphone et constantes en quittant l'écran de consultation.

---

## 7. Référentiel des Identifiants de Champs (`field_id`)

| `field_id` | Type attendu | Unité automatique | Rôle sur l'interface |
| :--- | :--- | :--- | :--- |
| `temperature` | `double` / `String` | `°C` | Jauge de température corporelle |
| `heart_rate` | `int` / `String` | `BPM` | Jauge de fréquence cardiaque |
| `spo2` | `int` / `String` | `%` | Jauge de saturation en oxygène |
| `vitals_state` | `"measuring"` / `"done"` | — | Animation du capteur en cours ou validé |
| `destination` | `String` | — | Nom du lieu de destination affiché |
| `distance` | `String` | `m` | Distance restante sur l'écran mission |
| `eta` | `String` | `s` / `min` | Temps estimé d'arrivée |
| `ticket_label` | `String` | — | Numéro du ticket grand format (ex: A-MAT-3) |
| `patient_name` | `String` | — | Nom complet du patient sur le formulaire |
| `mission_state` | `"RUNNING"` / `"STOPPED"` | — | État du moteur de navigation |

---

## 8. Exemple d'Implémentation Serveur Python (Raspberry Pi 4)

Voici un squelette de serveur autonome en Python 3 (`asyncio` + `websockets`) prêt à être intégré dans votre architecture ROS 2 ou centrale :

```python
import asyncio
import json
import time
import websockets

CONNECTED_CLIENTS = set()

def make_envelope(topic: str, payload: dict) -> str:
    """Emballe un payload dans le format d'enveloppe HIAR v4."""
    return json.dumps({
        "v": 1,
        "type": "pub",
        "ts": int(time.time()),
        "topic": topic,
        "payload": payload,
        "qos": 1
    })

async def send_instruction(instruction: dict):
    """Diffuse une instruction à tous les smartphones connectés."""
    if not CONNECTED_CLIENTS:
        return
    message = make_envelope("server/instruction", instruction)
    for ws in list(CONNECTED_CLIENTS):
        try:
            await ws.send(message)
        except Exception:
            pass

async def handle_smartphone(websocket):
    CONNECTED_CLIENTS.add(websocket)
    print(f"🟢 Smartphone connecté : {websocket.remote_address}")

    # Envoi du message de bienvenue
    welcome = {
        "v": 1,
        "type": "welcome",
        "ts": int(time.time()),
        "payload": {"server": "HIAR_Pi4_Brain", "version": "1.0"}
    }
    await websocket.send(json.dumps(welcome))

    try:
        async for raw_message in websocket:
            data = json.loads(raw_message)
            msg_type = data.get("type")
            topic = data.get("topic")
            payload = data.get("payload", {})

            # 1. Traitement du heartbeat
            if msg_type == "ping":
                await websocket.send(json.dumps({"v": 1, "type": "pong", "ts": int(time.time())}))
                continue

            # 2. Réception de la parole utilisateur (STT)
            if topic == "voice/stt/final":
                user_speech = payload.get("text", "").strip()
                print(f"🎤 [PAROLE REÇUE] : {user_speech}")
                
                # ICI : Votre logique d'analyse sémantique ou transfert vers ROS 2
                # Exemple : Déclencher un guidage ou une réponse
                # await send_instruction({...})

            # 3. Réception d'une action tactile
            elif topic == "ui/action/request":
                action_id = payload.get("action_id")
                args = payload.get("args", {})
                print(f"👆 [TACTILE REÇU] : {action_id} -> {args}")

    except websockets.exceptions.ConnectionClosed:
        print(f"🔴 Smartphone déconnecté : {websocket.remote_address}")
    finally:
        CONNECTED_CLIENTS.discard(websocket)

async def main():
    server = websockets.serve(handle_smartphone, "0.0.0.0", 5000)
    print("🚀 Serveur HIAR WebSocket actif sur ws://0.0.0.0:5000/ws")
    await server

if __name__ == "__main__":
    asyncio.run(main())
```
