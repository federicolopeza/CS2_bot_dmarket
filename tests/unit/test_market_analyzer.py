# tests/unit/test_market_analyzer.py
import pytest
import os
import sys
import logging
from unittest.mock import Mock, patch
from core.market_analyzer import MarketAnalyzer, FloatRarity, AttributeRarity, AttributeEvaluation

# Añadir el directorio raíz del proyecto a sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Descomentar si necesitas configurar logging para ver la salida de los logs del módulo durante las pruebas
# configure_logging(log_level=logging.DEBUG)


@pytest.fixture
def analyzer():
    """Proporciona una instancia de MarketAnalyzer para las pruebas."""
    return MarketAnalyzer()

@pytest.fixture
def mock_historical_data():
    """Datos históricos mockeados para pruebas."""
    return [
        {'price_usd': 10.00, 'timestamp': '2023-10-01T10:00:00Z', 'fuente_api': 'DMarket'},
        {'price_usd': 10.20, 'timestamp': '2023-10-02T10:00:00Z', 'fuente_api': 'DMarket'},
        {'price_usd': 9.80, 'timestamp': '2023-10-03T10:00:00Z', 'fuente_api': 'DMarket'},
    ]

@pytest.fixture
def mock_current_offers_dmarket():
    """Ofertas actuales de DMarket mockeadas."""
    return [
        {'assetId': '1', 'title': 'Item A', 'price': {'USD': '1050'}, 'amount': 1}, # $10.50
        {'assetId': '2', 'title': 'Item A', 'price': {'USD': '1030'}, 'amount': 1}, # $10.30 (lowest)
        {'assetId': '3', 'title': 'Item A', 'price': {'USD': '1100'}, 'amount': 1}, # $11.00
    ]

def test_calculate_pme_with_current_offers(analyzer, mock_historical_data, mock_current_offers_dmarket):
    """
    Prueba PME cuando hay ofertas actuales. Debería usar el precio más bajo de las ofertas.
    """
    avg_hist_price = (10.00 + 10.20 + 9.80) / 3
    pme = analyzer.calculate_estimated_market_price(
        "Item A",
        mock_historical_data, # Históricos tienen prioridad ahora
        mock_current_offers_dmarket
    )
    assert pme == pytest.approx(avg_hist_price) # Espera el promedio histórico

def test_calculate_pme_with_only_historical_data(analyzer, mock_historical_data):
    """
    Prueba PME cuando solo hay datos históricos y no hay ofertas actuales.
    Debería usar el promedio de los precios históricos.
    """
    avg_hist_price = (10.00 + 10.20 + 9.80) / 3
    pme = analyzer.calculate_estimated_market_price(
        "Item B",
        mock_historical_data,
        [] # Sin ofertas actuales
    )
    assert pme == pytest.approx(avg_hist_price)

def test_calculate_pme_no_data(analyzer):
    """
    Prueba PME cuando no hay datos históricos ni ofertas actuales.
    Debería devolver None.
    """
    pme = analyzer.calculate_estimated_market_price(
        "Item C",
        [], # Sin datos históricos
        []  # Sin ofertas actuales
    )
    assert pme is None

def test_calculate_pme_current_offers_no_usd_price(analyzer, mock_historical_data):
    """
    Prueba PME cuando las ofertas actuales no tienen precio en USD o está malformado.
    Si hay datos históricos, debería recurrir a ellos.
    """
    offers_no_usd = [
        {'assetId': '4', 'title': 'Item D', 'price': {'EUR': '900'}, 'amount': 1}, # Precio en EUR, no USD
        {'assetId': '5', 'title': 'Item D', 'price': {}, 'amount': 1}, # Sin clave 'USD'
    ]
    avg_hist_price = (10.00 + 10.20 + 9.80) / 3
    pme = analyzer.calculate_estimated_market_price(
        "Item D",
        mock_historical_data,
        offers_no_usd
    )
    assert pme == pytest.approx(avg_hist_price) # Debería usar el histórico

