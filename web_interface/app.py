import hmac
import json
import os
import time
from datetime import datetime

from flask import Flask, jsonify, render_template, request

from catalog import CATALOG, INFO_DISCLAIMER
from requests_model import build_request
from ros_bridge import RosBridge
from vital_signs import _build, _result
from appointments_store import (
    BookingError,
    create_appointment,
    init_db,
    init_sessions_db,
    list_appointments,
    list_slots,
    update_appointment_status,
)

from consultation_sessions_store import (
    DOCTORS,
    PERIODS,
    SESSION_STATUSES,
    TZ,
    create_session_appointment,
    ensure_daily_sessions,
    list_doctor_sessions,
    list_session_appointments,
    set_doctor_session,
    update_session_appointment_status,
)

BOOKING_ERROR_STATUS = {
    "invalid_phone": 400,
    "invalid_slot": 400,
    "duplicate_phone": 409,
    "slot_taken": 409,
}

app = Flask(__name__)
bridge = RosBridge()


@app.route("/")
def home():
    """Page d'accueil du web : Portail unique Médecin (Login et Liste des rendez-vous)."""
    return render_template("doctor.html")


@app.route("/staff")
def staff_page():
    # Page sans aucune donnée : les rendez-vous ne sont servis que par l'API,
    # protégée par le jeton du personnel.
    return render_template("staff.html")


@app.route("/admin")
def admin_page():
    """Page d'administration et de supervision du personnel médical."""
    return render_template("staff.html")



@app.route("/doctor")
def doctor_page():
    """Page de gestion de la file du médecin (le jeton est saisi côté page)."""
    return render_template("doctor.html")


@app.route("/api/appointments", methods=["POST"])
def api_appointments():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Corps JSON invalide."}), 400

    fields = (
        "patient_name",
        "contact",
        "reason",
        "requested_date",
        "requested_time",
    )
    if any(
        not isinstance(data.get(field), str)
        or not data[field].strip()
        for field in fields
    ):
        return jsonify({
            "ok": False,
            "error": "Tous les champs du rendez-vous sont obligatoires.",
        }), 400

    limits = {
        "patient_name": 120,
        "contact": 40,
        "reason": 500,
        "requested_date": 10,
        "requested_time": 5,
    }
    for field, maximum in limits.items():
        if len(data[field].strip()) > maximum:
            return jsonify({
                "ok": False,
                "error": f"Le champ « {field} » dépasse la longueur autorisée.",
            }), 400

    slot_id = data.get("slot_id")
    if slot_id is not None and (
        not isinstance(slot_id, int) or isinstance(slot_id, bool)
    ):
        return jsonify({
            "ok": False,
            "code": "invalid_slot",
            "error": "Créneau invalide.",
        }), 400

    # Les signes vitaux sont facultatifs : une valeur absente reste None.
    vital_limits = {
        "temperature_c": (25.0, 45.0),
        "heart_rate_bpm": (40, 200),
        "spo2_percent": (0.0, 100.0),
    }
    vitals = {}

    for field, (minimum, maximum) in vital_limits.items():
        value = data.get(field)

        if value is None:
            vitals[field] = None
            continue

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return jsonify({
                "ok": False,
                "error": f"Mesure invalide : {field}.",
            }), 400

        if not minimum <= value <= maximum:
            return jsonify({
                "ok": False,
                "error": f"Mesure hors plage : {field}.",
            }), 400

        if field == "heart_rate_bpm" and not isinstance(value, int):
            return jsonify({
                "ok": False,
                "error": "La fréquence cardiaque doit être un nombre entier.",
            }), 400

        vitals[field] = value

    try:
        init_db()
        appointment_id = create_appointment(
            data["patient_name"],
            data["contact"],
            data["reason"],
            data["requested_date"],
            data["requested_time"],
            slot_id=slot_id,
            temperature_c=vitals["temperature_c"],
            heart_rate_bpm=vitals["heart_rate_bpm"],
            spo2_percent=vitals["spo2_percent"],
        )
    except BookingError as err:
        return jsonify({
            "ok": False,
            "code": err.code,
            "error": str(err),
        }), BOOKING_ERROR_STATUS.get(err.code, 400)
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec d'enregistrement du rendez-vous")
        return jsonify({
            "ok": False,
            "error": "Impossible d'enregistrer la demande pour le moment.",
        }), 500

    # Le rendez-vous est déjà enregistré ici. Le numéro de file n'est lu
    # qu'après cet enregistrement réussi ; s'il est illisible, il reste None.
    queue_number = None
    doctor = None
    try:
        saved = next(
            (a for a in list_appointments() if a["id"] == appointment_id),
            None,
        )
        if saved:
            queue_number = saved["pass_number"]
            doctor = saved["doctor"]
    except Exception:
        app.logger.exception("Lecture du rendez-vous enregistré impossible")

    return jsonify({
        "ok": True,
        "appointment_id": appointment_id,
        "queue_number": queue_number,
        "doctor": doctor,
        "status": "PENDING",
        "message": "Votre demande est enregistrée et reste en attente de confirmation.",
    }), 201



