import logging
import os
import sys
from dotenv import load_dotenv

# Agregar el directorio padre al path para encontrar los módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dmarket_connector import DMarketAPI
from core.data_manager import get_db, add_or_update_skin, add_price_record, init_db
from utils.helpers import normalize_price_to_usd, normalize_skin_name
from utils.logger import configure_logging

# Definir logger a nivel de módulo
logger = logging.getLogger(__name__)

# Volver a definir API_KEY y API_SECRET a nivel de módulo para que puedan ser parcheadas
# en pruebas. Serán reasignadas en el bloque if __name__ == "__main__".
API_KEY = None
API_SECRET = None

# Constante para el ID del juego (CS2)
DEFAULT_GAME_ID = "a8db" 

def populate_dmarket_data():
    logger.info(f"Iniciando el proceso de población de datos de DMarket para el juego ID: {DEFAULT_GAME_ID}...")
    
    # Verificar claves API (que debieron ser cargadas desde el __main__)
    # y asignadas a las variables globales API_KEY y API_SECRET.
    if not API_KEY or not API_SECRET: # Estas son ahora las globales definidas en __main__
        logger.error("Claves API de DMarket no encontradas o no cargadas correctamente. Finalizando población.")
        return

    connector = DMarketAPI(public_key=API_KEY, secret_key=API_SECRET)
    db_session_gen = get_db()
    db = next(db_session_gen)

    # Inicializar contadores para el resumen de procesamiento
    summary_counters = {
        "paginas_solicitadas": 0,
        "items_validos_guardados": 0,
        "items_sin_titulo": 0,
        "items_sin_precio_usd": 0, # Incluye precios no dict o sin clave USD
        "items_con_error_conversion_precio": 0,
        "items_con_excepcion_general": 0
    }

    try:
        current_cursor = None
        max_pages_to_fetch = 2 # Limitar el número de páginas reales a obtener para esta prueba
        # pages_fetched ya está cubierto por summary_counters["paginas_solicitadas"]

        while True:
            summary_counters["paginas_solicitadas"] += 1
            logger.info(f"Solicitando página {summary_counters['paginas_solicitadas']} de DMarket (cursor: {current_cursor}) para el juego ID: {DEFAULT_GAME_ID}")
            
            response_data = connector.get_market_items(
                game_id=DEFAULT_GAME_ID, 
                currency="USD", 
                cursor=current_cursor, 
                limit=10 # Límite de ítems por página
            )

            if not response_data or "error" in response_data:
                logger.error(f"Error al obtener ítems de DMarket: {response_data.get('message', 'Error desconocido')}")
                # Podríamos añadir un contador para errores de API si quisiéramos diferenciar
                break

            items_on_page = response_data.get("objects", [])
            current_cursor = response_data.get("cursor")

            if not items_on_page:
                logger.info("No se obtuvieron más ítems en esta página.")
                if not current_cursor: # Doble check, si no hay items y no hay cursor, es el fin.
                    logger.info("Fin de la paginación (no hay ítems y no hay cursor).")
                    break
                # Si hay cursor pero no items, podría ser una página vacía antes del final, seguir por si acaso (o romper si DMarket garantiza items si hay cursor)
                # Por ahora, si hay cursor, continuamos por si acaso.
            
            # page_processed_count se usa para el log por página, summary_counters["items_validos_guardados"] es el total.
            # Mantenemos page_processed_count para el log informativo por página.
            page_processed_count = 0
            for item in items_on_page:
                try:
                    title = item.get('title') 
                    if not title:
                        logger.warning(f"Ítem omitido por falta de 'title': {item.get('itemId', 'ID Desconocido')}")
                        summary_counters["items_sin_titulo"] += 1
                        continue
                    
                    # Usar 'title' como market_hash_name y para el nombre normalizado
                    market_hash_name = title 
                    name_to_normalize = title
                    
                    price_dict = item.get('price')
                    price_value_str = None
                    currency = "USD" 
                    
                    if isinstance(price_dict, dict):
                        price_value_str = price_dict.get("USD")
                    
                    if price_value_str is None:
                        logger.warning(f"Precio USD no encontrado para {market_hash_name}. Datos de precio: {price_dict}")
                        summary_counters["items_sin_precio_usd"] += 1
                        continue # No se guarda skin si el precio USD no se puede determinar inicialmente
                    
                    image_url = item.get("image")
                    item_type = None
                    exterior = None
                    rarity = None
                    
                    extra_info = item.get("extra", {})
                    if isinstance(extra_info, dict):
                        exterior = extra_info.get("exterior")
                        item_type = extra_info.get("itemType")
                        rarity = extra_info.get("quality")

                    normalized_name = normalize_skin_name(name_to_normalize)
                    skin_info = {
                        "market_hash_name": market_hash_name,
                        "name": normalized_name,
                        "image_url": image_url,
                        "type": item_type,
                        "exterior": exterior,
                        "rarity": rarity
                    }
                    skin_db = add_or_update_skin(db, skin_info)
                    # logger.debug(f"Skin guardada/actualizada: {skin_db.market_hash_name}, ID: {skin_db.id}")

                    try:
                        price_float_cents = float(price_value_str)
                    except ValueError:
                        logger.warning(f"Valor de precio no es un número válido para {market_hash_name}: {price_value_str}")
                        summary_counters["items_con_error_conversion_precio"] += 1
                        continue # No se guarda precio, pero la skin sí (arriba)
                    
                    price_usd = normalize_price_to_usd(price_float_cents / 100.0, currency)

                    if price_usd is not None:
                        price_data = {"price": price_usd, "currency": "USD"}
                        add_price_record(db, skin_db.id, price_data)
                        # logger.debug(f"Precio guardado para {skin_db.market_hash_name}: {price_usd} USD")
                        page_processed_count += 1
                        summary_counters["items_validos_guardados"] += 1 # Ítem completo (skin y precio) guardado
                    else:
                        # Este caso es menos probable si pedimos USD y price_value_str estaba OK,
                        # a menos que normalize_price_to_usd tuviera lógica más compleja.
                        logger.warning(f"Precio no se pudo normalizar a USD para {market_hash_name}, moneda: {currency}")
                        # Podríamos añadir otro contador si esto fuera un caso común.

                except Exception as e:
                    logger.error(f"Error procesando ítem {item.get('title', 'Título Desconocido')}: {e}", exc_info=True)
                    summary_counters["items_con_excepcion_general"] += 1
            
            logger.info(f"Página {summary_counters['paginas_solicitadas']}: {page_processed_count} ítems procesados y guardados.")
            # all_processed_items_count ya está cubierto por summary_counters["items_validos_guardados"]

            if not current_cursor or (max_pages_to_fetch > 0 and summary_counters["paginas_solicitadas"] >= max_pages_to_fetch):
                if not current_cursor:
                    logger.info("Fin de la paginación (no hay más cursor).")
                else:
                    logger.info(f"Se alcanzó el límite de páginas a obtener ({max_pages_to_fetch}).")
                break

        logger.info(f"Proceso de población completado.")

    except Exception as e:
        logger.error(f"Error mayor durante la población de datos de DMarket: {e}", exc_info=True)
        # Podríamos añadir un contador para errores de este nivel si fuera necesario
    finally:
        logger.info("--- Resumen del Proceso de Población ---")
        logger.info(f"Juego procesado (ID): {DEFAULT_GAME_ID}")
        logger.info(f"Páginas solicitadas a DMarket: {summary_counters['paginas_solicitadas']}")
        logger.info(f"Ítems válidos (skin y precio) guardados: {summary_counters['items_validos_guardados']}")
        logger.info(f"Ítems omitidos por falta de título: {summary_counters['items_sin_titulo']}")
        logger.info(f"Ítems omitidos por falta de precio USD: {summary_counters['items_sin_precio_usd']}")
        logger.info(f"Ítems con error de conversión de precio (skin guardada, precio no): {summary_counters['items_con_error_conversion_precio']}")
        logger.info(f"Ítems con excepción general durante procesamiento: {summary_counters['items_con_excepcion_general']}")
        logger.info("----------------------------------------")
        
        logger.info("Cerrando sesión de base de datos.")
        try:
            next(db_session_gen)
        except StopIteration:
            pass
        db.close()

