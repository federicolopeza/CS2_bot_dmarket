import requests
import os
import time
import hmac
import hashlib
from urllib.parse import urlencode, quote_plus
import json # Import json a nivel de módulo
from typing import Optional, Dict, Any, Union
from datetime import datetime

from dotenv import load_dotenv
from utils.logger import logger # Asumiendo que utils.logger.py está creado

load_dotenv() # Carga variables desde .env si existe

class DMarketAPI:
    """
    Clase para interactuar con la API de DMarket.
    
    Atributos:
        public_key (str): Clave API pública de DMarket.
        secret_key (str): Clave API secreta de DMarket.
        base_url (str): URL base para los endpoints de la API de DMarket.
    """

    BASE_URL_V1 = "https://api.dmarket.com"
    # Otros endpoints base podrían añadirse aquí si la API los tiene (ej. v2)

    DEFAULT_TIMEOUT = 10 # Segundos

    def __init__(self, public_key: str = None, secret_key: str = None, timeout: int = DEFAULT_TIMEOUT):
        """
        Inicializa el conector de la API de DMarket.

        Las claves API se leen de las variables de entorno DMARKET_PUBLIC_KEY y 
        DMARKET_SECRET_KEY si no se proporcionan explícitamente.

        Args:
            public_key (str, optional): Clave API pública. 
                                        Por defecto None (se toma de variable de entorno).
            secret_key (str, optional): Clave API secreta. 
                                        Por defecto None (se toma de variable de entorno).
            timeout (int, optional): Tiempo máximo para las solicitudes a la API. Por defecto 10 segundos.

        Raises:
            ValueError: Si la clave pública o secreta no se encuentran.
        """
        self.public_key = public_key or os.environ.get("DMARKET_PUBLIC_KEY")
        self.secret_key = secret_key or os.environ.get("DMARKET_SECRET_KEY")

        if not self.public_key:
            logger.error("DMarket Public Key no encontrada. Asegúrate de que DMARKET_PUBLIC_KEY está definida en tus variables de entorno o pásala al constructor.")
            raise ValueError("DMarket Public Key no encontrada.")
        
        # La clave secreta podría no ser necesaria para todos los endpoints públicos,
        # pero es buena práctica verificarla si se va a usar para firmas.
        if not self.secret_key:
            logger.warning("DMarket Secret Key no encontrada. Algunas operaciones de la API podrían fallar.")
            # Considerar si levantar un error aquí o permitir la inicialización
            # para endpoints que no requieran firma.
            # raise ValueError("DMarket Secret Key no encontrada.")

        self.base_url = self.BASE_URL_V1
        self.timeout = timeout # Guardar el timeout
        self.session = requests.Session()
        # self.session.headers.update({
        #     "X-Api-Key": self.public_key # No es necesario aquí si _make_request lo añade siempre
        # })

    def get_market_items(self, game_id: str, title: str, limit: int = 100, offset: int = 0, currency: str = "USD", 
                         order_by: str = "price", order_dir: str = "asc", 
                         price_from: int = None, price_to: int = None, tree_filters: dict = None,
                         **kwargs) -> dict:
        """
        Obtiene ítems del mercado de DMarket utilizando el endpoint /exchange/v1/market/items.
        """
        endpoint = "/exchange/v1/market/items" # Corregido aquí, era 'path'
        query_params = {
            "gameId": game_id,
            "title": title,
            "limit": limit,
            # "offset": str(offset), # _make_request espera números si son números, str si son str.
                                    # La API usualmente espera strings para params, requests los convierte.
                                    # Por consistencia y para evitar errores, mejor convertir a str explícitamente si es necesario.
            "offset": str(offset) if offset is not None else None,
            "orderBy": order_by,
            "orderDir": order_dir,
            "currency": currency.upper(),
        }
        if price_from is not None:
            query_params["priceFrom"] = price_from # Asumimos que la API espera int/str según corresponda
        if price_to is not None:
            query_params["priceTo"] = price_to

        if tree_filters: # tree_filters es un dict, se une a query_params
            # Asegurarse que los valores en tree_filters sean adecuados para query params (strings usualmente)
            for key, value in tree_filters.items():
                if not isinstance(value, (str, int, float, bool)) and value is not None:
                    logger.warning(f"Valor de tree_filter '{key}' no es un tipo primitivo ({type(value)}), convirtiendo a str.")
                    query_params[key] = str(value)
                else:
                    query_params[key] = value

        if kwargs:
            # Similar para kwargs, asegurar tipos adecuados si es necesario.
            for key, value in kwargs.items():
                if not isinstance(value, (str, int, float, bool)) and value is not None:
                    logger.warning(f"Valor de kwarg '{key}' no es un tipo primitivo ({type(value)}), convirtiendo a str.")
                    query_params[key] = str(value)
                else:
                    query_params[key] = value

        # Filtrar parámetros None ANTES de pasarlos a _make_request
        final_params = {k: v for k, v in query_params.items() if v is not None}
        
        # Usar el método _make_request actualizado
        response_data = self._make_request(method="GET", endpoint=endpoint, params=final_params)

        if isinstance(response_data, dict) and response_data.get("error") == "HTTPError" and response_data.get("status_code") == 429:
            logger.warning(f"Rate limit (429) excedido para {endpoint}. Error: {response_data.get('message')}. "
                           "Considerar implementar una estrategia de backoff exponencial.")
        return response_data

    def get_account_balance(self) -> Dict[str, Any]:
        """
        Obtiene el balance actual de la cuenta del usuario en DMarket (USD y DMC).

        Este endpoint requiere autenticación (firma HMAC).

        Returns:
            dict: La respuesta JSON parseada de la API conteniendo el balance, 
                  o un diccionario de error si la petición falla.
                  Una respuesta exitosa típica podría ser: {'USD': '12345', 'DMC': '0'} (valores como string en centavos/unidades mínimas)
        """
        endpoint = "/account/v1/balance"
        # Este endpoint no requiere parámetros de query ni cuerpo, solo autenticación.
        # _make_request se encargará de la firma y las cabeceras necesarias.
        logger.info(f"Solicitando balance de la cuenta: GET {endpoint}")
        return self._make_request(method="GET", endpoint=endpoint)

    def _get_current_timestamp(self) -> str:
        """Devuelve el timestamp actual en formato ISO 8601 UTC."""
        return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    def _sign_request(self, method: str, path_with_query: str, timestamp: str, body_string: str) -> str:
        """
        Genera la firma HMAC-SHA256 para una petición según la especificación:
        stringToSign = method + path_with_query + body_string + timestamp
        """
        if not self.secret_key:
            logger.warning("No se puede generar firma: DMARKET_SECRET_KEY no encontrada.")
            return ""

        string_to_sign = f"{method}{path_with_query}{body_string}{timestamp}"
        logger.debug(f"String to sign: '{string_to_sign}'")
        
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        logger.debug(f"Generated signature: {signature}")
        return signature

    def _make_request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Realiza una petición HTTP a la API de DMarket.
        Incluye la lógica para firmar la petición si la secret_key está disponible.
        """
        full_url = f"{self.base_url}{endpoint}"
        # Usar el timestamp en formato ISO 8601 UTC para X-Sign-Date y para la firma
        timestamp_iso = self._get_current_timestamp() 
        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp_iso,
        }

        # Preparar path y body para la firma según la nueva especificación
        path_for_signing = endpoint
        if params:
            # Ordenar los parámetros por clave para consistencia en la firma
            # y codificarlos adecuadamente para la URL y para la firma.
            sorted_params = sorted(params.items())
            query_string = urlencode(sorted_params, quote_via=quote_plus)
            path_for_signing = f"{endpoint}?{query_string}"

        body_string_for_signing = ""
        # Variables para el cuerpo real de la solicitud con requests
        actual_body_for_request = None # para data=
        actual_json_for_request = None # para json=

        if body is not None:
            if isinstance(body, dict) or isinstance(body, list):
                # Para cuerpos JSON, serializar de forma compacta, ordenada y sin caracteres no ASCII escapados
                # para la firma. La librería requests se encargará de la serialización para el envío.
                body_string_for_signing = json.dumps(body, separators=(',', ':'), sort_keys=True, ensure_ascii=False)
                actual_json_for_request = body # requests usará esto con Content-Type: application/json
                if "Content-Type" not in headers: # Añadir solo si no está, aunque requests lo haría
                     headers["Content-Type"] = "application/json; charset=utf-8"
            elif isinstance(body, str):
                body_string_for_signing = body
                actual_body_for_request = body # Se enviará como data=
                # Si es una cadena JSON, el Content-Type debería ser application/json
                # Si es form-urlencoded, debería ser application/x-www-form-urlencoded
                # Por ahora, si es string, el usuario debe gestionar Content-Type si es necesario fuera o pasarlo en headers
            else:
                logger.warning(f"Tipo de cuerpo no manejado explícitamente para firma: {type(body)}. Usando str().")
                body_string_for_signing = str(body)
                actual_body_for_request = body_string_for_signing
        
        if self.secret_key:
            # Usar el mismo timestamp_iso para la firma
            signature = self._sign_request(method.upper(), path_for_signing, timestamp_iso, body_string_for_signing)
            if signature:
                headers["X-Request-Sign"] = signature
        else:
            logger.debug("No se generó firma: DMARKET_SECRET_KEY no configurada.")

        logger.debug(f"Petición: {method.upper()} {full_url}")
        logger.debug(f"  Firmar Path: {path_for_signing}")
        logger.debug(f"  Firmar Body: '{body_string_for_signing}'")
        logger.debug(f"  Firmar Timestamp: {timestamp_iso}")
        logger.debug(f"  Headers: {headers}")
        if params: logger.debug(f"  Query Params (para URL): {params}")
        if actual_json_for_request: logger.debug(f"  JSON Body (para request): {actual_json_for_request}")
        elif actual_body_for_request: logger.debug(f"  Data Body (para request): {actual_body_for_request}")

        try:
            response = requests.request(
                method.upper(),
                full_url,
                params=params, # requests maneja la codificación de params para la URL
                json=actual_json_for_request, 
                data=actual_body_for_request,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP: {e.response.status_code} - {e.response.text}")
            return {"error": "HTTPError", "status_code": e.response.status_code, "message": e.response.text, "response_headers": dict(e.response.headers)}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error de Conexión: {e}")
            return {"error": "ConnectionError", "message": str(e)}
        except requests.exceptions.Timeout as e:
            logger.error(f"Error de Timeout: {e}")
            return {"error": "Timeout", "message": str(e)}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de Request: {e}")
            return {"error": "RequestException", "message": str(e)}
        except Exception as e:
            logger.error(f"Error inesperado durante la petición a la API: {e}")
            return {"error": "UnexpectedAPIError", "message": str(e)}

# Ejemplo de uso (requiere que .env esté configurado con las claves)
if __name__ == "__main__":
    try:
        logger.info("Iniciando prueba del conector DMarketAPI...")
        # No pasar claves aquí para forzar la carga desde .env
        dmarket_api = DMarketAPI()
        logger.info("Conector DMarketAPI inicializado.")

        # Probar endpoint get_market_items
        logger.info("Probando get_market_items para AK-47 | Redline...")
        # Nota: el parámetro "name" en DMarket es "title". 
        # "gameId" para CS2 podría ser "csgo" o un ID específico. Revisar documentación de DMarket.
        # Usaremos "csgo" como placeholder si "CS2" no funciona.
        items_response = dmarket_api.get_market_items(game_id="csgo", title="AK-47 | Redline", limit=5)
        
        if "error" in items_response:
            logger.error(f"Error al obtener ítems: {items_response}")
        else:
            logger.info(f"Respuesta de get_market_items (primeros {items_response.get('limit', 0)} de {items_response.get('total', 0)} ítems):")
            for item in items_response.get("objects", []):
                logger.info(f"  Título: {item.get('title')}, Precio: {item.get('price').get(dmarket_api.session.headers.get('currency', 'USD'))/100 if item.get('price') else 'N/A'} {dmarket_api.session.headers.get('currency', 'USD')}, Market ID: {item.get('itemId')}")
            if not items_response.get("objects"):
                logger.info("No se encontraron ítems para 'AK-47 | Redline' o el gameId es incorrecto.")

        # Ejemplo de cómo se llamaría un endpoint que requiere firma (NO EJECUTAR SIN VERIFICAR DETALLES DE FIRMA CON DMarket)
        # if dmarket_api.secret_key: # Solo si la secret key está disponible
        #     logger.info("Probando un endpoint hipotético que requiere firma (ej. /account/v1/balance)...")
        #     # ESTO ES UN EJEMPLO, la ruta y método deben ser reales y la firma correcta
        #     # balance_response = dmarket_api._request("GET", "/account/v1/balance", add_auth_headers=True)
        #     # if "error" in balance_response:
        #     #     logger.error(f"Error al obtener balance: {balance_response}")
        #     # else:
        #     #     logger.info(f"Respuesta de balance: {balance_response}")
        # else:
        #     logger.warning("No se puede probar endpoint con firma porque la DMarket Secret Key no está configurada.")

    except ValueError as ve:
        logger.error(f"Error de configuración: {ve}")
    except Exception as e:
        logger.exception(f"Ocurrió un error inesperado durante la prueba: {e}")

    logger.info("Prueba del conector DMarketAPI finalizada.") 