@app.route("/api/consultation/appointments", methods=["POST"])
def api_create_session_appointment():
    """Inscrit un patient dans une session de consultation ouverte."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Corps JSON invalide."}), 400

    required = ("patient_name", "contact", "reason_code",
                "requested_date", "doctor_code", "period")
    if any(
        not isinstance(data.get(field), str) or not data[field].strip()
        for field in required
    ):
        return jsonify({
            "ok": False,
            "error": "Tous les champs obligatoires doivent être renseignés.",
        }), 400

    if len(data["patient_name"].strip()) > 120:
        return jsonify({"ok": False, "error": "Nom trop long."}), 400
    if len(data["contact"].strip()) > 40:
        return jsonify({"ok": False, "error": "Coordonnées trop longues."}), 400

    vital_limits = {
        "temperature_c": (25.0, 45.0),
        "heart_rate_bpm": (40, 200),
        "spo2_percent": (0.0, 100.0),
    }
    vitals = {}

    for field, (minimum, maximum) in vital_limits.items():
        value = data.get(field)
        if value is None:
            vitals[field] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return jsonify({
                "ok": False,
                "error": f"Mesure invalide : {field}.",
            }), 400
        if not minimum <= value <= maximum:
            return jsonify({
                "ok": False,
                "error": f"Mesure hors plage : {field}.",
            }), 400
        if field == "heart_rate_bpm" and not isinstance(value, int):
            return jsonify({
                "ok": False,
                "error": "La fréquence cardiaque doit être entière.",
            }), 400
        vitals[field] = value

    try:
        init_sessions_db()
        result = create_session_appointment(
            patient_name=data["patient_name"],
            contact=data["contact"],
            reason_code=data["reason_code"],
            requested_date=data["requested_date"],
            doctor_code=data["doctor_code"],
            period=data["period"],
            temperature_c=vitals["temperature_c"],
            heart_rate_bpm=vitals["heart_rate_bpm"],
            spo2_percent=vitals["spo2_percent"],
        )
    except BookingError as err:
        return jsonify({
            "ok": False,
            "code": err.code,
            "error": str(err),
        }), BOOKING_ERROR_STATUS.get(err.code, 400)
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec d'inscription en consultation")
        return jsonify({
            "ok": False,
            "error": "Impossible d'enregistrer cette consultation.",
        }), 500

    return jsonify({"ok": True, **result}), 201


@app.route("/api/consultation/sessions", methods=["GET"])
def api_public_consultation_sessions():
    """Expose uniquement les sessions ouvertes aux inscriptions."""
    requested_date = request.args.get("date", "")

    try:
        init_sessions_db()
        if requested_date == datetime.now(TZ).date().isoformat():
            ensure_daily_sessions()
        sessions = list_doctor_sessions(requested_date)
        available = [
            {
                "doctor_code": session["doctor_code"],
                "period": session["period"],
                "waiting_count": session["waiting_count"],
            }
            for session in sessions
            if session["registration_open"]
        ]
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception(
            "Échec de lecture des sessions publiques de consultation"
        )
        return jsonify({
            "ok": False,
            "error": "Impossible de consulter les consultations disponibles.",
        }), 500

    return jsonify({
        "ok": True,
        "date": requested_date,
        "sessions": available,
    }), 200


def staff_authorized():
    """Vérifie le jeton d'accès du personnel médical."""
    expected = os.environ.get("HIAR_STAFF_API_TOKEN", "")
    supplied = request.headers.get("X-Staff-Token", "")
    return bool(expected) and hmac.compare_digest(expected, supplied)


