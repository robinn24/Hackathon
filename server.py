import flask
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from werkzeug.utils import secure_filename
import time
import json
import requests
import pdfplumber
import shutil
from datetime import datetime, date, timedelta  # Ajout
import traceback  # Ajout
from dotenv import load_dotenv
import os

# Charger le fichier .env
load_dotenv()
AZURE_KEY_CHATBOT = os.getenv("AZURE_KEY_CHATBOT")
AZURE_ENDPOINT_CHATBOT = os.getenv("AZURE_ENDPOINT_CHATBOT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY_SECRET")

if not AZURE_OPENAI_KEY:
    print("ERREUR CRITIQUE: AZURE_OPENAI_KEY_SECRET n'est pas définie.")
    exit()
else:
    print("Clé Azure chargée avec succès :", AZURE_OPENAI_KEY[:8], "...")  # Masque la clé
# --- AJOUT: Importer le cerveau du Planificateur ---
try:
    from Planificateur import (
        load_context,
        greedy_plan,
        validate_plan,
        generate_sql_inserts
    )

    print("Logique du Planificateur.py importée avec succès.")
except ImportError:
    print("ERREUR CRITIQUE: Impossible d'importer Planificateur.py. Assure-toi qu'il est dans le dossier.")
    exit()
# --- FIN AJOUT ---


# --- 1. CONFIGURATION GLOBALE ---
app = Flask(__name__)
CORS(app)

DB_FILE = "hackaton.db"
SCHEMA_FILE = "main.sql"
UPLOAD_FOLDER = 'Contracts'
PROCESSED_DIR = "Contracts_Processed"
app.config['UPLOAD_FOLDER'] = os.path.abspath(UPLOAD_FOLDER)

# Config de l'IA (directement ici)
NOM_DU_DEPLOYEMENT = "gpt-5-mini"  # (Vérifie si c'est toujours le bon nom)
RESSOURCE_URL_BASE = "https://hachaton.cognitiveservices.azure.com"
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY_SECRET")
API_VERSION = "2025-04-01-preview"
AZURE_OPENAI_ENDPOINT_URL = f"{RESSOURCE_URL_BASE}/openai/deployments/{NOM_DU_DEPLOYEMENT}/chat/completions?api-version={API_VERSION}"
OUTPUT_SQL_FILE = "Watcher_SQL_Updates.txt"  # Le fichier d'archive SQL


# --- 2. FONCTIONS "CORE" (Copiées de tes anciens scripts) ---

