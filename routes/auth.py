from fastapi import Header, HTTPException
import config

def get_api_token(authorization: str = Header(None)):
    """
    Dépendance FastAPI pour vérifier la présence d'un jeton API valide.
    On attend un header "Authorization: Bearer <TOKEN>".
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Token API invalide.")
    return token
