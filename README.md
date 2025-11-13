# Hackathon

Voici les instructions simples pour démarrer le projet une fois le dépôt cloné.



Instructions de Démarrage

1\. Créer l'environnement virtuel

Pour isoler les paquets du projet, crée et active un environnement virtuel.



Bash

\# Va dans le dossier du projet

cd Hackaton



\# Crée l'environnement

python -m venv env



\# Active-le (choisis la commande pour ton OS)

\# Windows (cmd/PowerShell):

.\\env\\Scripts\\activate

\# Mac/Linux (bash/zsh):

source env/bin/activate



2\. Configurer la Clé API (le Fichier Secret)

Le script a besoin d'une clé API Azure pour fonctionner.



Copie le fichier .env.example et renomme la copie en .env.



Ouvre ce nouveau fichier .env et colle ta clé API.



Plaintext

\# Contenu de ton fichier .env

AZURE\_OPENAI\_KEY\_SECRET="colle-ta-cle-api-azure-ici"

3\. Lancer le Projet

C'est tout. Le script run.py s'occupe d'installer les dépendances et de lancer tous les services.



Execute la commande suivante dans ton terminal pour tout lancer :

python run.py (sur Windows)

python3 run.py (sur Mac/Linux)

Le terminal va d'abord installer les paquets (Flask, watchdog, etc.), puis afficher les logs du serveur web et du watcher en même temps.



Pour tout arrêter, appuie simplement sur Ctrl+C.

