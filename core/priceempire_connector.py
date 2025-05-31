import requests
import os
import time
import json
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from utils.logger import logger

load_dotenv()

PRICEEMPIRE_API_KEY = os.getenv("PRICEEMPIRE_API_KEY")
API_BASE_URL_V4 = "https://api.pricempire.com/v4/paid"
API_BASE_URL_V3 = "https://api.pricempire.com/v3"
# Podríamos considerar un sandbox si PriceEmpire lo ofrece explícitamente y tenemos una URL para ello.
# SANDBOX_API_BASE_URL_V4 = "https://sandbox-api.pricempire.com/v4/paid" 
# SANDBOX_API_BASE_URL_V3 = "https://sandbox-api.pricempire.com/v3"

class PriceEmpireAPI:
    """
    Cliente para interactuar con la API de PriceEmpire.
    Permite obtener precios de mercado, historial de precios y otros metadatos de skins.
    """
    def __init__(self, api_key: str = PRICEEMPIRE_API_KEY, use_sandbox: bool = False):
        if not api_key:
            logger.error("PRICEEMPIRE_API_KEY no encontrada en las variables de entorno.")
            raise ValueError("PRICEEMPIRE_API_KEY no está configurada.")
        
        self.api_key = api_key
        # self.base_url_v4 = SANDBOX_API_BASE_URL_V4 if use_sandbox else API_BASE_URL_V4
        # self.base_url_v3 = SANDBOX_API_BASE_URL_V3 if use_sandbox else API_BASE_URL_V3
        self.base_url_v4 = API_BASE_URL_V4 # De momento, usamos la URL de producción directamente
        self.base_url_v3 = API_BASE_URL_V3 # De momento, usamos la URL de producción directamente
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        logger.info(f"Cliente PriceEmpireAPI inicializado. Usando V4 URL: {self.base_url_v4}, V3 URL: {self.base_url_v3}")

    def _make_request(self, base_url: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Realiza una solicitud GET a la API de PriceEmpire y devuelve la respuesta JSON.
        """
        url = f"{base_url}{endpoint}"
        try:
            logger.debug(f"Realizando solicitud a PriceEmpire: {url} con params: {params}")
            response = requests.get(url, headers=self.headers, params=params, timeout=30) # Timeout de 30s
            response.raise_for_status()  # Lanza HTTPError para códigos 4xx/5xx
            
            # Intentar parsear JSON, si falla pero es un 204 No Content (u otro 2xx sin cuerpo), devolvemos un diccionario vacío
            if response.status_code == 204: # No Content
                 logger.info(f"Respuesta 204 No Content de {url}")
                 return {} 
            if not response.content: # Otros casos donde el cuerpo podría estar vacío con un 2xx
                logger.info(f"Respuesta {response.status_code} sin contenido de {url}")
                return {}

            data = response.json()
            logger.debug(f"Respuesta recibida de {url}: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...") # Loguea una parte de la respuesta
            return data
        except requests.exceptions.HTTPError as errh:
            logger.error(f"Error HTTP de PriceEmpire: {errh.response.status_code} - {errh.response.reason} para {url}. Respuesta: {errh.response.text[:500]}")
            if errh.response.status_code == 429: # Too Many Requests
                logger.warning("Límite de tasa de PriceEmpire alcanzado. Considera añadir esperas más largas.")
        except requests.exceptions.ConnectionError as errc:
            logger.error(f"Error de Conexión con PriceEmpire: {errc} para {url}")
        except requests.exceptions.Timeout as errt:
            logger.error(f"Error de Timeout con PriceEmpire: {errt} para {url}")
        except requests.exceptions.RequestException as err:
            logger.error(f"Error en la solicitud a PriceEmpire: {err} para {url}")
        except json.JSONDecodeError as errj:
            logger.error(f"Error al decodificar JSON de PriceEmpire para {url}. Respuesta: {response.text[:500]}. Error: {errj}")
        return None

    def get_market_items_prices(self, 
                                app_id: int = 730, 
                                currency: str = "USD", 
                                sources: Optional[List[str]] = None,
                                metas: Optional[List[str]] = None,
                                market_hash_names: Optional[List[str]] = None # Aunque la API no filtra directamente, lo usamos para post-filtrado
                               ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene los precios actuales de los artículos desde /v4/paid/items/prices.
        Permite filtrar por app_id, currency, sources y metas.
        Si se provee market_hash_names, filtra los resultados localmente.
        """
        endpoint = "/items/prices"
        params = {
            "app_id": app_id,
            "currency": currency,
        }
        if sources:
            params["sources"] = ",".join(sources) # La API espera una cadena separada por comas
        if metas:
            params["metas"] = ",".join(metas)
        
        # La API /v4/paid/items/prices no parece soportar un filtro directo por market_hash_name en la solicitud.
        # Se obtiene todo (o lo que la API devuelva por defecto/paginación) y se filtra después si es necesario.
        # Esto es importante si se quieren precios para muchos ítems específicos; si son pocos, es mejor filtrar aquí.
        
        response_data = self._make_request(self.base_url_v4, endpoint, params)

        if response_data is None: # Error en la petición
            return None
        
        if not isinstance(response_data, list):
            logger.error(f"Respuesta inesperada de PriceEmpire {endpoint}. Se esperaba una lista, se obtuvo: {type(response_data)}. Data: {str(response_data)[:500]}")
            return None
            
        if market_hash_names:
            filtered_data = [item for item in response_data if item.get("market_hash_name") in market_hash_names]
            logger.info(f"Filtrados {len(filtered_data)} de {len(response_data)} ítems por market_hash_name para PriceEmpire {endpoint}.")
            return filtered_data
        
        return response_data

    def get_item_price_history(self, 
                               market_hash_name: str, 
                               app_id: int = 730, 
                               days: int = 30, 
                               source: str = "buff163", # Ejemplo, puede ser steam, etc.
                               currency: str = "USD"
                              ) -> Optional[Dict[str, Any]]:
        """
        Obtiene el historial de precios para un skin específico desde /v3/items/prices/history.
        IMPORTANTE: La estructura exacta de la respuesta de este endpoint V3 no está garantizada
        y podría requerir inspección y adaptación.
        """
        endpoint = "/items/prices/history"
        params = {
            "app_id": app_id,
            "currency": currency,
            "days": days,
            "source": source,
            "market_hash_name": market_hash_name
        }
        
        logger.info(f"Solicitando historial de precios V3 para '{market_hash_name}' de la fuente '{source}' para {days} días.")
        return self._make_request(self.base_url_v3, endpoint, params)

    def get_items_metadata(self, 
                           app_id: int = 730,
                           market_hash_names: Optional[List[str]] = None # Para post-filtrado
                          ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene metadatos, incluyendo volumen de transacciones, para skins desde /v4/paid/items/metas.
        Si se provee market_hash_names, filtra los resultados localmente.
        """
        endpoint = "/items/metas"
        params = {
            "app_id": app_id
            # Este endpoint podría no soportar filtrado directo por market_hash_name en la solicitud en la API.
        }
        
        response_data = self._make_request(self.base_url_v4, endpoint, params)

        if response_data is None: # Error en la petición
            return None

        if not isinstance(response_data, list):
            logger.error(f"Respuesta inesperada de PriceEmpire {endpoint}. Se esperaba una lista, se obtuvo: {type(response_data)}. Data: {str(response_data)[:500]}")
            return None

        if market_hash_names:
            filtered_data = [item for item in response_data if item.get("market_hash_name") in market_hash_names]
            logger.info(f"Filtrados {len(filtered_data)} de {len(response_data)} ítems por market_hash_name para PriceEmpire {endpoint}.")
            return filtered_data
            
        return response_data

# --- Bloque de prueba simple (se moverá a test_priceempire_fetch.py) ---
if __name__ == '__main__':
    logger.info("--- Iniciando prueba del cliente PriceEmpireAPI ---")
    
    if not PRICEEMPIRE_API_KEY:
        logger.error("La variable de entorno PRICEEMPIRE_API_KEY no está configurada. Saliendo de la prueba.")
    else:
        client = PriceEmpireAPI(api_key=PRICEEMPIRE_API_KEY)

        # 1. Probar get_market_items_prices
        logger.info("\n--- Probando get_market_items_prices (AK-47 | Redline) ---")
        specific_skin = ["AK-47 | Redline (Field-Tested)"]
        prices = client.get_market_items_prices(
            sources=["steam", "buff163", "skinport"], 
            metas=["liquidity", "trades_7d"],
            market_hash_names=specific_skin
        )
        if prices:
            logger.info(f"Precios encontrados para '{specific_skin[0]}':")
            for item_price_data in prices:
                logger.info(json.dumps(item_price_data, indent=2, ensure_ascii=False))
        elif prices == []: # Lista vacía, no necesariamente un error si el ítem no tiene ofertas en esas fuentes
            logger.info(f"No se encontraron precios para '{specific_skin[0]}' con los filtros aplicados.")
        else: # None, indica error en la petición
            logger.warning(f"Fallo al obtener precios para '{specific_skin[0]}'.")

        # 2. Probar get_item_price_history
        logger.info("\n--- Probando get_item_price_history (AK-47 | Redline, Steam, 7 días) ---")
        history = client.get_item_price_history(
            market_hash_name="AK-47 | Redline (Field-Tested)",
            days=7,
            source="steam" # buff163 suele tener más datos, pero steam es una buena prueba.
        )
        if history:
            logger.info(f"Historial de precios para 'AK-47 | Redline (Field-Tested)':")
            logger.info(json.dumps(history, indent=2, ensure_ascii=False))
        else:
            logger.warning("Fallo al obtener el historial de precios.")

        # 3. Probar get_items_metadata
        logger.info("\n--- Probando get_items_metadata (AK-47 | Redline) ---")
        metadata = client.get_items_metadata(market_hash_names=specific_skin)
        if metadata:
            logger.info(f"Metadatos encontrados para '{specific_skin[0]}':")
            for item_meta_data in metadata:
                logger.info(json.dumps(item_meta_data, indent=2, ensure_ascii=False))
        elif metadata == []:
             logger.info(f"No se encontraron metadatos para '{specific_skin[0]}' con los filtros aplicados.")
        else: # None
            logger.warning(f"Fallo al obtener metadatos para '{specific_skin[0]}'.")
            
        logger.info("\n--- Prueba de PriceEmpireAPI finalizada ---") 