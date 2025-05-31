import requests
import logging
import urllib.parse
import time
import random
from decimal import Decimal, InvalidOperation

from utils.logger import configure_logging

# Configurar logging al nivel del módulo si es necesario, o asumir que se configura en el punto de entrada
# configure_logging() # Descomentar si se ejecuta este módulo de forma independiente para pruebas
logger = logging.getLogger(__name__)

class SteamMarketScraper:
    """
    Scraper para obtener datos de precios del Steam Community Market.
    """
    BASE_URL_PRICEOVERVIEW = "https://steamcommunity.com/market/priceoverview/"
    DEFAULT_APPID = "730"  # CS2 App ID
    DEFAULT_CURRENCY = "1"  # USD

    DEFAULT_USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36') # Tomado de steam_scraper.md

    def __init__(self, appid=DEFAULT_APPID, currency=DEFAULT_CURRENCY, user_agent=None):
        self.appid = appid
        self.currency = currency
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        logger.info(f"SteamMarketScraper inicializado para appid: {self.appid}, currency: {self.currency}")

    def _parse_price_string(self, price_str: str) -> Decimal | None:
        """
        Parsea un string de precio (ej. "$10.50", "€10,50", "CDN$ 12.34", "1.234,56€", "1,234", "10.000") a Decimal.
        Intenta manejar varios formatos comunes.
        """
        if not price_str:
            return None

        # Inicialmente, extraer solo dígitos, puntos y comas.
        raw_numeric_str = ''.join(c for c in price_str if c.isdigit() or c in ['.', ','])

        if not raw_numeric_str: # Si no quedó nada después de limpiar símbolos de moneda, etc.
            logger.error(f"No se pudo extraer una cadena numérica de: '{price_str}'")
            return None

        has_dot = '.' in raw_numeric_str
        has_comma = ',' in raw_numeric_str

        processed_str = raw_numeric_str

        if has_dot and has_comma:
            # Caso: Contiene tanto puntos como comas (ej. "1.234,56" o "1,234.56")
            last_dot_idx = raw_numeric_str.rfind('.')
            last_comma_idx = raw_numeric_str.rfind(',')
            if last_dot_idx > last_comma_idx: # Formato US: 1,234.56
                processed_str = raw_numeric_str.replace(',', '')
            else: # Formato EU: 1.234,56
                processed_str = raw_numeric_str.replace('.', '').replace(',', '.')
        elif has_dot:
            # Caso: Contiene solo puntos (ej. "10.50" o "10.000")
            parts = raw_numeric_str.split('.')
            if len(parts) > 2: # Múltiples puntos "1.2.3", tratar como error o quitar todos.
                processed_str = raw_numeric_str.replace('.', '')
            elif len(parts) == 2: # Un solo punto "10.50" o "10.000"
                # Si la parte después del punto tiene exactamente 3 dígitos y no hay comas en el string original,
                # es probable que sea un separador de miles (ej. "10.000" en algunos formatos EU).
                if len(parts[1]) == 3 and parts[1].isdigit() and not has_comma:
                    processed_str = raw_numeric_str.replace('.', '')
                else: # "10.50", "7.5", o formatos mixtos ya manejados
                    processed_str = raw_numeric_str # Mantenemos el punto como decimal
            # else: len(parts) == 1, no dots, no change. processed_str = raw_numeric_str
        elif has_comma:
            # Caso: Contiene solo comas (ej. "10,50" o "1,234")
            parts = raw_numeric_str.split(',')
            if len(parts) > 2: # Múltiples comas "1,2,3"
                processed_str = raw_numeric_str.replace(',', '')
            elif len(parts) == 2: # Una sola coma "10,50" o "1,234"
                # Si la parte después de la coma tiene exactamente 3 dígitos y no hay puntos en el string original,
                # es probable que sea un separador de miles (ej. "1,234").
                if len(parts[1]) == 3 and parts[1].isdigit() and not has_dot:
                    processed_str = raw_numeric_str.replace(',', '')
                else: # "10,50" o formatos mixtos
                    processed_str = raw_numeric_str.replace(',', '.') # Coma es decimal
            # else: len(parts) == 1, no commas, no change.
        # else: No dots or commas, processed_str remains raw_numeric_str (integer)

        try:
            return Decimal(processed_str)
        except InvalidOperation:
            logger.error(f"No se pudo parsear el precio: '{price_str}' (procesado como '{processed_str}') a Decimal")
            return None

    def _parse_volume_string(self, volume_str: str) -> int | None:
        """
        Parsea un string de volumen (ej. "1,234") a int.
        """
        if not volume_str:
            return None
        try:
            return int(volume_str.replace(',', '').replace('.', '')) # Eliminar comas y puntos
        except ValueError:
            logger.error(f"No se pudo parsear el volumen: '{volume_str}' a int")
            return None

    def get_item_price_overview(self, market_hash_name: str, delay_seconds: float = 2.0) -> dict | None:
        """
        Obtiene la información de precios para un ítem usando el endpoint priceoverview.

        Args:
            market_hash_name: El nombre del ítem (ej. "AK-47 | Redline (Field-Tested)").
            delay_seconds: Tiempo de espera antes de realizar la solicitud para evitar rate limits.

        Returns:
            Un diccionario con los datos del ítem si la solicitud es exitosa, None en caso contrario.
            Ejemplo de retorno exitoso:
            {
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "lowest_price": Decimal("10.50"), // Puede ser None si no está disponible
                "median_price": Decimal("10.75"), // Puede ser None si no está disponible
                "volume": 1234, // Puede ser None si no está disponible
                "currency_symbol": "$"
            }
        """
        if not market_hash_name:
            logger.warning("market_hash_name está vacío. No se puede obtener el precio.")
            return None

        time.sleep(random.uniform(delay_seconds, delay_seconds + 2.0)) # Delay aleatorio

        encoded_name = urllib.parse.quote(market_hash_name)
        url = (f"{self.BASE_URL_PRICEOVERVIEW}?appid={self.appid}&currency={self.currency}"
               f"&market_hash_name={encoded_name}")

        headers = {'User-Agent': self.user_agent}
        
        logger.debug(f"Solicitando datos de SCM para: {market_hash_name} desde URL: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                logger.warning(f"Rate limited (429) para {market_hash_name}. Esperando más tiempo antes de un posible reintento.")
                return None

            response.raise_for_status() 

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    lowest_price_str = data.get("lowest_price")
                    median_price_str = data.get("median_price")
                    volume_str = data.get("volume")

                    logger.info(f"Datos recibidos para {market_hash_name}: Lowest='{lowest_price_str}', Median='{median_price_str}', Volume='{volume_str}'")

                    lowest_price = self._parse_price_string(lowest_price_str) if lowest_price_str else None
                    median_price = self._parse_price_string(median_price_str) if median_price_str else None
                    volume = self._parse_volume_string(volume_str) if volume_str else None
                    
                    currency_symbol = "$" if self.currency == "1" else "" # Simplificación inicial

                    # Intenta extraer el símbolo de la moneda de lowest_price_str o median_price_str
                    price_str_for_symbol = lowest_price_str or median_price_str
                    if price_str_for_symbol:
                        # Extraer todos los caracteres no numéricos y no separadores al principio del string
                        temp_symbol = ""
                        for char_in_price in price_str_for_symbol.strip():
                            if not char_in_price.isdigit() and char_in_price not in ['.', ',']:
                                temp_symbol += char_in_price
                            else:
                                break # Parar al primer dígito o separador
                        
                        # Eliminar espacios del símbolo extraído
                        temp_symbol = temp_symbol.strip()

                        if temp_symbol: # Si se encontró un símbolo
                            currency_symbol = temp_symbol
                        elif currency_symbol == "$" and not price_str_for_symbol.startswith("$"):
                            # Si asumimos USD y no empieza con $, es raro. Mantener símbolo por defecto o loguear.
                            logger.debug(f"Símbolo de moneda por defecto '{currency_symbol}' no coincide con el inicio de '{price_str_for_symbol}'. Se mantiene por defecto.")


                    # Si no hay ni lowest_price ni median_price, el item podría no estar disponible o ser un error.
                    # Se considera un fallo parcial si 'success' es true pero no hay datos de precio parseables.
                    if lowest_price is None and median_price is None:
                        logger.warning(f"No se pudieron parsear precios (lowest/median) para {market_hash_name}, aunque success=true. Datos: {data}")
                        # Decidimos devolver None si no hay precios, en lugar de datos parciales sin precios.
                        # Si se quisiera devolver volumen aunque no haya precios, se cambiaría esta lógica.
                        return None

                    return {
                        "market_hash_name": market_hash_name,
                        "lowest_price": lowest_price,
                        "median_price": median_price,
                        "volume": volume,
                        "currency_symbol": currency_symbol
                    }
                else:
                    logger.warning(f"Solicitud a SCM para {market_hash_name} no exitosa (success: false). Respuesta: {data}")
                    return None
            else:
                # Esto no debería alcanzarse si raise_for_status() funciona como se espera para 200
                logger.error(f"Respuesta inesperada de SCM para {market_hash_name}. Status: {response.status_code}. Respuesta: {response.text[:200]}")
                return None

        except requests.exceptions.HTTPError as http_err:
            # El error 429 ya se maneja arriba, pero otros errores HTTP pueden ocurrir.
            logger.error(f"Error HTTP para {market_hash_name}: {http_err} - Status: {response.status_code if 'response' in locals() else 'N/A'}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Timeout en la solicitud a SCM para {market_hash_name} en la URL: {url}")
            return None
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Error en la solicitud a SCM para {market_hash_name}: {req_err}")
            return None
        except ValueError: # Incluye JSONDecodeError
            logger.error(f"No se pudo decodificar JSON para {market_hash_name}. Contenido: {response.text[:200] if 'response' in locals() else 'N/A'}")
            return None

if __name__ == '__main__':
    # Ejemplo de uso básico (requiere que configure_logging() se llame globalmente o aquí)
    configure_logging(log_level=logging.DEBUG) # Para ver todos los logs
    
    scraper = SteamMarketScraper()
    
    # Items de ejemplo
    items_to_test = [
        "AK-47 | Redline (Field-Tested)",
        "Glove Case Key", # Commodity
        "Sticker | Natus Vincere (Holo) | Katowice 2014", # Item caro y raro
        "NombreDeItemInexistente12345" # Para probar fallo
    ]
    
    for item_name in items_to_test:
        logger.info(f"--- Probando ítem: {item_name} ---")
        price_data = scraper.get_item_price_overview(item_name, delay_seconds=1.0) # Menor delay para pruebas locales
        if price_data:
            print(f"Datos para {item_name}:")
            for key, value in price_data.items():
                if isinstance(value, Decimal):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"No se pudieron obtener datos para {item_name}")
        print("-" * 30)

    # Prueba con moneda diferente (hipotético, necesitaría códigos de moneda SCM reales y verificar formato)
    # scraper_eur = SteamMarketScraper(currency="3") # Suponiendo que 3 es EUR
    # price_data_eur = scraper_eur.get_item_price_overview("AK-47 | Redline (Field-Tested)")
    # if price_data_eur:
    #     print(f"Datos (EUR) para AK-47 | Redline (Field-Tested): {price_data_eur}")

    # Prueba de _parse_price_string
    print("--- Pruebas de _parse_price_string ---")
    test_prices = ["$10.50", "€20,75", "£5.99", "CDN$ 12.34", "1.234,56€", "6,789.00 USD", "InvalidPrice", "", None, "CHF 15"]
    for tp in test_prices:
        parsed = scraper._parse_price_string(tp)
        print(f"Original: '{tp}', Parsed: {parsed} (Type: {type(parsed).__name__})")

    print("--- Pruebas de _parse_volume_string ---")
    test_volumes = ["1,234", "567", "1.000.000", "InvalidVolume", "", None]
    for tv in test_volumes:
        parsed = scraper._parse_volume_string(tv)
        print(f"Original: '{tv}', Parsed: {parsed} (Type: {type(parsed).__name__})") 