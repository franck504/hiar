#!/usr/bin/env python3
"""Recale la date des rendez-vous enregistrés pendant que l'horloge du Raspberry Pi était fausse.

Le Pi n'a pas de pile d'horloge : sans Internet, il peut redémarrer à une date ancienne
(ex. 18/11 alors qu'on est le 24/11). Les rendez-vous pris pendant ce temps sont datés du 18/11 :
la file « Rendez-vous » du jour ne les montre pas.

Ce script décale `requested_date` et `created_at` d'un nombre de jours, pour les rendez-vous
d'une plage de dates (et éventuellement d'une plage d'identifiants).

Sécurité :
  * SIMULATION par défaut : rien n'est écrit sans --apply ;
  * copie de sauvegarde de la base avant toute écriture ;
  * refus si le déplacement crée un doublon (même téléphone le même jour, même ticket dans la même
    session) ; --renumber attribue alors les numéros libres suivants ;
  * aucun nom ni téléphone de patient n'est affiché.

Exemples (sur le Raspberry Pi) :
  python3 scripts/hiar_fix_dates.py --from-date 2026-11-18 --to-date 2026-11-18 --shift-days 6
  python3 scripts/hiar_fix_dates.py --from-date 2026-11-18 --to-date 2026-11-18 --shift-days 6 --apply
"""

import argparse
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import shutil
import sqlite3
import sys

DEFAULT_DB = Path(__file__).resolve().parents[1] / "web_interface" / "instance" / "appointments.sqlite3"


def shift_iso_date(value: str, days: int) -> str:
    return (date.fromisoformat(value) + timedelta(days=days)).isoformat()


def shift_iso_datetime(value, days: int):
    if not value:
        return value
    try:
        return (datetime.fromisoformat(value) + timedelta(days=days)).isoformat(timespec="seconds")
    except ValueError:
        return value  # format inattendu : laissé tel quel


def plan(connection, from_date, to_date, days, min_id=None, max_id=None, renumber=False):
    """Calcule les modifications et les conflits, sans rien écrire."""
    query = "SELECT id, requested_date, created_at, doctor, period, ticket_number, contact_normalized " \
            "FROM appointments WHERE requested_date BETWEEN ? AND ?"
    params = [from_date, to_date]
    if min_id is not None:
        query += " AND id >= ?"
        params.append(min_id)
    if max_id is not None:
        query += " AND id <= ?"
        params.append(max_id)
    rows = connection.execute(query + " ORDER BY requested_date, id", params).fetchall()
    moving_ids = {r["id"] for r in rows}

    changes, conflicts = [], []
    next_ticket = {}
    for r in rows:
        new_date = shift_iso_date(r["requested_date"], days)
        ticket = r["ticket_number"]

        if r["contact_normalized"]:
            dup = connection.execute(
                "SELECT id FROM appointments WHERE contact_normalized = ? AND requested_date = ?",
                (r["contact_normalized"], new_date),
            ).fetchone()
            if dup and dup["id"] not in moving_ids:
                conflicts.append(f"id {r['id']} : le même téléphone est déjà inscrit le {new_date} (id {dup['id']})")
                continue

        if ticket is not None:
            key = (new_date, r["doctor"], r["period"])
            taken = connection.execute(
                "SELECT id FROM appointments WHERE requested_date = ? AND doctor = ? AND period = ? "
                "AND ticket_number = ?",
                (new_date, r["doctor"], r["period"], ticket),
            ).fetchone()
            if taken and taken["id"] not in moving_ids:
                if not renumber:
                    conflicts.append(
                        f"id {r['id']} : le ticket {r['doctor']}-{r['period']}-{ticket} existe déjà le {new_date} "
                        "(relancer avec --renumber pour attribuer le numéro libre suivant)"
                    )
                    continue
                if key not in next_ticket:
                    next_ticket[key] = connection.execute(
                        "SELECT COALESCE(MAX(ticket_number), 0) FROM appointments "
                        "WHERE requested_date = ? AND doctor = ? AND period = ?",
                        key,
                    ).fetchone()[0]
                next_ticket[key] += 1
                ticket = next_ticket[key]

        changes.append({
            "id": r["id"],
            "old_date": r["requested_date"],
            "new_date": new_date,
            "created_at": shift_iso_datetime(r["created_at"], days),
            "old_ticket": r["ticket_number"],
            "new_ticket": ticket,
            "session": (r["doctor"], r["period"]),
        })
    return changes, conflicts


