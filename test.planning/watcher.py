#!/usr/bin/env python3
import os, time, json, hashlib, sqlite3, itertools
from datetime import datetime, timedelta
import requests

DB_PATH = os.getenv('DB_PATH', 'planning.db')
# AGENT_API_URL = os.getenv('AGENT_API_URL', 'url')
# AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'change')
POLL_INTERVAL_SEC = float(os.getenv('POLL_INTERVAL_SEC', '1.5'))
BURST_WINDOW_SEC = float(os.getenv('BURST_WINDOW_SEC', '3.0'))
LOOKAHEAD_DAYS = int(os.getenv('LOOKAHEAD_DAYS', '14'))  # horizon de proposition

HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {AGENT_API_KEY}'
}

SQL_NOW = "SELECT datetime('now')"  # pour debug

SCHEMA_CHECKS = [
    # tables clés utilisées par le watcher
    'employees','skills','employee_skills','employee_availability',
    'tasks','task_required_skills','planning','absences',
    'db_events','ai_planning_proposals','ai_proposal_slots'
]


def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Performance raisonnable tout en gardant la sécurité
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    present = {r[0] for r in cur.fetchall()}
    missing = [t for t in SCHEMA_CHECKS if t not in present]
    if missing:
        raise RuntimeError(f"Tables manquantes: {missing}. Appliquez la migration SQL d'abord.")


def fetch_unprocessed_events(conn: sqlite3.Connection):
    cur = conn.execute("""
        SELECT id, table_name, operation, row_id, event_time
        FROM db_events
        WHERE processed=0
        ORDER BY id ASC
    """)
    return [dict(r) for r in cur.fetchall()]


def mark_events_processed(conn: sqlite3.Connection, ids):
    if not ids:
        return
    q = "UPDATE db_events SET processed=1 WHERE id IN (" + ",".join(["?"]*len(ids)) + ")"
    conn.execute(q, ids)
    conn.commit()


def build_context(conn: sqlite3.Connection):
    # Fenêtre temporelle à planifier
    today = datetime.utcnow().date()
    limit = today + timedelta(days=LOOKAHEAD_DAYS)

    # Employés
    employees = [dict(r) for r in conn.execute("""
        SELECT id, first_name, last_name, contract_type, weekly_hours_max, hourly_cost, accept_replacement
        FROM employees
    """)]

    # Compétences par employé
    emp_skills = {}
    for r in conn.execute("""
        SELECT es.employee_id, s.name AS skill
        FROM employee_skills es JOIN skills s ON s.id = es.skill_id
    """):
        emp_skills.setdefault(r["employee_id"], set()).add(r["skill"])

    # Disponibilités
    availability = {}
    for r in conn.execute("SELECT employee_id, day_of_week, start_time, end_time FROM employee_availability"):
        availability.setdefault(r["employee_id"], []).append(dict(r))

    # Absences approuvées
    absences = [dict(r) for r in conn.execute("""
        SELECT employee_id, start_date, end_date, reason
        FROM absences
        WHERE status='Approved'
    """)]

    # Tâches à planifier (Pending) + compétences requises
    tasks = [dict(r) for r in conn.execute("""
        SELECT id, title, description, duration_hours, deadline, priority, assigned_to, location
        FROM tasks
        WHERE status IN ('Pending','In progress')
    """)]
    task_skills = {}
    for r in conn.execute("""
        SELECT trs.task_id, s.name AS skill
        FROM task_required_skills trs JOIN skills s ON s.id = trs.skill_id
    """):
        task_skills.setdefault(r["task_id"], set()).add(r["skill"])

    # Planning existant (à ne pas modifier)
    planning = [dict(r) for r in conn.execute("""
        SELECT employee_id, task_id, date, start_time, end_time, validated_by_rh
        FROM planning
        WHERE date BETWEEN ? AND ?
    """, (str(today), str(limit)))]

    context = {
        "window": {"from": str(today), "to": str(limit)},
        "employees": employees,
        "employee_skills": {str(k): sorted(list(v)) for k,v in emp_skills.items()},
        "availability": availability,
        "absences": absences,
        "tasks": tasks,
        "task_required_skills": {str(k): sorted(list(v)) for k,v in task_skills.items()},
        "planning_readonly": planning,
        "rules": {
            "do_not_modify_existing_planning": True,
            "respect_weekly_hours_max": True,
            "match_required_skills": True,
            "avoid_absence_conflicts": True,
            "prefer_assigned_to_when_present": True
        }
    }
    return context


def call_agent(context: dict):
    # Versionnement simple du contenu envoyé
    payload = {
        "instruction": (
            "Proposer de nouveaux créneaux pour planifier les tâches sans modifier aucun créneau existant. "
            "Respecter les compétences requises, disponibilités, absences et heures hebdo max. "
            "Retourner un JSON minimal: {rationale: str, slots: [{task_id, employee_id, date, start_time, end_time}]}"
        ),
        "context": context
    }
    version = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    resp = requests.post(AGENT_API_URL, headers=HEADERS, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # data attendu: {"rationale": str, "slots": [{task_id, employee_id, date, start_time, end_time}]}
    return version, data


def save_proposal(conn: sqlite3.Connection, source_event_ids, version: str, data: dict):
    cur = conn.execute(
        "INSERT INTO ai_planning_proposals(source_event_ids, proposal_version, rationale) VALUES (?,?,?)",
        (",").join(map(str, source_event_ids)), version, data.get("rationale", "")
    )
    proposal_id = cur.lastrowid

    slots = data.get("slots", [])
    for s in slots:
        conn.execute(
            """
            INSERT OR IGNORE INTO ai_proposal_slots
                (proposal_id, task_id, employee_id, date, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                int(s["task_id"]),
                int(s["employee_id"]),
                s["date"], s["start_time"], s["end_time"]
            )
        )
    conn.commit()
    return proposal_id, len(slots)


def main():
    conn = connect(DB_PATH)
    ensure_schema(conn)
    print(f"Watcher connecté à {DB_PATH}. Press Ctrl+C pour quitter.")

    while True:
        try:
            evts = fetch_unprocessed_events(conn)
            if not evts:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            # Regrouper par fenêtre de temps
            first_time = datetime.fromisoformat(evts[0]['event_time'])
            burst = []
            for e in evts:
                t = datetime.fromisoformat(e['event_time'])
                if (t - first_time).total_seconds() <= BURST_WINDOW_SEC:
                    burst.append(e)
                else:
                    break

            event_ids = [e['id'] for e in burst]
            context = build_context(conn)
            version, data = call_agent(context)
            proposal_id, n = save_proposal(conn, event_ids, version, data)
            mark_events_processed(conn, event_ids)
            print(f"Proposition {proposal_id} créée avec {n} créneau(x) proposé(s) – events: {event_ids}")

        except requests.HTTPError as http_err:
            print(f"Agent API error: {http_err}")
            time.sleep(2.0)
        except Exception as ex:
            print(f"Erreur watcher: {ex}")
            time.sleep(2.0)

if __name__ == '__main__':
    main()