#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Planificateur IA (CLI) – SQLite

- Génère un planning sur 4 semaines (par défaut), pas de 30 minutes
- Appelle Azure OpenAI (chat/completions) si configuré, sinon heuristique locale
- Valide toutes les contraintes puis produit un fichier SQL (.txt) pour revue humaine
- Option d'application du SQL après validation (commande séparée)

Commandes:
    python Planificateur.py generate --db hackaton.db --schema-sql main.sql --seed-sql data.sql --sql-out SQLCommands.txt
    python Planificateur.py validate --db hackaton.db --plan-json plan_preview.json
    python Planificateur.py apply-sql --db hackaton.db --sql-file SQLCommands.txt
"""

import argparse
import os
import json
import sqlite3
from datetime import datetime, date, time, timedelta
from collections import defaultdict
from typing import List, Dict, Any

WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']


# ---------- Chargement .env.scheduler (Option C+) ----------
def load_scheduler_env(path: str = ".env.scheduler"):
    """
    Charge un fichier .env.scheduler (clé=valeur). Ne remplace pas des vars déjà présentes.
    N'affecte pas l'environnement global du serveur si vous ne l'appelez pas ailleurs.
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k not in os.environ:  # ne pas écraser l'env courant
                    os.environ[k] = v
    except Exception as e:
        print(f"[WARN] Impossible de lire {path}: {e}")


# ---------- Utilitaires date/heure ----------
def parse_time(t: str) -> time:
    return datetime.strptime(t, "%H:%M").time()

def tstr(t: time) -> str:
    return t.strftime("%H:%M")

