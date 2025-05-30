import requests
import os
import time
import hmac
import hashlib
from urllib.parse import urlencode
import json # Import json a nivel de módulo

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

    def __init__(self, public_key: str = None, secret_key: str = None):
        """
        Inicializa el conector de la API de DMarket.

        Las claves API se leen de las variables de entorno DMARKET_PUBLIC_KEY y 
        DMARKET_SECRET_KEY si no se proporcionan explícitamente.

        Args:
            public_key (str, optional): Clave API pública. 
                                        Por defecto None (se toma de variable de entorno).
            secret_key (str, optional): Clave API secreta. 
                                        Por defecto None (se toma de variable de entorno).

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
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": self.public_key
        })

    def _create_signature(self, method: str, path: str, body: str = "", timestamp: str = None) -> str:
        """
        Crea la firma HMAC-SHA256 requerida para ciertos endpoints de DMarket.
        La cadena a firmar es: method + path + body + timestamp.
        Consulta la documentación oficial de DMarket para la estructura exacta.

        Args:
            method (str): Método HTTP (GET, POST, PATCH, DELETE).
            path (str): Ruta del endpoint (ej. /exchange/v1/market/items).
            body (str): Cuerpo de la petición (para POST/PATCH, usualmente JSON stringificado).
            timestamp (str): Timestamp actual en segundos como string.

        Returns:
            str: La firma en formato hexadecimal.
        
        Raises:
            ValueError: Si la secret_key no está disponible.
        """
        if not self.secret_key:
            logger.error("No se puede crear la firma sin la DMarket Secret Key.")
            raise ValueError("DMarket Secret Key no configurada, no se puede firmar la petición.")

        if timestamp is None:
            timestamp = str(int(time.time()))
        
        string_to_sign = method.upper() + path + (body if body else "") + timestamp
        logger.debug(f"String para firmar: {string_to_sign}")
        
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        logger.debug(f"Firma generada: {signature}")
        return signature

    def _request(self, method: str, path: str, params: dict = None, data: dict = None, add_auth_headers: bool = False) -> dict:
        """
        Realiza una petición HTTP a la API de DMarket.

        Args:
            method (str): Método HTTP (GET, POST, PATCH, DELETE).
            path (str): Ruta del endpoint (ej. /market/items).
            params (dict, optional): Parámetros de query para la URL.
            data (dict, optional): Cuerpo de la petición (para POST/PATCH).
            add_auth_headers (bool): Si es True, añade cabeceras de autenticación (firma y timestamp).
                                     Esto es necesario para endpoints privados.

        Returns:
            dict: La respuesta JSON de la API o un diccionario de error.
        """
        url = f"{self.base_url}{path}"
        headers = self.session.headers.copy() # Copia las cabeceras base de la sesión
        request_body_str = ""

        if data:
            # DMarket espera el cuerpo como un string JSON para la firma
            # y requests lo enviará como application/json si pasamos 'json=data'
            import json
            request_body_str = json.dumps(data, separators=(',', ':')) # Compact JSON
        
        if add_auth_headers:
            timestamp = str(int(time.time()))
            signature = self._create_signature(method, path, request_body_str, timestamp)
            headers["X-Sign-Date"] = timestamp
            headers["X-Request-Sign"] = f"dmar ed25519 {signature}" # El prefijo 'dmar ed25519' es un ejemplo, verificar documentación de DMarket
                                                               # La documentación de DMarket indica HMAC-SHA256, así que el prefijo podría ser diferente o no necesario.
                                                               # Esta parte necesita verificación con la documentación oficial de DMarket para la firma.
                                                               # Por ahora, lo simplificaremos y asumiremos que la firma es solo el hexadecimal.
                                                               # DMarket USA HMAC-SHA256, el formato de X-Request-Sign usualmente es solo la signatura.
            headers["X-Request-Sign"] = signature # Corregido según la práctica común de HMAC-SHA256

        try:
            logger.debug(f"Realizando petición {method} a {url} con params: {params}, data: {data}, headers: {headers}")
            if method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, params=params, json=data, headers=headers, timeout=10) # Usar json=data para que requests ponga Content-Type: application/json
            # Añadir PUT, DELETE, PATCH si son necesarios
            else:
                logger.error(f"Método HTTP no soportado: {method}")
                return {"error": f"Método HTTP no soportado: {method}", "status_code": 0}

            response.raise_for_status()  # Lanza HTTPError para respuestas 4xx/5xx
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

    def get_market_items(self, game: str = "CS2", name: str = None, limit: int = 100, offset: int = 0, 
                         order_by: str = "price", order_dir: str = "asc", currency: str = "USD", 
                         price_from: int = None, price_to: int = None, tree_filters: dict = None) -> dict:
        """
        Obtiene ítems del mercado de DMarket. (Endpoint: /exchange/v1/market/items)
        Este endpoint generalmente no requiere autenticación compleja (firma), solo la X-Api-Key en cabeceras.

        Args:
            game (str): Juego para filtrar (ej. "CS2", "dota2", "rust"). Por defecto "CS2".
            name (str, optional): Nombre del ítem para buscar.
            limit (int): Número de ítems a devolver. Máximo permitido por la API (consultar doc).
            offset (int): Desplazamiento para paginación.
            order_by (str): Campo por el cual ordenar (ej. "price", "updated").
            order_dir (str): Dirección de ordenación ("asc" o "desc").
            currency (str): Moneda para los precios (ej. "USD", "EUR").
            price_from (int, optional): Precio mínimo (en centavos, ej. 1000 para $10.00).
            price_to (int, optional): Precio máximo (en centavos).
            tree_filters (dict, optional): Filtros adicionales basados en el árbol de categorías de DMarket.
                                         Ejemplo: {"category_path": "mil-spec_pistol/usp-s"}

        Returns:
            dict: Respuesta JSON de la API o diccionario de error.
        """
        path = "/exchange/v1/market/items"
        params = {
            "gameId": game.lower(), # DMarket suele usar Ids de juego como "a8db", "csgo", etc. "CS2" podría necesitar mapeo o usar el ID correcto.
                                     # Por ahora, se asume que la API podría aceptar el nombre. Revisar documentación.
            "title": name,
            "limit": limit,
            "offset": str(offset), # Algunos APIs esperan strings para offset/limit
            "orderBy": order_by,
            "orderDir": order_dir,
            "currency": currency.upper(),
        }
        if price_from is not None:
            params["priceFrom"] = price_from
        if price_to is not None:
            params["priceTo"] = price_to
        if tree_filters:
            # DMarket puede esperar los treeFilters como un string JSON en el query param
            # o como parámetros separados. Consultar documentación.
            # Ejemplo: treeFilters={"category":"weapon|pistol", "exterior":"mw"}
            # Esto se convertiría en &treeFilters[category]=weapon|pistol&treeFilters[exterior]=mw
            # o &treeFilters=JSON_STRING
            # Por simplicidad, si se usa urlencode, los diccionarios anidados se manejan bien.
            # params["treeFilters"] = json.dumps(tree_filters) # Si es un solo string JSON
            params.update(tree_filters) # Si son múltiples parámetros bajo treeFilters[key]
        
        # Limpiar parámetros None para no enviarlos vacíos
        params = {k: v for k, v in params.items() if v is not None}
        
        # Este endpoint es público y solo requiere X-Api-Key (ya en self.session.headers)
        # No necesita add_auth_headers = True a menos que la documentación lo indique.
        # Si fuera un endpoint que REQUIERE firma, sería add_auth_headers=True
        response = self._request("GET", path, params=params) # add_auth_headers=False por defecto
        
        # Ejemplo básico de manejo de rate limits (muy simplificado)
        if isinstance(response, dict) and response.get("error") == "HTTPError" and response.get("status_code") == 429:
            logger.warning("Rate limit excedido. Esperando 60 segundos para reintentar...")
            # time.sleep(60) # No usar time.sleep en código que pueda ser asíncrono o bloquear. Implementar backoff más robusto.
                            # Aquí solo logueamos y devolvemos el error para que el llamador decida.
            # return self.get_market_items(...) # Reintento simple (puede causar bucles)
        
        return response

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
        items_response = dmarket_api.get_market_items(game="csgo", name="AK-47 | Redline", limit=5)
        
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