def apply(connection, changes):
    with connection:
        # Mise à l'écart temporaire (date fictive) pour que les index uniques ne bloquent pas un échange
        for c in changes:
            connection.execute(
                "UPDATE appointments SET requested_date = ? WHERE id = ?", (f"0000-tmp-{c['id']}", c["id"])
            )
        for c in changes:
            connection.execute(
                "UPDATE appointments SET requested_date = ?, created_at = ?, ticket_number = ? WHERE id = ?",
                (c["new_date"], c["created_at"], c["new_ticket"], c["id"]),
            )
            doctor, period = c["session"]
            if doctor and period:
                try:
                    connection.execute(
                        "INSERT OR IGNORE INTO doctor_sessions (requested_date, doctor_code, period, is_open, "
                        "opened_at, closed_at) VALUES (?, ?, ?, 1, ?, NULL)",
                        (c["new_date"], doctor, period, c["created_at"]),
                    )
                except sqlite3.OperationalError:
                    pass  # ancienne base sans table de sessions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=os.environ.get("HIAR_APPOINTMENTS_DB", str(DEFAULT_DB)))
    parser.add_argument("--from-date", required=True, help="première date erronée (AAAA-MM-JJ)")
    parser.add_argument("--to-date", required=True, help="dernière date erronée (AAAA-MM-JJ)")
    parser.add_argument("--shift-days", type=int, required=True, help="décalage à appliquer (ex. 6)")
    parser.add_argument("--min-id", type=int)
    parser.add_argument("--max-id", type=int)
    parser.add_argument("--renumber", action="store_true", help="renuméroter les tickets en conflit")
    parser.add_argument("--apply", action="store_true", help="écrire réellement (sinon simulation)")
    args = parser.parse_args(argv)

    for d in (args.from_date, args.to_date):
        date.fromisoformat(d)
    if args.shift_days == 0:
        print("Décalage nul : rien à faire.")
        return 0

    db = Path(args.db)
    if not db.is_file():
        print(f"Base introuvable : {db}", file=sys.stderr)
        return 2
    connection = sqlite3.connect(str(db))
    connection.row_factory = sqlite3.Row

    changes, conflicts = plan(connection, args.from_date, args.to_date, args.shift_days,
                              args.min_id, args.max_id, args.renumber)
    print(f"{len(changes)} rendez-vous à recaler de {args.shift_days:+d} jour(s) :")
    for c in changes:
        ticket = ""
        if c["old_ticket"] is not None:
            doctor, period = c["session"]
            ticket = f"  ticket {doctor}-{period}-{c['old_ticket']}"
            if c["new_ticket"] != c["old_ticket"]:
                ticket += f" -> {doctor}-{period}-{c['new_ticket']}"
        print(f"  id {c['id']:>5} : {c['old_date']} -> {c['new_date']}{ticket}")
    if conflicts:
        print("\nCONFLITS (aucune modification effectuée) :")
        for msg in conflicts:
            print("  - " + msg)
        return 1
    if not args.apply:
        print("\nSimulation uniquement. Relancez avec --apply pour écrire.")
        return 0
    if not changes:
        return 0

    backup = db.with_name(f"{db.stem}.avant-recalage-{datetime.now():%Y%m%d-%H%M%S}{db.suffix}")
    shutil.copy2(db, backup)
    print(f"\nSauvegarde : {backup}")
    apply(connection, changes)
    print(f"{len(changes)} rendez-vous recalés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
