import requests
import os
import time
import json
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from nacl.bindings import crypto_sign

from dotenv import load_dotenv
from utils.logger import configure_logging

load_dotenv()

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

# Definir el prefijo de la firma como una constante
SIGNATURE_PREFIX = "dmar ed25519 "

class DMarketAPI:
    """
    Clase para interactuar con la API de DMarket.
    Utiliza firma Ed25519 para la autenticación.
    """

    BASE_URL_V1 = "https://api.dmarket.com"
    DEFAULT_TIMEOUT = 10 # Segundos

    def __init__(self, public_key: str = None, secret_key: str = None, timeout: int = DEFAULT_TIMEOUT):
        """
        Inicializa el conector de la API de DMarket.

        Las claves API se leen de las variables de entorno DMARKET_PUBLIC_KEY y 
        DMARKET_SECRET_KEY si no se proporcionan explícitamente.

        Args:
            public_key (str, optional): Clave API pública. 
            secret_key (str, optional): Clave API secreta (hexadecimal de 128 caracteres).
            timeout (int, optional): Tiempo máximo para las solicitudes a la API.

        Raises:
            ValueError: Si la clave pública o secreta no se encuentran o son inválidas.
        """
        self.public_key = public_key or os.environ.get("DMARKET_PUBLIC_KEY")
        self.secret_key_hex = secret_key or os.environ.get("DMARKET_SECRET_KEY")

        if not self.public_key:
            logger.error("DMarket Public Key no encontrada. Asegúrate de que DMARKET_PUBLIC_KEY está definida.")
            raise ValueError("DMarket Public Key no encontrada.")
        
        if not self.secret_key_hex:
            logger.error("DMarket Secret Key no encontrada. Asegúrate de que DMARKET_SECRET_KEY está definida.")
            raise ValueError("DMarket Secret Key no encontrada.")

        try:
            self.secret_key_bytes = bytes.fromhex(self.secret_key_hex)
            if len(self.secret_key_bytes) != 64:
                logger.error(f"La Secret Key decodificada debe tener 64 bytes, obtuvo {len(self.secret_key_bytes)}")
                raise ValueError("Secret Key con longitud incorrecta tras decodificación.")
        except ValueError as e:
            logger.error(f"Secret Key inválida o con formato incorrecto: {e}")
            raise ValueError(f"Secret Key inválida: {e}")

        self.base_url = self.BASE_URL_V1
        self.timeout = timeout
        self.session = requests.Session()

    def _generate_signature(self, string_to_sign_utf8_str: str) -> Optional[str]:
        """
        Genera la firma Ed25519 para la string_to_sign dada.
        La secret_key_bytes (64 bytes) se usa directamente.
        Devuelve la firma en formato hexadecimal (128 caracteres) o None si hay error.
        """
        if not self.secret_key_bytes:
            logger.error("ERROR Interno: Secret key bytes no están inicializados.")
            return None

        string_to_sign_bytes = string_to_sign_utf8_str.encode('utf-8')
        
        try:
            signed_message_bytes = crypto_sign(string_to_sign_bytes, self.secret_key_bytes)
            signature_bytes = signed_message_bytes[:64]
            signature_hex = signature_bytes.hex()
            
            if len(signature_hex) != 128:
                logger.error(f"Firma Ed25519 generada no tiene 128 caracteres: {len(signature_hex)}")
                return None
            return signature_hex
        except Exception as e:
            logger.error(f"Error crítico al generar firma Ed25519 con nacl.bindings.crypto_sign: {e}")
            return None

    def _make_request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, body_data: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Realiza una petición HTTP a la API de DMarket con firma Ed25519.
        """
        full_url = f"{self.base_url}{endpoint}"
        timestamp_str = str(int(time.time())) 

        # 1. Construir path_for_sig (endpoint + query_params_string_sorted)
        path_for_sig = endpoint
        query_string_for_sig = ""
        if params:
            # Filtrar None values antes de ordenar y codificar para la firma y la URL real
            active_params = {k: v for k, v in params.items() if v is not None}
            if active_params:
                sorted_params = sorted(active_params.items())
                query_string_for_sig = urlencode(sorted_params)
                path_for_sig += "?" + query_string_for_sig
        
        # 2. Construir body_str_for_sig (JSON compacto si hay body_data)
        body_str_for_sig = ""
        actual_json_for_request = None

        if body_data is not None:
            try:
                body_str_for_sig = json.dumps(body_data, separators=(',', ':'))
                actual_json_for_request = body_data
            except TypeError as e:
                logger.error(f"Error al serializar body_data a JSON para la firma: {e}. Body: {body_data}")
                return {"error": "BodySerializationError", "message": str(e)}
        
        # 3. Construir la string_to_sign completa
        string_to_sign = method.upper() + path_for_sig + body_str_for_sig + timestamp_str
        logger.debug(f"String para Firmar: {string_to_sign}")
        
        # 4. Generar la firma Ed25519
        generated_signature_hex = self._generate_signature(string_to_sign)
        
        if not generated_signature_hex:
            logger.error("Fallo al generar la firma Ed25519. Abortando petición.")
            return {"error": "SignatureGenerationError", "message": "Fallo al generar la firma"}

        # 5. Construir cabeceras
        final_signature_header = SIGNATURE_PREFIX + generated_signature_hex
        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp_str,
            "X-Request-Sign": final_signature_header,
            "Accept": "application/json"
        }
        if method.upper() in ["POST", "PATCH", "PUT"] and actual_json_for_request is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"

        logger.debug(f"Petición: {method.upper()} {full_url}")
        logger.debug(f"  Headers: {headers}")
        if params: logger.debug(f"  Query Params (para URL): {params}")
        if actual_json_for_request: logger.debug(f"  JSON Body (para request): {actual_json_for_request}")
        
        try:
            response = self.session.request(
                method.upper(),
                full_url,
                params=params,
                json=actual_json_for_request, 
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.warning(f"Respuesta no es JSON válido, devolviendo texto. Status: {response.status_code}, Contenido: {response.text[:200]}...")
                return {"error": "NonJSONResponse", "status_code": response.status_code, "message": response.text}

        except requests.exceptions.HTTPError as e:
            error_content = e.response.text
            try:
                error_details = e.response.json()
            except json.JSONDecodeError:
                error_details = error_content
            
            logger.error(f"Error HTTP: {e.response.status_code}. Respuesta: {error_details}")
            return {"error": "HTTPError", "status_code": e.response.status_code, "message": error_details, "response_headers": dict(e.response.headers)}
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
            logger.exception(f"Error inesperado durante la petición a la API: {e}")
            return {"error": "UnexpectedInternalError", "message": str(e)}

    def get_market_items(self, game_id: str, limit: int = 50, currency: str = "USD", 
                         order_by: Optional[str] = None, order_dir: Optional[str] = None, 
                         price_from: Optional[int] = None, price_to: Optional[int] = None,
                         title: Optional[str] = None,
                         cursor: Optional[str] = None,
                         tree_filters: Optional[dict] = None,
                         **kwargs) -> dict:
        """
        Obtiene ítems del mercado de DMarket. Endpoint: /exchange/v1/market/items
        """
        endpoint = "/exchange/v1/market/items"
        query_params = {
            "gameId": game_id,
            "limit": str(limit),
            "currency": currency.upper(),
            "orderBy": order_by,
            "orderDir": order_dir,
            "priceFrom": str(price_from) if price_from is not None else None,
            "priceTo": str(price_to) if price_to is not None else None,
            "title": title,
            "cursor": cursor
        }
        
        if tree_filters:
            for key, value in tree_filters.items():
                if isinstance(value, list):
                    logger.warning(f"El manejo de listas en tree_filters ('{key}') no está completamente implementado para la firma. Se usará str().")
                    query_params[f"Tree[{key}]"] = str(value)
                else:
                    query_params[f"Tree[{key}]"] = str(value) if value is not None else None

        if kwargs:
            for key, value in kwargs.items():
                query_params[key] = str(value) if value is not None else None
        
        final_params = {k: v for k, v in query_params.items() if v is not None}
        
        logger.info(f"Solicitando ítems del mercado: GET {endpoint} con params: {final_params}")
        return self._make_request(method="GET", endpoint=endpoint, params=final_params)

    def get_account_balance(self) -> Dict[str, Any]:
        """
        Obtiene el balance actual de la cuenta del usuario en DMarket (USD y DMC).
        Endpoint: /account/v1/balance
        """
        endpoint = "/account/v1/balance"
        logger.info(f"Solicitando balance de la cuenta: GET {endpoint}")
        return self._make_request(method="GET", endpoint=endpoint)

    def get_fee_rates(self, game_id: str) -> Dict[str, Any]:
        """
        Obtiene las tasas de comisión para un juego específico.
        Endpoint: /account/v1/fee-rates/{gameId}

        Args:
            game_id (str): El ID del juego (ej. "a8db" para CS2).

        Returns:
            Dict[str, Any]: Un diccionario con las tasas de comisión o un error.
        """
        endpoint = f"/account/v1/fee-rates/{game_id}"
        logger.info(f"Solicitando tasas de comisión para el juego {game_id}: GET {endpoint}")
        return self._make_request(method="GET", endpoint=endpoint)

    def get_offers_by_title(
        self, 
        title: str, 
        limit: int = 100, 
        currency: str = "USD", 
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene las ofertas de venta activas para un título de ítem específico.
        Endpoint: /marketplace/v1/offers-by-title

        Args:
            title (str): El market_hash_name del ítem.
            limit (int, optional): Número de ofertas a devolver por página. Máximo 100.
            currency (str, optional): Moneda para los precios. Default "USD".
            cursor (Optional[str], optional): Cursor para paginación.

        Returns:
            Dict[str, Any]: Un diccionario con las ofertas o un error.
                          La respuesta esperada incluye una lista de 'objects' y un 'cursor' para la siguiente página.
                          Cada 'object' (oferta) debería contener:
                            - assetId (str): ID único de la oferta específica.
                            - price (dict): Diccionario de precios, ej. {"USD": "1250"} (centavos).
                            - amount (int): Cantidad de este ítem en esta oferta (generalmente 1).
                            - attributes (dict, optional): Detalles como floatValue, paintSeed, paintIndex.
                            - stickers (list, optional): Lista de stickers aplicados.
                            - lock (dict, optional): Información sobre el bloqueo de trade si existe.
        """
        endpoint = "/marketplace/v1/offers-by-title"
        query_params = {
            "title": title,
            "limit": str(limit),
            "currency": currency.upper(),
            "cursor": cursor
        }
        
        final_params = {k: v for k, v in query_params.items() if v is not None}
        
        logger.info(f"Solicitando ofertas por título '{title}': GET {endpoint} con params: {final_params}")
        return self._make_request(method="GET", endpoint=endpoint, params=final_params)

    def get_buy_offers(
        self,
        title: str,
        game_id: str, # Requerido por la API, aunque el title debería ser suficiente para un item específico.
        limit: int = 100,
        currency: str = "USD",
        offset: Optional[int] = None, # DMarket usa offset para este endpoint en lugar de cursor
        order_by: Optional[str] = "price", # Default para obtener las más altas primero
        order_dir: Optional[str] = "desc"  # Default para obtener las más altas primero
    ) -> Dict[str, Any]:
        """
        Obtiene las órdenes de compra activas para un título de ítem específico.
        Endpoint: /marketplace/v1/buy-offers

        Args:
            title (str): El market_hash_name del ítem.
            game_id (str): El ID del juego (ej. "a8db" para CS2).
            limit (int, optional): Número de ofertas a devolver por página. Máximo 100.
            currency (str, optional): Moneda para los precios. Default "USD".
            offset (Optional[int], optional): Offset para paginación.
            order_by (Optional[str], optional): Campo por el cual ordenar (ej. "price", "created").
            order_dir (Optional[str], optional): Dirección de orden ("asc", "desc").

        Returns:
            Dict[str, Any]: Un diccionario con las órdenes de compra o un error.
                          La respuesta esperada incluye una lista de 'offers' y 'total'.
                          Cada 'offer' debería contener:
                            - offerId (str): ID de la orden de compra.
                            - title (str): Nombre del ítem.
                            - price (dict): {"USD": "1000"} (centavos).
                            - amount (int): Cantidad deseada.
                            - conditions (dict, optional): Podría incluir condiciones de float, stickers, etc.
        """
        endpoint = "/marketplace/v1/buy-offers"
        query_params = {
            "title": title,
            "gameId": game_id,
            "limit": str(limit),
            "currency": currency.upper(),
            "offset": str(offset) if offset is not None else None,
            "orderBy": order_by,
            "orderDir": order_dir
        }
        
        final_params = {k: v for k, v in query_params.items() if v is not None}
        
        logger.info(f"Solicitando órdenes de compra para '{title}': GET {endpoint} con params: {final_params}")
        return self._make_request(method="GET", endpoint=endpoint, params=final_params)

    def buy_item(self, asset_id: str, price_usd: float) -> Dict[str, Any]:
        """
        Compra un ítem específico por su asset_id.
        
        Args:
            asset_id: ID único del asset a comprar.
            price_usd: Precio de compra en USD (será convertido a centavos).
            
        Returns:
            Dict con el resultado de la compra.
        """
        logger.info(f"Intentando comprar ítem {asset_id} por ${price_usd:.2f}")
        
        # Convertir precio a centavos (formato requerido por DMarket)
        price_cents = int(price_usd * 100)
        
        endpoint = "/exchange/v1/buy-offers"
        body_data = {
            "offers": [
                {
                    "assetId": asset_id,
                    "price": {
                        "amount": str(price_cents),
                        "currency": "USD"
                    }
                }
            ]
        }
        
        logger.debug(f"Datos de compra: {body_data}")
        response = self._make_request("POST", endpoint, body_data=body_data)
        
        if "error" not in response:
            logger.info(f"Compra exitosa para {asset_id}: {response}")
        else:
            logger.error(f"Error en compra de {asset_id}: {response}")
            
        return response

    def create_sell_offer(
        self, 
        asset_id: str, 
        price_usd: float, 
        game_id: str = "a8db"
    ) -> Dict[str, Any]:
        """
        Crea una oferta de venta para un ítem del inventario.
        
        Args:
            asset_id: ID único del asset a vender.
            price_usd: Precio de venta en USD.
            game_id: ID del juego (por defecto CS2).
            
        Returns:
            Dict con el resultado de la creación de oferta.
        """
        logger.info(f"Creando oferta de venta para {asset_id} por ${price_usd:.2f}")
        
        # Convertir precio a centavos
        price_cents = int(price_usd * 100)
        
        endpoint = "/exchange/v1/offers"
        body_data = {
            "items": [
                {
                    "assetId": asset_id,
                    "price": {
                        "amount": str(price_cents),
                        "currency": "USD"
                    }
                }
            ],
            "gameId": game_id
        }
        
        logger.debug(f"Datos de oferta de venta: {body_data}")
        response = self._make_request("POST", endpoint, body_data=body_data)
        
        if "error" not in response:
            logger.info(f"Oferta de venta creada exitosamente para {asset_id}: {response}")
        else:
            logger.error(f"Error creando oferta de venta para {asset_id}: {response}")
            
        return response

    def cancel_sell_offer(self, offer_id: str) -> Dict[str, Any]:
        """
        Cancela una oferta de venta activa.
        
        Args:
            offer_id: ID de la oferta a cancelar.
            
        Returns:
            Dict con el resultado de la cancelación.
        """
        logger.info(f"Cancelando oferta de venta {offer_id}")
        
        endpoint = f"/exchange/v1/offers/{offer_id}/close"
        response = self._make_request("PATCH", endpoint)
        
        if "error" not in response:
            logger.info(f"Oferta {offer_id} cancelada exitosamente: {response}")
        else:
            logger.error(f"Error cancelando oferta {offer_id}: {response}")
            
        return response

    def get_user_offers(self, game_id: str = "a8db", limit: int = 100) -> Dict[str, Any]:
        """
        Obtiene las ofertas activas del usuario.
        
        Args:
            game_id: ID del juego.
            limit: Límite de ofertas a obtener.
            
        Returns:
            Dict con las ofertas del usuario.
        """
        logger.debug(f"Obteniendo ofertas del usuario para {game_id}")
        
        endpoint = "/exchange/v1/user/offers"
        params = {
            "gameId": game_id,
            "limit": limit
        }
        
        response = self._make_request("GET", endpoint, params=params)
        
        if "error" not in response:
            logger.debug(f"Ofertas del usuario obtenidas: {len(response.get('objects', []))} ofertas")
        else:
            logger.error(f"Error obteniendo ofertas del usuario: {response}")
            
        return response

    def get_user_inventory(self, game_id: str = "a8db", limit: int = 100) -> Dict[str, Any]:
        """
        Obtiene el inventario del usuario.
        
        Args:
            game_id: ID del juego.
            limit: Límite de ítems a obtener.
            
        Returns:
            Dict con el inventario del usuario.
        """
        logger.debug(f"Obteniendo inventario del usuario para {game_id}")
        
        endpoint = "/exchange/v1/user/items"
        params = {
            "gameId": game_id,
            "limit": limit
        }
        
        response = self._make_request("GET", endpoint, params=params)
        
        if "error" not in response:
            logger.debug(f"Inventario obtenido: {len(response.get('objects', []))} ítems")
        else:
            logger.error(f"Error obteniendo inventario: {response}")
            
        return response

