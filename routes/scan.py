from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from routes.auth import get_api_token
from services import extractor

router = APIRouter()

@router.post("/api/scan")
def scan_file(file: UploadFile = File(...), db: Session = Depends(models.SessionLocal), token: str = Depends(get_api_token)):
    """
    Analyse un fichier uploadé pour détecter une empreinte de fuite.
    Retourne l'identité du destinataire d'origine si une empreinte valide est trouvée.
    """
    filename = file.filename
    content_type = file.content_type.lower()
    # Identifier le type du fichier suspect
    if filename.lower().endswith(".pdf") or "pdf" in content_type:
        file_type = "PDF"
    elif filename.lower().endswith(".png") or "png" in content_type:
        file_type = "PNG"
    elif filename.lower().endswith(".txt") or "text" in content_type:
        file_type = "TXT"
    else:
        raise HTTPException(status_code=400, detail="Type de fichier non supporté pour scan.")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fichier vide ou illisible.")
    # Tenter d'identifier la fuite
    result = extractor.identify_leak(data, file_type, db)
    if not result:
        return {"status": "not_found", "message": "Aucune empreinte détectée ou empreinte invalide."}
    # Si trouvé, result est un tuple (Distribution, DistributionFile)
    distribution, dist_file = result
    return {
        "status": "found",
        "distribution_id": distribution.id,
        "file_name": distribution.file_name,
        "date": str(distribution.date),
        "recipient": dist_file.recipient
    }
