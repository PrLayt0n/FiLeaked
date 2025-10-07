from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

import config

# Initialisation de l'ORM SQLAlchemy
engine = create_engine(config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Distribution(Base):
    """Modèle représentant un événement de distribution d'un fichier à des destinataires."""
    __tablename__ = "distributions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)    # Nom du fichier original distribué
    file_type = Column(String(10), nullable=False)     # Type de fichier ("PDF", "PNG", "TXT")
    date = Column(DateTime, default=datetime.utcnow)   # Date/heure de la distribution
    # Relation vers les copies distribuées (fichiers fingerprintés pour chaque destinataire)
    files = relationship("DistributionFile", back_populates="distribution", cascade="all, delete-orphan")

class DistributionFile(Base):
    """Modèle représentant un fichier distribué à un destinataire (une copie fingerprintée)."""
    __tablename__ = "distribution_files"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    distribution_id = Column(Integer, ForeignKey("distributions.id", ondelete="CASCADE"))
    recipient = Column(String(255), nullable=False)    # Identifiant du destinataire (nom ou email)
    file_path = Column(Text, nullable=False)           # Chemin du fichier généré sur le disque (empreinte)
    # Relation vers la distribution parent
    distribution = relationship("Distribution", back_populates="files")

# Création des tables dans la base de données si elles n'existent pas déjà
Base.metadata.create_all(bind=engine)
