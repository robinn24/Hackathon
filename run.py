import subprocess
import sys
import os
import update_database


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("--- 🚀 Démarrage du projet Hackaton ---")

    # === ÉTAPE 1: INSTALLER LES DÉPENDANCES ===
    print("--- 1/3 : Installation des dépendances (requirements.txt) ---")
    pip_command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    result = subprocess.run(pip_command, capture_output=True, text=True, encoding='utf-8')

    if result.returncode != 0:
        print("ERREUR lors de l'installation des dépendances:")
        print(result.stderr)
        sys.exit(1)
    else:
        print("--- Dépendances installées avec succès ---")

    # === ÉTAPE 2: PRÉPARER LA BASE DE DONNÉES ===
    print("\n--- 2/3 : Préparation de la base de données (main.sql) ---")
    try:
        # On appelle la fonction main() de ton autre script
        update_database.main()
        print("--- Base de données initialisée ---")
    except Exception as e:
        print(f"ERREUR lors de l'initialisation de la BDD : {e}")
        sys.exit(1)

    # === ÉTAPE 3: LANCER L'APPLICATION (SERVEUR + WATCHER) ===
    print("\n--- 3/3 : Lancement de l'application (Serveur + Watcher) ---")
    print("--- Les logs des deux scripts vont s'afficher ci-dessous ---")
    print("--- Appuyez sur Ctrl+C pour arrêter TOUS les processus ---")

    honcho_command = [sys.executable, "-m", "honcho", "start"]

    try:
        subprocess.call(honcho_command)
    except KeyboardInterrupt:
        print("\n--- Arrêt de l'application demandé par l'utilisateur ---")


if __name__ == "__main__":
    main()