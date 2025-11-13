import subprocess
import sys
import os


def main():
    # Se place dans le dossier où se trouve le script run.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("--- 🚀 Démarrage du projet Hackaton ---")

    # === ÉTAPE 1: INSTALLER LES DÉPENDANCES ===
    print("--- 1/2 : Installation des dépendances (requirements.txt) ---")

    # On utilise sys.executable pour être sûr d'utiliser le bon pip
    pip_command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]

    # On exécute la commande d'installation
    result = subprocess.run(pip_command, capture_output=True, text=True, encoding='utf-8')

    if result.returncode != 0:
        print("ERREUR lors de l'installation des dépendances:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)  # Arrête le script si l'installation échoue
    else:
        print(result.stdout)  # Montre le résultat de pip
        print("--- Dépendances installées avec succès ---")

    # === ÉTAPE 2: LANCER L'APPLICATION (SERVEUR + WATCHER) ===
    print("\n--- 2/2 : Lancement de l'application (Serveur + Watcher) ---")
    print("--- Les logs des deux scripts vont s'afficher ci-dessous ---")
    print("--- Appuyez sur Ctrl+C pour arrêter TOUS les processus ---")

    # On appelle honcho via son module Python
    honcho_command = [sys.executable, "-m", "honcho", "start"]

    try:
        # subprocess.call va lancer honcho et afficher ses logs
        # en direct dans ce terminal. Il bloque jusqu'à ce que tu l'arrêtes.
        subprocess.call(honcho_command)
    except KeyboardInterrupt:
        print("\n--- Arrêt de l'application demandé par l'utilisateur ---")
    except Exception as e:
        print(f"\nERREUR: Impossible de lancer 'honcho'.")
        print(f"Assure-toi qu'il est bien dans requirements.txt et installé.")
        print(f"Détail: {e}")


if __name__ == "__main__":
    main()