def staff_auth_error():
    """Construit la réponse lorsque l'accès du personnel est refusé."""
    if not os.environ.get("HIAR_STAFF_API_TOKEN"):
        status_code = 503
        error = "Accès du personnel non configuré sur le serveur."
    else:
        status_code = 401
        error = "Authentification du personnel requise."

    app.logger.warning(
        "Refus d'accès : %s %s — HTTP %s",
        request.method,
        request.path,
        status_code,
    )
    return jsonify({"ok": False, "error": error}), status_code


def doctor_identity():
    """Retourne le code du médecin identifié par son jeton."""
    configured = {
        code: os.environ.get(f"HIAR_DOCTOR_TOKEN_{code}", "")
        for code in DOCTORS
    }
    configured = {
        code: token for code, token in configured.items() if token
    }

    if not configured:
        return None, "unconfigured"

    supplied = request.headers.get("X-Doctor-Token", "")
    matches = [
        code for code, expected in configured.items()
        if hmac.compare_digest(expected, supplied)
    ]

    if len(matches) > 1:
        return None, "ambiguous"
    if len(matches) == 1:
        return matches[0], None
    return None, "unauthorized"


def doctor_auth_error(reason):
    """Construit une réponse explicite en cas d'échec d'authentification."""
    if reason in {"unconfigured", "ambiguous"}:
        status_code = 503
        error = (
            "Authentification des médecins non configurée correctement."
        )
    else:
        status_code = 401
        error = "Authentification du médecin requise."

    app.logger.warning(
        "Refus d'accès médecin : %s %s — HTTP %s",
        request.method,
        request.path,
        status_code,
    )
    return jsonify({"ok": False, "error": error}), status_code


@app.route("/api/doctor/sessions", methods=["GET"])
def api_doctor_sessions():
    """Retourne uniquement les sessions du médecin authentifié."""
    doctor_code, auth_error = doctor_identity()
    if auth_error:
        return doctor_auth_error(auth_error)

    requested_date = request.args.get("date", "")
    if not requested_date:
        return jsonify({
            "ok": False,
            "error": "Le paramètre date est obligatoire.",
        }), 400

    try:
        init_sessions_db()
        sessions = list_doctor_sessions(requested_date)
        sessions = [
            session for session in sessions
            if session["doctor_code"] == doctor_code
        ]
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de lecture des sessions médecin")
        return jsonify({
            "ok": False,
            "error": "Impossible de consulter les sessions.",
        }), 500

    return jsonify({"ok": True, "doctor": doctor_code, "sessions": sessions})


@app.route("/api/doctor/sessions", methods=["POST"])
def api_doctor_update_session():
    """Ouvre ou ferme une session appartenant au médecin authentifié."""
    doctor_code, auth_error = doctor_identity()
    if auth_error:
        return doctor_auth_error(auth_error)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "ok": False,
            "error": "Corps JSON invalide.",
        }), 400

    requested_date = data.get("requested_date")
    period = data.get("period")
    is_open = data.get("is_open")

    try:
        init_sessions_db()
        set_doctor_session(
            requested_date,
            doctor_code,
            period,
            is_open,
        )
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de modification de session médecin")
        return jsonify({
            "ok": False,
            "error": "Impossible de modifier cette session.",
        }), 500

    return jsonify({
        "ok": True,
        "doctor": doctor_code,
        "requested_date": requested_date,
        "period": period,
        "is_open": is_open,
    })



