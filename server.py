from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

DB_FILE = "hackaton.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par leur nom
    return conn


@app.route('/api/planning', methods=['GET'])
def get_planning():
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
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "role": row["contract_type"],
                "day": row["day_of_week"],
                "start": row["start_time"],
                "end": row["end_time"]
            })

        return jsonify(results)

    except Exception as e:
        # En mode debug, Flask affichera l'erreur exacte
        raise e  # On lève l'exception pour voir l'erreur dans le terminal
    finally:
        conn.close()


if __name__ == '__main__':
    # On enlève l'emoji et l'encodage bizarre
    print("--- Serveur API lance sur http://localhost:5000 ---")
    app.run(debug=True, port=5000)