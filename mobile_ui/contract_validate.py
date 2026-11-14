#!/usr/bin/env python3
"""Valide hiar_contract_v1.json et ses vecteurs de test.

Usage : python3 -I contract_validate.py [hiar_contract_v1.json]
Code de sortie 0 si tout est conforme. Utilisable côté serveur (pytest) et en CI.
Dépendance : jsonschema >= 4.
"""
import json, sys
from jsonschema import Draft202012Validator as V

path = sys.argv[1] if len(sys.argv) > 1 else "hiar_contract_v1.json"
c = json.load(open(path, encoding="utf-8"))
fails = []

def check(cond, msg):
    if not cond:
        fails.append(msg)

def validates(schema, inst):
    return not list(V(schema).iter_errors(inst))

# 1. Tous les schémas sont eux-mêmes valides
V.check_schema(c["envelope"])
for t, d in c["topics"].items():
    V.check_schema(d["payload"])
for a, s in c["action_args"].items():
    V.check_schema(s)
for k, r in c["rest"].items():
    for st, s in r["responses"].items():
        V.check_schema(s)
    if r["request"] and "type" in r["request"]:
        V.check_schema(r["request"])

# 2. Vecteurs de messages
for v in c["vectors"]["messages"]:
    m = v["message"]
    env_ok = validates(c["envelope"], m)
    pay_ok = True
    if env_ok and m.get("type") == "pub":
        t = c["topics"].get(m["topic"])
        if t is None:
            pay_ok = False
        else:
            pay_ok = validates(t["payload"], m["payload"])
            check(m["qos"] == t["qos"], f"{v['name']}: qos {m['qos']} != contrat {t['qos']}")
            if t["retain"] is False:
                check(not m.get("retain"), f"{v['name']}: retain interdit sur {m['topic']}")
    ok = env_ok and pay_ok
    check(ok == v["valid"], f"vecteur '{v['name']}': attendu valid={v['valid']}, obtenu {ok}")

# 3. Arguments d'actions
for v in c["vectors"]["action_args"]:
    s = c["action_args"].get(v["action_id"])
    ok = s is not None and validates(s, v["args"])
    check(ok == v["valid"], f"args {v['action_id']} {v['args']}: attendu {v['valid']}")

# 4. Droits par rôle
for v in c["vectors"]["permissions"]:
    allowed = v["topic"] in c["permissions"][v["role"]][v["op"]]
    check(allowed == v["allowed"], f"droit {v}")
for t in c["topics"]:
    check(not t.startswith("robot/") or all("robot" not in p for p in []), "")
for role, p in c["permissions"].items():
    check(not any(x.startswith("robot/") for x in p["publish"]), f"{role} ne doit jamais publier sur robot/#")
    check(not any(x.startswith("vitals/result") for x in p["publish"]), f"{role} ne doit pas publier vitals/result")

# 5. Règles de sûreté du registre
check("robot.forward" not in c["action_args"], "aucune action de mouvement direct")
check(c["action_risk_overrides"].get("robot.stop") == "R3" and c["action_risk_overrides"].get("orientation.confirm") == "R2", "risques R2/R3")
for t, d in c["topics"].items():
    if d["retain"]:
        check(d["qos"] in (0, 1), t)

# 6. Exemples REST
samples = {
 ("POST /api/consultation/appointments", "201"): {"ok": True, "ticket_number": 3, "ticket_label": "A-MAT-3"},
 ("POST /api/consultation/appointments", "409"): {"ok": False, "code": "duplicate_phone", "error": "déjà réservé"},
 ("POST /api/navigation/cancel", "200"): {"ok": True, "published": True, "message": "Commande STOP publiée."},
 ("GET /api/health", "200"): {"ok": True, "version": "1", "registry_hash": "sha256:a", "db": "ok", "ros_bridge": "up", "hub": {"clients": 1}},
 ("POST /api/vitals/acquire", "200"): {"ok": True, "state": "valide", "values": {"temperature_c": 36.6, "heart_rate_bpm": 72, "spo2_percent": None}, "measured_at": "2026-11-14T10:00:00+03:00", "checked_at": "2026-11-14T10:00:01+03:00", "reason": None},
}
for (k, st), inst in samples.items():
    check(validates(c["rest"][k]["responses"][st], inst), f"REST {k} {st}")
bad_sample = {"ok": True, "ticket_number": 3, "ticket_label": "Z-XX-3"}
check(not validates(c["rest"]["POST /api/consultation/appointments"]["responses"]["201"], bad_sample), "ticket_label doit être A-D / MAT|AM / n")

n = len(c["vectors"]["messages"]) + len(c["vectors"]["action_args"]) + len(c["vectors"]["permissions"]) + len(samples) + 1
if fails:
    print("ÉCHEC :", *fails, sep="\n  - ")
    sys.exit(1)
print(f"OK : contrat {c['contract_version']} conforme ({len(c['topics'])} topics, {len(c['action_args'])} actions, {n} vecteurs vérifiés)")
