# test_dmarket_fetch.py

import os
from core.dmarket_connector import DMarketAPI
from utils.logger import logger
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
# Es importante hacerlo antes de instanciar DMarketAPI si las claves no se pasan directamente
load_dotenv()

def run_test():
    """
    Ejecuta una prueba simple del conector DMarketAPI para obtener ítems.
    """
    logger.info("--- Iniciando Script de Prueba de DMarket Fetch ---")

    # Verificar si las claves API están cargadas (opcional, DMarketAPI lo hará internamente)
    public_key = os.getenv("DMARKET_PUBLIC_KEY")
    if not public_key:
        logger.warning("DMARKET_PUBLIC_KEY no encontrada en las variables de entorno. "
                       "Asegúrate de que tu archivo .env está configurado correctamente.")
        # Podríamos optar por salir aquí si la clave pública es estrictamente necesaria para cualquier prueba
        # return

    try:
        logger.info("Inicializando DMarketAPI...")
        # DMarketAPI intentará cargar las claves desde el entorno si no se proporcionan aquí
        dmarket_api_client = DMarketAPI()
        logger.info("DMarketAPI inicializado exitosamente.")

    except ValueError as e:
        logger.error(f"Error al inicializar DMarketAPI: {e}")
        logger.error("Asegúrate de que DMARKET_PUBLIC_KEY (y DMARKET_SECRET_KEY si es necesaria para la inicialización) estén en tu archivo .env")
        return
    except Exception as e:
        logger.error(f"Error inesperado durante la inicialización de DMarketAPI: {e}", exc_info=True)
        return

    # Lista de skins de ejemplo para probar
    # Usaremos un game_id placeholder. ¡RECUERDA VERIFICAR EL GAME_ID CORRECTO PARA CS2!
    test_game_id = "a8db" # Placeholder, podría ser "csgo" u otro valor según la doc de DMarket
    skins_to_test = [
        "AK-47 | Redline",
        "AWP | Asiimov",
        "Glock-18 | Fade" # Un ítem que podría tener menos listados
    ]

    for skin_name in skins_to_test:
        logger.info(f"--- Buscando ítems para: '{skin_name}' (Juego ID: {test_game_id}) ---")
        try:
            # Llama al método para obtener ítems del mercado
            items_data = dmarket_api_client.get_market_items(
                game_id=test_game_id, 
                title=skin_name, 
                limit=5, # Obtener solo algunos para la prueba
                currency="USD" # Especificar moneda
            )

            if "error" in items_data:
                logger.error(f"Error al obtener ítems para '{skin_name}': {items_data.get('message', str(items_data))}")
                if items_data.get("status_code"):
                    logger.error(f"  Status Code: {items_data['status_code']}")
            else:
                # Corregir acceso a Total y Limit, y convertirlos a int para el log
                total_items_api_dict = items_data.get("total", {})
                total_items_count = int(total_items_api_dict.get("items", 0))
                
                requested_limit = 5 # El límite que pasamos a la API
                
                # Corregir acceso a la lista de ítems (debe ser "objects")
                retrieved_objects = items_data.get("objects", []) 
                
                logger.info(f"Respuesta para '{skin_name}': {total_items_count} ítems encontrados en total (solicitados hasta {requested_limit}, recibidos {len(retrieved_objects)}).")
                
                if retrieved_objects:
                    for item in retrieved_objects:
                        price_info = item.get("price", {})
                        # Corregir conversión de precio (string a int antes de dividir)
                        # y usar un default string "0" para int()
                        price_str = price_info.get("USD", "0") 
                        price_value = int(price_str) / 100 
                        
                        # Acceder a los campos itemId, assetId y floatValue desde la estructura correcta
                        item_id = item.get('itemId', 'N/A') # Correcto: itemId
                        asset_id = item.get('extra', {}).get('inGameAssetID', 'N/A') # Correcto: item['extra']['inGameAssetID']
                        float_value = item.get('extra', {}).get('floatValue', 'N/A') # Correcto: item['extra']['floatValue']

                        logger.info(
                            f"  - Nombre: {item.get('title', 'N/A')}, "
                            f"Precio: {price_value:.2f} USD, "
                            f"Market ID: {item_id}, "
                            f"Asset ID: {asset_id}, "
                            f"Float: {float_value}"
                        )
                else:
                    logger.info(f"No se encontraron listados para '{skin_name}' con los filtros actuales (Respuesta API: {items_data})")
        
        except Exception as e:
            logger.error(f"Ocurrió una excepción inesperada al procesar '{skin_name}': {e}", exc_info=True)
        logger.info("---") # Separador para la salida

    logger.info("--- Script de Prueba de DMarket Fetch Finalizado ---")

    # --- Prueba para obtener balance de la cuenta ---
    logger.info("--- Iniciando Prueba de Obtención de Balance --- ")
    if not dmarket_api_client.secret_key:
        logger.warning("No se puede probar la obtención de balance: DMARKET_SECRET_KEY no está configurada en .env")
    else:
        try:
            logger.info("Solicitando balance de la cuenta...")
            balance_data = dmarket_api_client.get_account_balance()

            if "error" in balance_data:
                logger.error(f"Error al obtener el balance: {balance_data.get('message', str(balance_data))}")
                if balance_data.get("status_code"):
                    logger.error(f"  Status Code: {balance_data['status_code']}")
                if balance_data.get("response_headers"):
                    logger.error(f"  Response Headers: {balance_data['response_headers']}") # Puede dar pistas si hay error de firma
            else:
                usd_balance_str = balance_data.get("usd", "0")
                dmc_balance_str = balance_data.get("dmc", "0")
                # Asumimos que el balance viene en la unidad mínima (centavos para USD)
                try:
                    usd_balance = int(usd_balance_str) / 100
                    dmc_balance = int(dmc_balance_str) # Asumiendo que DMC no tiene decimales o es unidad mínima
                    logger.info(f"Balance de la cuenta: {usd_balance:.2f} USD, {dmc_balance} DMC")
                except ValueError:
                    logger.error(f"No se pudo convertir el balance a números. Respuesta: USD='{usd_balance_str}', DMC='{dmc_balance_str}'")
        except Exception as e:
            logger.error(f"Ocurrió una excepción inesperada al obtener el balance: {e}", exc_info=True)
    logger.info("--- Prueba de Obtención de Balance Finalizada ---")

if __name__ == "__main__":
    run_test() 