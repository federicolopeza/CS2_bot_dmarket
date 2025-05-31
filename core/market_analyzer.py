# core/market_analyzer.py
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class FloatRarity(Enum):
    """Niveles de rareza basados en el valor de float."""
    FACTORY_NEW = "factory_new"      # 0.00 - 0.07
    MINIMAL_WEAR = "minimal_wear"    # 0.07 - 0.15
    FIELD_TESTED = "field_tested"    # 0.15 - 0.38
    WELL_WORN = "well_worn"          # 0.38 - 0.45
    BATTLE_SCARRED = "battle_scarred" # 0.45 - 1.00

class AttributeRarity(Enum):
    """Niveles de rareza para atributos especiales."""
    COMMON = 0
    UNCOMMON = 1
    RARE = 2
    VERY_RARE = 3
    EXTREMELY_RARE = 4

@dataclass
class AttributeEvaluation:
    """Resultado de la evaluación de atributos de un ítem."""
    float_value: Optional[float]
    float_rarity: Optional[FloatRarity]
    pattern_index: Optional[int]
    pattern_rarity: AttributeRarity
    stickers_value: float
    stickers_rarity: AttributeRarity
    stattrak: bool
    souvenir: bool
    overall_rarity_score: float
    premium_multiplier: float
    special_attributes: Dict[str, Any]

