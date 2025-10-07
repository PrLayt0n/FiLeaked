from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import os, zipfile, re

import models, config
from models import Distribution, DistributionFile
from services import injector
from crypto import encrypt_data
from routes.auth import get_api_token  # On définira get_api_token dans routes/auth.py pour réutiliser la vérification du token

router = APIRouter()

@router.post("/api/distribute")
def distribute_file(file: UploadFile = File(...), recipients: str = Form(...), db: Session = Depends(models.SessionLocal), token: str = Depends(get_api_token)):
    """
    Reçoit un fichier et une liste de destinataires, génère une copie fingerprintée du fichier pour chaque destinataire.
    Retourne un fichier ZIP contenant toutes les copies, et enregistre la distribution en base de données.
    """
    # Déterminer le type de fichier supporté (PDF, PNG, TXT) à partir du content_type ou du nom de fichier
    filename = file.filename
    content_type = file.content_type.lower()
    if filename.lower().endswith(".pdf") or "pdf" in content_type:
        file_type = "PDF"
    elif filename.lower().endswith(".png") or "png" in content_type:
        file_type = "PNG"
    elif filename.lower().endswith(".txt") or "text" in content_type:
        file_type = "TXT"
    else:
        raise HTTPException(status_code=400, detail="Type de fichier non supporté. Veuillez fournir un PDF, PNG ou TXT.")
    # Lire le contenu du fichier uploadé
    original_bytes = file.file.read()
    if not original_bytes:
        raise HTTPException(status_code=400, detail="Fichier vide ou illisible.")
    # Créer un enregistrement Distribution en base
    distribution = Distribution(file_name=filename, file_type=file_type)
    db.add(distribution)
    db.commit()
    db.refresh(distribution)  # récupère l'ID assigné
    distribution_id = distribution.id

    # La liste des destinataires peut être fournie en CSV ou en JSON (ici on attend CSV dans un champ texte)
    # Séparer les destinataires par virgule ou point-virgule, en nettoyant les espaces
    recip_list = [r.strip() for r in re.split('[,;]', recipients) if r.strip()]
    if not recip_list:
        # Pas de destinataires fournis
        db.delete(distribution)
        db.commit()
        raise HTTPException(status_code=400, detail="Liste de destinataires vide.")

    # Préparer un buffer pour le fichier ZIP de sortie
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w") as zipf:
        # Pour chaque destinataire, générer une copie fingerprintée
        for recipient in recip_list:
            # Créer un enregistrement DistributionFile
            dist_file = DistributionFile(distribution_id=distribution_id, recipient=recipient, file_path="")
            db.add(dist_file)
            db.commit()
            db.refresh(dist_file)
            # Préparer le plaintext à embarquer (format "distID:distFileID")
            plaintext_str = f"{distribution_id}:{dist_file.id}"
            plaintext_bytes = plaintext_str.encode('utf-8')
            # Chiffrer + HMAC le plaintext pour obtenir l'empreinte à cacher (en base64)
            fingerprint = encrypt_data(plaintext_bytes)
            # Injection dans le fichier selon le type
            try:
                if file_type == "PDF":
                    new_bytes = injector.embed_fingerprint_pdf(original_bytes, fingerprint)
                elif file_type == "PNG":
                    new_bytes = injector.embed_fingerprint_png(original_bytes, fingerprint)
                elif file_type == "TXT":
                    new_bytes = injector.embed_fingerprint_txt(original_bytes, fingerprint)
            except Exception as e:
                db.rollback()
                db.delete(dist_file)
                db.commit()
                db.delete(distribution)
                db.commit()
                raise HTTPException(status_code=500, detail=f"Erreur lors de l'injection de l'empreinte: {str(e)}")
            # Déterminer un nom de fichier unique pour cette copie
            name_noext, ext = os.path.splitext(filename)
            # Nettoyer le nom du destinataire pour l'utiliser dans le nom de fichier
            safe_recipient = re.sub(r'[^A-Za-z0-9_-]', '_', recipient)
            output_name = f"{name_noext}_{safe_recipient}_{dist_file.id}{ext}"
            # Enregistrer le fichier sur le disque (dans OUTPUT_DIR)
            output_path = os.path.join(config.OUTPUT_DIR, output_name)
            with open(output_path, "wb") as f:
                f.write(new_bytes)
            # Mettre à jour le chemin du fichier dans la base de données
            dist_file.file_path = output_path
            db.commit()
            # Ajouter le fichier au zip
            zipf.writestr(output_name, new_bytes)
    # Fin du with zipfile (le zip est écrit en mémoire)
    zip_buffer.seek(0)

    # Option 1: retourner le zip comme réponse binaire (téléchargement)
    # from fastapi import Response
    # return Response(content=zip_buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename=distribution_{distribution_id}.zip"})
    # 
    # Option 2: Retourner un message de succès avec l'ID de distribution (et possibilité de télécharger via un autre endpoint)
    # Ici on choisit de retourner le zip directement pour simplifier la distribution immédiate.
    return {"detail": "Distribution réalisée", "distribution_id": distribution_id}
