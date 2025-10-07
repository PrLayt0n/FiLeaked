import os

# Configuration globale du service

# Clé secrète maître utilisée pour l'encryption AES-GCM et le HMAC.
# Doit être une chaîne aléatoire suffisamment longue. On peut la définir via une variable d'environnement.
MASTER_SECRET = os.environ.get("MASTER_SECRET", "CHANGE_ME_MASTER_SECRET")

# Jeton API pour l'authentification des requêtes (par exemple un token admin).
API_TOKEN = os.environ.get("API_TOKEN", "CHANGE_ME_API_TOKEN")

# URL de connexion à la base de données PostgreSQL.
# Format: postgresql://user:password@host:port/database
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/leakdetector")

# Répertoire de sortie où seront enregistrés les fichiers fingerprintés générés.
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_files")

# Création du répertoire OUTPUT_DIR s'il n'existe pas
os.makedirs(OUTPUT_DIR, exist_ok=True)
