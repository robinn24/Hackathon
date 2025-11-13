import time
import os
import json
import requests
import pdfplumber  # Pour lire les PDF
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- 1. CONFIGURATION ---
# (Remplissez ces valeurs)

# Votre endpoint et clé API Azure (Mistral)
NOM_DU_DEPLOYEMENT = "gpt-5-mini"

# L'URL de base de votre ressource (elle a l'air correcte)
RESSOURCE_URL_BASE = "https://hachaton.cognitiveservices.azure.com"

# La clé API (c'est la clé de votre ressource Azure OpenAI)
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY_SECRET")

# L'API version (gardez celle de votre erreur)
API_VERSION = "2025-04-01-preview"

# --- NOUVELLE URL COMPLETE ---
# C'est le format standard pour le chat
AZURE_OPENAI_ENDPOINT_URL = f"{RESSOURCE_URL_BASE}/openai/deployments/{NOM_DU_DEPLOYEMENT}/chat/completions?api-version={API_VERSION}"

# Le dossier à surveiller
DOSSIER_CONTRATS = "Contracts"  # Le dossier contenant vos PDF

# Le fichier texte où stocker les commandes SQL
OUTPUT_SQL_FILE = "SQLCommands.txt"


# --- 2. FONCTIONS DE TRAVAIL ---

def extract_text_from_pdf(pdf_path):
    """Ouvre un PDF et en extrait tout le texte."""
    print(f"Lecture du PDF : {pdf_path}")
    full_text = ""
    try:
        # Attend une seconde pour être sûr que le fichier est déverrouillé
        time.sleep(1)
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        return full_text
    except Exception as e:
        print(f"Erreur lors de la lecture du PDF {pdf_path}: {e}")
        return None


def call_mistral_for_sql(texte_contrat):
    """Appelle l'IA pour extraire les données ET générer une commande SQL."""
    print("Appel de l'IA (Azure OpenAI Service) pour génération SQL...")

    # Ce prompt est la clé. Il demande à l'IA d'extraire ET de formater en SQL.
    prompt = f"""
    Tu es un assistant RH expert en SQL (SQLite). Analyse le contrat de travail suivant.

    ÉTAPE 1 : Extrais les informations suivantes en te basant sur le contrat :
    - first_name: Le prénom de l'employé.
    - last_name: Le nom de famille de l'employé.
    - weekly_hours_max: Le temps de travail hebdomadaire (juste le nombre, ex: 35).
    - contract_type: Le type de contrat. Il doit correspondre EXACTEMENT à une de ces valeurs : 'Full-time', 'Part-time', 'Intern', 'Contractor'. (Mets 'Full-time' si c'est un CDI 35h, 'Part-time' si c'est un temps partiel).

    ÉTAPE 2 : Utilise ces informations pour générer une commande SQL pour la table 'employees'.
    La syntaxe pour mettre à jour ou insérer est :
    INSERT INTO employees (first_name, last_name, weekly_hours_max, contract_type)
    VALUES ('Jean', 'Dupont', 35, 'Full-time')
    ON CONFLICT(first_name, last_name) DO UPDATE SET
    weekly_hours_max=excluded.weekly_hours_max,
    contract_type=excluded.contract_type;

    RÉPONSE : Ne retourne RIEN D'AUTRE que la commande SQL complète, en une seule ligne, terminée par un point-virgule.

    --- DEBUT CONTRAT ---
    {texte_contrat}
    --- FIN CONTRAT ---

    Commande SQL:
    """

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        # J'ai mis 1024, c'est suffisant pour cette requête
        "max_completion_tokens": 1024,
        # On remet temperature à 1 si votre modèle l'exige
        # "temperature": 1
    }

    # Si votre modèle n'accepte pas temperature, supprimez la ligne du dessus
    if "temperature" in payload and payload["temperature"] == 1:
        # On suppose que 1 est la valeur par défaut et peut être omis
        del payload["temperature"]

    # --- CHANGEMENT 2 : LES HEADERS ---
    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_OPENAI_KEY
    }

    try:
        # On appelle la NOUVELLE URL
        response = requests.post(AZURE_OPENAI_ENDPOINT_URL, data=json.dumps(payload), headers=headers)

        print(f"DEBUG: Code de statut de la réponse : {response.status_code}")
        print(f"DEBUG: Texte brut de la réponse : '{response.text}'")

        response.raise_for_status()  # Lève une exception si erreur HTTP (4xx, 5xx)

        result = response.json()  # C'est ici que l'erreur se produisait

        # --- CHANGEMENT 3 : LIRE LA REPONSE ---
        sql_command = result['choices'][0]['message']['content']

        # Nettoyer la réponse pour n'avoir que le SQL
        sql_command = sql_command.strip().replace("```sql", "").replace("```", "")

        # On vérifie qu'elle commence bien par INSERT
        if not sql_command.startswith("INSERT"):
            print(f"Erreur: L'IA n'a pas retourné une commande SQL valide. Réponse: {sql_command}")
            return None

        return sql_command

    except json.JSONDecodeError as e:
        print(f"ERREUR JSON : L'API a répondu (code {response.status_code}) mais pas avec du JSON.")
        print(f"Réponse brute qui a causé l'erreur : {response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERREUR HTTP : L'appel à l'API a échoué : {e}")
        if response is not None:
            print(f"Réponse brute de l'erreur : {response.text}")
        return None
    except KeyError:
        print(f"Erreur: La structure JSON de la réponse n'est pas celle attendue (pas de 'choices' ou 'message').")
        print(f"Réponse reçue : {result}")
        return None
    except Exception as e:
        print(f"Erreur inattendue lors de l'appel à l'IA : {e}")
        return None

