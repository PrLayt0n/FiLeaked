import os, base64, hashlib, hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# On importe les paramètres de config, notamment MASTER_SECRET
import config

# Dérivation de deux clés (une pour AES-GCM, une pour HMAC) à partir du MASTER_SECRET
# On utilise SHA-512 pour générer 64 octets, dont 32 pour AES (256 bits) et 32 pour HMAC.
_secret_bytes = config.MASTER_SECRET.encode('utf-8')
_key_material = hashlib.sha512(_secret_bytes).digest()
KEY_ENC = _key_material[:32]   # Clé de 256 bits pour AES-GCM
KEY_HMAC = _key_material[32:]  # Clé de 256 bits pour HMAC-SHA256

# Initialisation de l'objet AES-GCM (de la librairie cryptography) avec la clé de chiffrement.
aesgcm = AESGCM(KEY_ENC)

def encrypt_data(plaintext: bytes) -> str:
    """
    Chiffre des données brutes avec AES-GCM + HMAC.
    - Calcule le HMAC-SHA256 du plaintext et l'attache.
    - Chiffre le plaintext+HMAC avec AES-GCM.
    - Concatène IV + ciphertext + tag, encode en base64 et retourne la chaîne.
    """
    # Calcul du HMAC-SHA256 du plaintext
    mac = hmac.new(KEY_HMAC, plaintext, digestmod="sha256").digest()
    # On combine le plaintext et le HMAC avant chiffrement
    data_to_encrypt = plaintext + mac
    # Génération d'un vecteur d'initialisation (IV) aléatoire de 12 octets (96 bits):contentReference[oaicite:0]{index=0}
    iv = os.urandom(12)
    # Chiffrement AES-GCM (le ciphertext retourné inclut le tag d'authentification de 16 octets):contentReference[oaicite:1]{index=1}
    ciphertext = aesgcm.encrypt(iv, data_to_encrypt, None)
    # Construction du blob final: IV (12o) + ciphertext+tag
    encrypted_blob = iv + ciphertext
    # Encodage en base64 pour produire une chaîne ASCII à cacher dans les fichiers
    return base64.b64encode(encrypted_blob).decode('utf-8')

def decrypt_data(encoded: str) -> bytes:
    """
    Déchiffre une chaîne base64 produite par encrypt_data.
    - Renvoie les données plaintext originales si HMAC est valide.
    - Lève une exception si le tag GCM ou le HMAC est invalide.
    """
    # Décodage base64 → octets
    blob = base64.b64decode(encoded)
    # Séparation IV et ciphertext+tag
    iv = blob[:12]
    ciphertext = blob[12:]
    # Tentative de déchiffrement AES-GCM (lève une exception si le tag d'authenticité ne correspond pas):contentReference[oaicite:2]{index=2}
    data_with_mac = aesgcm.decrypt(iv, ciphertext, None)
    # Séparation du plaintext et du HMAC
    if len(data_with_mac) < 32:
        raise ValueError("Données déchiffrées trop courtes pour contenir un HMAC.")
    plaintext = data_with_mac[:-32]
    mac = data_with_mac[-32:]
    # Vérification du HMAC
    expected_mac = hmac.new(KEY_HMAC, plaintext, digestmod="sha256").digest()
    if not hmac.compare_digest(mac, expected_mac):
        # Si le HMAC ne correspond pas, on considère l'empreinte invalide/tampered.
        raise ValueError("HMAC invalide ou données altérées.")
    return plaintext