@app.route("/api/doctor/appointments", methods=["GET"])
def api_doctor_appointments():
    """Retourne uniquement les tickets du médecin authentifié."""
    doctor_code, auth_error = doctor_identity()
    if auth_error:
        return doctor_auth_error(auth_error)

    requested_date = request.args.get("date", "")
    if not requested_date:
        return jsonify({
            "ok": False,
            "error": "Le paramètre date est obligatoire.",
        }), 400

    period = request.args.get("period") or None
    status = request.args.get("status") or None

    try:
        init_sessions_db()
        appointments = list_session_appointments(
            requested_date,
            doctor_code=doctor_code,
            period=period,
            status=status,
        )
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de lecture de la file médecin")
        return jsonify({
            "ok": False,
            "error": "Impossible de consulter la file.",
        }), 500

    return jsonify({
        "ok": True,
        "doctor": doctor_code,
        "appointments": appointments,
    }), 200



@app.route("/api/doctor/appointments/<int:appointment_id>", methods=["PATCH"])
def api_update_doctor_appointment(appointment_id):
    """Permet au médecin authentifié de modifier ses propres tickets."""
    doctor_code, auth_error = doctor_identity()
    if auth_error:
        return doctor_auth_error(auth_error)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Corps JSON invalide."}), 400

    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        return jsonify({
            "ok": False,
            "error": "Le nouveau statut est obligatoire.",
        }), 400

    if data.get("exceptional_correction"):
        return jsonify({
            "ok": False,
            "error": "La correction exceptionnelle est réservée au personnel.",
        }), 403

    try:
        init_sessions_db()
        updated = update_session_appointment_status(
            appointment_id,
            status.strip(),
            doctor_code=doctor_code,
        )
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de mise à jour du ticket médecin")
        return jsonify({
            "ok": False,
            "error": "Impossible de mettre à jour le ticket.",
        }), 500

    if not updated:
        return jsonify({
            "ok": False,
            "error": "Ticket introuvable ou accès non autorisé.",
        }), 404

    return jsonify({"ok": True, "message": "Statut du ticket mis à jour."}), 200



@app.route("/api/staff/consultations", methods=["GET"])
def api_staff_consultations():
    """Retourne les files de consultation au personnel autorisé."""
    if not staff_authorized():
        return staff_auth_error()

    requested_date = request.args.get("date", "")
    if not requested_date:
        return jsonify({
            "ok": False,
            "error": "Le paramètre date est obligatoire.",
        }), 400

    doctor_code = request.args.get("doctor") or None
    period = request.args.get("period") or None
    status = request.args.get("status") or None

    try:
        init_sessions_db()
        appointments = list_session_appointments(
            requested_date,
            doctor_code=doctor_code,
            period=period,
            status=status,
        )
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de lecture des files de consultation")
        return jsonify({
            "ok": False,
            "error": "Impossible de consulter les files.",
        }), 500

    return jsonify({
        "ok": True,
        "appointments": appointments,
    }), 200


@app.route(
    "/api/staff/consultations/<int:appointment_id>",
    methods=["PATCH"],
)
def api_update_staff_consultation(appointment_id):
    """Modifie un ticket avec les droits du personnel autorisé."""
    if not staff_authorized():
        return staff_auth_error()

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Corps JSON invalide."}), 400

    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        return jsonify({
            "ok": False,
            "error": "Le nouveau statut est obligatoire.",
        }), 400

    exceptional_correction = data.get("exceptional_correction", False)
    if not isinstance(exceptional_correction, bool):
        return jsonify({
            "ok": False,
            "error": "L'indicateur de correction exceptionnelle doit être booléen.",
        }), 400

    try:
        init_sessions_db()
        updated = update_session_appointment_status(
            appointment_id,
            status.strip(),
            exceptional_correction=exceptional_correction,
        )
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de mise à jour du ticket par le personnel")
        return jsonify({
            "ok": False,
            "error": "Impossible de mettre à jour le ticket.",
        }), 500

    if not updated:
        return jsonify({
            "ok": False,
            "error": "Ticket de consultation introuvable.",
        }), 404

    return jsonify({
        "ok": True,
        "appointment_id": appointment_id,
        "status": status.strip(),
    }), 200