def get_db_connection():
    """Ouvre une nouvelle connexion à la BDD."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par leur nom
    return conn


def create_tables():
    """Crée les tables dans la BDD en utilisant le fichier main.sql."""
    conn = None
    try:
        conn = get_db_connection()  # Utilise la fonction standard
        print(f"Vérification de la structure de la BDD (schéma: {SCHEMA_FILE})...")
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        print("Structure de la BDD vérifiée/créée.")
    except Exception as e:
        print(f"ERREUR SQL lors de la création des tables : {e}")
        return False
    finally:
        if conn: conn.close()
    return True


# --- MODIFICATION: Ajout du paramètre 'archive' ---
def apply_sql_script(sql_script_text, archive=True):
    """Applique un script SQL (string) à la BDD."""
    conn = None
    try:
        conn = get_db_connection()  # Utilise la fonction standard
        cursor = conn.cursor()
        cursor.executescript(sql_script_text)
        conn.commit()
        print(f"Succès ! Le script SQL a été appliqué à {DB_FILE}.")

        # On archive seulement si c'est un script d'onboarding
        if archive:
            with open(OUTPUT_SQL_FILE, "a", encoding="utf-8") as f:
                f.write(sql_script_text + "\n\n")
            print(f"Script SQL d'onboarding archivé dans {OUTPUT_SQL_FILE}.")

    except sqlite3.Error as e:
        print(f"ERREUR SQL lors de l'application des commandes : {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()


def extract_text_from_pdf(pdf_path):
    print(f"Lecture du PDF : {pdf_path}")
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: full_text += text + "\n"
        return full_text
    except Exception as e:
        print(f"Erreur lors de la lecture du PDF {pdf_path}: {e}")
        return None


def call_mistral_for_json_data(texte_contrat):
    print("Appel de l'IA (Azure OpenAI Service) pour extraction JSON...")
    prompt = f"""
    Tu es un assistant RH expert. Analyse le contrat de travail suivant.
    Extrais les informations et réponds **UNIQUEMENT** avec un objet JSON.

    1.  **Informations Employé :**
        -   `first_name`: Prénom (normalisé).
        -   `last_name`: Nom (normalisé).
        -   `weekly_hours_max`: Heures de travail par semaine (juste le nombre, ex: 35).
        -   `contract_type`: Type de contrat ('Full-time', 'Part-time', 'Intern', 'Contractor').

    2.  **Disponibilités (`availability`) :**
        -   **RÈGLE CRITIQUE :** Tu DOIS fournir un `start_time` et `end_time` (format HH:MM).
        -   Ces heures représentent la **FENÊTRE DE PRÉSENCE TOTALE**.
        -   **Si le contrat dit '10h de travail le lundi'**, déduis une fenêtre de présence (ex: 10h de travail + 1h de pause = 11h de présence -> "09:00" à "20:00").
        -   **Si un jour est "off"**, tu dois **NE PAS** inclure cet objet jour.

    Format JSON de sortie attendu :
    {{
      "employee": {{ "first_name": "Bibendum", "last_name": "Michelin", "weekly_hours_max": 35, "contract_type": "Full-time" }},
      "availability": [
        {{"day": "Mon", "start_time": "09:00", "end_time": "20:00"}}, 
        {{"day": "Tue", "start_time": "09:00", "end_time": "19:00"}}
      ]
    }}

    --- DEBUT CONTRAT ---
    {texte_contrat}
    --- FIN CONTRAT ---

    JSON:
    """
    payload = {"messages": [{"role": "user", "content": prompt}], "max_completion_tokens": 2048}
    headers = {'Content-Type': 'application/json', 'api-key': AZURE_OPENAI_KEY}

    try:
        response = requests.post(AZURE_OPENAI_ENDPOINT_URL, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        result = response.json()
        json_string = result['choices'][0]['message']['content'].strip().replace("```json", "").replace("```", "")
        return json.loads(json_string)
    except Exception as e:
        print(f"ERREUR lors de l'appel à l'IA pour JSON : {e}")
        if 'response' in locals(): print(f"Réponse brute de l'IA: {response.text}")
        return None


def process_new_contract(pdf_path):
    """
    Prend un chemin de PDF, l'analyse, et met à jour la BDD.
    Renvoie (True, "Message de succès") ou (False, "Message d'erreur").
    """
    try:
        # 1. Lire le PDF
        texte_contrat = extract_text_from_pdf(pdf_path)
        if not texte_contrat: return (False, "Impossible de lire le PDF.")

        # 2. Appeler l'IA pour extraire les données en JSON
        data = call_mistral_for_json_data(texte_contrat)
        if not data or 'employee' not in data or 'availability' not in data:
            return (False, "L'IA a retourné un JSON incomplet.")
        print(f"Données JSON extraites par l'IA : {data}")

        # 3. Construire les commandes SQL en Python
        sql_commands = []
        emp = data['employee']

        f_name = emp['first_name'].strip().capitalize()
        l_name = emp['last_name'].strip().capitalize()
        names_normalized = sorted([f_name.lower(), l_name.lower()])
        canonical_key = f"{names_normalized[0]}_{names_normalized[1]}"
        print(f"Clé canonique générée : {canonical_key}")

        sql_emp = f"""
        INSERT INTO employees (first_name, last_name, canonical_name_key, weekly_hours_max, contract_type)
        VALUES ('{f_name}', '{l_name}', '{canonical_key}', {emp['weekly_hours_max']}, '{emp['contract_type']}')
        ON CONFLICT(canonical_name_key) DO UPDATE SET
        first_name=excluded.first_name, last_name=excluded.last_name,
        weekly_hours_max=excluded.weekly_hours_max, contract_type=excluded.contract_type;
        """
        sql_commands.append(sql_emp)

        get_id_subquery = f"(SELECT id FROM employees WHERE canonical_name_key = '{canonical_key}')"
        sql_delete_avail = f"DELETE FROM employee_availability WHERE employee_id = {get_id_subquery};"
        sql_commands.append(sql_delete_avail)

        for avail in data['availability']:
            sql_avail = f"""
            INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time)
            VALUES ({get_id_subquery}, '{avail['day']}', '{avail['start_time']}', '{avail['end_time']}');
            """
            sql_commands.append(sql_avail)

        final_sql_script = "\n".join(sql_commands)
        print(f"SQL Généré : \n{final_sql_script}")

        # 4. Exécuter la mise à jour BDD (en archivant)
        print("Exécution de la mise à jour BDD...")
        apply_sql_script(final_sql_script, archive=True)
        print("--- Onboarding terminé ! ---")

        # 5. Déplacer le fichier traité
        nom_fichier = os.path.basename(pdf_path)
        destination = os.path.join(PROCESSED_DIR, nom_fichier)
        shutil.move(pdf_path, destination)
        print(f"Fichier déplacé vers {destination}")

        return (True, "Employé ajouté/mis à jour.")

    except Exception as e:
        print(f"ERREUR grave lors du traitement de {pdf_path} : {e}")
        return (False, f"Erreur serveur: {e}")


# --- 3. ROUTES API (Le contrôleur web) ---

@app.route('/api/planning', methods=['GET'])
def get_planning():
    """
    API pour le site web. Affiche la DISPONIBILITÉ (pas encore le planning).
    """
    conn = get_db_connection()
    query = """
    SELECT e.first_name, e.last_name, e.contract_type, 
           a.day_of_week, a.start_time, a.end_time
    FROM employees e
    LEFT JOIN employee_availability a ON e.id = a.employee_id
    """
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                "first_name": row["first_name"], "last_name": row["last_name"],
                "role": row["contract_type"], "day": row["day_of_week"],
                "start": row["start_time"], "end": row["end_time"]
            })
        return jsonify(results)
    except Exception as e:
        print(f"ERREUR dans /api/planning: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()


# --- MODIFICATION: Logique du planificateur ajoutée ici ---
@app.route('/api/upload-contract', methods=['POST'])
def upload_contract():
    """
    Reçoit le PDF, le sauvegarde, appelle le traitement complet,
    et renvoie une proposition de plan.
    """
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier trouvé"}), 400
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return jsonify({"error": "Fichier PDF non valide"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        file.save(save_path)
        print(f"Fichier '{filename}' uploadé, début du traitement...")

        # --- FLUX INTÉGRÉ ---
        # 1. Onboarder l'employé (le met dans la BDD)
        success, message = process_new_contract(save_path)

        if not success:
            # Si l'onboarding échoue, on s'arrête là
            return jsonify({"error": message}), 500

        # 2. Générer la proposition de planning
        print("Onboarding réussi. Génération du plan initial...")

        conn = get_db_connection()
        from_date = date.today()
        to_date = from_date + timedelta(weeks=4)  # Génère un plan sur 4 semaines

        # On utilise les fonctions de Planificateur.py
        context = load_context(conn, from_date, to_date)
        plan_json = greedy_plan(context)  # Utilise le Plan B (local, rapide)
        report = validate_plan(context, plan_json)

        conn.close()

        if report['errors']:
            print(f"Erreurs dans le plan généré: {report['errors']}")
            return jsonify({
                "message": f"{message}. AVERTISSEMENT: Impossible de générer un plan auto.",
                "plan_proposal": None, "report": report
            })

        print("Plan généré avec succès.")
        # 3. Renvoyer le plan (JSON) au navigateur
        return jsonify({
            "message": f"{message} Proposition de plan générée.",
            "plan_proposal": plan_json,  # C'est le JSON du plan
            "report": report
        })

    except Exception as e:
        print(f"ERREUR grave dans /api/upload-contract: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Erreur serveur lors de l'upload: {e}"}), 500


@app.route('/api/my-schedule', methods=['GET'])
def get_my_schedule():
    """
    Renvoie le planning RÉEL (tâches assignées) pour un employé spécifique.
    Prend un paramètre d'URL ?name=Alice
    """
    employee_name = request.args.get('name')
    if not employee_name:
        return jsonify({"error": "Nom de l'employé manquant"}), 400

    conn = get_db_connection()

    # La requête JOIN dont on a besoin :
    # On cherche l'ID de l'employé par son prénom (first_name)
    # On JOIN planning et tasks pour avoir le nom de la tâche
    query = """
    SELECT 
        p.date, 
        p.start_time, 
        p.end_time, 
        t.title AS task_title
    FROM planning p
    JOIN tasks t ON p.task_id = t.id
    WHERE p.employee_id = (
        SELECT id FROM employees WHERE first_name = ?
    )
    ORDER BY p.date, p.start_time;
    """

    try:
        cursor = conn.cursor()
        # On passe le nom en paramètre sécurisé
        cursor.execute(query, (employee_name,))
        rows = cursor.fetchall()

        # On convertit les résultats en JSON
        schedule = []
        for row in rows:
            schedule.append({
                "date": row["date"],
                "start": row["start_time"],
                "end": row["end_time"],
                "task": row["task_title"]
            })

        return jsonify(schedule)  # Renvoie la liste des tâches

    except Exception as e:
        print(f"ERREUR dans /api/my-schedule: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

# --- NOUVELLE ROUTE: Pour l'approbation ---
@app.route('/api/approve-plan', methods=['POST'])
def approve_plan():
    """
    Reçoit un plan (JSON) approuvé par la RH, le convertit en SQL,
    et l'applique à la base de données (table 'planning').
    """
    plan_json = request.json

    if not plan_json or 'plan' not in plan_json:
        return jsonify({"error": "Plan JSON invalide"}), 400

    try:
        # 1. Convertir le plan JSON en commandes SQL
        #    On utilise la fonction de Planificateur.py
        sql_script_text = generate_sql_inserts(plan_json['plan'])

        # 2. Appliquer ce script SQL à la BDD (sans archiver)
        apply_sql_script(sql_script_text, archive=False)

        return jsonify({"message": "Plan appliqué avec succès !"})

    except Exception as e:
        print(f"ERREUR grave dans /api/approve-plan: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Erreur serveur: {e}"}), 500


# --- 4. POINT DE DÉMARRAGE ---
from flask import send_from_directory

# --- ROUTE POUR LA PAGE D'ACCUEIL ---
@app.route("/")
def home():
    return send_from_directory(".", "index.html")  # Sert index.html depuis le dossier racine

# --- ROUTE POUR LES FICHIERS STATIQUES (CSS, JS, etc.) ---
@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(".", path)  # Sert styles.css, images, etc.

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    """
    Reçoit un message du RH, appelle Azure OpenAI, et renvoie la réponse.
    """
    try:
        user_message = request.json.get("message")
        if not user_message:
            return jsonify({"error": "Message manquant"}), 400

        # Prompt pour guider l'IA
        system_prompt = """
        Tu es un assistant RH connecté à une base SQLite.
        - Si l'utilisateur demande une modification (ajout de skill, absence), propose la requête SQL mais ne l'exécute pas sans confirmation.
        - Réponds de manière claire et concise.
        """

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "max_completion_tokens": 1024
        }

        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_KEY_CHATBOT
        }

        response = requests.post(AZURE_ENDPOINT_CHATBOT, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        result = response.json()

        ai_reply = result['choices'][0]['message']['content'].strip()
        return jsonify({"reply": ai_reply})

    except Exception as e:
        print(f"Erreur dans /api/chat: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not AZURE_OPENAI_KEY:
        print("ERREUR CRITIQUE: 'AZURE_OPENAI_KEY_SECRET' n'est pas définie.")
        print("Vérifie ton fichier .env. Le serveur ne peut pas démarrer.")
    else:
        print("Clé API Azure trouvée.")
        print("--- 1. Initialisation de la base de données ---")
        create_tables()
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        print(f"--- 2. Serveur API lancé (uploads vers '{app.config['UPLOAD_FOLDER']}') ---")

        # On lance SANS debug pour éviter le redémarrage qui cause l'erreur de connexion
        app.run(debug=False, port=5000)