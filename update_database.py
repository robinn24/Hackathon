import sqlite3
import os

# --- Configuration ---
# Assurez-vous que ces noms de fichiers sont corrects
DB_FILE = "hackaton.db"  # Le nom de votre fichier de base de données
SCHEMA_FILE = "main.sql"  # Votre fichier de structure de table
COMMANDS_FILE = "SQLCommands.txt"  # Le fichier généré par votre watcher


# ---------------------

def create_tables(conn):
    """
    Crée les tables dans la BDD en utilisant le fichier schema.sql.
    Ne fait rien si les tables existent déjà (grâce à 'IF NOT EXISTS').
    """
    print(f"Vérification de la structure de la BDD (schéma: {SCHEMA_FILE})...")
    try:
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        cursor = conn.cursor()
        cursor.executescript(schema_sql)  # Exécute tout le fichier .sql
        conn.commit()
        print("Structure de la BDD vérifiée/créée.")

    except FileNotFoundError:
        print(f"ERREUR: Fichier de schéma '{SCHEMA_FILE}' non trouvé.")
        print("Impossible de continuer sans le schéma.")
        return False
    except sqlite3.Error as e:
        print(f"ERREUR SQL lors de la création des tables : {e}")
        return False
    return True


def apply_sql_commands(conn):
    """
    Applique toutes les commandes SQL trouvées dans le fichier SQLCommands.txt.
    """
    print(f"Tentative d'application des commandes depuis {COMMANDS_FILE}...")
    try:
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        if not sql_script.strip():
            print("Le fichier de commandes SQL est vide. Aucune mise à jour à appliquer.")
            return

        cursor = conn.cursor()
        # executescript est conçu pour exécuter un string contenant
        # plusieurs commandes SQL (séparées par ';')
        cursor.executescript(sql_script)
        conn.commit()
        print(f"Succès ! Les commandes de {COMMANDS_FILE} ont été appliquées à {DB_FILE}.")

        print(f"Vidage du fichier {COMMANDS_FILE}...")
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            f.write("")
        print("Fichier de commandes vidé.")

    except FileNotFoundError:
        print(f"ERREUR: Fichier de commandes '{COMMANDS_FILE}' non trouvé.")
    except sqlite3.Error as e:
        print(f"ERREUR SQL lors de l'application des commandes : {e}")
        print("Les modifications ont été annulées (rollback).")
        conn.rollback()  # Annule la transaction en cas d'erreur


def main():
    """Point d'entrée principal du script."""

    conn = None
    try:
        # Connexion (crée le fichier .db s'il n'existe pas)
        conn = sqlite3.connect(DB_FILE)

        # 1. Créer les tables en premier
        if not create_tables(conn):
            return  # Arrête si le schéma n'a pas pu être appliqué

        # 2. Appliquer les mises à jour
        apply_sql_commands(conn)

    except sqlite3.Error as e:
        print(f"ERREUR de connexion à la base de données : {e}")
    finally:
        if conn:
            conn.close()
            print(f"Connexion à {DB_FILE} fermée.")


# --- Lancement du script ---
if __name__ == "__main__":
    main()