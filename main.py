from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import config
from routes import distribute, scan, admin

# Initialisation de l'application FastAPI
app = FastAPI(title="Leak Detector", description="Service de fingerprinting de documents (PDF, PNG, TXT) pour traquer les fuites.")

# Middleware CORS (au besoin, par exemple si l'interface web est servie depuis une autre origine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routeurs d'API
app.include_router(distribute.router)
app.include_router(scan.router)
app.include_router(admin.router)

# Servir les fichiers statiques (interface web) - on suppose un dossier "static" avec index.html, script.js, style.css
app.mount("/", StaticFiles(directory="static", html=True), name="static")