def dstr(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def daterange(d1: date, d2: date):
    cur = d1
    while cur <= d2:
        yield cur
        cur += timedelta(days=1)

def weekday_str(d: date) -> str:
    return WEEKDAYS[d.weekday()]


# ---------- Accès DB et extraction ----------
def compute_allowed_slots(conn: sqlite3.Connection, from_date: date, to_date: date, granularity_min=30):
    """
    Calcule TOUS les créneaux disponibles (par pas de 30 min) pour chaque employé
    sur la fenêtre [from_date..to_date], en respectant:
      - disponibilités par jour de semaine,
      - absences approuvées,
      - planning existant (aucun chevauchement).
    Retour: liste de dicts {employee_id, date, start_time, end_time}
    """
    # Dispos
    avails = fetch_all(conn, "SELECT employee_id, day_of_week, start_time, end_time FROM employee_availability")
    avail_map = defaultdict(list)
    for a in avails:
        avail_map[(a['employee_id'], a['day_of_week'])].append((a['start_time'], a['end_time']))
    # Absences
    abs_rows = fetch_all(conn, "SELECT employee_id, start_date, end_date FROM absences WHERE status='Approved'")
    abs_map = defaultdict(list)
    for r in abs_rows:
        abs_map[r['employee_id']].append((r['start_date'], r['end_date']))
    # Planning existant
    planned = fetch_all(conn, "SELECT employee_id, date, start_time, end_time FROM planning WHERE date BETWEEN ? AND ?",
                        (dstr(from_date), dstr(to_date)))
    occ = defaultdict(lambda: defaultdict(list))  # emp -> date -> [(s,e)]
    for p in planned:
        occ[p['employee_id']][p['date']].append((p['start_time'], p['end_time']))

    def is_absent(emp_id, d: date) -> bool:
        for s,e in abs_map.get(emp_id, []):
            if s <= dstr(d) <= e:
                return True
        return False

    allowed = []
    cur = from_date
    while cur <= to_date:
        dow = weekday_str(cur)
        ds = dstr(cur)
        # pour chaque employé avec dispo ce jour
        emp_ids = set([k[0] for k in avail_map.keys() if k[1] == dow])
        for emp_id in emp_ids:
            if is_absent(emp_id, cur):
                continue
            # fenêtres dispo du jour
            for (st, en) in avail_map[(emp_id, dow)]:
                # soustraire le planning existant
                # on discretise en pas de 30 min et on garde seulement ce qui n'est pas occupé
                def to_time(t): return datetime.strptime(t, "%H:%M").time()
                tcur = to_time(st)
                tend = to_time(en)
                while (datetime.combine(date.today(), tcur) + timedelta(minutes=granularity_min)).time() <= tend:
                    tnext = (datetime.combine(date.today(), tcur) + timedelta(minutes=granularity_min)).time()
                    # vérifier chevauchement avec occ
                    free = True
                    for (os, oe) in occ.get(emp_id, {}).get(ds, []):
                        s0 = to_time(os); e0 = to_time(oe)
                        if not (tnext <= s0 or tcur >= e0):
                            free = False; break
                    if free:
                        allowed.append({
                            "employee_id": emp_id,
                            "date": ds,
                            "start_time": tcur.strftime("%H:%M"),
                            "end_time": tnext.strftime("%H:%M")
                        })
                    tcur = tnext
        cur += timedelta(days=1)
    return allowed

def ensure_db(conn: sqlite3.Connection, schema_sql_path: str, seed_sql_path: str=None):
    with open(schema_sql_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    # IMPORTANT : ne seed que si explicitement demandé (--seed-sql)
    if seed_sql_path:
        with open(seed_sql_path, 'r', encoding='utf-8') as f:
            seed_sql = f.read()
        conn.executescript(seed_sql)
    conn.commit()

def fetch_all(conn: sqlite3.Connection, q: str, params: tuple=()):
    cur = conn.execute(q, params)
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows

def load_context(conn: sqlite3.Connection, from_date: date, to_date: date) -> Dict[str, Any]:
    employees = fetch_all(conn, """
        SELECT id, first_name, last_name, contract_type, weekly_hours_max, accept_replacement, supervisor_id
        FROM employees
    """)
    # compétences
    emp_skills_rows = fetch_all(conn, "SELECT employee_id, skill_id FROM employee_skills")
    emp_skills = defaultdict(list)
    for r in emp_skills_rows:
        emp_skills[r['employee_id']].append(r['skill_id'])
    # disponibilités
    avail_rows = fetch_all(conn, "SELECT employee_id, day_of_week, start_time, end_time FROM employee_availability")
    emp_avail = defaultdict(list)
    for r in avail_rows:
        emp_avail[r['employee_id']].append({'day': r['day_of_week'], 'start': r['start_time'], 'end': r['end_time']})
    # absences approuvées
    abs_rows = fetch_all(conn, "SELECT employee_id, start_date, end_date FROM absences WHERE status='Approved'")
    abs_map = defaultdict(list)
    for r in abs_rows:
        abs_map[r['employee_id']].append({'start': r['start_date'], 'end': r['end_date']})
    # tâches
    tasks = fetch_all(conn, """
        SELECT id, title, description, duration_hours, deadline, priority, assigned_to, status, location
        FROM tasks
        WHERE status IN ('Pending','In progress')
    """)
    # compétences requises
    req_rows = fetch_all(conn, "SELECT task_id, skill_id FROM task_required_skills")
    req_skills = defaultdict(list)
    for r in req_rows:
        req_skills[r['task_id']].append(r['skill_id'])
    # planning existant dans la fenêtre
    plan_rows = fetch_all(conn, """
        SELECT employee_id, task_id, date, start_time, end_time
        FROM planning
        WHERE date BETWEEN ? AND ?
    """, (dstr(from_date), dstr(to_date)))

    employees_out = []
    for e in employees:
        employees_out.append({
            'id': e['id'],
            'name': f"{e['first_name']} {e['last_name']}",
            'weekly_hours_max': e['weekly_hours_max'],
            'accept_replacement': bool(e['accept_replacement']),
            'availability': emp_avail[e['id']],
            'skills': emp_skills[e['id']]
        })
    tasks_out = []
    for t in tasks:
        tasks_out.append({
            'id': t['id'],
            'title': t['title'],
            'duration_hours': t['duration_hours'],
            'deadline': t['deadline'],
            'priority': t['priority'],
            'assigned_to': t['assigned_to'],
            'required_skills': req_skills[t['id']],
            'location': t['location']
        })

    allowed_slots = compute_allowed_slots(conn, from_date, to_date, granularity_min=30)

    context = {
        'time_window': {'from': dstr(from_date), 'to': dstr(to_date)},
        'slot_granularity_minutes': 30,
        'rules': {
            'must_match_skills': True,
            'respect_availability': True,
            'respect_absences': True,
            'respect_weekly_hours_max': True,  # exception si remplacement autorisé
            'allow_task_splitting': True,
            'max_continuous_hours': 6,
            'working_days': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        },
        'objective': {
            'order': ['no_deadline_delay','priority_weighted_coverage','minimize_unplanned_hours']
        },
        'employees': employees_out,
        'tasks': tasks_out,
        'preexisting_assignments': plan_rows,
        'absences': abs_map
    }
    return context


# ---------- Appel Azure OpenAI (optionnel) ----------
def call_azure_openai(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ordre de recherche de la config :
      1) .env.scheduler (chargé localement par ce script)
      2) variables d'env namespacées SCHED_*
      3) fallback AI_*
    Sinon, renvoie {} pour déclencher l'heuristique locale.
    """
    load_scheduler_env(".env.scheduler")

    call_enabled = os.getenv('SCHED_AI_CALL_ENABLED')
    if call_enabled is None:
        call_enabled = os.getenv('AI_CALL_ENABLED', 'true')
    call_enabled = str(call_enabled).lower() == 'true'

    api_url = os.getenv('SCHED_AI_API_URL') or os.getenv('AI_API_URL', '')
    api_key = os.getenv('SCHED_AI_API_KEY') or os.getenv('AI_API_KEY', '')

    if not call_enabled or not api_url or not api_key:
        return {}

    import urllib.request

    system_msg = {
    "role": "system",
    "content": (
        "Vous êtes un planificateur. Répondez EXCLUSIVEMENT au format JSON: "
        "{\"plan\": [{\"employee_id\": int, \"task_id\": int, \"date\": \"YYYY-MM-DD\", \"start_time\": \"HH:MM\", "
        "\"end_time\": \"HH:MM\", \"pause\": \"HH:MM\" | null } ... ], \"notes\": string } "
        "CONTRAINTE ABSOLUE: tous les créneaux retournés doivent être un assemblage de créneaux présents dans 'allowed_slots' "
        "fournis dans le contexte (même date/employé et segments contigus). N'utilisez AUCUN autre horaire. "
        "Respect strict: compétences requises, disponibilités, absences, ≤6h d'affilée, pas de chevauchement, "
        "granularité 30 minutes, semaine complète possible. Objectifs: 1) aucune tâche en retard à sa deadline; "
        "2) priorités (Critical>High>Medium>Low); 3) minimiser les heures non planifiées."
    )
}
    user_msg = {"role": "user", "content": json.dumps(context, ensure_ascii=False)}
    body = {"messages": [system_msg, user_msg], "temperature": 0.2, "response_format": {"type": "json_object"}}

    req = urllib.request.Request(api_url, data=json.dumps(body).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('api-key', api_key)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        content = payload.get('choices', [{}])[0].get('message', {}).get('content', '{}')
        return json.loads(content)
    except Exception as e:
        print(f"[WARN] Appel Azure OpenAI échoué: {e}. Passage à l'heuristique locale.")
        return {}


# ---------- Heuristique locale (greedy) ----------
def minutes_between(t1: time, t2: time) -> int:
    return int((datetime.combine(date.today(), t2) - datetime.combine(date.today(), t1)).total_seconds() // 60)

def add_minutes(t: time, mins: int) -> time:
    dt = datetime.combine(date.today(), t) + timedelta(minutes=mins)
    return dt.time()

def can_do_task(emp: Dict[str, Any], task: Dict[str, Any]) -> bool:
    req = set(task.get('required_skills', []))
    have = set(emp.get('skills', []))
    return req.issubset(have)

def slots_from_availability(avails: List[Dict[str,str]], day: str, granularity_min=30):
    for a in avails:
        if a['day'] == day:
            st, en = parse_time(a['start']), parse_time(a['end'])
            cur = st
            while add_minutes(cur, granularity_min) <= en:
                nxt = add_minutes(cur, granularity_min)
                yield (cur, nxt)
                cur = nxt

def build_existing_map(preassign: List[Dict[str,Any]]):
    occ = defaultdict(lambda: defaultdict(list))  # emp_id -> date -> [(start,end)]
    for p in preassign:
        occ[p['employee_id']][p['date']].append((parse_time(p['start_time']), parse_time(p['end_time'])))
    # fusion des intervalles
    for emp, days in occ.items():
        for d, intervals in days.items():
            intervals.sort(key=lambda x: x[0])
            merged = []
            for s,e in intervals:
                if not merged or s >= merged[-1][1]:
                    merged.append([s,e])
                else:
                    merged[-1][1] = max(merged[-1][1], e)
            occ[emp][d] = [(s,e) for s,e in merged]
    return occ

def is_free(occ_map, emp_id, d, s, e):
    for (os, oe) in occ_map.get(emp_id, {}).get(d, []):
        if not (e <= os or s >= oe):
            return False
    return True

def weekly_hours_used(occ_map, emp_id, d: date) -> float:
    year, week, _ = d.isocalendar()
    total_min = 0
    for day_str, intervals in occ_map.get(emp_id, {}).items():
        dd = datetime.strptime(day_str, "%Y-%m-%d").date()
        y2, w2, _ = dd.isocalendar()
        if (y2, w2) == (year, week):
            for (s,e) in intervals:
                total_min += minutes_between(s,e)
    return total_min / 60.0

def is_absent(absences_map, emp_id, d: date) -> bool:
    for rng in absences_map.get(emp_id, []):
        s = datetime.strptime(rng['start'], '%Y-%m-%d').date()
        e = datetime.strptime(rng['end'], '%Y-%m-%d').date()
        if s <= d <= e:
            return True
    return False

def greedy_plan(context: Dict[str,Any]) -> Dict[str,Any]:
    employees = {e['id']: e for e in context['employees']}
    tasks = list(context['tasks'])
    pre = context['preexisting_assignments']
    rules = context['rules']
    absences = context.get('absences', {})
    tw_from = datetime.strptime(context['time_window']['from'], "%Y-%m-%d").date()
    tw_to = datetime.strptime(context['time_window']['to'], "%Y-%m-%d").date()

    occ = build_existing_map(pre)

    priority_rank = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    tasks.sort(key=lambda t: (-priority_rank.get(t.get('priority','Medium'),2), t.get('deadline','9999-12-31')))

    plan = []
    remaining = {t['id']: float(t['duration_hours']) for t in tasks}

    for t in tasks:
        deadline = datetime.strptime(t['deadline'], "%Y-%m-%d").date() if t.get('deadline') else tw_to
        # candidats: d'abord assigned_to si compétent, puis autres compétents
        candidates = []
        if t.get('assigned_to') and t['assigned_to'] in employees and can_do_task(employees[t['assigned_to']], t):
            candidates.append(employees[t['assigned_to']])
        for e in employees.values():
            if t.get('assigned_to') == e['id']:
                continue
            if can_do_task(e, t):
                candidates.append(e)

        for day in daterange(tw_from, min(tw_to, deadline)):
            if remaining[t['id']] <= 0:
                break
            if weekday_str(day) not in rules['working_days']:
                continue
            day_str = dstr(day)
            for emp in candidates:
                if is_absent(absences, emp['id'], day):
                    continue
                slots = list(slots_from_availability(emp['availability'], weekday_str(day), granularity_min=context['slot_granularity_minutes']))
                if not slots:
                    continue
                block_start = None
                block_minutes = 0
                for (s,e_) in slots:
                    if not is_free(occ, emp['id'], day_str, s, e_):
                        if block_start and block_minutes > 0:
                            max_block_min = min(block_minutes, int(rules['max_continuous_hours']*60))
                            to_assign_min = min(max_block_min, int(remaining[t['id']]*60))
                            if to_assign_min >= context['slot_granularity_minutes']:
                                bs = block_start
                                be = add_minutes(block_start, to_assign_min)
                                is_replacement = (t.get('assigned_to') and t['assigned_to'] != emp['id'])
                                week_hours_before = weekly_hours_used(occ, emp['id'], day)
                                assigned_emp_ok = False
                                if is_replacement and t.get('assigned_to') in employees:
                                    assigned_emp_ok = employees[t['assigned_to']]['accept_replacement']
                                replacement_allowed = is_replacement and (emp.get('accept_replacement') or assigned_emp_ok)
                                if (week_hours_before + to_assign_min/60.0) <= emp['weekly_hours_max'] or replacement_allowed:
                                    plan.append({
                                        'employee_id': emp['id'],
                                        'task_id': t['id'],
                                        'date': day_str,
                                        'start_time': tstr(bs),
                                        'end_time': tstr(be),
                                        'pause': None
                                    })
                                    occ[emp['id']].setdefault(day_str, []).append((bs, be))
                                    remaining[t['id']] -= to_assign_min/60.0
                        block_start = None
                        block_minutes = 0
                        continue
                    if block_start is None:
                        block_start = s
                        block_minutes = minutes_between(s,e_)
                    else:
                        prev_end = add_minutes(block_start, block_minutes)
                        if s == prev_end:
                            block_minutes += minutes_between(s,e_)
                        else:
                            max_block_min = min(block_minutes, int(rules['max_continuous_hours']*60))
                            to_assign_min = min(max_block_min, int(remaining[t['id']]*60))
                            if to_assign_min >= context['slot_granularity_minutes']:
                                bs = block_start
                                be = add_minutes(block_start, to_assign_min)
                                is_replacement = (t.get('assigned_to') and t['assigned_to'] != emp['id'])
                                week_hours_before = weekly_hours_used(occ, emp['id'], day)
                                assigned_emp_ok = False
                                if is_replacement and t.get('assigned_to') in employees:
                                    assigned_emp_ok = employees[t['assigned_to']]['accept_replacement']
                                replacement_allowed = is_replacement and (emp.get('accept_replacement') or assigned_emp_ok)
                                if (week_hours_before + to_assign_min/60.0) <= emp['weekly_hours_max'] or replacement_allowed:
                                    plan.append({
                                        'employee_id': emp['id'],
                                        'task_id': t['id'],
                                        'date': day_str,
                                        'start_time': tstr(bs),
                                        'end_time': tstr(be),
                                        'pause': None
                                    })
                                    occ[emp['id']].setdefault(day_str, []).append((bs, be))
                                    remaining[t['id']] -= to_assign_min/60.0
                            block_start = s
                            block_minutes = minutes_between(s,e_)
                if block_start and remaining[t['id']] > 0:
                    max_block_min = min(block_minutes, int(rules['max_continuous_hours']*60))
                    to_assign_min = min(max_block_min, int(remaining[t['id']]*60))
                    if to_assign_min >= context['slot_granularity_minutes']:
                        bs = block_start
                        be = add_minutes(block_start, to_assign_min)
                        is_replacement = (t.get('assigned_to') and t['assigned_to'] != emp['id'])
                        week_hours_before = weekly_hours_used(occ, emp['id'], day)
                        assigned_emp_ok = False
                        if is_replacement and t.get('assigned_to') in employees:
                            assigned_emp_ok = employees[t['assigned_to']]['accept_replacement']
                        replacement_allowed = is_replacement and (emp.get('accept_replacement') or assigned_emp_ok)
                        if (week_hours_before + to_assign_min/60.0) <= emp['weekly_hours_max'] or replacement_allowed:
                            plan.append({
                                'employee_id': emp['id'],
                                'task_id': t['id'],
                                'date': day_str,
                                'start_time': tstr(bs),
                                'end_time': tstr(be),
                                'pause': None
                            })
                            occ[emp['id']].setdefault(day_str, []).append((bs, be))
                            remaining[t['id']] -= to_assign_min/60.0

    notes = "Heuristique: priorité -> deadline, 30min, blocs ≤6h, heures hebdo strictes sauf remplacement autorisé, absences prises en compte."
    return {"plan": plan, "notes": notes}


# ---------- Validation ----------
def validate_plan(context: Dict[str,Any], result: Dict[str,Any]) -> Dict[str,Any]:
    employees = {e['id']: e for e in context['employees']}
    tasks = {t['id']: t for t in context['tasks']}
    rules = context['rules']
    absences = context.get('absences', {})
    tw_from = context['time_window']['from']
    tw_to = context['time_window']['to']

    errors, warnings = [], []
    occ = defaultdict(lambda: defaultdict(list))
    task_minutes_before_deadline = defaultdict(int)

    def err(m): errors.append(m)
    def warn(m): warnings.append(m)

    for p in result.get('plan', []):
        emp_id = p['employee_id']
        task_id = p['task_id']
        d = p['date']
        s = parse_time(p['start_time'])
        e = parse_time(p['end_time'])
        if e <= s:
            err(f"[Temps] fin <= début (emp {emp_id} le {d})."); continue
        if not (tw_from <= d <= tw_to):
            err(f"[Fenêtre] {d} hors fenêtre {tw_from}..{tw_to}.")
        if weekday_str(datetime.strptime(d, "%Y-%m-%d").date()) not in rules['working_days']:
            err(f"[Jour] {d} non autorisé.")
        t = tasks.get(task_id); eobj = employees.get(emp_id)
        if not t or not eobj:
            err(f"[Références] Tâche ou employé introuvable (task={task_id}, emp={emp_id})."); continue
        if set(t.get('required_skills', [])) - set(eobj.get('skills', [])):
            err(f"[Compétences] Emp {emp_id} n'a pas toutes les compétences pour tâche {task_id}.")
        # disponibilité + absence
        wday = weekday_str(datetime.strptime(d, "%Y-%m-%d").date())
        allowed = any(a['day']==wday and parse_time(a['start'])<=s and parse_time(a['end'])>=e for a in eobj.get('availability', []))
        if not allowed:
            err(f"[Disponibilité] Emp {emp_id} non dispo {d} {tstr(s)}-{tstr(e)}.")
        else:
            the_date = datetime.strptime(d, '%Y-%m-%d').date()
            for rng in absences.get(emp_id, []):
                sabs = datetime.strptime(rng['start'], '%Y-%m-%d').date()
                eabs = datetime.strptime(rng['end'], '%Y-%m-%d').date()
                if sabs <= the_date <= eabs:
                    err(f"[Absence] Emp {emp_id} absent le {d}.")
                    break
        # 6h max
        if minutes_between(s,e) > rules['max_continuous_hours']*60:
            err(f"[Règle 6h] Créneau > 6h (emp {emp_id} le {d}).")
        # chevauchement
        for (os_, oe_) in occ[emp_id][d]:
            if not (e <= os_ or s >= oe_):
                err(f"[Chevauchement] Emp {emp_id} {d} {tstr(s)}-{tstr(e)} chevauche {tstr(os_)}-{tstr(oe_)}.")
        occ[emp_id][d].append((s,e))
        if t.get('deadline') and d <= t['deadline']:
            task_minutes_before_deadline[task_id] += minutes_between(s,e)

    # couverture avant deadline
    for tid, t in tasks.items():
        need = int(t.get('duration_hours', 0)*60)
        got = task_minutes_before_deadline.get(tid, 0)
        if need > 0 and got < need:
            warn(f"[Deadline] Tâche {tid} incomplète avant deadline: {got/60:.1f}h / {need/60:.1f}h.")

    # heures hebdo (signalement; vérifier remplacements si dépassements)
    weekly = defaultdict(lambda: defaultdict(int))  # emp -> (y,w) -> minutes
    for emp_id, days in occ.items():
        for ds, intervals in days.items():
            dd = datetime.strptime(ds, "%Y-%m-%d").date()
            yw = dd.isocalendar()[:2]
            for (s,e) in intervals:
                weekly[emp_id][yw] += minutes_between(s,e)
    for emp_id, weeks in weekly.items():
        maxh = employees[emp_id]['weekly_hours_max']
        for (y,w), mins in weeks.items():
            if mins/60.0 > maxh:
                warnings.append(f"[Heures hebdo] Emp {emp_id} semaine {y}-W{w}: {mins/60.0:.1f}h > {maxh}h. "
                                f"Si dépassement, vérifier que ce sont des remplacements autorisés.")

    return {"errors": errors, "warnings": warnings}


# ---------- Export SQL ----------
def generate_sql_inserts(plan: List[Dict[str,Any]]) -> str:
    lines = ["-- Fichier généré par Planificateur.py ; à relire avant exécution."]
    for p in plan:
        pause_val = (f"'{p['pause']}'" if p.get('pause') else 'NULL')
        line = (
            "INSERT INTO planning (employee_id, task_id, date, start_time, end_time, pause, validated_by_rh) "
            f"VALUES ({p['employee_id']}, {p['task_id']}, '{p['date']}', '{p['start_time']}', '{p['end_time']}', {pause_val}, 0);"
        )
        lines.append(line)
    return "\n".join(lines) + "\n"


# ---------- CLI ----------
def cmd_generate(args):
    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").date() if args.from_date else date.today()
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else from_date + timedelta(weeks=4)
    conn = sqlite3.connect(args.db)
    ensure_db(conn, args.schema_sql, args.seed_sql)  # seed_sql None par défaut => pas de reseed
    context = load_context(conn, from_date, to_date)

    ai_result = call_azure_openai(context)
    if not ai_result:
        ai_result = greedy_plan(context)

    report = validate_plan(context, ai_result)
    if report['errors']:
        print("\n[ERREURS] Le plan contient des erreurs bloquantes :")
        for e in report['errors']:
            print(" -", e)
        print("\nAucun fichier SQL généré (mais un aperçu JSON/rapport est produit).")

    with open(args.plan_json, 'w', encoding='utf-8') as f:
        json.dump(ai_result, f, ensure_ascii=False, indent=2)
    with open(args.report_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if report['errors']:
        return 2

    sql_text = generate_sql_inserts(ai_result.get('plan', []))
    with open(args.sql_out, 'w', encoding='utf-8') as f:
        f.write(sql_text)

    print(f"\n[OK] Plan généré.")
    print(f" - Aperçu JSON : {args.plan_json}")
    print(f" - Rapport     : {args.report_json}")
    print(f" - SQL à valider : {args.sql_out}")
    return 0

def cmd_validate(args):
    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").date() if args.from_date else date.today()
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else from_date + timedelta(weeks=4)
    conn = sqlite3.connect(args.db)
    ensure_db(conn, args.schema_sql, args.seed_sql)
    context = load_context(conn, from_date, to_date)

    with open(args.plan_json, 'r', encoding='utf-8') as f:
        result = json.load(f)
    report = validate_plan(context, result)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report['errors'] else 2

def cmd_apply_sql(args):
    conn = sqlite3.connect(args.db)
    ensure_db(conn, args.schema_sql, args.seed_sql)
    with open(args.sql_file, 'r', encoding='utf-8') as f:
        sql_text = f.read()
    try:
        conn.executescript(sql_text)
        conn.commit()
        print("[OK] SQL appliqué.")
        return 0
    except Exception as e:
        print(f"[ERREUR] Application SQL: {e}")
        return 2

def build_parser():
    p = argparse.ArgumentParser(description="Générateur de planning IA")
    sub = p.add_subparsers(dest='cmd', required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--db', default='hackaton.db', help='Chemin de la base SQLite')
    common.add_argument('--schema-sql', default='main.sql', help='Fichier SQL du schéma')
    # IMPORTANT: par défaut None => pas de reseed involontaire
    common.add_argument('--seed-sql', default=None, help='Fichier SQL de données (à utiliser pour l’initialisation uniquement)')
    common.add_argument('--from-date', help="Date début (YYYY-MM-DD), défaut: aujourd'hui")
    common.add_argument('--to-date', help='Date fin (YYYY-MM-DD), défaut: +4 semaines')

    g = sub.add_parser('generate', parents=[common], help='Générer un plan')
    g.add_argument('--plan-json', default='plan_preview.json', help='Fichier de sortie JSON du plan')
    g.add_argument('--report-json', default='plan_report.json', help='Rapport de validation JSON')
    g.add_argument('--sql-out', default='PropositionPlanning.txt', help='Fichier SQL (texte) à valider')
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser('validate', parents=[common], help='Valider un plan JSON existant')
    v.add_argument('--plan-json', required=True, help='Plan JSON à valider')
    v.set_defaults(func=cmd_validate)

    a = sub.add_parser('apply-sql', parents=[common], help='(Optionnel) Appliquer un fichier SQL après revue')
    a.add_argument('--sql-file', required=True, help='Fichier SQL à exécuter')
    a.set_defaults(func=cmd_apply_sql)

    return p

def main():
    parser = build_parser()
    args = parser.parse_args()
    exit(args.func(args))

if __name__ == '__main__':
    main()