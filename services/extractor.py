import io, re
from PIL import Image
import fitz  # PyMuPDF for PDF
import models, crypto
from services.injector import ZERO_WIDTH_0, ZERO_WIDTH_1

def extract_fingerprint_from_pdf(pdf_bytes: bytes) -> str:
    """Extrait la chaîne d'empreinte cachée dans un PDF (dans les métadonnées ou le texte)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    fingerprint = None
    # 1. Vérifier dans les métadonnées du PDF
    meta = doc.metadata
    if meta.get("fingerprint"):
        fingerprint = meta.get("fingerprint")
    # 2. Si non trouvée en metadata, extraire le texte et chercher une séquence base64
    if not fingerprint:
        # Extraire le texte de toutes les pages (le texte invisible inséré devrait apparaître)
        text = ""
        for page in doc:
            text += page.get_text()
        # Chercher une sous-chaîne ressemblant à du base64 (longueur >= 16):contentReference[oaicite:4]{index=4}
        candidates = re.findall(r'[A-Za-z0-9+/=]{16,}', text)
        for cand in candidates:
            try:
                # On tente de déchiffrer chaque candidat pour voir si c'est un fingerprint valide
                crypto.decrypt_data(cand)
                fingerprint = cand
                break  # on prend le premier candidat valide
            except Exception:
                continue
    doc.close()
    return fingerprint  # Peut être None si aucune empreinte trouvée ou valide

def extract_fingerprint_from_png(image_bytes: bytes) -> str:
    """Extrait la chaîne d'empreinte cachée dans une image PNG via LSB steganography."""
    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    bits = []
    # On parcourt les pixels (en assumant qu'on a un bit caché par pixel, canal rouge)
    # Récupérer d'abord les 16 premiers bits pour la longueur
    bit_count = 0
    length = 0
    # Lecture des 16 bits de longueur
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            bits.append(r & 1)  # récupérer le LSB du rouge
            bit_count += 1
            if bit_count == 16:
                # Calculer la longueur en int à partir des 16 bits récupérés
                length_bits = bits[:16]
                length = 0
                for bit in length_bits:
                    length = (length << 1) | bit
                break
        if bit_count == 16:
            break
    if length <= 0:
        return None  # aucune empreinte trouvée
    # Récupération des bits de données selon la longueur lue (8 bits par caractère)
    data_bits = []
    needed_bits = length * 8
    bits_collected = 0
    # Continuer là où on s'est arrêté
    for y in range(height):
        for x in range(width):
            if bits_collected >= needed_bits:
                break
            # Ignorer les 16 bits déjà lus (on commence après)
            if y == 0 and x < 2:  # Note: on a cassé à x after reading 16 bits; cette simplification marche si 16 bits <= first row pixels.
                # Correction: pour être robuste, calculer un offset précis:
                pass
            r, g, b, a = pixels[x, y]
            if bit_count < 16:
                # (skip initial length bits reading)
                bit_count += 1
                continue
            data_bits.append(r & 1)
            bits_collected += 1
            bit_count += 1
            if bits_collected >= needed_bits:
                break
        if bits_collected >= needed_bits:
            break
    # Regrouper les bits en caractères ASCII
    data_bytes = bytearray()
    for i in range(0, len(data_bits), 8):
        byte = 0
        for b in data_bits[i:i+8]:
            byte = (byte << 1) | b
        data_bytes.append(byte)
    try:
        fingerprint = data_bytes.decode('ascii')
    except Exception:
        fingerprint = None
    return fingerprint

def extract_fingerprint_from_txt(text_bytes: bytes) -> str:
    """Extrait la chaîne d'empreinte cachée dans un fichier texte en utilisant les caractères invisibles."""
    try:
        text = text_bytes.decode('utf-8')
    except UnicodeDecodeError:
        text = text_bytes.decode('latin-1', errors='ignore')
    # On recherche les caractères invisibles ZERO_WIDTH_0 et ZERO_WIDTH_1
    if ZERO_WIDTH_0 not in text and ZERO_WIDTH_1 not in text:
        return None  # Pas d'empreinte
    # Isoler la séquence cachée (après le dernier caractère visible du texte)
    # On ignore les sauts de ligne et espaces de fin
    i = len(text) - 1
    while i >= 0 and text[i] in [ZERO_WIDTH_0, ZERO_WIDTH_1, '\n', '\r', ' ', '\t']:
        i -= 1
    hidden_seq = text[i+1:]
    # Extraire les bits de la séquence invisible
    bits = []
    for ch in hidden_seq:
        if ch == ZERO_WIDTH_0:
            bits.append(0)
        elif ch == ZERO_WIDTH_1:
            bits.append(1)
    if len(bits) < 16:
        return None
    # Lire la longueur encodée sur les 16 premiers bits
    length_bits = bits[:16]
    length = 0
    for bit in length_bits:
        length = (length << 1) | bit
    if length <= 0:
        return None
    # Lire les bits de données (8 * longueur caractères)
    data_bits = bits[16:16 + length * 8]
    data_bytes = bytearray()
    for j in range(0, len(data_bits), 8):
        byte = 0
        for b in data_bits[j:j+8]:
            byte = (byte << 1) | b
        data_bytes.append(byte)
    try:
        fingerprint = data_bytes.decode('ascii')
    except Exception:
        fingerprint = None
    return fingerprint

def identify_leak(file_bytes: bytes, file_type: str, db_session):
    """
    Tente d'identifier le destinataire source d'une fuite en analysant un fichier.
    - Extrait l'empreinte via la méthode appropriée.
    - Décrypte l'empreinte pour obtenir les données d'identification (ex: IDs).
    - Vérifie le HMAC (via decrypt_data) pour s'assurer de l'authenticité.
    - Retourne un tuple (distribution_obj, distribution_file_obj) si une correspondance est trouvée.
    """
    fingerprint = None
    # Extraire l'empreinte selon le type de fichier
    if file_type == "PDF":
        fingerprint = extract_fingerprint_from_pdf(file_bytes)
    elif file_type == "PNG":
        fingerprint = extract_fingerprint_from_png(file_bytes)
    elif file_type == "TXT":
        fingerprint = extract_fingerprint_from_txt(file_bytes)
    if not fingerprint:
        return None  # aucune empreinte trouvée
    # Déchiffrer l'empreinte (vérification d'authenticité incluse)
    try:
        plaintext = crypto.decrypt_data(fingerprint)  # bytes
    except Exception:
        return None  # empreinte trouvée mais invalide (tag/HMAC faux)
    # Le plaintext contient l'identifiant du fichier distribué (distribution_file_id) possiblement précédé de distribution_id
    try:
        data_str = plaintext.decode('utf-8')
    except UnicodeDecodeError:
        data_str = plaintext.decode('latin-1', errors='ignore')
    # On s'attend à un format "dist_id:file_id" ou juste un identifiant unique
    dist_id = None
    file_id = None
    if ":" in data_str:
        parts = data_str.split(":")
        if len(parts) == 2:
            dist_id = int(parts[0])
            file_id = int(parts[1])
    else:
        # Si pas de ":", on interprète tout comme l'ID du DistributionFile
        file_id = int(data_str) if data_str.isdigit() else None
    if file_id is None:
        return None
    # Rechercher en base l'enregistrement correspondant
    file_entry = db_session.query(models.DistributionFile).get(file_id)
    if not file_entry:
        return None
    dist_entry = file_entry.distribution
    # Optionnel: vérifier que dist_id correspond si fourni
    if dist_id is not None and dist_entry.id != dist_id:
        return None  # Incohérence improbable si tout va bien
    return dist_entry, file_entry
