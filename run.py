import subprocess
import sys
import os


def main():
    # Se place dans le dossier où se trouve le script run.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("--- 🚀 Démarrage du projet Hackaton ---")

    # === ÉTAPE 1: INSTALLER LES DÉPENDANCES ===
    print("--- 1/2 : Installation des dépendances (requirements.txt) ---")

    pip_command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]

    result = subprocess.run(pip_command, capture_output=True, text=True, encoding='utf-8')

    if result.returncode != 0:
        print("ERREUR lors de l'installation des dépendances:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)  # Arrête le script si l'installation échoue
    else:
        print(result.stdout)  # Montre le résultat de pip
        print("--- Dépendances installées avec succès ---")

    # === ÉTAPE 2: LANCER LE SERVEUR WEB ===
    print("\n--- 2/2 : Lancement du serveur applicatif ---")
    print("--- Appuyez sur Ctrl+C pour arrêter le serveur ---")

    # On lance directement server.py
    server_command = [sys.executable, "server.py"]

    try:
        # On lance le serveur
        subprocess.call(server_command)
    except KeyboardInterrupt:
        print("\n--- Arrêt de l'application demandé par l'utilisateur ---")
    except Exception as e:
        print(f"\nERREUR: Impossible de lancer 'server.py'.")
        print(f"Détail: {e}")


if __name__ == "__main__":
    main()