if __name__ == "__main__":
    configure_logging(log_level=logging.DEBUG) # Mantenido en DEBUG por ahora

    # # --- Inicio: Depuración del archivo .env (COMENTADO) ---
    # env_path = os.path.join(os.getcwd(), ".env")
    # logger.debug(f"Intentando leer el archivo .env desde: {env_path}")
    # try:
    #     with open(env_path, "r") as f:
    #         logger.debug("Contenido del archivo .env:")
    #         for line_number, line_content in enumerate(f, 1):
    #             logger.debug(f"  Línea {line_number}: {line_content.strip()} (raw: {repr(line_content)})")
    # except FileNotFoundError:
    #     logger.error(f"Archivo .env NO encontrado en {env_path}")
    # except Exception as e:
    #     logger.error(f"Error al leer el archivo .env: {e}")
    # # --- Fin: Depuración del archivo .env ---

    load_dotenv()
    
    # API_KEY y API_SECRET son ya globales del módulo. Simplemente las reasignamos.
    # No se necesita 'global API_KEY, API_SECRET' aquí.
    API_KEY = os.getenv("DMARKET_PUBLIC_KEY")
    API_SECRET = os.getenv("DMARKET_SECRET_KEY")

    logger.debug(f"DMARKET_PUBLIC_KEY cargada en __main__: {API_KEY}")
    logger.debug(f"DMARKET_SECRET_KEY cargada en __main__: {API_SECRET}")

    logger.info("Iniciando script populate_db.py...")
    logger.info("Inicializando base de datos (si es necesario)...")
    init_db()
    populate_dmarket_data()
    logger.info("Script populate_db.py finalizado.") 