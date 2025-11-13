import sqlite3
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DB_FILE = "hackaton.db"
OUTPUT_FILE = "PropositionPlanning.txt"
SQL_OUTPUT_FILE = "SQLCommands.txt"
ALERTS_OUTPUT_FILE = "Alertes.txt"

# ⚠️ Remplace par ton URL complète Azure et ta clé API
AZURE_OPENAI_ENDPOINT = "https://hachaton.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
AZURE_OPENAI_API_KEY = "cle"

# --- EXTRACTION DES DONNÉES ---
def fetch_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT id, first_name, last_name, weekly_hours_max FROM employees")
    employees = cursor.fetchall()

    cursor.execute("SELECT employee_id, day_of_week, start_time, end_time FROM employee_availability")
    availability = cursor.fetchall()

    cursor.execute("SELECT employee_id, start_date, end_date FROM absences WHERE status='Approved'")
    absences = cursor.fetchall()

    cursor.execute("""
        SELECT e.id, s.name FROM employees e
        JOIN employee_skills es ON e.id = es.employee_id
        JOIN skills s ON s.id = es.skill_id
    """)
    skills = cursor.fetchall()

    conn.close()
    return employees, availability, absences, skills

# --- CONSTRUCTION DU PROMPT ---
def build_prompt(employees, availability, absences, skills):
    start_date = datetime.now()
    end_date = start_date + timedelta(weeks=4)

    prompt = f"""
Tu es un planificateur RH. Génère des INSERT INTO planning pour remplir le planning du {start_date.date()} au {end_date.date()}.
Règles :
- Créneaux entre 09:00 et 19:00, minimum 2h.
- Skill "accueil" présent tout le temps.
- 2 conseillers présents en permanence.
- Directeur présent chaque matin.
- Respecter weekly_hours_max, disponibilités, absences.
- Couper les créneaux débordant.
- Exclure les jours d'absence.
- Un employé ne peut pas travailler plus de 5h d'affilée. Si un créneau dépasse 5h, insérer une pause d'1h et renseigner le champ pause avec l'heure de la pause (exemple: '13:00-14:00').
- Si impossible, inclure ALERTES dans la sortie.

Format attendu :
INSERT INTO planning (employee_id, task_id, date, start_time, end_time, pause) VALUES (...);
Ne mets pas de texte explicatif, uniquement les requêtes SQL et ALERTES si nécessaire.

Données :
Employés : {employees}
Disponibilités : {availability}
Absences : {absences}
Skills : {skills}
"""
    return prompt

# --- APPEL AZURE OPENAI ---
def call_azure_openai(prompt):
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }
    payload = {
        "messages": [
            {"role": "system", "content": "Tu es un assistant SQL expert en planification RH."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 3000
    }
    response = requests.post(AZURE_OPENAI_ENDPOINT, headers=headers, json=payload)
    return response.json()["choices"][0]["message"]["content"]

# --- MAIN ---
def main():
    employees, availability, absences, skills = fetch_data()
    prompt = build_prompt(employees, availability, absences, skills)
    sql_output = call_azure_openai(prompt)

    # Sauvegarde brute
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(sql_output)
    print(f"Planning généré dans {OUTPUT_FILE}")

    # Nettoyage : séparation SQL et alertes
    sql_lines = []
    alert_lines = []

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("--") or "ALERTES" in line:
                alert_lines.append(line)
            elif line.upper().startswith("INSERT INTO"):
                sql_lines.append(line)

    with open(SQL_OUTPUT_FILE, "w", encoding="utf-8") as f_sql:
        f_sql.write("\n".join(sql_lines).strip().replace("```sql", "").replace("```", ""))

    with open(ALERTS_OUTPUT_FILE, "w", encoding="utf-8") as f_alert:
        f_alert.write("\n".join(alert_lines))

    print(f"✅ Fichier SQL : {SQL_OUTPUT_FILE}")
    print(f"✅ Fichier alertes : {ALERTS_OUTPUT_FILE}")

if __name__ == "__main__":
    main()