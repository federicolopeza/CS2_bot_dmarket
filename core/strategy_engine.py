# core/strategy_engine.py
import logging
import time
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer
from core.data_manager import get_db, SkinsMaestra, PreciosHistoricos

logger = logging.getLogger(__name__)

DEFAULT_GAME_ID = "a8db" # CS2 Game ID en DMarket

class StrategyEngine:
    """
    Motor para ejecutar estrategias de trading en DMarket.
    """

    def __init__(self, dmarket_connector: DMarketAPI, market_analyzer: MarketAnalyzer, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el StrategyEngine.

        Args:
            dmarket_connector (DMarketAPI): Instancia del conector de DMarket.
            market_analyzer (MarketAnalyzer): Instancia del analizador de mercado.
            config (Optional[Dict[str, Any]], optional): Configuración para umbrales,
                                                         parámetros de estrategia, etc.
        """
        self.connector = dmarket_connector
        self.analyzer = market_analyzer
        self.config = self._get_default_config() # Empezar con los defaults
        if config: # Si se proporciona una configuración (no None y no vacía)
            self.config.update(config) # Actualizar los defaults con la configuración proporcionada
            
        self.dmarket_fee_info: Optional[Dict[str, Any]] = None # Para cachear las tasas

        logger.info(f"StrategyEngine inicializado con configuración: {self.config}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Retorna una configuración por defecto si no se provee una."""
        return {
            "min_profit_usd_basic_flip": 0.50, # Mínimo beneficio en USD para un flip básico
            "min_profit_percentage_basic_flip": 0.05, # Mínimo % de beneficio para un flip básico (5%)
            "max_items_to_scan_per_run": 100, # Límite de ítems a escanear en una ejecución
            "min_price_usd_for_sniping": 1.00, # Precio mínimo de un ítem para considerarlo para sniping
            "snipe_discount_percentage": 0.15, # % de descuento sobre PME para considerar un snipe (15%)
            "game_id": DEFAULT_GAME_ID,
            "delay_between_items_sec": 1.0 # Nueva config para delay
        }

    def _fetch_and_cache_fee_info(self, game_id: str) -> bool:
        """
        Obtiene y cachea las tasas de comisión de DMarket para un juego.
        Retorna True si fue exitoso, False en caso contrario.
        """
        if self.dmarket_fee_info and self.dmarket_fee_info.get("gameId") == game_id:
            logger.debug(f"Usando tasas de comisión cacheadas para el juego {game_id}.")
            return True
        
        logger.info(f"Obteniendo tasas de comisión de DMarket para el juego {game_id}...")
        response = self.connector.get_fee_rates(game_id=game_id)

        if response and "error" not in response and "rates" in response:
            self.dmarket_fee_info = response
            # Podríamos parsear y almacenar las tasas de una forma más estructurada si es necesario.
            # Por ahora, guardamos la respuesta completa.
            # Ejemplo: self.dmarket_sale_fee_percentage = float(response['rates'][0]['amount'])
            logger.info(f"Tasas de comisión obtenidas y cacheadas para {game_id}: {self.dmarket_fee_info}")
            return True
        else:
            logger.error(f"No se pudieron obtener las tasas de comisión para {game_id}. Respuesta: {response}")
            self.dmarket_fee_info = None # Invalidar cache si falla
            return False

    def _calculate_dmarket_sale_fee_cents(self, item_price_cents: int) -> int:
        """
        Calcula la comisión de venta de DMarket en centavos para un precio dado en centavos.
        Utiliza la información de `self.dmarket_fee_info`.
        Se debe llamar a `_fetch_and_cache_fee_info` antes.

        Args:
            item_price_cents (int): Precio del ítem en centavos.

        Returns:
            int: La comisión de venta calculada en centavos.
                 Retorna 0 si no se pueden calcular las tasas.
        """
        if not self.dmarket_fee_info or "rates" not in self.dmarket_fee_info:
            logger.warning("No hay información de tasas de DMarket disponible para calcular comisión. Se asume 0.")
            return 0

        # Asumimos que la primera tasa en 'rates' es la relevante (exchange/sale fee)
        # Esto podría necesitar ser más robusto si hay múltiples tipos de tasas.
        try:
            sale_fee_rate_info = next(filter(lambda r: r.get('type') == 'exchange', self.dmarket_fee_info['rates']), None)
            if not sale_fee_rate_info or 'amount' not in sale_fee_rate_info:
                 sale_fee_rate_info = self.dmarket_fee_info['rates'][0] # Fallback a la primera si no hay 'exchange'

            fee_percentage_str = sale_fee_rate_info.get('amount')
            if not fee_percentage_str:
                logger.error("Formato de tasa de comisión inesperado, no se encontró 'amount'.")
                return 0
            
            fee_percentage = float(fee_percentage_str) # Ej: "0.030" para 3%
            
            calculated_fee_cents = int(item_price_cents * fee_percentage)

            min_commission_info = self.dmarket_fee_info.get('minCommission')
            if min_commission_info and min_commission_info.get('currency') == 'USD':
                min_commission_cents = int(float(min_commission_info.get('amount', "0")) * 100)
                if calculated_fee_cents < min_commission_cents:
                    logger.debug(f"Comisión calculada ({calculated_fee_cents/100} USD) es menor que la mínima ({min_commission_cents/100} USD). Usando comisión mínima.")
                    return min_commission_cents
            
            return calculated_fee_cents
        except (IndexError, ValueError, TypeError, KeyError) as e:
            logger.error(f"Error al parsear o calcular la comisión de DMarket: {e}. Info de tasas: {self.dmarket_fee_info}")
            return 0 # O manejar el error de otra forma

    def _find_basic_flips(self, item_title: str, current_sell_offers: List[Dict[str, Any]], current_buy_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifica oportunidades de "Flip Básico" (comprar barato, vender caro en DMarket).
        Considera LSO (Lowest Sell Offer) vs HBO (Highest Buy Order).
        """
        opportunities = []
        logger.info(f"Buscando flips básicos para: {item_title}")

        if not current_sell_offers or not current_buy_orders:
            logger.debug(f"No hay suficientes datos de ofertas/órdenes para buscar flips básicos en {item_title}.")
            return opportunities

        # 1. Extraer LSO (Lowest Sell Offer) en centavos
        lowest_sell_price_cents: Optional[int] = None
        lso_offer_details: Optional[Dict[str, Any]] = None

        for offer in current_sell_offers:
            try:
                price_str = offer.get('price', {}).get('USD')
                if price_str:
                    price_cents = int(price_str)
                    if lowest_sell_price_cents is None or price_cents < lowest_sell_price_cents:
                        lowest_sell_price_cents = price_cents
                        lso_offer_details = offer # Guardar detalles de la oferta LSO
            except (ValueError, TypeError):
                logger.warning(f"Error parseando precio de oferta de venta para {item_title}: {offer}")
                continue
        
        if lowest_sell_price_cents is None:
            logger.debug(f"No se encontró LSO válida para {item_title}.")
            return opportunities
        
        logger.debug(f"LSO para {item_title}: {lowest_sell_price_cents / 100:.2f} USD (Oferta: {lso_offer_details.get('assetId', 'N/A') if lso_offer_details else 'N/A'})")

        # 2. Extraer HBO (Highest Buy Order) en centavos
        highest_buy_price_cents: Optional[int] = None
        hbo_order_details: Optional[Dict[str, Any]] = None

        for order in current_buy_orders:
            try:
                # El formato de buy_offers es ligeramente diferente: order['price']['USD']
                price_str = order.get('price', {}).get('USD') 
                if price_str:
                    price_cents = int(price_str)
                    if highest_buy_price_cents is None or price_cents > highest_buy_price_cents:
                        highest_buy_price_cents = price_cents
                        hbo_order_details = order # Guardar detalles de la orden HBO
            except (ValueError, TypeError):
                logger.warning(f"Error parseando precio de orden de compra para {item_title}: {order}")
                continue

        if highest_buy_price_cents is None:
            logger.debug(f"No se encontró HBO válida para {item_title}.")
            return opportunities

        logger.debug(f"HBO para {item_title}: {highest_buy_price_cents / 100:.2f} USD (Orden: {hbo_order_details.get('offerId', 'N/A') if hbo_order_details else 'N/A'})")

        # 3. Calcular beneficio potencial
        # Si compramos la LSO y la vendemos instantáneamente a la HBO.
        # El precio de compra es LSO. El precio de venta es HBO.
        # La comisión se aplica sobre el precio de venta (HBO).
        
        if lowest_sell_price_cents >= highest_buy_price_cents:
            logger.debug(f"No hay spread positivo para {item_title} (LSO: {lowest_sell_price_cents}, HBO: {highest_buy_price_cents}).")
            return opportunities

        # Asegurar que las tasas de comisión estén cargadas
        game_id = self.config.get("game_id", DEFAULT_GAME_ID)
        if not self.dmarket_fee_info or self.dmarket_fee_info.get("gameId") != game_id:
            if not self._fetch_and_cache_fee_info(game_id):
                logger.warning(f"No se pudieron obtener las tasas de comisión para {item_title}, no se puede calcular profit de flip.")
                return opportunities
        
        commission_cents = self._calculate_dmarket_sale_fee_cents(item_price_cents=highest_buy_price_cents)
        
        potential_profit_cents = highest_buy_price_cents - lowest_sell_price_cents - commission_cents
        
        if potential_profit_cents <= 0:
            logger.debug(f"Profit no positivo para {item_title} después de comisión (Profit: {potential_profit_cents} centavos).")
            return opportunities

        potential_profit_usd = potential_profit_cents / 100.0
        cost_usd = lowest_sell_price_cents / 100.0
        
        # Evitar división por cero si el costo es 0 (aunque no debería serlo para LSO)
        profit_percentage = (potential_profit_usd / cost_usd) if cost_usd > 0 else float('inf')

        logger.info(f"Flip Potencial para {item_title}: Comprar a {cost_usd:.2f} USD, Vender a {highest_buy_price_cents/100.0:.2f} USD, Comisión: {commission_cents/100.0:.2f} USD, Profit: {potential_profit_usd:.2f} USD ({profit_percentage*100:.2f}%)")

        # 4. Verificar umbrales de beneficio
        min_profit_usd = self.config.get("min_profit_usd_basic_flip", 0.50)
        min_profit_percentage = self.config.get("min_profit_percentage_basic_flip", 0.05)

        if potential_profit_usd >= min_profit_usd and profit_percentage >= min_profit_percentage:
            opportunity = {
                "type": "basic_flip",
                "item_title": item_title,
                "buy_price_usd": cost_usd,
                "sell_price_usd": highest_buy_price_cents / 100.0,
                "profit_usd": potential_profit_usd,
                "profit_percentage": profit_percentage,
                "lso_details": lso_offer_details, # Incluye assetId, etc.
                "hbo_details": hbo_order_details, # Incluye offerId, etc.
                "commission_usd": commission_cents / 100.0,
                "timestamp": time.time() # Usar time.time() para un timestamp flotante simple
            }
            opportunities.append(opportunity)
            logger.info(f"OPORTUNIDAD DE FLIP BÁSICO ENCONTRADA para {item_title}: Profit {potential_profit_usd:.2f} USD ({profit_percentage*100:.2f}%)")
        else:
            logger.debug(f"Flip para {item_title} no cumple umbrales de beneficio (Profit: {potential_profit_usd:.2f} USD vs Min: {min_profit_usd:.2f} USD, %Profit: {profit_percentage*100:.2f}% vs Min: {min_profit_percentage*100:.2f}%)")
            
        return opportunities

    def _find_snipes(self, item_title: str, current_sell_offers: List[Dict[str, Any]], historical_prices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifica oportunidades de "Sniping" (ítems listados significativamente por debajo de su PME).
        """
        opportunities = []
        logger.info(f"Buscando snipes para: {item_title}")

        if not current_sell_offers:
            logger.debug(f"No hay ofertas de venta actuales para {item_title}, no se pueden buscar snipes.")
            return opportunities

        estimated_market_price_usd = self.analyzer.calculate_estimated_market_price(
            market_hash_name=item_title,
            historical_prices=historical_prices,
            current_offers=current_sell_offers 
        )

        if estimated_market_price_usd is None:
            logger.debug(f"No se pudo calcular PME para {item_title}, no se pueden buscar snipes.")
            return opportunities
        
        logger.debug(f"PME para {item_title}: {estimated_market_price_usd:.2f} USD")

        # Asegurar que las tasas de comisión estén cargadas para calcular el profit potencial
        game_id = self.config.get("game_id", DEFAULT_GAME_ID)
        if not self.dmarket_fee_info or self.dmarket_fee_info.get("gameId") != game_id:
            if not self._fetch_and_cache_fee_info(game_id):
                logger.warning(f"No se pudieron obtener las tasas de comisión para {item_title}, no se puede calcular profit de snipe.")
                # Podríamos decidir retornar aquí, o continuar y marcar el profit como no calculado.
                # Por ahora, el cálculo del profit se omitirá si las tasas no están.
                pass # Continuar para identificar el snipe, el profit será None o 0

        min_price_for_sniping_usd = self.config.get("min_price_usd_for_sniping", 1.00)
        snipe_discount_percentage_threshold = self.config.get("snipe_discount_percentage", 0.15)

        for offer in current_sell_offers:
            try:
                offer_price_str = offer.get('price', {}).get('USD')
                if not offer_price_str:
                    continue
                
                offer_price_cents = int(offer_price_str)
                offer_price_usd = offer_price_cents / 100.0

                if offer_price_usd < min_price_for_sniping_usd:
                    logger.debug(f"Oferta para {item_title} a {offer_price_usd:.2f} USD está por debajo del umbral de precio mínimo para sniping ({min_price_for_sniping_usd:.2f} USD).")
                    continue
                
                # Evitar ZeroDivisionError si PME es 0 o muy cercano a 0
                if estimated_market_price_usd <= 0:
                    logger.debug(f"PME para {item_title} es {estimated_market_price_usd:.2f}, no se puede calcular descuento de snipe.")
                    continue

                discount_percentage = (estimated_market_price_usd - offer_price_usd) / estimated_market_price_usd

                if discount_percentage >= snipe_discount_percentage_threshold:
                    logger.info(f"SNIPE POTENCIAL para {item_title}: Oferta a {offer_price_usd:.2f} USD, PME: {estimated_market_price_usd:.2f} USD (Descuento: {discount_percentage*100:.2f}%)")

                    # Calcular profit potencial si se revende al PME
                    potential_sell_price_cents = int(estimated_market_price_usd * 100)
                    commission_cents = self._calculate_dmarket_sale_fee_cents(item_price_cents=potential_sell_price_cents)
                    
                    profit_cents = potential_sell_price_cents - offer_price_cents - commission_cents
                    profit_usd = profit_cents / 100.0
                    
                    if profit_usd > 0: # Solo registrar si el profit después de comisión es positivo
                        opportunity = {
                            "type": "snipe",
                            "item_title": item_title,
                            "pme_usd": estimated_market_price_usd,
                            "offer_price_usd": offer_price_usd,
                            "discount_percentage": discount_percentage,
                            "potential_profit_usd": profit_usd,
                            "offer_details": offer, # assetId, attributes, etc.
                            "commission_on_pme_usd": commission_cents / 100.0,
                            "timestamp": time.time()
                        }
                        opportunities.append(opportunity)
                        logger.info(f"OPORTUNIDAD DE SNIPE ENCONTRADA para {item_title}: Comprar a {offer_price_usd:.2f}, revender a PME ~{estimated_market_price_usd:.2f}, Profit Potencial: {profit_usd:.2f} USD")
                    else:
                        logger.debug(f"Snipe para {item_title} a {offer_price_usd:.2f} USD no genera profit positivo después de comisiones al PME ({profit_usd:.2f} USD).")
                else:
                    if discount_percentage > 0.01: # Loguear si hay al menos un 1% de descuento pero no es snipe
                         logger.debug(f"Oferta para {item_title} a {offer_price_usd:.2f} USD (PME: {estimated_market_price_usd:.2f} USD) no alcanza descuento de snipe ({discount_percentage*100:.2f}% < {snipe_discount_percentage_threshold*100:.2f}%).")

            except (ValueError, TypeError) as e:
                logger.warning(f"Error parseando precio de oferta de venta para snipe en {item_title}: {offer}. Error: {e}")
                continue
            # La ZeroDivisionError ya se maneja con la comprobación de estimated_market_price_usd > 0
            
        return opportunities

    def run_strategies(self, items_to_scan: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Ejecuta las estrategias configuradas para una lista de ítems.
        """
        all_opportunities = {
            "basic_flips": [],
            "snipes": []
        }
        
        if not items_to_scan:
            logger.warning("No se proporcionaron ítems para escanear.")
            return all_opportunities

        game_id = self.config.get("game_id", DEFAULT_GAME_ID)
        if not self._fetch_and_cache_fee_info(game_id):
            logger.error(f"Fallo al obtener tasas de comisión para el juego {game_id}. Las estrategias pueden no funcionar correctamente.")
            # Se podría retornar aquí si las comisiones son cruciales para todas las estrategias
            # return all_opportunities 

        db: Session = next(get_db()) # Obtener sesión de BD

        for item_title in items_to_scan[:self.config.get("max_items_to_scan_per_run", 100)]:
            logger.info(f"--- Procesando estrategias para: {item_title} ---")
            
            # 1. Obtener ofertas de venta (LSO) de DMarket
            logger.debug(f"Obteniendo ofertas de venta para {item_title}...")
            response_sell_offers = self.connector.get_offers_by_title(title=item_title, limit=100, currency="USD") # Aumentar límite para mejor LSO
            current_sell_offers = []
            if response_sell_offers and "error" not in response_sell_offers and "objects" in response_sell_offers:
                current_sell_offers = response_sell_offers.get('objects', [])
                logger.debug(f"Encontradas {len(current_sell_offers)} ofertas de venta para {item_title}.")
            else:
                logger.warning(f"No se pudieron obtener ofertas de venta para {item_title} o hubo un error: {response_sell_offers.get('error') if response_sell_offers else 'Respuesta vacía'}")

            # 2. Obtener órdenes de compra (HBO) de DMarket
            logger.debug(f"Obteniendo órdenes de compra para {item_title}...")
            response_buy_orders = self.connector.get_buy_offers(title=item_title, game_id=game_id, limit=100, order_by="price", order_dir="desc", currency="USD") # Aumentar límite
            current_buy_orders = []
            if response_buy_orders and "error" not in response_buy_orders and "offers" in response_buy_orders:
                current_buy_orders = response_buy_orders.get('offers', [])
                logger.debug(f"Encontradas {len(current_buy_orders)} órdenes de compra para {item_title}.")
            else:
                logger.warning(f"No se pudieron obtener órdenes de compra para {item_title} o hubo un error: {response_buy_orders.get('error') if response_buy_orders else 'Respuesta vacía'}")
            
            # 3. Obtener precios históricos (de la BD)
            logger.debug(f"Obteniendo precios históricos de la BD para {item_title}...")
            skin_maestra_entry = db.query(SkinsMaestra).filter(SkinsMaestra.market_hash_name == item_title).first()
            historical_prices_db_formatted = []
            if skin_maestra_entry and skin_maestra_entry.precios: # Changed precios_historicos to precios
                # Convertir a formato esperado por MarketAnalyzer (lista de dicts)
                # Ordenar por fecha descendente para tomar los más recientes si es necesario limitar
                sorted_historical_prices = sorted(skin_maestra_entry.precios, key=lambda p: p.timestamp, reverse=True) # Changed precios_historicos to precios
                
                historical_prices_db_formatted = [ # Por ahora, tomar todos
                    {"price_usd": p.price, "timestamp": p.timestamp.isoformat(), "fuente_api": p.fuente_api} # Changed p.price_usd to p.price 
                    for p in sorted_historical_prices
                ]
                logger.debug(f"Encontrados {len(historical_prices_db_formatted)} registros de precios históricos en BD para {item_title}.")
            else:
                logger.debug(f"No se encontraron precios históricos en BD para {item_title}.")


            # Ejecutar estrategias
            if current_sell_offers and current_buy_orders: # Basic flips necesita ambos
                logger.info(f"Ejecutando Basic Flips para {item_title}...")
                flip_ops = self._find_basic_flips(item_title, current_sell_offers, current_buy_orders)
                if flip_ops:
                    all_opportunities["basic_flips"].extend(flip_ops)
                    logger.info(f"Encontradas {len(flip_ops)} oportunidades de Basic Flip para {item_title}.")
            
            if current_sell_offers: # Snipes necesita ofertas de venta (y opcionalmente históricos)
                logger.info(f"Ejecutando Snipes para {item_title}...")
                snipe_ops = self._find_snipes(item_title, current_sell_offers, historical_prices_db_formatted)
                if snipe_ops:
                    all_opportunities["snipes"].extend(snipe_ops)
                    logger.info(f"Encontradas {len(snipe_ops)} oportunidades de Snipe para {item_title}.")
            
            # Pausa breve para no saturar la API de DMarket si se escanean muchos ítems rápidamente.
            time.sleep(self.config.get("delay_between_items_sec", 1.0)) 

        try:
            db.close() # Cerrar sesión de BD después de iterar todos los ítems
        except Exception as e:
            logger.error(f"Error al cerrar la sesión de base de datos: {e}")

        logger.info("Ejecución de todas las estrategias completada.")
        return all_opportunities

if __name__ == '__main__':
    from utils.logger import configure_logging
    configure_logging(log_level=logging.DEBUG)

    # Se necesitarían mocks para DMarketAPI y MarketAnalyzer para una prueba directa aquí.
    # O una configuración real con claves API si se quisiera probar la conexión.
    logger.info("Ejecutando bloque __main__ de strategy_engine.py (solo para estructura inicial).")

    # Ejemplo (muy simplificado, necesitaría mocks adecuados):
    class MockDMarketAPI:
        def get_fee_rates(self, game_id):
            logger.debug(f"MockDMarketAPI.get_fee_rates llamada para {game_id}")
            if game_id == DEFAULT_GAME_ID:
                return {
                    "gameId": game_id,
                    "rates": [{"type": "exchange", "amount": "0.05"}], # 5% fee
                    "minCommission": {"amount": "0.01", "currency": "USD"}
                }
            return {"error": "not found"}
        # ... otros métodos mockeados según necesidad ...

    class MockMarketAnalyzer:
        def calculate_estimated_market_price(self, market_hash_name, historical_prices, current_offers):
            logger.debug(f"MockMarketAnalyzer.calculate_estimated_market_price llamada para {market_hash_name}")
            if market_hash_name == "Test Item 1":
                return 10.0 # 10 USD PME
            return None

    mock_connector = MockDMarketAPI()
    mock_analyzer = MockMarketAnalyzer()
    
    engine = StrategyEngine(dmarket_connector=mock_connector, market_analyzer=mock_analyzer)
    
    # Probar cálculo de comisión
    fee_fetched = engine._fetch_and_cache_fee_info(DEFAULT_GAME_ID)
    assert fee_fetched
    if fee_fetched:
        commission1 = engine._calculate_dmarket_sale_fee_cents(item_price_cents=1000) # 10 USD
        logger.info(f"Comisión calculada para 1000 centavos: {commission1} centavos") # Esperado: 50 (5% de 1000)
        assert commission1 == 50

        commission2 = engine._calculate_dmarket_sale_fee_cents(item_price_cents=10) # 0.10 USD
        logger.info(f"Comisión calculada para 10 centavos: {commission2} centavos") # Esperado: 1 (min commission $0.01)
        assert commission2 == 1


    # Probar run_strategies (con lógica interna aún como placeholder)
    # items = ["Test Item 1", "Test Item 2"]
    # opportunities = engine.run_strategies(items)
    # logger.info(f"Oportunidades encontradas (placeholders): {opportunities}")