@app.route("/api/appointments", methods=["GET"])
def api_list_appointments():
    """Retourne les rendez-vous au personnel autorisé."""
    if not staff_authorized():
        return staff_auth_error()

    status = request.args.get("status") or None
    try:
        init_db()
        appointments = list_appointments(status)
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de lecture des rendez-vous")
        return jsonify({
            "ok": False,
            "error": "Impossible de consulter les rendez-vous.",
        }), 500

    return jsonify({"ok": True, "appointments": appointments}), 200


@app.route("/api/appointments/<int:appointment_id>", methods=["PATCH"])
def api_update_appointment(appointment_id):
    """Met à jour le statut d'un rendez-vous pour le personnel autorisé."""
    if not staff_authorized():
        return staff_auth_error()

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("status"), str):
        return jsonify({
            "ok": False,
            "error": "Un statut valide est obligatoire.",
        }), 400

    exceptional_correction = data.get("exceptional_correction", False)
    if not isinstance(exceptional_correction, bool):
        return jsonify({
            "ok": False,
            "error": "L'indicateur de correction exceptionnelle doit être booléen.",
        }), 400

    try:
        init_db()
        updated = update_appointment_status(
            appointment_id,
            data["status"],
            exceptional_correction=exceptional_correction,
        )
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception:
        app.logger.exception("Échec de mise à jour du rendez-vous")
        return jsonify({
            "ok": False,
            "error": "Impossible de mettre à jour le rendez-vous.",
        }), 500

    if not updated:
        return jsonify({
            "ok": False,
            "error": "Rendez-vous introuvable ou déjà archivé.",
        }), 404

    return jsonify({
        "ok": True,
        "appointment_id": appointment_id,
        "status": data["status"],
    }), 200


@app.route("/api/slots", methods=["GET"])
def api_slots():
    # Disponibilité seulement : aucune donnée patient n'est exposée.
    date = request.args.get("date", "")
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        parsed = None
    if parsed is None or parsed.isoformat() != date:
        return jsonify({
            "ok": False,
            "error": "Date invalide. Format attendu : AAAA-MM-JJ.",
        }), 400

    try:
        init_db()
        slots = list_slots(date)
    except Exception:
        app.logger.exception("Échec de lecture des créneaux")
        return jsonify({
            "ok": False,
            "error": "Impossible de consulter les créneaux.",
        }), 500

    return jsonify({"ok": True, "date": date, "slots": slots}), 200


@app.route("/api/vitals/acquire", methods=["POST"])
def api_vitals_acquire():
    # La mesure passe par ROS2 : seul esp32_interface_node
    # possède la liaison série avec l'ESP32.
    try:
        response = bridge.acquire_vitals(timeout=35.0)
    except Exception as exc:
        result = _result("indisponible", f"Pont ROS2 indisponible : {exc}")
        result["ok"] = True
        return jsonify(result), 200

    if not isinstance(response, dict) or not response.get("ok"):
        reason = (
            response.get("reason")
            if isinstance(response, dict)
            else None
        ) or (
            bridge.error
            or "Aucune réponse du pont ROS2."
        )
        result = _result("indisponible", reason)
        result["ok"] = True
        return jsonify(result), 200

    line = response.get("line", "")

    if isinstance(line, str) and line.startswith("RESULT,"):
        result = _build(line)
    elif isinstance(line, str) and line.startswith("ERROR,"):
        result = _result(
            "indisponible",
            "Capteurs indisponibles : " + line[len("ERROR,"):],
        )
    else:
        result = _result(
            "indisponible",
            "Réponse de mesure absente ou invalide.",
        )

    result["ok"] = True
    return jsonify(result), 200