def test_calculate_pme_current_offers_invalid_price_format(analyzer):
    """
    Prueba PME cuando las ofertas actuales tienen un formato de precio inválido (no numérico).
    Si no hay datos históricos, debería devolver None.
    """
    offers_invalid_price = [
        {'assetId': '6', 'title': 'Item E', 'price': {'USD': 'not_a_number'}, 'amount': 1},
    ]
    pme = analyzer.calculate_estimated_market_price(
        "Item E",
        [], # Sin datos históricos
        offers_invalid_price
    )
    assert pme is None # No puede parsear precio de oferta, no hay histórico

def test_calculate_pme_current_offers_empty_list(analyzer, mock_historical_data):
    """
    Prueba PME cuando la lista de ofertas actuales está vacía.
    Debería usar los datos históricos.
    """
    avg_hist_price = (10.00 + 10.20 + 9.80) / 3
    pme = analyzer.calculate_estimated_market_price(
        "Item F",
        mock_historical_data,
        []
    )
    assert pme == pytest.approx(avg_hist_price)

def test_calculate_pme_historical_data_empty_list(analyzer, mock_current_offers_dmarket):
    """
    Prueba PME cuando la lista de datos históricos está vacía.
    Debería usar el precio más bajo de las ofertas actuales.
    """
    pme = analyzer.calculate_estimated_market_price(
        "Item G",
        [],
        mock_current_offers_dmarket
    )
    assert pme == pytest.approx(10.30)

def test_calculate_pme_offer_price_missing_key(analyzer):
    """
    Prueba el caso donde una oferta no tiene la clave 'price'.
    Debería ignorar esa oferta y, si no hay otras fuentes, devolver None.
    """
    offers_missing_price_key = [
        {'assetId': '1', 'title': 'Item H', 'amount': 1}, # Falta 'price'
    ]
    pme = analyzer.calculate_estimated_market_price(
        "Item H",
        [],
        offers_missing_price_key
    )
    assert pme is None

def test_calculate_pme_offer_price_usd_missing_key(analyzer):
    """
    Prueba el caso donde 'price' existe pero no la sub-clave 'USD'.
    """
    offers_missing_usd_key = [
        {'assetId': '1', 'title': 'Item I', 'price': {'EUR': '1000'}, 'amount': 1}, # Solo EUR
    ]
    pme = analyzer.calculate_estimated_market_price(
        "Item I",
        [],
        offers_missing_usd_key
    )
    assert pme is None

