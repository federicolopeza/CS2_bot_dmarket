from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, Session, DeclarativeBase
import datetime
from datetime import timezone
import logging

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///./cs2_trading.db"  # Se usará un archivo SQLite local

class Base(DeclarativeBase):
    pass

class SkinsMaestra(Base):
    __tablename__ = "skins_maestra"

    id = Column(Integer, primary_key=True, index=True)
    market_hash_name = Column(String, unique=True, index=True, nullable=False) # Identificador único de DMarket
    name = Column(String, index=True) # Nombre legible
    game_id = Column(String, default="a8db") # CS2 en DMarket
    type = Column(String, nullable=True) # Ej: Knife, Rifle
    exterior = Column(String, nullable=True) # Ej: Factory New
    rarity = Column(String, nullable=True) # Ej: Covert
    image_url = Column(Text, nullable=True)

    precios = relationship("PreciosHistoricos", back_populates="skin")

    def __repr__(self):
        return f"<SkinsMaestra(market_hash_name='{self.market_hash_name}')>"

class PreciosHistoricos(Base):
    __tablename__ = "precios_historicos"

    id = Column(Integer, primary_key=True, index=True)
    skin_id = Column(Integer, ForeignKey("skins_maestra.id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), nullable=False)
    price = Column(Float, nullable=False) # Precio en la moneda especificada
    currency = Column(String, default="USD", nullable=False) # Moneda del precio
    volume = Column(Integer, nullable=True) # Volumen de transacciones si está disponible
    fuente_api = Column(String, default="DMarket", nullable=False) # Fuente de los datos

    skin = relationship("SkinsMaestra", back_populates="precios")

    def __repr__(self):
        return f"<PreciosHistoricos(skin_id={self.skin_id}, price={self.price}, timestamp='{self.timestamp}')>"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Inicializa la base de datos creando todas las tablas."""
    Base.metadata.create_all(bind=engine)
    logger.info("Base de datos inicializada y tablas creadas (si no existían).")

def get_db():
    """Generador para obtener una sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_or_update_skin(db: Session, skin_info: dict) -> SkinsMaestra:
    """Añade una nueva skin o actualiza una existente si ya se encuentra en la BD.

    Args:
        db: Sesión de SQLAlchemy.
        skin_info: Diccionario con la información de la skin. Debe contener al menos 'market_hash_name'.
                   Campos opcionales: 'name', 'type', 'exterior', 'rarity', 'image_url'.

    Returns:
        La instancia de SkinsMaestra creada o actualizada.
    """
    market_hash_name = skin_info.get("market_hash_name")
    if not market_hash_name:
        raise ValueError("market_hash_name es requerido para añadir o actualizar una skin.")

    skin = db.query(SkinsMaestra).filter(SkinsMaestra.market_hash_name == market_hash_name).first()

    if skin:
        # Actualizar skin existente
        skin.name = skin_info.get("name", skin.name)
        skin.type = skin_info.get("type", skin.type)
        skin.exterior = skin_info.get("exterior", skin.exterior)
        skin.rarity = skin_info.get("rarity", skin.rarity)
        skin.image_url = skin_info.get("image_url", skin.image_url)
        # game_id se mantiene con su valor por defecto o el existente
    else:
        # Crear nueva skin
        skin = SkinsMaestra(
            market_hash_name=market_hash_name,
            name=skin_info.get("name"),
            type=skin_info.get("type"),
            exterior=skin_info.get("exterior"),
            rarity=skin_info.get("rarity"),
            image_url=skin_info.get("image_url")
            # game_id tomará el valor por defecto "a8db"
        )
        db.add(skin)
    
    db.commit()
    db.refresh(skin)
    return skin

def add_price_record(db: Session, skin_id: int, price_data: dict) -> PreciosHistoricos:
    """Añade un nuevo registro de precio para una skin.

    Args:
        db: Sesión de SQLAlchemy.
        skin_id: ID de la skin en la tabla SkinsMaestra.
        price_data: Diccionario con la información del precio. Debe contener 'price'.
                    Campos opcionales: 'currency' (default 'USD'), 'volume'.

    Returns:
        La instancia de PreciosHistoricos creada.
    """
    price = price_data.get("price")
    if price is None:
        raise ValueError("El campo 'price' es requerido para añadir un registro de precio.")

    new_price = PreciosHistoricos(
        skin_id=skin_id,
        price=price,
        currency=price_data.get("currency", "USD"),
        volume=price_data.get("volume"),
        timestamp=datetime.datetime.now(timezone.utc)
        # fuente_api tomará el valor por defecto "DMarket"
    )
    db.add(new_price)
    db.commit()
    db.refresh(new_price)
    return new_price

# Funciones de consulta

def get_skin_by_market_hash_name(db: Session, market_hash_name: str) -> SkinsMaestra | None:
    """Obtiene una skin por su market_hash_name."""
    return db.query(SkinsMaestra).filter(SkinsMaestra.market_hash_name == market_hash_name).first()

def get_skin_by_id(db: Session, skin_id: int) -> SkinsMaestra | None:
    """Obtiene una skin por su ID."""
    return db.query(SkinsMaestra).filter(SkinsMaestra.id == skin_id).first()

def get_latest_price_for_skin(db: Session, skin_id: int) -> PreciosHistoricos | None:
    """Obtiene el último registro de precio para una skin específica, ordenado por timestamp descendente."""
    return (
        db.query(PreciosHistoricos)
        .filter(PreciosHistoricos.skin_id == skin_id)
        .order_by(PreciosHistoricos.timestamp.desc())
        .first()
    )

def get_price_history_for_skin(db: Session, skin_id: int, limit: int = 100) -> list[PreciosHistoricos]:
    """Obtiene el historial de precios para una skin específica, limitado por `limit`.
       Los resultados se ordenan por timestamp descendente (más reciente primero).
    """
    return (
        db.query(PreciosHistoricos)
        .filter(PreciosHistoricos.skin_id == skin_id)
        .order_by(PreciosHistoricos.timestamp.desc())
        .limit(limit)
        .all()
    )

if __name__ == "__main__":
    # Esto se puede ejecutar para crear la base de datos manualmente si es necesario.
    # Por ejemplo: python core/data_manager.py
    print("Creando base de datos y tablas...")
    init_db()
    print("Proceso completado.") 