@app.route("/api/request", methods=["POST"])
def api_request():
    data = request.get_json(silent=True) or {}
    try:
        structured = build_request(data.get("category"), data.get("item"))
    except ValueError as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    entry = CATALOG[data["category"]]
    item = entry["items"][data["item"]]
    if "info" in item:
        title = item["label"]
        message = item["info"] + "\n\n" + INFO_DISCLAIMER
    else:
        title = "Votre choix"
        message = entry["confirm"].format(label=item["label"])
    published = bridge.publish(structured)
    response = {
        "ok": published,
        "request": structured,
        "title": title,
        "message": message,
        "published": published,
    }
    if not published:
        response["error"] = bridge.error or "Échec de publication ROS2"
        return jsonify(response), 503
    return jsonify(response), 200


@app.route("/api/system/diagnostics", methods=["GET"])
def api_system_diagnostics():
    """Retourne l'état temps réel de l'ESP32, des capteurs, des nœuds ROS 2 et du LLM."""
    diag_path = os.environ.get("HIAR_DIAGNOSTICS_FILE", "/tmp/hiar_diagnostics.json").strip()
    now = time.time()
    data = None
    if diag_path and os.path.isfile(diag_path):
        try:
            with open(diag_path, "r", encoding="utf-8") as fh:
                parsed = json.load(fh)
            if isinstance(parsed, dict):
                ts = float(parsed.get("ts") or 0.0)
                age_sec = max(0.0, now - ts)
                if age_sec <= 12.0:
                    data = parsed
                    data["bridge_online"] = True
                    data["age_sec"] = round(age_sec, 1)
        except Exception:
            data = None

    if data is None:
        data = {
            "ts": round(now, 2),
            "bridge_online": False,
            "age_sec": None,
            "firmware_diagnostics": "offline",
            "esp32": {
                "status": "offline",
                "port": "/dev/ttyUSB0",
                "detail": "Pont ROS 2 hors ligne ou en démarrage",
            },
            "sensors": {
                "ultrasonic": {"status": "offline", "distance_cm": None, "detail": "Hors ligne"},
                "ultrasonic_left": {"status": "offline", "distance_cm": None, "detail": "Hors ligne"},
                "ultrasonic_right": {"status": "offline", "distance_cm": None, "detail": "Hors ligne"},
                "ds18b20": {"status": "offline", "detail": "Hors ligne"},
                "max30102": {"status": "offline", "detail": "Hors ligne"},
                "motors": {"status": "offline", "mode": "OFFLINE", "detail": "Hors ligne"},
            },
            "ros_nodes": {
                "status": "offline",
                "active_count": 0,
                "total_count": 6,
                "detail": "0/6 actifs (pont hors ligne)",
            },
            "llm": {
                "status": "offline",
                "detail": "En attente du pont ROS 2",
            },
            "network": {
                "hostname": "",
                "ip": request.host.split(":")[0],
                "ws_port": 5000,
                "web_port": 5001,
            },
        }
    return jsonify(data), 200


@app.route("/api/navigation/cancel", methods=["POST"])
def api_navigation_cancel():
    published = bridge.cancel_navigation()
    response = {
        "ok": published,
        "published": published,
        "message": "Commande STOP publiée." if published else None,
    }
    if not published:
        response["error"] = bridge.error or "Échec de publication de STOP"
        return jsonify(response), 503
    return jsonify(response), 200


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Staff-Token, X-Doctor-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
    return response


@app.before_request
def handle_options_preflight():
    if request.method == "OPTIONS":
        res = app.make_default_options_response()
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Staff-Token, X-Doctor-Token"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
        return res


if __name__ == "__main__":
    if bridge.start():
        print("Pont ROS2 actif : demandes publiées sur /hmi/request")
    else:
        print("Pont ROS2 inactif : " + str(bridge.error))
    server_port = int(os.environ.get("HIAR_WEB_PORT", os.environ.get("PORT", "5000")))
    try:
        app.run(host="0.0.0.0", port=server_port)
    except OSError as e:
        if "Address already in use" in str(e) and server_port == 5000:
            print("Port 5000 déjà utilisé (ex. hmi_websocket_bridge). Démarrage sur le port 5001...")
            app.run(host="0.0.0.0", port=5001)
        else:
            raise
    finally:
        bridge.stop()