class TestMarketAnalyzer:
    """Pruebas unitarias para MarketAnalyzer."""

    def setup_method(self):
        """Configuración para cada prueba."""
        self.analyzer = MarketAnalyzer()

    def test_init_default_config(self):
        """Prueba la inicialización con configuración por defecto."""
        analyzer = MarketAnalyzer()
        assert analyzer.config is not None
        assert "float_ranges" in analyzer.config
        assert "special_patterns" in analyzer.config
        assert "valuable_stickers" in analyzer.config

    def test_init_custom_config(self):
        """Prueba la inicialización con configuración personalizada."""
        custom_config = {"test_key": "test_value"}
        analyzer = MarketAnalyzer(custom_config)
        assert analyzer.config == custom_config

    def test_calculate_estimated_market_price_with_historical_data(self):
        """Prueba el cálculo de PME con datos históricos."""
        historical_prices = [
            {'price_usd': 10.00},
            {'price_usd': 12.00},
            {'price_usd': 8.00}
        ]
        current_offers = []
        
        pme = self.analyzer.calculate_estimated_market_price(
            "AK-47 | Redline", historical_prices, current_offers
        )
        
        assert pme == 10.0  # Promedio: (10 + 12 + 8) / 3

    def test_calculate_estimated_market_price_with_current_offers(self):
        """Prueba el cálculo de PME con ofertas actuales."""
        historical_prices = []
        current_offers = [
            {'price': {'USD': '1000'}},  # $10.00
            {'price': {'USD': '1200'}},  # $12.00
            {'price': {'USD': '800'}}    # $8.00
        ]
        
        pme = self.analyzer.calculate_estimated_market_price(
            "AK-47 | Redline", historical_prices, current_offers
        )
        
        assert pme == 8.0  # Precio mínimo

    def test_calculate_estimated_market_price_no_data(self):
        """Prueba el cálculo de PME sin datos."""
        pme = self.analyzer.calculate_estimated_market_price(
            "AK-47 | Redline", [], []
        )
        
        assert pme is None

    def test_calculate_estimated_market_price_invalid_offers(self):
        """Prueba el cálculo de PME con ofertas inválidas."""
        historical_prices = []
        current_offers = [
            {'invalid': 'data'},
            {'price': {'EUR': '1000'}},  # Moneda incorrecta
            {'price': {'USD': 'invalid'}}  # Precio inválido
        ]
        
        pme = self.analyzer.calculate_estimated_market_price(
            "AK-47 | Redline", historical_prices, current_offers
        )
        
        assert pme is None

    def test_calculate_estimated_market_price_invalid_historical(self):
        """Prueba el cálculo de PME con datos históricos inválidos."""
        historical_prices = [
            {'price_usd': 'invalid'},
            {'invalid': 'data'},
            {'price_usd': None}
        ]
        current_offers = [{'price': {'USD': '1000'}}]
        
        pme = self.analyzer.calculate_estimated_market_price(
            "AK-47 | Redline", historical_prices, current_offers
        )
        
        assert pme == 10.0  # Fallback a ofertas actuales

    # Nuevas pruebas para análisis de atributos

    def test_evaluate_float_rarity_factory_new(self):
        """Prueba la evaluación de rareza de float Factory New."""
        float_rarity = self.analyzer._evaluate_float_rarity(0.03)
        assert float_rarity == FloatRarity.FACTORY_NEW

    def test_evaluate_float_rarity_minimal_wear(self):
        """Prueba la evaluación de rareza de float Minimal Wear."""
        float_rarity = self.analyzer._evaluate_float_rarity(0.10)
        assert float_rarity == FloatRarity.MINIMAL_WEAR

    def test_evaluate_float_rarity_field_tested(self):
        """Prueba la evaluación de rareza de float Field-Tested."""
        float_rarity = self.analyzer._evaluate_float_rarity(0.25)
        assert float_rarity == FloatRarity.FIELD_TESTED

    def test_evaluate_float_rarity_well_worn(self):
        """Prueba la evaluación de rareza de float Well-Worn."""
        float_rarity = self.analyzer._evaluate_float_rarity(0.40)
        assert float_rarity == FloatRarity.WELL_WORN

    def test_evaluate_float_rarity_battle_scarred(self):
        """Prueba la evaluación de rareza de float Battle-Scarred."""
        float_rarity = self.analyzer._evaluate_float_rarity(0.60)
        assert float_rarity == FloatRarity.BATTLE_SCARRED

    def test_evaluate_float_rarity_none(self):
        """Prueba la evaluación de rareza de float con valor None."""
        float_rarity = self.analyzer._evaluate_float_rarity(None)
        assert float_rarity is None

    def test_evaluate_pattern_rarity_blue_gem_tier1(self):
        """Prueba la evaluación de patrón blue gem tier 1."""
        pattern_rarity = self.analyzer._evaluate_pattern_rarity(661, "AK-47 | Case Hardened")
        assert pattern_rarity == AttributeRarity.EXTREMELY_RARE

    def test_evaluate_pattern_rarity_blue_gem_tier2(self):
        """Prueba la evaluación de patrón blue gem tier 2."""
        pattern_rarity = self.analyzer._evaluate_pattern_rarity(151, "AK-47 | Case Hardened")
        assert pattern_rarity == AttributeRarity.VERY_RARE

    def test_evaluate_pattern_rarity_fade_100(self):
        """Prueba la evaluación de patrón fade 100%."""
        pattern_rarity = self.analyzer._evaluate_pattern_rarity(15, "★ Karambit | Fade")
        assert pattern_rarity == AttributeRarity.VERY_RARE

    def test_evaluate_pattern_rarity_fade_90(self):
        """Prueba la evaluación de patrón fade 90%."""
        pattern_rarity = self.analyzer._evaluate_pattern_rarity(100, "★ Karambit | Fade")
        assert pattern_rarity == AttributeRarity.RARE

    def test_evaluate_pattern_rarity_fade_80(self):
        """Prueba la evaluación de patrón fade 80%."""
        pattern_rarity = self.analyzer._evaluate_pattern_rarity(200, "★ Karambit | Fade")
        assert pattern_rarity == AttributeRarity.UNCOMMON

    def test_evaluate_pattern_rarity_common(self):
        """Prueba la evaluación de patrón común."""
        pattern_rarity = self.analyzer._evaluate_pattern_rarity(500, "AK-47 | Redline")
        assert pattern_rarity == AttributeRarity.COMMON

    def test_evaluate_pattern_rarity_no_data(self):
        """Prueba la evaluación de patrón sin datos."""
        pattern_rarity = self.analyzer._evaluate_pattern_rarity(None, None)
        assert pattern_rarity == AttributeRarity.COMMON

    def test_evaluate_stickers_katowice_2014_holo(self):
        """Prueba la evaluación de stickers Katowice 2014 Holo."""
        stickers = [{'name': 'iBUYPOWER (Holo)'}]
        value, rarity = self.analyzer._evaluate_stickers(stickers)
        
        assert value == 50000.0  # Valor completo en primera posición
        assert rarity == AttributeRarity.EXTREMELY_RARE

    def test_evaluate_stickers_multiple_positions(self):
        """Prueba la evaluación de stickers en múltiples posiciones."""
        stickers = [
            {'name': 'iBUYPOWER (Holo)'},  # Posición 0: 100%
            {'name': 'Titan (Holo)'},      # Posición 1: 80%
            {'name': 'Crown (Foil)'},      # Posición 2: 60%
        ]
        value, rarity = self.analyzer._evaluate_stickers(stickers)
        
        expected_value = 50000.0 * 1.0 + 30000.0 * 0.8 + 2000.0 * 0.6
        assert value == expected_value
        assert rarity == AttributeRarity.EXTREMELY_RARE

    def test_evaluate_stickers_no_stickers(self):
        """Prueba la evaluación sin stickers."""
        value, rarity = self.analyzer._evaluate_stickers([])
        assert value == 0.0
        assert rarity == AttributeRarity.COMMON

    def test_evaluate_stickers_unknown_sticker(self):
        """Prueba la evaluación de stickers desconocidos."""
        stickers = [{'name': 'Unknown Sticker'}]
        value, rarity = self.analyzer._evaluate_stickers(stickers)
        
        assert value == 0.0
        assert rarity == AttributeRarity.COMMON

    def test_calculate_overall_rarity_score_max(self):
        """Prueba el cálculo de puntuación máxima de rareza."""
        score = self.analyzer._calculate_overall_rarity_score(
            float_value=0.005,  # Ultra low float
            float_rarity=FloatRarity.FACTORY_NEW,
            pattern_rarity=AttributeRarity.EXTREMELY_RARE,
            stickers_rarity=AttributeRarity.EXTREMELY_RARE,
            stattrak=True,
            souvenir=True
        )
        
        # 20 (FN) + 15 (ultra low) + 30 (pattern) + 25 (stickers) + 8 (ST) + 12 (souvenir) = 110 -> 100 (max)
        assert score == 100.0

    def test_calculate_overall_rarity_score_min(self):
        """Prueba el cálculo de puntuación mínima de rareza."""
        score = self.analyzer._calculate_overall_rarity_score(
            float_value=0.50,
            float_rarity=FloatRarity.BATTLE_SCARRED,
            pattern_rarity=AttributeRarity.COMMON,
            stickers_rarity=AttributeRarity.COMMON,
            stattrak=False,
            souvenir=False
        )
        
        # 2 (BS) + 0 (pattern) + 0 (stickers) + 0 (ST) + 0 (souvenir) = 2
        assert score == 2.0

    def test_calculate_premium_multiplier_basic(self):
        """Prueba el cálculo de multiplicador premium básico."""
        multiplier = self.analyzer._calculate_premium_multiplier(
            float_value=0.15,
            float_rarity=FloatRarity.FIELD_TESTED,
            pattern_rarity=AttributeRarity.COMMON,
            stickers_value=0.0,
            stattrak=False,
            souvenir=False
        )
        
        assert multiplier == 1.0  # FT base multiplier

    def test_calculate_premium_multiplier_extreme_float(self):
        """Prueba el cálculo de multiplicador con float extremo."""
        multiplier = self.analyzer._calculate_premium_multiplier(
            float_value=0.005,  # Ultra low float
            float_rarity=FloatRarity.FACTORY_NEW,
            pattern_rarity=AttributeRarity.COMMON,
            stickers_value=0.0,
            stattrak=False,
            souvenir=False
        )
        
        # 1.5 (FN) * 2.0 (ultra low) = 3.0
        assert multiplier == 3.0

    def test_calculate_premium_multiplier_blue_gem(self):
        """Prueba el cálculo de multiplicador con blue gem."""
        multiplier = self.analyzer._calculate_premium_multiplier(
            float_value=0.03,
            float_rarity=FloatRarity.FACTORY_NEW,
            pattern_rarity=AttributeRarity.EXTREMELY_RARE,
            stickers_value=0.0,
            stattrak=False,
            souvenir=False
        )
        
        # 1.5 (FN) * 5.0 (extremely rare pattern) = 7.5
        assert multiplier == 7.5

    def test_calculate_premium_multiplier_stattrak_souvenir(self):
        """Prueba el cálculo de multiplicador con StatTrak y Souvenir."""
        multiplier = self.analyzer._calculate_premium_multiplier(
            float_value=0.15,
            float_rarity=FloatRarity.FIELD_TESTED,
            pattern_rarity=AttributeRarity.COMMON,
            stickers_value=0.0,
            stattrak=True,
            souvenir=True
        )
        
        # 1.0 (FT) * 1.3 (ST) * 1.5 (souvenir) = 1.95 (con tolerancia para float precision)
        assert abs(multiplier - 1.95) < 0.001

    def test_calculate_premium_multiplier_expensive_stickers(self):
        """Prueba el cálculo de multiplicador con stickers caros."""
        multiplier = self.analyzer._calculate_premium_multiplier(
            float_value=0.15,
            float_rarity=FloatRarity.FIELD_TESTED,
            pattern_rarity=AttributeRarity.COMMON,
            stickers_value=10000.0,  # $10k en stickers
            stattrak=False,
            souvenir=False
        )
        
        # 1.0 (FT) * (1.0 + 10000 * 0.1 / 1000) = 1.0 * 2.0 = 2.0
        assert multiplier == 2.0

    def test_identify_special_attributes_ultra_low_float(self):
        """Prueba la identificación de float ultra bajo."""
        special = self.analyzer._identify_special_attributes(
            float_value=0.0005,
            pattern_index=None,
            item_name=None,
            attributes={}
        )
        
        assert special["ultra_low_float"] is True

    def test_identify_special_attributes_max_float(self):
        """Prueba la identificación de float máximo."""
        special = self.analyzer._identify_special_attributes(
            float_value=0.9995,
            pattern_index=None,
            item_name=None,
            attributes={}
        )
        
        assert special["max_float"] is True

    def test_identify_special_attributes_doppler_phase(self):
        """Prueba la identificación de fase Doppler."""
        special = self.analyzer._identify_special_attributes(
            float_value=None,
            pattern_index=None,
            item_name=None,
            attributes={'phase': 'Phase 2'}
        )
        
        assert special["doppler_phase"] == 'Phase 2'

    def test_identify_special_attributes_fade_percentage(self):
        """Prueba la identificación de porcentaje de fade."""
        special = self.analyzer._identify_special_attributes(
            float_value=None,
            pattern_index=None,
            item_name=None,
            attributes={'fade_percentage': 95}
        )
        
        assert special["fade_percentage"] == 95

    def test_evaluate_attribute_rarity_complete(self):
        """Prueba la evaluación completa de atributos."""
        attributes = {
            'float': 0.003,
            'paintseed': 661,
            'stattrak': True
        }
        
        stickers = [
            {'name': 'iBUYPOWER (Holo)'},
            {'name': 'Titan (Holo)'}
        ]
        
        evaluation = self.analyzer.evaluate_attribute_rarity(
            attributes, stickers, "AK-47 | Case Hardened (Factory New)"
        )
        
        assert isinstance(evaluation, AttributeEvaluation)
        assert evaluation.float_value == 0.003
        assert evaluation.float_rarity == FloatRarity.FACTORY_NEW
        assert evaluation.pattern_index == 661
        assert evaluation.pattern_rarity == AttributeRarity.EXTREMELY_RARE
        assert evaluation.stickers_value > 0
        assert evaluation.stickers_rarity == AttributeRarity.EXTREMELY_RARE
        assert evaluation.stattrak is True
        assert evaluation.souvenir is False
        assert evaluation.overall_rarity_score > 80  # Debería ser muy alto
        assert evaluation.premium_multiplier > 10   # Debería ser muy alto

    def test_evaluate_attribute_rarity_stattrak_in_name(self):
        """Prueba la detección de StatTrak en el nombre del ítem."""
        attributes = {'float': 0.15}
        
        evaluation = self.analyzer.evaluate_attribute_rarity(
            attributes, [], "StatTrak™ AK-47 | Redline (Field-Tested)"
        )
        
        assert evaluation.stattrak is True

    def test_evaluate_attribute_rarity_souvenir_in_name(self):
        """Prueba la detección de Souvenir en el nombre del ítem."""
        attributes = {'float': 0.15}
        
        evaluation = self.analyzer.evaluate_attribute_rarity(
            attributes, [], "Souvenir AK-47 | Safari Mesh (Field-Tested)"
        )
        
        assert evaluation.souvenir is True

    def test_evaluate_attribute_rarity_minimal_attributes(self):
        """Prueba la evaluación con atributos mínimos."""
        attributes = {}
        
        evaluation = self.analyzer.evaluate_attribute_rarity(
            attributes, [], None
        )
        
        assert evaluation.float_value is None
        assert evaluation.float_rarity is None
        assert evaluation.pattern_index is None
        assert evaluation.pattern_rarity == AttributeRarity.COMMON
        assert evaluation.stickers_value == 0.0
        assert evaluation.stickers_rarity == AttributeRarity.COMMON
        assert evaluation.stattrak is False
        assert evaluation.souvenir is False
        assert evaluation.overall_rarity_score == 0.0
        assert evaluation.premium_multiplier == 1.0

    def test_evaluate_attribute_rarity_pattern_as_pattern_key(self):
        """Prueba la evaluación usando 'pattern' en lugar de 'paintseed'."""
        attributes = {
            'float': 0.03,
            'pattern': 661  # Usando 'pattern' en lugar de 'paintseed'
        }
        
        evaluation = self.analyzer.evaluate_attribute_rarity(
            attributes, [], "AK-47 | Case Hardened"
        )
        
        assert evaluation.pattern_index == 661
        assert evaluation.pattern_rarity == AttributeRarity.EXTREMELY_RARE

# Para ejecutar: pytest tests/unit/test_market_analyzer.py