class MarketAnalyzer:
    """
    Clase para analizar datos de mercado y atributos de ítems.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el MarketAnalyzer.
        
        Args:
            config: Configuración opcional para el análisis de atributos.
        """
        self.config = config or self._get_default_config()
        logger.info("MarketAnalyzer inicializado con configuración de atributos.")

    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto para el análisis de atributos."""
        return {
            # Configuración de float
            "float_ranges": {
                FloatRarity.FACTORY_NEW.value: (0.00, 0.07),
                FloatRarity.MINIMAL_WEAR.value: (0.07, 0.15),
                FloatRarity.FIELD_TESTED.value: (0.15, 0.38),
                FloatRarity.WELL_WORN.value: (0.38, 0.45),
                FloatRarity.BATTLE_SCARRED.value: (0.45, 1.00),
            },
            # Multiplicadores de rareza por float
            "float_multipliers": {
                FloatRarity.FACTORY_NEW.value: 1.5,
                FloatRarity.MINIMAL_WEAR.value: 1.2,
                FloatRarity.FIELD_TESTED.value: 1.0,
                FloatRarity.WELL_WORN.value: 0.8,
                FloatRarity.BATTLE_SCARRED.value: 0.6,
            },
            # Patrones especiales conocidos (ejemplos)
            "special_patterns": {
                # AK-47 Case Hardened blue gems
                "AK-47 | Case Hardened": {
                    "blue_gems": [661, 670, 387, 151, 179, 868, 955],
                    "tier_1": [661, 670, 387],
                    "tier_2": [151, 179, 868, 955],
                },
                # Karambit Fade patterns
                "★ Karambit | Fade": {
                    "100_fade": list(range(1, 31)),
                    "90_fade": list(range(31, 151)),
                    "80_fade": list(range(151, 301)),
                },
                # Five-Seven Case Hardened blue gems
                "Five-SeveN | Case Hardened": {
                    "blue_gems": [278, 868, 690, 363, 592],
                }
            },
            # Stickers valiosos (ejemplos)
            "valuable_stickers": {
                "Katowice 2014": {
                    "iBUYPOWER (Holo)": 50000.0,
                    "Titan (Holo)": 30000.0,
                    "Reason Gaming (Holo)": 25000.0,
                    "iBUYPOWER": 8000.0,
                    "Titan": 5000.0,
                },
                "Katowice 2015": {
                    "Fnatic (Holo)": 500.0,
                    "TSM (Holo)": 400.0,
                    "Virtus.Pro (Holo)": 350.0,
                },
                "Crown (Foil)": 2000.0,
                "Howling Dawn": 1500.0,
            },
            # Multiplicadores por posición de sticker
            "sticker_position_multipliers": {
                0: 1.0,  # Primera posición
                1: 0.8,  # Segunda posición
                2: 0.6,  # Tercera posición
                3: 0.4,  # Cuarta posición
            },
            # Multiplicadores especiales
            "special_multipliers": {
                "stattrak": 1.3,
                "souvenir": 1.5,
                "low_float_fn": 2.0,  # Float < 0.01 en FN
                "high_float_bs": 1.8,  # Float > 0.95 en BS
            }
        }

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

    def evaluate_attribute_rarity(
        self, 
        attributes: Dict[str, Any], 
        stickers: Optional[List[Dict[str, Any]]] = None,
        item_name: Optional[str] = None
    ) -> AttributeEvaluation:
        """
        Evalúa la rareza y valor de los atributos de un ítem.
        
        Args:
            attributes: Diccionario con atributos del ítem (float, pattern, etc.)
            stickers: Lista de stickers aplicados al ítem
            item_name: Nombre del ítem para evaluaciones específicas
            
        Returns:
            AttributeEvaluation: Evaluación completa de los atributos
        """
        logger.debug(f"Evaluando atributos para {item_name}: {attributes}")
        
        # Evaluar float
        float_value = attributes.get('float')
        float_rarity = self._evaluate_float_rarity(float_value)
        
        # Evaluar pattern
        pattern_index = attributes.get('paintseed') or attributes.get('pattern')
        pattern_rarity = self._evaluate_pattern_rarity(pattern_index, item_name)
        
        # Evaluar stickers
        stickers_value, stickers_rarity = self._evaluate_stickers(stickers or [])
        
        # Detectar atributos especiales
        stattrak = attributes.get('stattrak', False) or 'StatTrak' in str(item_name or '')
        souvenir = attributes.get('souvenir', False) or 'Souvenir' in str(item_name or '')
        
        # Calcular puntuación general de rareza
        overall_score = self._calculate_overall_rarity_score(
            float_value, float_rarity, pattern_rarity, stickers_rarity, stattrak, souvenir
        )
        
        # Calcular multiplicador premium
        premium_multiplier = self._calculate_premium_multiplier(
            float_value, float_rarity, pattern_rarity, stickers_value, stattrak, souvenir
        )
        
        # Atributos especiales adicionales
        special_attributes = self._identify_special_attributes(
            float_value, pattern_index, item_name, attributes
        )
        
        evaluation = AttributeEvaluation(
            float_value=float_value,
            float_rarity=float_rarity,
            pattern_index=pattern_index,
            pattern_rarity=pattern_rarity,
            stickers_value=stickers_value,
            stickers_rarity=stickers_rarity,
            stattrak=stattrak,
            souvenir=souvenir,
            overall_rarity_score=overall_score,
            premium_multiplier=premium_multiplier,
            special_attributes=special_attributes
        )
        
        logger.info(f"Evaluación de atributos completada para {item_name}: score={overall_score:.2f}, multiplier={premium_multiplier:.2f}")
        return evaluation

    def _evaluate_float_rarity(self, float_value: Optional[float]) -> Optional[FloatRarity]:
        """Evalúa la rareza basada en el valor de float."""
        if float_value is None:
            return None
            
        for rarity, (min_val, max_val) in self.config["float_ranges"].items():
            if min_val <= float_value < max_val:
                return FloatRarity(rarity)
        
        return FloatRarity.BATTLE_SCARRED  # Fallback

    def _evaluate_pattern_rarity(self, pattern_index: Optional[int], item_name: Optional[str]) -> AttributeRarity:
        """Evalúa la rareza del patrón."""
        if not pattern_index or not item_name:
            return AttributeRarity.COMMON
            
        special_patterns = self.config.get("special_patterns", {})
        
        for weapon_name, patterns in special_patterns.items():
            if weapon_name in str(item_name):
                # Verificar patrones tier 1 (más raros)
                if pattern_index in patterns.get("tier_1", []):
                    return AttributeRarity.EXTREMELY_RARE
                elif pattern_index in patterns.get("blue_gems", []):
                    return AttributeRarity.VERY_RARE
                elif pattern_index in patterns.get("tier_2", []):
                    return AttributeRarity.RARE
                elif pattern_index in patterns.get("100_fade", []):
                    return AttributeRarity.VERY_RARE
                elif pattern_index in patterns.get("90_fade", []):
                    return AttributeRarity.RARE
                elif pattern_index in patterns.get("80_fade", []):
                    return AttributeRarity.UNCOMMON
                    
        return AttributeRarity.COMMON

    def _evaluate_stickers(self, stickers: List[Dict[str, Any]]) -> Tuple[float, AttributeRarity]:
        """Evalúa el valor y rareza de los stickers."""
        if not stickers:
            return 0.0, AttributeRarity.COMMON
            
        total_value = 0.0
        max_rarity = AttributeRarity.COMMON
        
        valuable_stickers = self.config.get("valuable_stickers", {})
        position_multipliers = self.config.get("sticker_position_multipliers", {})
        
        for i, sticker in enumerate(stickers):
            sticker_name = sticker.get('name', '')
            position_multiplier = position_multipliers.get(i, 0.2)
            
            # Buscar en stickers valiosos
            sticker_value = 0.0
            sticker_rarity = AttributeRarity.COMMON
            
            for category, sticker_dict in valuable_stickers.items():
                if isinstance(sticker_dict, dict):
                    if sticker_name in sticker_dict:
                        sticker_value = sticker_dict[sticker_name] * position_multiplier
                        if sticker_value > 10000:
                            sticker_rarity = AttributeRarity.EXTREMELY_RARE
                        elif sticker_value > 1000:
                            sticker_rarity = AttributeRarity.VERY_RARE
                        elif sticker_value > 100:
                            sticker_rarity = AttributeRarity.RARE
                        elif sticker_value > 10:
                            sticker_rarity = AttributeRarity.UNCOMMON
                        break
                elif isinstance(sticker_dict, (int, float)) and category in sticker_name:
                    sticker_value = sticker_dict * position_multiplier
                    sticker_rarity = AttributeRarity.RARE
            
            total_value += sticker_value
            if sticker_rarity.value > max_rarity.value:
                max_rarity = sticker_rarity
                
        return total_value, max_rarity

    def _calculate_overall_rarity_score(
        self,
        float_value: Optional[float],
        float_rarity: Optional[FloatRarity],
        pattern_rarity: AttributeRarity,
        stickers_rarity: AttributeRarity,
        stattrak: bool,
        souvenir: bool
    ) -> float:
        """Calcula una puntuación general de rareza (0-100)."""
        score = 0.0
        
        # Puntuación base por float (0-20 puntos)
        if float_rarity:
            float_scores = {
                FloatRarity.FACTORY_NEW: 20,
                FloatRarity.MINIMAL_WEAR: 15,
                FloatRarity.FIELD_TESTED: 10,
                FloatRarity.WELL_WORN: 5,
                FloatRarity.BATTLE_SCARRED: 2,
            }
            score += float_scores.get(float_rarity, 0)
            
            # Bonus por float extremo
            if float_value is not None:
                if float_value < 0.01:  # Float muy bajo
                    score += 15
                elif float_value > 0.95:  # Float muy alto
                    score += 10
        
        # Puntuación por patrón (0-30 puntos)
        pattern_scores = {
            AttributeRarity.EXTREMELY_RARE: 30,
            AttributeRarity.VERY_RARE: 25,
            AttributeRarity.RARE: 15,
            AttributeRarity.UNCOMMON: 8,
            AttributeRarity.COMMON: 0,
        }
        score += pattern_scores.get(pattern_rarity, 0)
        
        # Puntuación por stickers (0-25 puntos)
        sticker_scores = {
            AttributeRarity.EXTREMELY_RARE: 25,
            AttributeRarity.VERY_RARE: 20,
            AttributeRarity.RARE: 12,
            AttributeRarity.UNCOMMON: 6,
            AttributeRarity.COMMON: 0,
        }
        score += sticker_scores.get(stickers_rarity, 0)
        
        # Bonus por atributos especiales (0-15 puntos)
        if stattrak:
            score += 8
        if souvenir:
            score += 12
            
        return min(score, 100.0)  # Máximo 100 puntos

    def _calculate_premium_multiplier(
        self,
        float_value: Optional[float],
        float_rarity: Optional[FloatRarity],
        pattern_rarity: AttributeRarity,
        stickers_value: float,
        stattrak: bool,
        souvenir: bool
    ) -> float:
        """Calcula el multiplicador premium para el precio base."""
        multiplier = 1.0
        
        # Multiplicador por float
        if float_rarity:
            float_multipliers = self.config.get("float_multipliers", {})
            multiplier *= float_multipliers.get(float_rarity.value, 1.0)
            
            # Multiplicador adicional por float extremo
            if float_value is not None:
                if float_value < 0.01:
                    multiplier *= self.config["special_multipliers"]["low_float_fn"]
                elif float_value > 0.95:
                    multiplier *= self.config["special_multipliers"]["high_float_bs"]
        
        # Multiplicador por patrón
        pattern_multipliers = {
            AttributeRarity.EXTREMELY_RARE: 5.0,
            AttributeRarity.VERY_RARE: 3.0,
            AttributeRarity.RARE: 2.0,
            AttributeRarity.UNCOMMON: 1.3,
            AttributeRarity.COMMON: 1.0,
        }
        multiplier *= pattern_multipliers.get(pattern_rarity, 1.0)
        
        # Multiplicador por stickers (basado en valor)
        if stickers_value > 0:
            # Los stickers añaden valor pero con depreciación
            sticker_multiplier = 1.0 + (stickers_value * 0.1 / 1000.0)  # 10% del valor por cada $1000
            multiplier *= min(sticker_multiplier, 3.0)  # Máximo 3x por stickers
        
        # Multiplicadores especiales
        if stattrak:
            multiplier *= self.config["special_multipliers"]["stattrak"]
        if souvenir:
            multiplier *= self.config["special_multipliers"]["souvenir"]
            
        return multiplier

    def _identify_special_attributes(
        self,
        float_value: Optional[float],
        pattern_index: Optional[int],
        item_name: Optional[str],
        attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identifica atributos especiales adicionales."""
        special = {}
        
        if float_value is not None:
            if float_value < 0.001:
                special["ultra_low_float"] = True
            elif float_value > 0.999:
                special["max_float"] = True
                
        if pattern_index is not None:
            special["pattern_index"] = pattern_index
            
        # Detectar otros atributos especiales
        if attributes.get('phase'):
            special["doppler_phase"] = attributes['phase']
            
        if attributes.get('fade_percentage'):
            special["fade_percentage"] = attributes['fade_percentage']
            
        return special