# Ejemplo de uso (requiere que .env esté configurado con las claves)
if __name__ == "__main__":
    # Configurar logging para la ejecución directa de este script
    configure_logging(log_level=logging.DEBUG)

    try:
        logger.info("Iniciando prueba del conector DMarketAPI desde core/dmarket_connector.py...")
        
        if not os.getenv("DMARKET_PUBLIC_KEY") or not os.getenv("DMARKET_SECRET_KEY"):
            logger.error("DMARKET_PUBLIC_KEY o DMARKET_SECRET_KEY no encontradas en .env. Saliendo.")
            exit(1)
            
        dmarket_api = DMarketAPI()
        logger.info("Conector DMarketAPI inicializado.")

        logger.info("Probando get_account_balance...")
        balance_response = dmarket_api.get_account_balance()
        
        if balance_response and "error" not in balance_response:
            logger.info(f"Respuesta de Balance: {json.dumps(balance_response, indent=2)}")
        else:
            logger.error(f"Error al obtener balance: {balance_response}")

        logger.info("\nProbando get_market_items para CS2 (gameId a8db), limit 2...")
        market_items_response = dmarket_api.get_market_items(
            game_id="a8db", 
            limit=2, 
            currency="USD",
            order_by="price",
            order_dir="desc"
        )
        
        if market_items_response and "error" not in market_items_response:
            logger.info(f"Respuesta de Market Items: {json.dumps(market_items_response, indent=2)}")
        else:
            logger.error(f"Error al obtener ítems del mercado: {market_items_response}")

    except ValueError as ve:
        logger.error(f"Error de configuración al inicializar DMarketAPI: {ve}")
    except Exception as e:
        logger.exception(f"Ocurrió un error inesperado durante la prueba del conector: {e}")

    logger.info("\nPrueba del conector DMarketAPI (core/dmarket_connector.py) finalizada.") 