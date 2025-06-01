import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.data_manager import SkinsMaestra, PreciosHistoricos, Base # Asegúrate que Base está disponible o usa el Engine directamente

# Configurar un logger simple para este script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///cs2_trading.db"

def inspect_database():
    logger.info(f"Conectando a la base de datos: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        logger.info("--- Inspeccionando tabla 'skins_maestra' (primeros 5 registros) ---")
        skins = db.query(SkinsMaestra).limit(5).all()
        if skins:
            for skin in skins:
                logger.info(f"  ID: {skin.id}, Name: {skin.name}, MarketHashName: {skin.market_hash_name}, Type: {skin.type}, Exterior: {skin.exterior}")
        else:
            logger.info("  No se encontraron registros en 'skins_maestra'.")

        logger.info("\n--- Inspeccionando tabla 'precios_historicos' (primeros 10 registros) ---")
        prices = db.query(PreciosHistoricos).limit(10).all()
        if prices:
            for price in prices:
                logger.info(f"  ID: {price.id}, SkinID: {price.skin_id}, Price: {price.price:.2f} {price.currency}, Timestamp: {price.timestamp}, Source: {price.fuente_api}")
        else:
            logger.info("  No se encontraron registros en 'precios_historicos'.")
            
        # Contar registros
        total_skins = db.query(SkinsMaestra).count()
        total_prices = db.query(PreciosHistoricos).count()
        logger.info(f"\n--- Conteo Total ---")
        logger.info(f"Total skins en 'skins_maestra': {total_skins}")
        logger.info(f"Total precios en 'precios_historicos': {total_prices}")

    except Exception as e:
        logger.error(f"Error durante la inspección de la base de datos: {e}", exc_info=True)
    finally:
        logger.info("Cerrando sesión de base de datos.")
        db.close()

if __name__ == "__main__":
    inspect_database() 