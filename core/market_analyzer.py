# core/market_analyzer.py
import logging
from typing import List, Dict, Any, Optional

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class MarketAnalyzer:
    """
    Clase para analizar datos de mercado y atributos de ítems.
    """

    def __init__(self):
        """
        Inicializa el MarketAnalyzer.
        Podría tomar dependencias como el data_manager si es necesario para
        acceder a datos históricos directamente, o recibirlos en los métodos.
        """
        logger.info("MarketAnalyzer inicializado.")

    def calculate_estimated_market_price(
        self,
        market_hash_name: str,
        historical_prices: List[Dict[str, Any]], # Lista de registros de PreciosHistoricos
        current_offers: List[Dict[str, Any]] # Lista de ofertas actuales de DMarket (formato de get_offers_by_title)
    ) -> Optional[float]:
        """
        Calcula el Precio de Mercado Estimado (PME) para un ítem.

        Esta es una implementación inicial y puede ser refinada.
        Considerará precios históricos y ofertas actuales.

        Args:
            market_hash_name (str): El nombre del ítem.
            historical_prices (List[Dict[str, Any]]): Una lista de diccionarios,
                cada uno representando un registro de precio histórico para el ítem.
                Ej: [{'price_usd': 10.50, 'timestamp': '2023-01-01T10:00:00Z'}, ...]
            current_offers (List[Dict[str, Any]]): Una lista de diccionarios,
                cada uno representando una oferta de venta actual en DMarket.
                Ej: [{'price': {'USD': '1100'}, ...}, ...]

        Returns:
            Optional[float]: El precio de mercado estimado en USD, o None si no se puede calcular.
        """
        logger.info(f"Calculando PME para: {market_hash_name}")

        if not historical_prices and not current_offers:
            logger.warning(f"No hay datos históricos ni ofertas actuales para {market_hash_name}. No se puede calcular PME.")
            return None

        # Lógica de ejemplo (muy básica, a ser expandida):
        # Podríamos promediar precios históricos recientes,
        # o tomar el precio más bajo de las ofertas actuales si hay suficientes.
        # O una combinación ponderada.

        # Por ahora, si hay ofertas actuales, tomemos la más baja como una primera aproximación.
        # DMarket devuelve precios en centavos como string.
        current_offer_prices_usd = []
        if current_offers:
            for offer in current_offers:
                try:
                    price_str = offer.get('price', {}).get('USD')
                    if price_str:
                        current_offer_prices_usd.append(int(price_str) / 100.0)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parseando precio de oferta para {market_hash_name}: {offer}. Error: {e}")
            
        # Prioritize historical prices if available
        if historical_prices:
            try:
                # Ensure historical prices are valid numbers
                valid_historical_prices = [p['price_usd'] for p in historical_prices if isinstance(p.get('price_usd'), (int, float))]
                if valid_historical_prices:
                    avg_historical_price = sum(valid_historical_prices) / len(valid_historical_prices)
                    logger.debug(f"Usando precio histórico promedio para {market_hash_name}: {avg_historical_price:.2f} USD")
                    return avg_historical_price
                else:
                    logger.warning(f"No hay precios históricos válidos para {market_hash_name} después de filtrar.")
            except (TypeError, KeyError, ZeroDivisionError) as e:
                logger.error(f"Error al calcular el promedio de precios históricos para {market_hash_name}: {e}")

        # Fallback to current offers if no valid historical PME could be calculated
        if current_offer_prices_usd:
            min_current_price = min(current_offer_prices_usd)
            logger.debug(f"Usando precio mínimo de ofertas actuales para {market_hash_name} como PME (fallback): {min_current_price:.2f} USD")
            return min_current_price
            
        logger.warning(f"No se pudo determinar PME para {market_hash_name} ni con datos históricos ni con ofertas actuales.")
        return None

if __name__ == '__main__':
    # Ejemplo de uso y prueba simple (requerirá datos mockeados)
    # Añadir utils.logger a la importación si no está
    from utils.logger import configure_logging 
    configure_logging(log_level=logging.DEBUG) # Asumiendo que tienes configure_logging en utils
    
    analyzer = MarketAnalyzer()

    mock_historical = [
        {'price_usd': 10.00, 'timestamp': '2023-10-01T10:00:00Z'},
        {'price_usd': 10.20, 'timestamp': '2023-10-02T10:00:00Z'},
        {'price_usd': 9.80, 'timestamp': '2023-10-03T10:00:00Z'},
    ]
    
    mock_offers_dmarket = [
        {'assetId': '1', 'price': {'USD': '1050'}, 'amount': 1}, # $10.50
        {'assetId': '2', 'price': {'USD': '1030'}, 'amount': 1}, # $10.30
        {'assetId': '3', 'price': {'USD': '1100'}, 'amount': 1}, # $11.00
    ]

    mock_offers_dmarket_no_price = [
        {'assetId': '1', 'amount': 1}, 
    ]
    
    # Caso 1: Con ofertas actuales
    pme1 = analyzer.calculate_estimated_market_price("AK-47 | Redline", mock_historical, mock_offers_dmarket)
    logger.info(f"PME Caso 1 (con ofertas): {pme1}") # Esperado: 10.30

    # Caso 2: Sin ofertas actuales, solo históricas
    pme2 = analyzer.calculate_estimated_market_price("M4A1-S | Hyper Beast", mock_historical, [])
    logger.info(f"PME Caso 2 (solo históricas): {pme2}") # Esperado: promedio de mock_historical (10.00)

    # Caso 3: Sin datos
    pme3 = analyzer.calculate_estimated_market_price("Desert Eagle | Blaze", [], [])
    logger.info(f"PME Caso 3 (sin datos): {pme3}") # Esperado: None

    # Caso 4: Con ofertas pero sin campo de precio o formato incorrecto
    pme4 = analyzer.calculate_estimated_market_price("AWP | Dragon Lore", [], mock_offers_dmarket_no_price)
    logger.info(f"PME Caso 4 (ofertas sin precio): {pme4}") # Esperado: None