if __name__ == '__main__':
    # Ejemplo de uso y prueba simple (requerirá datos mockeados)
    # Añadir utils.logger a la importación si no está
    from utils.logger import configure_logging 
    configure_logging(log_level=logging.DEBUG) # Asumiendo que tienes configure_logging en utils
    
    analyzer = MarketAnalyzer()

    # Prueba de PME (código existente)
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

    # Caso 1: Con ofertas actuales
    pme1 = analyzer.calculate_estimated_market_price("AK-47 | Redline", mock_historical, mock_offers_dmarket)
    logger.info(f"PME Caso 1 (con ofertas): {pme1}") # Esperado: 10.00 (promedio histórico)

    # Prueba de evaluación de atributos
    test_attributes = {
        'float': 0.003,
        'paintseed': 661,
        'stattrak': True
    }
    
    test_stickers = [
        {'name': 'iBUYPOWER (Holo) | Katowice 2014'},
        {'name': 'Titan (Holo) | Katowice 2014'}
    ]
    
    evaluation = analyzer.evaluate_attribute_rarity(
        test_attributes, 
        test_stickers, 
        "AK-47 | Case Hardened (Factory New)"
    )
    
    logger.info(f"Evaluación de atributos:")
    logger.info(f"  Float: {evaluation.float_value} ({evaluation.float_rarity})")
    logger.info(f"  Pattern: {evaluation.pattern_index} ({evaluation.pattern_rarity})")
    logger.info(f"  Stickers value: ${evaluation.stickers_value:.2f} ({evaluation.stickers_rarity})")
    logger.info(f"  StatTrak: {evaluation.stattrak}")
    logger.info(f"  Overall score: {evaluation.overall_rarity_score:.2f}")
    logger.info(f"  Premium multiplier: {evaluation.premium_multiplier:.2f}x")