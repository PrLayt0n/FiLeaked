from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import io, zipfile

import models, config
from models import Distribution, DistributionFile
from routes.auth import get_api_token
from fastapi.responses import FileResponse, StreamingResponse

router = APIRouter()

@router.get("/admin/distributions")
def list_distributions(db: Session = Depends(models.SessionLocal), token: str = Depends(get_api_token)):
    """
    Renvoie la liste de toutes les distributions passées, avec leurs destinataires.
    """
    distributions = db.query(Distribution).order_by(Distribution.date.desc()).all()
    result = []
    for dist in distributions:
        result.append({
            "id": dist.id,
            "file_name": dist.file_name,
            "file_type": dist.file_type,
            "date": dist.date.strftime("%Y-%m-%d %H:%M:%S"),
            "recipients": [df.recipient for df in dist.files]
        })
    return result

@router.get("/admin/download/{file_id}")
def download_distributed_file(file_id: int, token: str = Depends(get_api_token)):
    """
    Télécharge un fichier distribué spécifique (copie fingerprintée) par son ID.
    """
    # Rechercher le fichier en base
    session = models.SessionLocal()
    dist_file = session.query(DistributionFile).get(file_id)
    session.close()
    if not dist_file:
        raise HTTPException(status_code=404, detail="Fichier non trouvé.")
    # Vérifier que le fichier existe sur le disque
    file_path = dist_file.file_path
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur.")
    # Envoyer le fichier
    return FileResponse(file_path, media_type="application/octet-stream", filename=os.path.basename(file_path))

@router.get("/admin/distributions/{dist_id}/download")
def download_distribution_zip(dist_id: int, db: Session = Depends(models.SessionLocal), token: str = Depends(get_api_token)):
    """
    Crée et renvoie un ZIP contenant tous les fichiers distribués pour une distribution donnée.
    """
    dist = db.query(Distribution).get(dist_id)
    if not dist:
        raise HTTPException(status_code=404, detail="Distribution introuvable.")
    # Préparer un ZIP en mémoire
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w") as zipf:
        for dist_file in dist.files:
            if dist_file.file_path and os.path.isfile(dist_file.file_path):
                zipf.write(dist_file.file_path, arcname=os.path.basename(dist_file.file_path))
    if len(dist.files) == 0:
        raise HTTPException(status_code=404, detail="Aucun fichier dans cette distribution.")
    zip_buffer.seek(0)
    # Nom du zip incluant l'ID ou le nom du fichier original
    zip_name = f"distribution_{dist.id}.zip"
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={zip_name}"})