def save_sql_to_file(sql_command):
    """Ajoute la commande SQL au fichier texte."""
    try:
        # "a" signifie "append" (ajouter à la fin du fichier)
        with open(OUTPUT_SQL_FILE, "a", encoding="utf-8") as f:
            f.write(sql_command + "\n\n")  # Ajoute la commande + 2 sauts de ligne
        print(f"Commande SQL ajoutée avec succès à {OUTPUT_SQL_FILE}")
    except IOError as e:
        print(f"Erreur lors de l'écriture dans le fichier {OUTPUT_SQL_FILE}: {e}")


# --- 3. LE "GARDIEN" (WATCHDOG) ---

class ContractHandler(FileSystemEventHandler):

    '''def on_created(self, event):
        """Appelé quand un fichier est CRÉÉ."""
        if not event.is_directory and event.src_path.endswith('.pdf'):
            print(f"Nouveau fichier détecté : {event.src_path}")
            self.process_file(event.src_path)'''

    def on_modified(self, event):
        """Appelé quand un fichier est MODIFIÉ."""
        if not event.is_directory and event.src_path.endswith('.pdf'):
            print(f"Fichier modifié détecté : {event.src_path}")
            self.process_file(event.src_path)

    def process_file(self, pdf_path):
        """Orchestre tout le processus pour un fichier."""
        # On ajoute un "verrou" pour être 100% sûr
        # de ne pas traiter le même fichier deux fois en 2 secondes

        # On crée un dictionnaire pour stocker les temps de traitement
        if not hasattr(self, 'last_processed_time'):
            self.last_processed_time = {}

        current_time = time.time()
        last_time = self.last_processed_time.get(pdf_path, 0)

        # Si le fichier a été traité il y a moins de 5 secondes, on ignore
        if current_time - last_time < 5.0:
            print(f"Ignoré (traité récemment) : {pdf_path}")
            return

        # On enregistre le moment où on commence ce traitement
        self.last_processed_time[pdf_path] = current_time

        try:
            # 1. Lire le PDF
            # (Note: le time.sleep(1) est déjà dans votre fonction extract_text_from_pdf)
            texte_contrat = extract_text_from_pdf(pdf_path)
            if not texte_contrat:
                return

            # 2. Appeler l'IA pour générer le SQL
            sql_command = call_mistral_for_sql(texte_contrat)
            if not sql_command:
                return

            print(f"SQL Généré : {sql_command}")

            # 3. Sauvegarder le SQL dans le fichier texte
            save_sql_to_file(sql_command)

        except Exception as e:
            print(f"Erreur lors du traitement du fichier {pdf_path} : {e}")
        finally:
            print(f"\n--- En attente du prochain changement ---")


# --- 4. SCRIPT PRINCIPAL ---

if __name__ == "__main__":
    # 1. Installer les dépendances :
    # pip install watchdog requests pdfplumber

    # 2. Lancer le gardien
    path = DOSSIER_CONTRATS
    event_handler = ContractHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)

    print(f"Surveillance du dossier '{path}' démarrée.")
    print(f"Les commandes SQL seront stockées dans '{OUTPUT_SQL_FILE}'.")
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
        print("Surveillance arrêtée.")
    observer.join()