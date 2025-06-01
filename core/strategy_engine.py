# core/strategy_engine.py
import logging
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer, AttributeEvaluation
from core.volatility_analyzer import VolatilityAnalyzer
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
        self.volatility_analyzer = VolatilityAnalyzer(config.get('volatility_config') if config else None)
        self.config = self._get_default_config() # Empezar con los defaults
        if config: # Si se proporciona una configuración (no None y no vacía)
            self.config.update(config) # Actualizar los defaults con la configuración proporcionada
            
        self.dmarket_fee_info: Optional[Dict[str, Any]] = None # Para cachear las tasas
        self._fee_cache = {} # Cache para almacenar información de comisiones

        logger.info(f"StrategyEngine inicializado con configuración: {self.config}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Retorna una configuración por defecto si no se provee una."""
        return {
            "min_profit_usd_basic_flip": 0.01, # Mínimo beneficio en USD para un flip básico (1 centavo)
            "min_profit_percentage_basic_flip": 0.01, # Mínimo % de beneficio para un flip básico (1%)
            "max_items_to_scan_per_run": 100, # Límite de ítems a escanear en una ejecución
            "min_price_usd_for_sniping": 0.25, # Precio mínimo de un ítem para considerarlo para sniping
            "snipe_discount_percentage": 0.10, # % de descuento sobre PME para considerar un snipe (10%)
            "game_id": DEFAULT_GAME_ID,
            "delay_between_items_sec": 1.0, # Nueva config para delay
            
            # Configuración para Estrategia 2: Flip por Atributos Premium
            "min_profit_usd_attribute_flip": 0.05, # Mínimo beneficio en USD para flip por atributos (5 centavos)
            "min_profit_percentage_attribute_flip": 0.05, # Mínimo % de beneficio (5%)
            "min_rarity_score_for_premium": 30.0, # Puntuación mínima de rareza para considerar premium
            "min_premium_multiplier": 1.2, # Multiplicador mínimo para considerar premium
            "max_price_usd_attribute_flip": 100.00, # Precio máximo para flip por atributos
            
            # Configuración para Estrategia 5: Arbitraje por Bloqueo de Intercambio
            "min_profit_usd_trade_lock": 0.10, # Mínimo beneficio en USD para trade lock
            "min_profit_percentage_trade_lock": 0.10, # Mínimo % de beneficio (10%)
            "trade_lock_discount_threshold": 0.15, # Descuento mínimo para considerar trade lock (15%)
            "max_trade_lock_days": 14, # Máximo días de bloqueo a considerar
            
            # Configuración para Estrategia 4: Volatilidad
            "min_profit_usd_volatility": 0.05, # Mínimo beneficio en USD para volatilidad
            "min_confidence_volatility": 0.5, # Confianza mínima para señales de volatilidad
            "max_price_usd_volatility": 1000.00, # Precio máximo para análisis de volatilidad
        }

    def _fetch_and_cache_fee_info(self, game_id: str) -> bool:
        """
        Obtiene y cachea la información de comisiones de DMarket.
        Intenta usar /exchange/v1/customized-fees.
        Retorna True si la información se obtuvo y procesó correctamente, False en caso contrario.
        """
        # Priorizar info de caché si es reciente y para el mismo juego
        cache_entry = self._fee_cache.get(game_id)
        if cache_entry and (datetime.now(timezone.utc) - cache_entry['timestamp']).total_seconds() < self.config.get("FEE_CACHE_DURATION_SECONDS", 3600):
            logger.debug(f"Usando información de comisiones cacheada para {game_id}.")
            return True

        logger.info(f"Solicitando información de comisiones (customized-fees) para el juego {game_id}...")
        
        endpoint = "/exchange/v1/customized-fees"
        query_params = {"gameId": game_id}
        try:
            response = self.connector._make_request(method="GET", endpoint=endpoint, params=query_params)

            if "error" in response or not response: # Asumiendo que una respuesta vacía también es un problema
                logger.error(f"Error al obtener customized-fees: {response.get('message', 'Respuesta vacía o error no especificado')}")
                # Guardar un intento fallido en caché para evitar reintentos rápidos
                self._fee_cache[game_id] = { 
                    'data': self.config.get("DEFAULT_FEE_INFO", {}), # Usar default si falla
                    'timestamp': datetime.now(timezone.utc)
                }
                return False

            # Imprimir directamente la respuesta para depuración
            print("DEBUG: Respuesta CRUDA de /exchange/v1/customized-fees:")
            print(response)
            # logger.info(f"Respuesta de customized-fees: {json.dumps(response, indent=2)}") # Comentado temporalmente

            processed_fee_data = None
            if isinstance(response, dict) and "defaultFee" in response:
                default_fee_info = response["defaultFee"]
                if "fraction" in default_fee_info and "minAmount" in default_fee_info:
                    try:
                        fee_rate_str = str(default_fee_info["fraction"])
                        min_commission_cents_str = str(default_fee_info["minAmount"])
                        
                        # Validar que los valores se puedan convertir
                        float(fee_rate_str) # Intenta convertir a float para validar
                        int(min_commission_cents_str) # Intenta convertir a int para validar

                        processed_fee_data = {
                            "feeRate": {"amount": fee_rate_str}, # Guardar como string, DMarketAPI espera strings
                            "minCommission": {"amount": min_commission_cents_str} # Guardar como string
                        }
                        logger.info(f"Comisiones por defecto extraídas de API: Tasa={fee_rate_str}, Mínima(centavos)={min_commission_cents_str}")
                    except ValueError as ve:
                        logger.error(f"Error al convertir valores de comisiones desde la API: {ve}. Respuesta: {default_fee_info}")
                        processed_fee_data = None # Forzar uso de defaults globales si hay error de conversión
            
            if not processed_fee_data:
                logger.warning("No se pudo extraer 'defaultFee' o sus componentes de la respuesta de customized-fees. Usando defaults globales del config.")
                processed_fee_data = self.config.get("DEFAULT_FEE_INFO", {
                    "feeRate": {"amount": "0.05"}, 
                    "minCommission": {"amount": "1"} # API defaultFee.minAmount está en centavos, default aquí también
                })


            self._fee_cache[game_id] = {
                'data': processed_fee_data,
                'timestamp': datetime.now(timezone.utc)
            }
            logger.info(f"Información de comisiones (customized-fees) para {game_id} cacheada: {processed_fee_data}")
            return True

        except Exception as e:
            logger.error(f"Excepción al obtener/procesar customized-fees para {game_id}: {e}", exc_info=True)
            self._fee_cache[game_id] = {
                'data': self.config.get("DEFAULT_FEE_INFO", {}), 
                'timestamp': datetime.now(timezone.utc)
            }
            return False

    def _calculate_dmarket_sale_fee_cents(self, item_price_cents: int) -> int:
        """Calcula la comisión de venta de DMarket en centavos."""
        fee_info_entry = self._fee_cache.get(self.config.get("DEFAULT_GAME_ID", "a8db"))
        if not fee_info_entry or not fee_info_entry.get('data'):
            logger.warning("No hay información de tasas de DMarket disponible para calcular comisión. Se asume 0.")
            return 0

        fee_data = fee_info_entry['data']
        
        fee_rate_str = fee_data.get("feeRate", {}).get("amount")
        # minCommission.amount ahora se espera que sea un string representando CENTAVOS
        min_comm_cents_str = fee_data.get("minCommission", {}).get("amount")

        if fee_rate_str is None or min_comm_cents_str is None:
            logger.error(f"Formato de comisiones inesperado: {fee_data}. Se asume comisión 0.")
            return 0

        try:
            fee_rate = float(fee_rate_str) # Ej: 0.1 para 10%
            min_commission_cents = int(min_comm_cents_str) # Ej: 1 para 1 centavo

            calculated_fee_cents = int(item_price_cents * fee_rate)
            final_fee_cents = max(calculated_fee_cents, min_commission_cents)
            
            # logger.debug(f"Cálculo comisión: Precio={item_price_cents}c, Tasa={fee_rate*100}%, MinCom={min_commission_cents}c => Calculada={calculated_fee_cents}c, Final={final_fee_cents}c")
            return final_fee_cents
        except ValueError as e:
            logger.error(f"Error al convertir valores de comisión para cálculo: {e}. Tasa str: '{fee_rate_str}', MinCom str: '{min_comm_cents_str}'. Se asume comisión 0.")
            return 0

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

        #DEBUG: Imprimir la primera current_sell_offer para ver su estructura
        if current_sell_offers:
            logger.info(f"DEBUG StrategyEngine: Primera current_sell_offer para {item_title}: {current_sell_offers[0]}")

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
        min_profit_usd = self.config.get("min_profit_usd_basic_flip", 0.01)
        min_profit_percentage = self.config.get("min_profit_percentage_basic_flip", 0.01)

        if potential_profit_usd >= min_profit_usd and profit_percentage >= min_profit_percentage:
            opportunity = {
                "strategy": "basic_flip",
                "item_title": item_title,
                "asset_id": lso_offer_details.get('assetId') if lso_offer_details else None,
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

        min_price_for_sniping_usd = self.config.get("min_price_usd_for_sniping", 0.25)
        snipe_discount_percentage_threshold = self.config.get("snipe_discount_percentage", 0.10)

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
                            "strategy": "snipe",
                            "item_title": item_title,
                            "asset_id": offer.get('assetId'),
                            "pme_usd": estimated_market_price_usd,
                            "offer_price_usd": offer_price_usd,
                            "discount_percentage": discount_percentage,
                            "profit_usd": profit_usd,
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

    def _find_attribute_premium_flips(self, item_data: Dict[str, Any], fee_info: Dict[str, Any], market_analyzer: MarketAnalyzer) -> List[Dict[str, Any]]:
        """
        Estrategia 2: Identifica oportunidades de flip basadas en atributos premium.
        Busca ítems con atributos raros/valiosos que estén subvalorados.
        """
        opportunities = []
        item_title = item_data.get('title', 'Unknown')
        current_sell_offers = item_data.get('current_sell_offers', [])
        
        logger.info(f"Buscando flips por atributos premium para: {item_title}")
        
        if not current_sell_offers:
            logger.debug(f"No hay ofertas de venta para analizar atributos en {item_title}.")
            return opportunities
        
        # Analizar cada oferta individual para evaluar sus atributos
        for offer in current_sell_offers:
            try:
                # Extraer precio de la oferta
                price_str = offer.get('price', {}).get('USD')
                if not price_str:
                    continue
                    
                offer_price_cents = int(price_str)
                offer_price_usd = offer_price_cents / 100.0
                
                # Verificar límites de precio
                max_price = self.config.get("max_price_usd_attribute_flip", 100.0)
                if offer_price_usd > max_price:
                    continue
                
                # Extraer atributos del ítem
                attributes = self._extract_item_attributes(offer)
                if not attributes:
                    continue
                
                # Evaluar rareza de atributos
                evaluation = market_analyzer.evaluate_attribute_rarity(
                    attributes=attributes,
                    stickers=offer.get('stickers', []),
                    item_name=item_title
                )
                
                # Verificar si cumple criterios de premium
                min_rarity_score = self.config.get("min_rarity_score_for_premium", 30.0)
                min_premium_multiplier = self.config.get("min_premium_multiplier", 1.2)
                
                if (evaluation.overall_rarity_score < min_rarity_score or 
                    evaluation.premium_multiplier < min_premium_multiplier):
                    continue
                
                # Calcular precio estimado con premium por atributos
                base_price_estimate = self._estimate_base_item_price(item_title, item_data)
                if not base_price_estimate:
                    continue
                
                estimated_premium_price = base_price_estimate * evaluation.premium_multiplier
                
                # Calcular beneficio potencial
                commission_cents = self._calculate_dmarket_sale_fee_cents(int(estimated_premium_price * 100))
                potential_profit_cents = int(estimated_premium_price * 100) - offer_price_cents - commission_cents
                potential_profit_usd = potential_profit_cents / 100.0
                profit_percentage = potential_profit_usd / offer_price_usd if offer_price_usd > 0 else 0
                
                # Verificar umbrales de beneficio
                min_profit_usd = self.config.get("min_profit_usd_attribute_flip", 0.05)
                min_profit_percentage = self.config.get("min_profit_percentage_attribute_flip", 0.05)
                
                if (potential_profit_usd >= min_profit_usd and 
                    profit_percentage >= min_profit_percentage):
                    
                    opportunity = {
                        "strategy": "attribute_premium_flip",
                        "item_title": item_title,
                        "asset_id": offer.get('assetId'),
                        "buy_price_usd": offer_price_usd,
                        "estimated_sell_price_usd": estimated_premium_price,
                        "potential_profit_usd": potential_profit_usd,
                        "profit_percentage": profit_percentage,
                        "commission_usd": commission_cents / 100.0,
                        "rarity_score": evaluation.overall_rarity_score,
                        "premium_multiplier": evaluation.premium_multiplier,
                        "attributes": {
                            "float_value": evaluation.float_value,
                            "float_rarity": evaluation.float_rarity.value if evaluation.float_rarity else None,
                            "pattern_index": evaluation.pattern_index,
                            "pattern_rarity": evaluation.pattern_rarity.value,
                            "stickers_value": evaluation.stickers_value,
                            "stickers_rarity": evaluation.stickers_rarity.value,
                            "stattrak": evaluation.stattrak,
                            "souvenir": evaluation.souvenir,
                            "special_attributes": evaluation.special_attributes
                        },
                        "confidence": "high" if evaluation.overall_rarity_score > 80 else "medium",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    opportunities.append(opportunity)
                    logger.info(f"Oportunidad de flip por atributos encontrada: {item_title} - "
                              f"Compra: ${offer_price_usd:.2f}, Venta estimada: ${estimated_premium_price:.2f}, "
                              f"Beneficio: ${potential_profit_usd:.2f} ({profit_percentage:.1%})")
                    
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error procesando oferta para flip por atributos en {item_title}: {e}")
                continue
        
        return opportunities

    def _find_trade_lock_opportunities(self, item_data: Dict[str, Any], fee_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Estrategia 5: Identifica oportunidades de arbitraje por bloqueo de intercambio.
        Busca ítems con trade lock que estén con descuento significativo.
        """
        opportunities = []
        item_title = item_data.get('title', 'Unknown')
        current_sell_offers = item_data.get('current_sell_offers', [])
        
        logger.info(f"Buscando oportunidades de trade lock para: {item_title}")
        
        if not current_sell_offers:
            logger.debug(f"No hay ofertas de venta para analizar trade lock en {item_title}.")
            return opportunities
        
        # Obtener precio de referencia (sin trade lock)
        reference_price = self._get_reference_price_no_trade_lock(item_title, current_sell_offers)
        if not reference_price:
            logger.debug(f"No se pudo obtener precio de referencia para {item_title}.")
            return opportunities
        
        # Analizar ofertas con trade lock
        for offer in current_sell_offers:
            try:
                # Verificar si tiene trade lock
                trade_lock_info = self._extract_trade_lock_info(offer)
                if not trade_lock_info or not trade_lock_info.get('has_trade_lock'):
                    continue
                
                # Extraer precio de la oferta
                price_str = offer.get('price', {}).get('USD')
                if not price_str:
                    continue
                    
                offer_price_cents = int(price_str)
                offer_price_usd = offer_price_cents / 100.0
                
                # Verificar duración del trade lock
                lock_days = trade_lock_info.get('days_remaining', 0)
                max_lock_days = self.config.get("max_trade_lock_days", 14)
                if lock_days > max_lock_days:
                    continue
                
                # Calcular descuento
                discount_percentage = (reference_price - offer_price_usd) / reference_price if reference_price > 0 else 0
                min_discount = self.config.get("trade_lock_discount_threshold", 0.15)
                
                if discount_percentage < min_discount:
                    continue
                
                # Calcular beneficio potencial (vender después del unlock)
                commission_cents = self._calculate_dmarket_sale_fee_cents(int(reference_price * 100))
                potential_profit_cents = int(reference_price * 100) - offer_price_cents - commission_cents
                potential_profit_usd = potential_profit_cents / 100.0
                profit_percentage = potential_profit_usd / offer_price_usd if offer_price_usd > 0 else 0
                
                # Verificar umbrales de beneficio
                min_profit_usd = self.config.get("min_profit_usd_trade_lock", 0.10)
                min_profit_percentage = self.config.get("min_profit_percentage_trade_lock", 0.10)
                
                if (potential_profit_usd >= min_profit_usd and 
                    profit_percentage >= min_profit_percentage):
                    
                    opportunity = {
                        "strategy": "trade_lock_arbitrage",
                        "item_title": item_title,
                        "asset_id": offer.get('assetId'),
                        "buy_price_usd": offer_price_usd,
                        "reference_price_usd": reference_price,
                        "potential_profit_usd": potential_profit_usd,
                        "profit_percentage": profit_percentage,
                        "commission_usd": commission_cents / 100.0,
                        "discount_percentage": discount_percentage,
                        "trade_lock_days": lock_days,
                        "unlock_date": trade_lock_info.get('unlock_date'),
                        "confidence": "high" if discount_percentage > 0.40 else "medium",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    opportunities.append(opportunity)
                    logger.info(f"Oportunidad de trade lock encontrada: {item_title} - "
                              f"Compra: ${offer_price_usd:.2f}, Referencia: ${reference_price:.2f}, "
                              f"Descuento: {discount_percentage:.1%}, Lock: {lock_days} días")
                    
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error procesando oferta para trade lock en {item_title}: {e}")
                continue
        
        return opportunities

    def _extract_item_attributes(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae atributos del ítem de una oferta de DMarket."""
        attributes = {}
        
        # Extraer float value
        if 'float' in offer:
            try:
                attributes['float'] = float(offer['float'])
            except (ValueError, TypeError):
                pass
        
        # Extraer pattern/paintseed
        if 'paintseed' in offer:
            try:
                attributes['paintseed'] = int(offer['paintseed'])
            except (ValueError, TypeError):
                pass
        elif 'pattern' in offer:
            try:
                attributes['pattern'] = int(offer['pattern'])
            except (ValueError, TypeError):
                pass
        
        # Detectar StatTrak y Souvenir
        title = offer.get('title', '')
        attributes['stattrak'] = 'StatTrak' in title
        attributes['souvenir'] = 'Souvenir' in title
        
        # Extraer otros atributos específicos
        if 'phase' in offer:
            attributes['phase'] = offer['phase']
        
        if 'fade_percentage' in offer:
            try:
                attributes['fade_percentage'] = float(offer['fade_percentage'])
            except (ValueError, TypeError):
                pass
        
        return attributes

    def _estimate_base_item_price(self, item_title: str, item_data: Dict[str, Any]) -> Optional[float]:
        """Estima el precio base del ítem sin considerar atributos premium."""
        # Usar el PME calculado por el market analyzer
        historical_prices = item_data.get('historical_prices', [])
        current_offers = item_data.get('current_sell_offers', [])
        
        base_price = self.analyzer.calculate_estimated_market_price(
            item_title, historical_prices, current_offers
        )
        
        return base_price

    def _get_reference_price_no_trade_lock(self, item_title: str, offers: List[Dict[str, Any]]) -> Optional[float]:
        """Obtiene precio de referencia de ofertas sin trade lock."""
        no_lock_prices = []
        
        for offer in offers:
            trade_lock_info = self._extract_trade_lock_info(offer)
            if trade_lock_info and trade_lock_info.get('has_trade_lock'):
                continue  # Saltar ofertas con trade lock
            
            try:
                price_str = offer.get('price', {}).get('USD')
                if price_str:
                    price_usd = int(price_str) / 100.0
                    no_lock_prices.append(price_usd)
            except (ValueError, TypeError):
                continue
        
        if not no_lock_prices:
            return None
        
        # Retornar precio promedio de las ofertas sin trade lock
        return sum(no_lock_prices) / len(no_lock_prices)

    def _extract_trade_lock_info(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae información de trade lock de una oferta."""
        trade_lock_info = {
            'has_trade_lock': False,
            'days_remaining': 0,
            'unlock_date': None
        }
        
        # Verificar diferentes campos donde puede estar la info de trade lock
        if 'tradeLock' in offer:
            trade_lock_info['has_trade_lock'] = True
            
            # Extraer días restantes
            if 'daysRemaining' in offer['tradeLock']:
                try:
                    trade_lock_info['days_remaining'] = int(offer['tradeLock']['daysRemaining'])
                except (ValueError, TypeError):
                    pass
            
            # Calcular fecha de unlock
            if trade_lock_info['days_remaining'] > 0:
                unlock_date = datetime.now() + timedelta(days=trade_lock_info['days_remaining'])
                trade_lock_info['unlock_date'] = unlock_date.isoformat()
        
        # Verificar en el título si menciona trade lock
        title = offer.get('title', '').lower()
        if 'trade lock' in title or 'tradelock' in title:
            trade_lock_info['has_trade_lock'] = True
        
        return trade_lock_info

    def _get_item_data(self, item_title: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene todos los datos necesarios para un ítem: ofertas de venta, órdenes de compra y precios históricos.
        
        Args:
            item_title: Nombre del ítem
            
        Returns:
            Diccionario con los datos del ítem o None si hay error
        """
        logger.debug(f"Obteniendo datos completos para: {item_title}")
        
        item_data = {
            'title': item_title,
            'current_sell_offers': [],
            'current_buy_orders': [],
            'historical_prices': []
        }

        game_id = self.config.get("game_id", DEFAULT_GAME_ID)
        
        try:
            # 1. Obtener ofertas de venta (LSO) de DMarket
            logger.debug(f"Obteniendo ofertas de venta para {item_title}...")
            response_sell_offers = self.connector.get_offers_by_title(
                title=item_title, 
                limit=100, 
                currency="USD"
            )
            
            if response_sell_offers and "error" not in response_sell_offers and "objects" in response_sell_offers:
                item_data['current_sell_offers'] = response_sell_offers.get('objects', [])
                logger.debug(f"Encontradas {len(item_data['current_sell_offers'])} ofertas de venta para {item_title}.")
            else:
                logger.warning(f"No se pudieron obtener ofertas de venta para {item_title}: {response_sell_offers.get('error') if response_sell_offers else 'Respuesta vacía'}")

            # 2. Obtener órdenes de compra (HBO) de DMarket
            logger.debug(f"Obteniendo órdenes de compra para {item_title}...")
            response_buy_orders = self.connector.get_buy_offers(
                title=item_title, 
                game_id=game_id, 
                limit=100, 
                order_by="price", 
                order_dir="desc", 
                currency="USD"
            )
            
            if response_buy_orders and "error" not in response_buy_orders and "objects" in response_buy_orders:
                item_data['current_buy_orders'] = response_buy_orders.get('objects', [])
                logger.debug(f"Encontradas {len(item_data['current_buy_orders'])} órdenes de compra para {item_title}.")
            else:
                logger.warning(f"No se pudieron obtener órdenes de compra para {item_title}: {response_buy_orders.get('error') if response_buy_orders else 'Respuesta vacía'}")
            
            # 3. Obtener precios históricos (de la BD)
            logger.debug(f"Obteniendo precios históricos de la BD para {item_title}...")
            db: Session = next(get_db())
            
            try:
                skin_maestra_entry = db.query(SkinsMaestra).filter(SkinsMaestra.market_hash_name == item_title).first()
                
                if skin_maestra_entry and skin_maestra_entry.precios:
                    # Convertir a formato esperado por MarketAnalyzer
                    sorted_historical_prices = sorted(
                        skin_maestra_entry.precios, 
                        key=lambda p: p.timestamp, 
                        reverse=True
                    )
                    
                    item_data['historical_prices'] = [
                        {
                            "price_usd": p.price, 
                            "timestamp": p.timestamp.isoformat(), 
                            "fuente_api": p.fuente_api
                        } 
                        for p in sorted_historical_prices
                    ]
                    logger.debug(f"Encontrados {len(item_data['historical_prices'])} registros de precios históricos para {item_title}.")
                else:
                    logger.debug(f"No se encontraron precios históricos en BD para {item_title}.")

            finally:
                db.close()
            
            return item_data
            
        except Exception as e:
            logger.error(f"Error obteniendo datos para {item_title}: {e}")
            return None

    def _find_volatility_opportunities(self, item_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Estrategia 4: Identifica oportunidades basadas en análisis de volatilidad.
        Utiliza indicadores técnicos para detectar patrones de precio.
        """
        opportunities = []
        item_title = item_data.get('title', 'Unknown')
        historical_prices = item_data.get('historical_prices', [])
        current_sell_offers = item_data.get('current_sell_offers', [])
        
        logger.info(f"Buscando oportunidades de volatilidad para: {item_title}")
        
        if not historical_prices or len(historical_prices) < 10:
            logger.debug(f"Insuficientes datos históricos para análisis de volatilidad en {item_title}.")
            return opportunities
        
        if not current_sell_offers:
            logger.debug(f"No hay ofertas actuales para análisis de volatilidad en {item_title}.")
            return opportunities
        
        try:
            # Obtener precio actual (LSO)
            current_price = None
            for offer in current_sell_offers:
                try:
                    price_str = offer.get('price', {}).get('USD')
                    if price_str:
                        current_price = int(price_str) / 100.0
                        break
                except (ValueError, TypeError):
                    continue
            
            if not current_price:
                logger.debug(f"No se pudo obtener precio actual para {item_title}.")
                return opportunities
            
            # Verificar límites de precio
            max_price = self.config.get("max_price_usd_volatility", 1000.0)
            if current_price > max_price:
                logger.debug(f"Precio de {item_title} (${current_price:.2f}) excede límite para volatilidad.")
                return opportunities
            
            # Analizar volatilidad
            volatility_signals = self.volatility_analyzer.identify_volatility_opportunities(
                item_title, historical_prices, current_price
            )
            
            # Convertir señales a oportunidades
            min_confidence = self.config.get("min_confidence_volatility", 0.5)
            min_profit_usd = self.config.get("min_profit_usd_volatility", 0.05)
            
            for signal in volatility_signals:
                if signal.confidence < min_confidence:
                    continue
                
                if signal.expected_profit < min_profit_usd:
                    continue
                
                # Calcular comisión estimada
                commission_cents = self._calculate_dmarket_sale_fee_cents(int(signal.target_price * 100)) if signal.target_price else 0
                commission_usd = commission_cents / 100.0
                
                # Ajustar beneficio por comisión
                adjusted_profit = signal.expected_profit - commission_usd
                
                if adjusted_profit < min_profit_usd:
                    continue
                
                opportunity = {
                    "strategy": "volatility_trading",
                    "item_title": item_title,
                    "signal_type": signal.signal_type,
                    "entry_price_usd": signal.entry_price,
                    "target_price_usd": signal.target_price,
                    "stop_loss_usd": signal.stop_loss,
                    "expected_profit_usd": adjusted_profit,
                    "commission_usd": commission_usd,
                    "confidence": signal.confidence,
                    "strength": signal.strength.value,
                    "risk_reward_ratio": signal.risk_reward_ratio,
                    "reasoning": signal.reasoning,
                    "technical_indicators": {
                        "rsi": signal.indicators.rsi,
                        "bollinger_upper": signal.indicators.bollinger_upper,
                        "bollinger_lower": signal.indicators.bollinger_lower,
                        "bollinger_width": signal.indicators.bollinger_width,
                        "ma_short": signal.indicators.moving_average_short,
                        "ma_long": signal.indicators.moving_average_long,
                        "volatility_score": signal.indicators.volatility_score,
                        "price_change_24h": signal.indicators.price_change_24h,
                        "price_change_7d": signal.indicators.price_change_7d
                    },
                    "timestamp": signal.timestamp.isoformat()
                }
                
                opportunities.append(opportunity)
                logger.info(f"Oportunidad de volatilidad encontrada: {item_title} - "
                          f"Señal: {signal.signal_type}, Confianza: {signal.confidence:.1%}, "
                          f"Beneficio esperado: ${adjusted_profit:.2f}")
                
        except Exception as e:
            logger.error(f"Error procesando volatilidad para {item_title}: {e}")
        
        return opportunities

    def run_strategies(self, items_to_scan: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Ejecuta todas las estrategias configuradas sobre una lista de ítems.

        Args:
            items_to_scan (List[str]): Lista de nombres de ítems a escanear.

        Returns:
            Dict[str, List[Dict[str, Any]]]: Diccionario con las oportunidades encontradas por estrategia.
                                             Claves: "basic_flips", "snipes", "attribute_flips", "trade_lock_arbitrage", "volatility_trading"
        """
        logger.info(f"Ejecutando estrategias en {len(items_to_scan)} ítems...")
        
        all_opportunities = {
            "basic_flips": [],
            "snipes": [],
            "attribute_flips": [],
            "trade_lock_arbitrage": [],
            "volatility_trading": []
        }

        game_id = self.config.get("game_id", DEFAULT_GAME_ID)
        
        # Asegurar que las tasas de comisión estén cargadas (ahora siempre devuelve True con valores por defecto)
        self._fetch_and_cache_fee_info(game_id)
        logger.info("Tasas de comisión cargadas (reales o por defecto). Continuando con estrategias...")

        for i, item_title in enumerate(items_to_scan):
            logger.info(f"Procesando ítem {i+1}/{len(items_to_scan)}: {item_title}")
            
            try:
                # Obtener datos del ítem
                item_data = self._get_item_data(item_title)
                if not item_data:
                    logger.warning(f"No se pudieron obtener datos para {item_title}. Saltando.")
                    continue

                # Ejecutar Estrategia 1: Basic Flips
                basic_flip_opportunities = self._find_basic_flips(
                    item_title, 
                    item_data.get('current_sell_offers', []), 
                    item_data.get('current_buy_orders', [])
                )
                all_opportunities["basic_flips"].extend(basic_flip_opportunities)

                # Ejecutar Estrategia 3: Snipes
                snipe_opportunities = self._find_snipes(
                    item_title, 
                    item_data.get('current_sell_offers', []), 
                    item_data.get('historical_prices', [])
                )
                all_opportunities["snipes"].extend(snipe_opportunities)

                # Ejecutar Estrategia 2: Attribute Premium Flips
                attribute_flip_opportunities = self._find_attribute_premium_flips(
                    item_data, self.dmarket_fee_info, self.analyzer
                )
                all_opportunities["attribute_flips"].extend(attribute_flip_opportunities)

                # Ejecutar Estrategia 5: Trade Lock Arbitrage
                trade_lock_opportunities = self._find_trade_lock_opportunities(
                    item_data, self.dmarket_fee_info
                )
                all_opportunities["trade_lock_arbitrage"].extend(trade_lock_opportunities)

                # Ejecutar Estrategia 4: Volatility Trading
                volatility_opportunities = self._find_volatility_opportunities(item_data)
                all_opportunities["volatility_trading"].extend(volatility_opportunities)

                # Delay entre ítems para no sobrecargar la API
                delay = self.config.get("delay_between_items_sec", 1.0)
                if delay > 0 and i < len(items_to_scan) - 1:  # No delay después del último ítem
                    logger.debug(f"Esperando {delay} segundos antes del siguiente ítem...")
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Error procesando {item_title}: {e}")
                continue

        # Resumen de resultados
        total_opportunities = sum(len(opps) for opps in all_opportunities.values())
        logger.info(f"Estrategias completadas. Total de oportunidades encontradas: {total_opportunities}")
        for strategy, opportunities in all_opportunities.items():
            if opportunities:
                logger.info(f"  {strategy}: {len(opportunities)} oportunidades")

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