import io, os, re
from PIL import Image
import fitz  # PyMuPDF for PDF manipulation

import config
import crypto

# Caractères invisibles utilisés pour le tatouage des fichiers texte
ZERO_WIDTH_0 = '\u200B'  # Zero-width space (représente un bit 0)
ZERO_WIDTH_1 = '\u200C'  # Zero-width non-joiner (représente un bit 1)

def embed_fingerprint_pdf(pdf_bytes: bytes, fingerprint: str) -> bytes:
    """
    Insère l'empreinte (chaîne base64) dans un PDF:
    - Ajoute un champ de métadonnées 'fingerprint' dans le document PDF.
    - Insère le texte de l'empreinte de manière invisible sur la première page (texte blanc).
    Retourne les bytes du PDF modifié.
    """
    # Ouvrir le PDF en mémoire avec PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    # 1. Injection dans les métadonnées du PDF
    metadata = doc.metadata
    metadata["fingerprint"] = fingerprint
    doc.set_metadata(metadata)
    # 2. Injection d'un texte invisible sur la première page
    try:
        page = doc[0]
    except Exception:
        # Si le PDF est vide ou invalide
        raise ValueError("PDF invalide ou sans page pour insertion.")
    # Choisir une position pour le texte (par ex coin en haut à gauche)
    insert_position = fitz.Point(10, 10)
    # Insérer le texte avec une police de petite taille en blanc (couleur (1,1,1) => blanc)
    page.insert_text(insert_position, fingerprint, fontsize=5, color=(1, 1, 1))
    # Récupérer le PDF modifié en bytes
    pdf_output = doc.write()  # PyMuPDF: renvoie le PDF modifié en mémoire:contentReference[oaicite:3]{index=3}
    doc.close()
    return pdf_output

def embed_fingerprint_png(image_bytes: bytes, fingerprint: str) -> bytes:
    """
    Insère l'empreinte (chaîne base64) dans une image PNG par stéganographie LSB.
    - Encode la longueur de l'empreinte puis les bits de l'empreinte dans les bits de poids faible des pixels.
    - Retourne les bytes de l'image PNG modifiée.
    """
    # Ouvrir l'image en mémoire avec PIL
    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGBA")  # s'assurer d'avoir 4 canaux (RGBA) pour homogénéité
    pixels = image.load()
    width, height = image.size

    # Préparer les bits à cacher
    # Convertir la chaîne fingerprint (base64) en bits (8 bits par caractère)
    fingerprint_bytes = fingerprint.encode('ascii')
    data_bits = []
    # 16 bits en en-tête pour la longueur de la chaîne (nombre de caractères)
    length = len(fingerprint_bytes)
    if length > 65535:
        raise ValueError("Empreinte trop longue à insérer dans l'image.")
    for i in range(15, -1, -1):
        data_bits.append((length >> i) & 1)
    # Bits des données (base64 en ASCII)
    for byte in fingerprint_bytes:
        for i in range(7, -1, -1):
            data_bits.append((byte >> i) & 1)

    # Vérifier la capacité de l'image (chaque pixel RGBA a 4 canaux, on utilise 1 bit par pixel ici pour simplicité)
    num_pixels = width * height
    if len(data_bits) > num_pixels:
        raise ValueError("Image trop petite pour contenir l'empreinte.")
    # Injecter les bits un par un dans le LSB de chaque pixel (canal Rouge par exemple)
    bit_index = 0
    for y in range(height):
        for x in range(width):
            if bit_index >= len(data_bits):
                break
            r, g, b, a = pixels[x, y]
            # Modifier le LSB du canal rouge selon le bit courant
            new_r = (r & 0xFE) | data_bits[bit_index]  # met le LSB à 0 puis ajoute le bit
            pixels[x, y] = (new_r, g, b, a)
            bit_index += 1
        if bit_index >= len(data_bits):
            break

    # Sauvegarder l'image modifiée en PNG dans un buffer mémoire
    output_buffer = io.BytesIO()
    image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()

def embed_fingerprint_txt(text_bytes: bytes, fingerprint: str) -> bytes:
    """
    Insère l'empreinte (chaîne base64) dans un fichier texte en utilisant des caractères invisibles (zéro-width).
    - Les bits du texte base64 sont encodés en une séquence de U+200B et U+200C.
    - La séquence est ajoutée en fin de fichier, précédée d'une nouvelle ligne.
    """
    # Décoder le texte d'entrée en UTF-8 (en supposant encodage UTF-8 ou ASCII)
    try:
        text = text_bytes.decode('utf-8')
    except UnicodeDecodeError:
        text = text_bytes.decode('latin-1', errors='ignore')
    # Supprimer les espaces et sauts de ligne de fin pour insérer proprement
    text = text.rstrip()
    # Préparer les bits de la chaîne fingerprint (base64)
    fingerprint_bytes = fingerprint.encode('ascii')
    data_bits = []
    # Encodage de la longueur sur 16 bits (nombre de caractères de la chaîne fingerprint)
    length = len(fingerprint_bytes)
    if length > 65535:
        raise ValueError("Empreinte trop longue à insérer dans le texte.")
    for i in range(15, -1, -1):
        data_bits.append((length >> i) & 1)
    # Bits des données (chaque caractère ASCII codé sur 8 bits)
    for byte in fingerprint_bytes:
        for i in range(7, -1, -1):
            data_bits.append((byte >> i) & 1)
    # Construire la séquence de caractères invisibles correspondante
    hidden_seq = ''.join([ZERO_WIDTH_0 if bit == 0 else ZERO_WIDTH_1 for bit in data_bits])
    # Ajouter la séquence cachée dans le texte, après une nouvelle ligne pour isolement
    text_with_hidden = text + "\n" + hidden_seq
    # Retourner les bytes UTF-8 du texte modifié
    return text_with_hidden.encode('utf-8')
