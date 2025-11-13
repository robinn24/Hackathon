from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
# CORS permet à ton site (fichier html) de parler à ce serveur sans être bloqué par le navigateur
CORS(app)

DB_FILE = "hackaton.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par leur nom
    return conn


@app.route('/api/planning', methods=['GET'])
def get_planning():
    conn = get_db_connection()

    # On récupère les employés ET leurs disponibilités
    # On fait une jointure pour avoir le nom + les horaires
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

        # On transforme le résultat SQL en une liste de dictionnaires
        results = []
        for row in rows:
            results.append({
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "role": row["contract_type"],  # On utilise le type de contrat comme rôle pour l'instant
                "day": row["day_of_week"],
                "start": row["start_time"],
                "end": row["end_time"]
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    print("🚀 Serveur API lancé sur http://localhost:5000")
    app.run(debug=True, port=5000)