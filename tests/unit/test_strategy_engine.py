# tests/unit/test_strategy_engine.py
import pytest
import os
import sys
import logging
import time
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from datetime import datetime, timedelta

# Añadir el directorio raíz del proyecto a sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.strategy_engine import StrategyEngine, DEFAULT_GAME_ID
from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer, AttributeEvaluation, FloatRarity, AttributeRarity
from core.data_manager import SkinsMaestra, PreciosHistoricos 

# Configurar logger para pruebas si es necesario ver la salida
# from utils.logger import configure_logging
# configure_logging(log_level=logging.DEBUG)

@pytest.fixture
def mock_dmarket_connector():
    """Mock para DMarketAPI."""
    connector = MagicMock(spec=DMarketAPI)
    # Simular los atributos que DMarketAPI esperaría en su __init__ si no se mockea completamente
    # o si alguna lógica interna del mock los necesita.
    # Para un MagicMock(spec=...), usualmente no se necesitan a menos que el spec sea una clase real y se llame su __init__.
    # Aquí los ponemos por si acaso, aunque con spec=DMarketAPI, el constructor original no se llama.
    connector.public_key = "test_public_key" 
    connector.secret_key_hex = "a" * 128 
    return connector

@pytest.fixture
def mock_market_analyzer():
    """Mock para MarketAnalyzer."""
    return MagicMock(spec=MarketAnalyzer)

@pytest.fixture
def mock_db_session():
    """Mock para la sesión de SQLAlchemy."""
    session = MagicMock()
    
    # Mock para query(SkinsMaestra).filter().first()
    mock_query_obj = MagicMock() # Objeto que es devuelto por session.query(...)
    mock_filter_obj = MagicMock() # Objeto que es devuelto por mock_query_obj.filter(...)
    
    session.query.return_value = mock_query_obj
    mock_query_obj.filter.return_value = mock_filter_obj
    # mock_filter_obj.first() será configurado en cada test según necesidad
    # session.close = MagicMock() # Mockear close para verificar si se llama

    return session

@pytest.fixture
def strategy_engine_factory(mock_dmarket_connector, mock_market_analyzer):
    """Factory para crear instancias de StrategyEngine con mocks y config opcional."""
    def _factory(config_override=None):
        # No necesitamos pasar las claves al mock si DMarketAPI está bien mockeado y no se llama su __init__.
        # El spec asegura que el mock se comporte como DMarketAPI.
        engine = StrategyEngine(
            dmarket_connector=mock_dmarket_connector,
            market_analyzer=mock_market_analyzer,
            config=config_override if config_override is not None else {}
        )
        # Limpiar mocks entre creaciones de factory si es necesario para algunos tests
        mock_dmarket_connector.reset_mock()
        mock_market_analyzer.reset_mock()
        return engine
    return _factory

@pytest.fixture
def default_strategy_engine(strategy_engine_factory):
    """Instancia de StrategyEngine con configuración por defecto y mocks."""
    return strategy_engine_factory() 

# --- Pruebas para Configuración y Comisiones ---

def test_get_default_config(default_strategy_engine: StrategyEngine):
    """Prueba que se carga la configuración por defecto correctamente."""
    config = default_strategy_engine.config
    assert config["min_profit_usd_basic_flip"] == 0.50
    assert config["game_id"] == DEFAULT_GAME_ID
    assert "delay_between_items_sec" in config
    assert config.get("delay_between_items_sec") == 1.0 # Chequear valor por defecto

def test_override_default_config(strategy_engine_factory):
    """Prueba que la configuración por defecto puede ser sobreescrita."""
    custom_config = {"game_id": "custom_game", "min_profit_usd_basic_flip": 1.00, "delay_between_items_sec": 0.5}
    engine = strategy_engine_factory(config_override=custom_config)
    assert engine.config["game_id"] == "custom_game"
    assert engine.config["min_profit_usd_basic_flip"] == 1.00
    assert engine.config["delay_between_items_sec"] == 0.5
    # Asegurar que otras configs por defecto aún existen si no se sobreescriben
    assert "snipe_discount_percentage" in engine.config 

# --- Pruebas para _fetch_and_cache_fee_info ---

def test_fetch_and_cache_fee_info_success(default_strategy_engine: StrategyEngine, mock_dmarket_connector: MagicMock):
    """Prueba la obtención y cacheo exitoso de tasas de comisión."""
    game_id = "test_game_1"
    mock_fee_response = {
        "gameId": game_id,
        "rates": [{"type": "exchange", "amount": "0.05"}], # 5%
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }
    mock_dmarket_connector.get_fee_rates.return_value = mock_fee_response
    
    assert default_strategy_engine.dmarket_fee_info is None
    
    # Primera llamada: debe llamar a la API
    result = default_strategy_engine._fetch_and_cache_fee_info(game_id)
    assert result is True
    assert default_strategy_engine.dmarket_fee_info == mock_fee_response
    mock_dmarket_connector.get_fee_rates.assert_called_once_with(game_id=game_id)
    
    # Segunda llamada: debe usar la caché
    mock_dmarket_connector.get_fee_rates.reset_mock() # Resetear mock para la segunda llamada
    result_cached = default_strategy_engine._fetch_and_cache_fee_info(game_id)
    assert result_cached is True
    assert default_strategy_engine.dmarket_fee_info == mock_fee_response # Sigue siendo la misma info
    mock_dmarket_connector.get_fee_rates.assert_not_called() # No debe llamar a la API de nuevo

def test_fetch_fee_info_api_failure(default_strategy_engine: StrategyEngine, mock_dmarket_connector: MagicMock, caplog):
    """Prueba el manejo de fallo al obtener tasas de la API."""
    game_id = "test_game_2"
    mock_dmarket_connector.get_fee_rates.return_value = {"error": "API Error", "message": "Failed to fetch"}
    
    with caplog.at_level(logging.ERROR):
        result = default_strategy_engine._fetch_and_cache_fee_info(game_id)
    
    assert result is False
    assert default_strategy_engine.dmarket_fee_info is None # Cache debe invalidarse o no establecerse
    mock_dmarket_connector.get_fee_rates.assert_called_once_with(game_id=game_id)
    assert f"No se pudieron obtener las tasas de comisión para {game_id}" in caplog.text

def test_fetch_fee_info_different_game_id_refreshes_cache(default_strategy_engine: StrategyEngine, mock_dmarket_connector: MagicMock):
    """Prueba que la caché se refresca si se pide un game_id diferente."""
    game_id_1 = "game1"
    game_id_2 = "game2"
    mock_fee_response_1 = {"gameId": game_id_1, "rates": [{"type": "exchange", "amount": "0.05"}]}
    mock_fee_response_2 = {"gameId": game_id_2, "rates": [{"type": "exchange", "amount": "0.03"}]}

    # Cargar para game_id_1
    mock_dmarket_connector.get_fee_rates.return_value = mock_fee_response_1
    default_strategy_engine._fetch_and_cache_fee_info(game_id_1)
    assert default_strategy_engine.dmarket_fee_info == mock_fee_response_1
    mock_dmarket_connector.get_fee_rates.assert_called_once_with(game_id=game_id_1)
    
    # Pedir para game_id_2
    mock_dmarket_connector.get_fee_rates.reset_mock()
    mock_dmarket_connector.get_fee_rates.return_value = mock_fee_response_2
    default_strategy_engine._fetch_and_cache_fee_info(game_id_2)
    assert default_strategy_engine.dmarket_fee_info == mock_fee_response_2
    mock_dmarket_connector.get_fee_rates.assert_called_once_with(game_id=game_id_2)


# --- Pruebas para _calculate_dmarket_sale_fee_cents ---

@pytest.mark.parametrize("item_price_cents, fee_rate_str, min_comm_str, expected_fee_cents", [
    (1000, "0.05", "0.01", 50),  # 5% de 1000 = 50. Mínima 1. -> 50
    (100, "0.05", "0.01", 5),   # 5% de 100 = 5. Mínima 1. -> 5
    (10, "0.05", "0.01", 1),    # 5% de 10 = 0.5 (int->0). Mínima 1. -> 1
    (2000, "0.03", "0.02", 60), # 3% de 2000 = 60. Mínima 2. -> 60
    (50, "0.03", "0.02", 2),    # 3% de 50 = 1.5 (int->1). Mínima 2. -> 2
    (1000, "0.00", "0.00", 0),  # 0% de comisión, 0 mínima -> 0
    (1000, "0.07", "0.00", 70),  # Sin comisión mínima explícita (o 0)
])
def test_calculate_sale_fee_cents_valid_rates(default_strategy_engine: StrategyEngine, item_price_cents, fee_rate_str, min_comm_str, expected_fee_cents):
    """Prueba el cálculo de comisión con varias tasas y precios."""
    default_strategy_engine.dmarket_fee_info = {
        "gameId": "test_game",
        "rates": [{"type": "exchange", "amount": fee_rate_str}],
        "minCommission": {"amount": min_comm_str, "currency": "USD"}
    }
    fee = default_strategy_engine._calculate_dmarket_sale_fee_cents(item_price_cents)
    assert fee == expected_fee_cents

def test_calculate_sale_fee_cents_no_fee_info(default_strategy_engine: StrategyEngine, caplog):
    """Prueba el cálculo de comisión cuando no hay información de tasas cacheadas."""
    default_strategy_engine.dmarket_fee_info = None # Asegurar que no hay info
    with caplog.at_level(logging.WARNING):
        fee = default_strategy_engine._calculate_dmarket_sale_fee_cents(1000)
    assert fee == 0
    assert "No hay información de tasas de DMarket disponible" in caplog.text

def test_calculate_sale_fee_cents_invalid_rate_format(default_strategy_engine: StrategyEngine, caplog):
    """Prueba el cálculo de comisión con formato de tasa inválido."""
    default_strategy_engine.dmarket_fee_info = {
        "gameId": "test_game",
        "rates": [{"type": "exchange", "amount": "invalid_format"}], # Tasa no numérica
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }
    with caplog.at_level(logging.ERROR):
        fee = default_strategy_engine._calculate_dmarket_sale_fee_cents(1000)
    assert fee == 0
    assert "Error al parsear o calcular la comisión de DMarket" in caplog.text

def test_calculate_sale_fee_cents_missing_rates_key(default_strategy_engine: StrategyEngine, caplog):
    """Prueba el cálculo de comisión si falta la clave 'rates'."""
    default_strategy_engine.dmarket_fee_info = { "gameId": "test_game" } # Falta 'rates'
    with caplog.at_level(logging.WARNING): # El primer check es un warning
        fee = default_strategy_engine._calculate_dmarket_sale_fee_cents(1000)
    assert fee == 0
    
def test_calculate_sale_fee_cents_missing_amount_in_rate(default_strategy_engine: StrategyEngine, caplog):
    """Prueba el cálculo si falta 'amount' dentro de una tasa."""
    default_strategy_engine.dmarket_fee_info = {
        "gameId": "test_game",
        "rates": [{"type": "exchange"}], # Falta 'amount'
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }
    with caplog.at_level(logging.ERROR):
        fee = default_strategy_engine._calculate_dmarket_sale_fee_cents(1000)
    assert fee == 0
    assert "Formato de tasa de comisión inesperado, no se encontró 'amount'." in caplog.text

# --- Pruebas para _find_basic_flips ---

MOCK_BASIC_FLIP_LSO = [{'assetId': 'sell123', 'price': {'USD': '1000'}}] # 10.00 USD
MOCK_BASIC_FLIP_HBO = [{'offerId': 'buyXYZ', 'price': {'USD': '1200'}}]   # 12.00 USD
MOCK_FEE_INFO_5_PERCENT_MIN_1_CENT = {
    "gameId": DEFAULT_GAME_ID,
    "rates": [{"type": "exchange", "amount": "0.05"}], # 5%
    "minCommission": {"amount": "0.01", "currency": "USD"}
}

@pytest.fixture
def engine_with_fees_cached(default_strategy_engine: StrategyEngine):
    """Pre-cachea información de tasas en el engine."""
    default_strategy_engine.dmarket_fee_info = MOCK_FEE_INFO_5_PERCENT_MIN_1_CENT
    # Asegurar que la config del engine también use el DEFAULT_GAME_ID para que la caché coincida
    default_strategy_engine.config["game_id"] = DEFAULT_GAME_ID 
    return default_strategy_engine

def test_find_basic_flips_success(engine_with_fees_cached: StrategyEngine):
    """Prueba una oportunidad de flip básica exitosa."""
    engine = engine_with_fees_cached
    # Config: min_profit_usd = 0.50, min_profit_percentage = 0.05 (por defecto)
    # LSO: 10.00 USD, HBO: 12.00 USD
    # Comisión sobre HBO (12.00 USD) = 12.00 * 0.05 = 0.60 USD
    # Profit = 12.00 - 10.00 - 0.60 = 1.40 USD
    # Profit % = 1.40 / 10.00 = 14%
    # Cumple umbrales (1.40 >= 0.50, 0.14 >= 0.05)

    lso = [{'assetId': 's1', 'price': {'USD': '1000'}}] # 10 USD
    hbo = [{'offerId': 'b1', 'price': {'USD': '1200'}}] # 12 USD

    opportunities = engine._find_basic_flips("Flip Item 1", lso, hbo)
    
    assert len(opportunities) == 1
    op = opportunities[0]
    assert op["strategy"] == "basic_flip"
    assert op["item_title"] == "Flip Item 1"
    assert op["buy_price_usd"] == pytest.approx(10.00)
    assert op["sell_price_usd"] == pytest.approx(12.00)
    assert op["commission_usd"] == pytest.approx(0.60)
    assert op["profit_usd"] == pytest.approx(1.40)
    assert op["profit_percentage"] == pytest.approx(0.14)
    assert op["lso_details"] == lso[0]
    assert op["hbo_details"] == hbo[0]

def test_find_basic_flips_no_lso(engine_with_fees_cached: StrategyEngine):
    """Prueba cuando no hay LSO válidas."""
    opportunities = engine_with_fees_cached._find_basic_flips("No LSO Item", [], MOCK_BASIC_FLIP_HBO)
    assert len(opportunities) == 0
    opportunities_invalid_price = engine_with_fees_cached._find_basic_flips(
        "No LSO Item", [{'price': {'EUR': '1000'}}], MOCK_BASIC_FLIP_HBO
    )
    assert len(opportunities_invalid_price) == 0

def test_find_basic_flips_no_hbo(engine_with_fees_cached: StrategyEngine):
    """Prueba cuando no hay HBO válidas."""
    opportunities = engine_with_fees_cached._find_basic_flips("No HBO Item", MOCK_BASIC_FLIP_LSO, [])
    assert len(opportunities) == 0
    opportunities_invalid_price = engine_with_fees_cached._find_basic_flips(
        "No HBO Item", MOCK_BASIC_FLIP_LSO, [{'price': {'EUR': '1200'}}]
    )
    assert len(opportunities_invalid_price) == 0

def test_find_basic_flips_negative_spread(engine_with_fees_cached: StrategyEngine):
    """Prueba cuando LSO es mayor o igual que HBO (spread negativo o cero)."""
    lso_expensive = [{'assetId': 's2', 'price': {'USD': '1300'}}] # 13 USD
    opportunities = engine_with_fees_cached._find_basic_flips("Negative Spread Item", lso_expensive, MOCK_BASIC_FLIP_HBO) # HBO 12 USD
    assert len(opportunities) == 0

    lso_equal_hbo = [{'assetId': 's3', 'price': {'USD': '1200'}}] # 12 USD
    opportunities_equal = engine_with_fees_cached._find_basic_flips("Equal Spread Item", lso_equal_hbo, MOCK_BASIC_FLIP_HBO) # HBO 12 USD
    assert len(opportunities_equal) == 0

def test_find_basic_flips_profit_below_usd_threshold(engine_with_fees_cached: StrategyEngine):
    """Prueba cuando el profit en USD está por debajo del umbral."""
    # LSO: 10.00 USD, HBO: 10.80 USD
    # Comisión sobre HBO (10.80 USD) = 10.80 * 0.05 = 0.54 USD
    # Profit = 10.80 - 10.00 - 0.54 = 0.26 USD
    # Umbral USD por defecto: 0.50.  0.26 < 0.50 -> No oportunidad
    lso = [{'assetId': 's4', 'price': {'USD': '1000'}}] # 10.00 USD
    hbo_low_profit = [{'offerId': 'b4', 'price': {'USD': '1080'}}] # 10.80 USD
    
    opportunities = engine_with_fees_cached._find_basic_flips("Low USD Profit Item", lso, hbo_low_profit)
    assert len(opportunities) == 0

def test_find_basic_flips_profit_below_percentage_threshold(engine_with_fees_cached: StrategyEngine):
    """Prueba cuando el profit porcentual está por debajo del umbral."""
    engine = engine_with_fees_cached
    engine.config["min_profit_usd_basic_flip"] = 0.10 # Bajar umbral USD para aislar el de %
    engine.config["min_profit_percentage_basic_flip"] = 0.03 # 3%

    # LSO: 100.00 USD (10000 centavos), HBO: 106.00 USD (10600 centavos)
    # Fee: 10600 * 0.05 = 530 centavos (5.30 USD)
    # Profit USD: 10600 - 10000 - 530 = 70 centavos (0.70 USD). Pasa umbral USD de 0.10.
    # Profit %: 0.70 / 100.00 = 0.007 (0.7%). Falla umbral % de 3%.
    
    lso = [{'assetId': 's5', 'price': {'USD': '10000'}}] 
    hbo_low_percentage = [{'offerId': 'b5', 'price': {'USD': '10600'}}] 

    opportunities = engine._find_basic_flips("Low Percentage Profit Item", lso, hbo_low_percentage)
    assert len(opportunities) == 0


def test_find_basic_flips_fee_fetch_failure(default_strategy_engine: StrategyEngine, mock_dmarket_connector: MagicMock, caplog):
    """Prueba _find_basic_flips cuando falla la obtención de tasas y no están cacheadas."""
    engine = default_strategy_engine
    engine.dmarket_fee_info = None # Asegurar que no hay fee info cacheada
    
    # Configurar el mock del conector para que falle la llamada a get_fee_rates
    engine.connector.get_fee_rates.return_value = {"error": "Fee API down"}
    
    with caplog.at_level(logging.WARNING):
        opportunities = engine._find_basic_flips(
            "Fee Fetch Fail Item", 
            MOCK_BASIC_FLIP_LSO, 
            MOCK_BASIC_FLIP_HBO
        )
    
    assert len(opportunities) == 0
    # Verificar que se intentó llamar a get_fee_rates, ya que no estaba en caché
    engine.connector.get_fee_rates.assert_called_once_with(game_id=engine.config["game_id"])
    assert "No se pudieron obtener las tasas de comisión" in caplog.text
    assert "no se puede calcular profit de flip" in caplog.text

# --- Pruebas para _find_snipes ---

MOCK_SNIPE_SELL_OFFERS_VALID = [{'assetId': 'sn1', 'price': {'USD': '800'}}] # 8.00 USD
MOCK_SNIPE_PME_USD = 10.00 # PME de 10.00 USD
MOCK_HISTORICAL_FOR_SNIPE = [{'price_usd': 9.90, 'timestamp': '2023-01-01T00:00:00Z'}] # Solo para pasar al analizador

def test_find_snipes_success(engine_with_fees_cached: StrategyEngine, mock_market_analyzer: MagicMock):
    """Prueba una oportunidad de snipe exitosa."""
    engine = engine_with_fees_cached
    # Config: min_price_usd_for_sniping = 1.00, snipe_discount_percentage = 0.15 (por defecto)
    #         min_profit_usd (no aplicado directamente en snipe, pero profit debe ser >0)
    #         Fee: 5%
    # Oferta: 8.00 USD. PME: 10.00 USD.
    # Descuento: (10.00 - 8.00) / 10.00 = 0.20 (20%).  20% >= 15% -> OK
    # Profit si se revende a PME:
    #   Precio Venta PME: 10.00 USD
    #   Comisión sobre PME: 10.00 * 0.05 = 0.50 USD
    #   Profit: 10.00 (venta PME) - 8.00 (compra oferta) - 0.50 (comisión) = 1.50 USD
    #   1.50 USD > 0 -> OK
    
    mock_market_analyzer.calculate_estimated_market_price.return_value = MOCK_SNIPE_PME_USD
    
    opportunities = engine._find_snipes(
        "Snipe Item 1", 
        MOCK_SNIPE_SELL_OFFERS_VALID, 
        MOCK_HISTORICAL_FOR_SNIPE
    )
    
    assert len(opportunities) == 1
    op = opportunities[0]
    assert op["strategy"] == "snipe"
    assert op["item_title"] == "Snipe Item 1"
    assert op["pme_usd"] == pytest.approx(MOCK_SNIPE_PME_USD)
    assert op["offer_price_usd"] == pytest.approx(8.00)
    assert op["discount_percentage"] == pytest.approx(0.20)
    assert op["commission_on_pme_usd"] == pytest.approx(0.50)
    assert op["potential_profit_usd"] == pytest.approx(1.50)
    assert op["offer_details"] == MOCK_SNIPE_SELL_OFFERS_VALID[0]
    mock_market_analyzer.calculate_estimated_market_price.assert_called_once()

def test_find_snipes_no_pme(engine_with_fees_cached: StrategyEngine, mock_market_analyzer: MagicMock):
    """Prueba cuando no se puede calcular el PME."""
    mock_market_analyzer.calculate_estimated_market_price.return_value = None
    opportunities = engine_with_fees_cached._find_snipes(
        "No PME Item", MOCK_SNIPE_SELL_OFFERS_VALID, MOCK_HISTORICAL_FOR_SNIPE
    )
    assert len(opportunities) == 0
    mock_market_analyzer.calculate_estimated_market_price.assert_called_once()

def test_find_snipes_no_current_offers(engine_with_fees_cached: StrategyEngine, mock_market_analyzer: MagicMock):
    """Prueba cuando no hay ofertas de venta actuales."""
    # Resetear el mock para esta prueba específica
    mock_market_analyzer.calculate_estimated_market_price.reset_mock()
    
    opportunities = engine_with_fees_cached._find_snipes("No Offers Item", [], MOCK_HISTORICAL_FOR_SNIPE)
    assert len(opportunities) == 0
    # En la implementación actual de _find_snipes, si no hay current_sell_offers,
    # se retorna una lista vacía ANTES de llamar a calculate_estimated_market_price.
    mock_market_analyzer.calculate_estimated_market_price.assert_not_called()


def test_find_snipes_discount_insufficient(engine_with_fees_cached: StrategyEngine, mock_market_analyzer: MagicMock):
    """Prueba cuando el descuento de la oferta no es suficiente."""
    # Oferta: 9.00 USD. PME: 10.00 USD. Descuento: 10%. Umbral: 15%.
    offers_low_discount = [{'assetId': 'sn2', 'price': {'USD': '900'}}]
    mock_market_analyzer.calculate_estimated_market_price.return_value = MOCK_SNIPE_PME_USD
    
    opportunities = engine_with_fees_cached._find_snipes(
        "Low Discount Snipe", offers_low_discount, MOCK_HISTORICAL_FOR_SNIPE
    )
    assert len(opportunities) == 0

def test_find_snipes_price_below_min_threshold(engine_with_fees_cached: StrategyEngine, mock_market_analyzer: MagicMock):
    """Prueba cuando el precio de la oferta es demasiado bajo para ser considerado snipe."""
    engine = engine_with_fees_cached
    engine.config["min_price_usd_for_sniping"] = 5.00 # Setear umbral alto
    
    # Oferta: 4.00 USD. PME: 10.00 USD. Descuento: 60% (suficiente)
    # Pero 4.00 < 5.00 (umbral de precio)
    offers_too_cheap = [{'assetId': 'sn3', 'price': {'USD': '400'}}]
    mock_market_analyzer.calculate_estimated_market_price.return_value = MOCK_SNIPE_PME_USD
    
    opportunities = engine._find_snipes(
        "Too Cheap Snipe", offers_too_cheap, MOCK_HISTORICAL_FOR_SNIPE
    )
    assert len(opportunities) == 0

def test_find_snipes_profit_not_positive(engine_with_fees_cached: StrategyEngine, mock_market_analyzer: MagicMock):
    """Prueba cuando el descuento es bueno pero el profit final no es positivo."""
    # Oferta: 9.50 USD. PME: 10.00 USD.
    # Descuento: (10.00 - 9.50) / 10.00 = 0.05 (5%). Si el umbral de config es 5%, pasaría el chequeo de descuento.
    engine_with_fees_cached.config["snipe_discount_percentage"] = 0.05 # Bajar umbral de descuento
    
    # Profit si se revende a PME (10.00 USD):
    #   Comisión sobre PME: 10.00 * 0.05 = 0.50 USD
    #   Profit: 10.00 (venta PME) - 9.50 (compra oferta) - 0.50 (comisión) = 0.00 USD
    #   0.00 no es > 0 -> No oportunidad
    offers_zero_profit = [{'assetId': 'sn4', 'price': {'USD': '950'}}]
    mock_market_analyzer.calculate_estimated_market_price.return_value = MOCK_SNIPE_PME_USD
    
    opportunities = engine_with_fees_cached._find_snipes(
        "Zero Profit Snipe", offers_zero_profit, MOCK_HISTORICAL_FOR_SNIPE
    )
    assert len(opportunities) == 0

def test_find_snipes_pme_is_zero(engine_with_fees_cached: StrategyEngine, mock_market_analyzer: MagicMock, caplog):
    """Prueba el manejo cuando PME es cero para evitar ZeroDivisionError."""
    mock_market_analyzer.calculate_estimated_market_price.return_value = 0.0
    offers = [{'assetId': 'sn5', 'price': {'USD': '100'}}] # 1 USD
    
    with caplog.at_level(logging.DEBUG):
        opportunities = engine_with_fees_cached._find_snipes(
            "Zero PME Snipe", offers, MOCK_HISTORICAL_FOR_SNIPE
        )
    assert len(opportunities) == 0
    assert "PME para Zero PME Snipe es 0.00, no se puede calcular descuento de snipe." in caplog.text


def test_find_snipes_fee_fetch_failure_still_finds_snipe_no_profit(
    default_strategy_engine: StrategyEngine, 
    mock_dmarket_connector: MagicMock, 
    mock_market_analyzer: MagicMock,
    caplog
):
    """
    Prueba que un snipe (basado en descuento) se identifica incluso si las tasas fallan,
    pero el profit no se calculará correctamente (o será 0 / negativo).
    La lógica actual de _find_snipes continúa si falla el fetch de tasas.
    """
    engine = default_strategy_engine
    engine.dmarket_fee_info = None # No fees cached
    engine.connector.get_fee_rates.return_value = {"error": "Fee API down for snipes"} # Simular fallo

    mock_market_analyzer.calculate_estimated_market_price.return_value = MOCK_SNIPE_PME_USD # PME 10.00
    valid_snipe_offer = [{'assetId': 'sn_valid', 'price': {'USD': '800'}}] # Oferta 8.00 (20% desc)

    with caplog.at_level(logging.WARNING):
        opportunities = engine._find_snipes(
            "Snipe Fee Fail", valid_snipe_offer, MOCK_HISTORICAL_FOR_SNIPE
        )
    
    assert "No se pudieron obtener las tasas de comisión para Snipe Fee Fail" in caplog.text
    
    # El snipe debería ser identificado por el descuento, pero el profit puede ser 0 o negativo
    # porque _calculate_dmarket_sale_fee_cents retornará 0 si las tasas no están.
    # Profit = PME_cents - offer_cents - 0 (comisión) = 1000 - 800 - 0 = 200.  2.00 USD
    # Esto significa que la oportunidad SÍ se registrará si el profit es > 0.
    
    assert len(opportunities) == 1 # Se espera que se encuentre el snipe
    op = opportunities[0]
    assert op["potential_profit_usd"] == pytest.approx(2.00) # PME - offer_price (sin comisión)
    assert op["commission_on_pme_usd"] == pytest.approx(0.00) # Comisión es 0 debido al fallo

# --- Pruebas para run_strategies ---

@patch('core.strategy_engine.get_db') # Mockear get_db a nivel de módulo
@patch('core.strategy_engine.time.sleep') # Mockear time.sleep
def test_run_strategies_orchestration(
    mock_time_sleep: MagicMock,
    mock_get_db: MagicMock,
    default_strategy_engine: StrategyEngine, 
    mock_dmarket_connector: MagicMock, 
    mock_market_analyzer: MagicMock, # Aunque no se usa directamente, es parte del engine
    mock_db_session: MagicMock,
    caplog
):
    """
    Prueba la orquestación de run_strategies, verificando llamadas a dependencias
    y métodos internos.
    """
    engine = default_strategy_engine
    mock_get_db.return_value = iter([mock_db_session]) # get_db es un generador

    # Configurar mocks para las llamadas a la API de DMarket
    mock_sell_offers_item1 = {"objects": [{'assetId': 's1', 'price': {'USD': '1000'}}]}
    mock_buy_orders_item1 = {"offers": [{'offerId': 'b1', 'price': {'USD': '900'}}]}
    mock_sell_offers_item2 = {"objects": [{'assetId': 's2', 'price': {'USD': '2000'}}]}
    mock_buy_orders_item2 = {"offers": [{'offerId': 'b2', 'price': {'USD': '1800'}}]}

    # Configurar series de retornos para get_offers_by_title y get_buy_offers
    mock_dmarket_connector.get_offers_by_title.side_effect = [
        mock_sell_offers_item1, 
        mock_sell_offers_item2
    ]
    mock_dmarket_connector.get_buy_offers.side_effect = [
        mock_buy_orders_item1,
        mock_buy_orders_item2
    ]
    
    # Configurar mock para la respuesta de la BD
    # Item 1: Con datos históricos
    mock_skin_item1 = MagicMock(spec=SkinsMaestra)
    mock_skin_item1.market_hash_name = "Item 1"
    # Crear un mock para el objeto datetime y su método isoformat
    mock_datetime_obj_item1 = MagicMock()
    mock_datetime_obj_item1.isoformat.return_value = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 3600))
    mock_precio1_item1 = MagicMock(spec=PreciosHistoricos, price=9.50, timestamp=mock_datetime_obj_item1, fuente_api="DMarket")
    mock_skin_item1.precios = [mock_precio1_item1]
    
    # Item 2: Sin datos históricos en BD
    mock_skin_item2_no_history = None # Simula que db.query(...).first() retorna None

    # Configurar mock_db_session.query().filter().first() para retornar secuencialmente
    # Es importante que el objeto que retorna .filter() sea el mismo que tiene .first()
    # Si session.query(SkinsMaestra) es un objeto, y ese objeto tiene .filter(), y ese tiene .first()
    # Esta es una forma más robusta de mockear la cadena de llamadas de SQLAlchemy:
    mock_query_result_item1 = MagicMock()
    mock_query_result_item1.filter.return_value.first.return_value = mock_skin_item1
    
    mock_query_result_item2 = MagicMock()
    mock_query_result_item2.filter.return_value.first.return_value = mock_skin_item2_no_history

    mock_db_session.query.side_effect = [mock_query_result_item1, mock_query_result_item2]

    # Datos de ítems simulados para _get_item_data
    mock_item_data_1 = {
        'title': 'Item 1',
        'current_sell_offers': mock_sell_offers_item1["objects"],
        'current_buy_orders': mock_buy_orders_item1["offers"],
        'historical_prices': [{"price_usd": mock_precio1_item1.price, 
                              "timestamp": mock_precio1_item1.timestamp.isoformat(), 
                              "fuente_api": mock_precio1_item1.fuente_api}]
    }
    
    mock_item_data_2 = {
        'title': 'Item 2',
        'current_sell_offers': mock_sell_offers_item2["objects"],
        'current_buy_orders': mock_buy_orders_item2["offers"],
        'historical_prices': []  # Sin datos históricos
    }

    # Mockear las funciones de estrategia internas para verificar que se llaman
    # y para controlar qué oportunidades retornan.
    expected_flip_op_item1 = {"strategy": "basic_flip", "item_title": "Item 1", "profit_usd": 0.10}
    expected_snipe_op_item1 = {"strategy": "snipe", "item_title": "Item 1", "profit_usd": 0.20}
    
    with patch.object(engine, '_fetch_and_cache_fee_info', return_value=True) as mock_fetch_fees, \
         patch.object(engine, '_get_item_data') as mock_get_item_data, \
         patch.object(engine, '_find_basic_flips') as mock_find_flips, \
         patch.object(engine, '_find_snipes') as mock_find_snipes, \
         patch.object(engine, '_find_attribute_premium_flips', return_value=[]) as mock_find_attr, \
         patch.object(engine, '_find_trade_lock_opportunities', return_value=[]) as mock_find_trade, \
         patch.object(engine, '_find_volatility_opportunities', return_value=[]) as mock_find_vol:
        
        # Configurar _get_item_data para retornar datos simulados
        mock_get_item_data.side_effect = [mock_item_data_1, mock_item_data_2]
        
        mock_find_flips.side_effect = [
            [expected_flip_op_item1], # Para Item 1
            []                        # Para Item 2
        ]
        mock_find_snipes.side_effect = [
            [expected_snipe_op_item1],# Para Item 1
            []                        # Para Item 2
        ]

        items_to_scan = ["Item 1", "Item 2"]
        with caplog.at_level(logging.INFO): # Para verificar logs si es necesario
            results = engine.run_strategies(items_to_scan)

    # Verificaciones
    mock_fetch_fees.assert_called_once_with(engine.config["game_id"])
    
    # Verificar que _get_item_data se llamó para ambos ítems
    assert mock_get_item_data.call_count == 2
    mock_get_item_data.assert_any_call("Item 1")
    mock_get_item_data.assert_any_call("Item 2")

    assert mock_find_flips.call_count == 2
    mock_find_flips.assert_any_call("Item 1", mock_item_data_1['current_sell_offers'], mock_item_data_1['current_buy_orders'])
    mock_find_flips.assert_any_call("Item 2", mock_item_data_2['current_sell_offers'], mock_item_data_2['current_buy_orders'])

    assert mock_find_snipes.call_count == 2
    mock_find_snipes.assert_any_call("Item 1", mock_item_data_1['current_sell_offers'], mock_item_data_1['historical_prices'])
    mock_find_snipes.assert_any_call("Item 2", mock_item_data_2['current_sell_offers'], mock_item_data_2['historical_prices'])

    # Verificar que las nuevas estrategias también se llamaron
    assert mock_find_attr.call_count == 2
    assert mock_find_trade.call_count == 2
    assert mock_find_vol.call_count == 2

    # time.sleep solo se llama entre ítems, no después del último
    assert mock_time_sleep.call_count == len(items_to_scan) - 1
    mock_time_sleep.assert_called_with(engine.config["delay_between_items_sec"])

    assert len(results["basic_flips"]) == 1
    assert results["basic_flips"][0] == expected_flip_op_item1
    assert len(results["snipes"]) == 1
    assert results["snipes"][0] == expected_snipe_op_item1
    
    # Verificar que las nuevas estrategias están en los resultados
    assert "attribute_flips" in results
    assert "trade_lock_arbitrage" in results
    assert "volatility_trading" in results


def test_run_strategies_no_items(default_strategy_engine: StrategyEngine, caplog):
    """Prueba run_strategies con una lista vacía de ítems."""
    # Configurar el mock para que las tasas fallen
    default_strategy_engine.connector.get_fee_rates.return_value = {"error": "No fees"}
    
    with caplog.at_level(logging.ERROR):
        results = default_strategy_engine.run_strategies([])
    assert results["basic_flips"] == []
    assert results["snipes"] == []
    assert "No se pudieron cargar las tasas de comisión" in caplog.text

def test_run_strategies_fee_fetch_fails_globally(
    default_strategy_engine: StrategyEngine, 
    mock_dmarket_connector: MagicMock,
    caplog
):
    """Prueba que si el _fetch_and_cache_fee_info inicial falla, se loguea un error."""
    engine = default_strategy_engine
    with patch.object(engine, '_fetch_and_cache_fee_info', return_value=False) as mock_initial_fetch_fees:
        with caplog.at_level(logging.ERROR):
            engine.run_strategies(["Item 1"]) 
    
    mock_initial_fetch_fees.assert_called_once()
    assert "No se pudieron cargar las tasas de comisión" in caplog.text

# Fin de las pruebas para StrategyEngine por ahora.

class TestStrategyEngine:
    """Pruebas unitarias para StrategyEngine."""

    def setup_method(self):
        """Configuración para cada prueba."""
        self.mock_connector = MagicMock()
        self.mock_analyzer = MagicMock()
        self.mock_volatility_analyzer = MagicMock()
        self.engine = StrategyEngine(self.mock_connector, self.mock_analyzer)
        # Reemplazar el volatility_analyzer real con nuestro mock
        self.engine.volatility_analyzer = self.mock_volatility_analyzer

    def test_init_default_config(self):
        """Prueba la inicialización con configuración por defecto."""
        engine = StrategyEngine(MagicMock(), MagicMock())
        assert engine.config is not None
        assert "min_profit_usd_basic_flip" in engine.config
        assert "min_profit_usd_attribute_flip" in engine.config
        assert "min_profit_usd_trade_lock" in engine.config

    def test_init_custom_config(self):
        """Prueba la inicialización con configuración personalizada."""
        custom_config = {"min_profit_usd_basic_flip": 2.0}
        engine = StrategyEngine(MagicMock(), MagicMock(), custom_config)
        assert engine.config["min_profit_usd_basic_flip"] == 2.0

    def test_fetch_and_cache_fee_info_success(self):
        """Prueba la obtención exitosa de información de tasas."""
        mock_response = {
            "gameId": "a8db",
            "rates": [{"type": "exchange", "amount": "0.030"}],
            "minCommission": {"currency": "USD", "amount": "0.01"}
        }
        self.mock_connector.get_fee_rates.return_value = mock_response
        
        result = self.engine._fetch_and_cache_fee_info("a8db")
        
        assert result is True
        assert self.engine.dmarket_fee_info == mock_response

    def test_fetch_and_cache_fee_info_failure(self):
        """Prueba el fallo en la obtención de información de tasas."""
        self.mock_connector.get_fee_rates.return_value = {"error": "API Error"}
        
        result = self.engine._fetch_and_cache_fee_info("a8db")
        
        assert result is False
        assert self.engine.dmarket_fee_info is None

    def test_calculate_dmarket_sale_fee_cents(self):
        """Prueba el cálculo de comisión de venta."""
        self.engine.dmarket_fee_info = {
            "rates": [{"type": "exchange", "amount": "0.030"}],
            "minCommission": {"currency": "USD", "amount": "0.01"}
        }
        
        # Precio de $10.00 (1000 centavos) con 3% de comisión = 30 centavos
        fee = self.engine._calculate_dmarket_sale_fee_cents(1000)
        assert fee == 30

    def test_calculate_dmarket_sale_fee_cents_minimum(self):
        """Prueba el cálculo de comisión mínima."""
        self.engine.dmarket_fee_info = {
            "rates": [{"type": "exchange", "amount": "0.030"}],
            "minCommission": {"currency": "USD", "amount": "0.05"}
        }
        
        # Precio de $0.50 (50 centavos) con 3% = 1.5 centavos, pero mínimo es 5 centavos
        fee = self.engine._calculate_dmarket_sale_fee_cents(50)
        assert fee == 5

    def test_find_basic_flips_success(self):
        """Prueba la búsqueda exitosa de flips básicos."""
        # Configurar las tasas de comisión correctamente
        self.engine.dmarket_fee_info = {
            "gameId": "a8db",
            "rates": [{"type": "exchange", "amount": "0.030"}]
        }
        
        sell_offers = [
            {"price": {"USD": "1000"}, "assetId": "asset1"}  # $10.00
        ]
        buy_orders = [
            {"price": {"USD": "1200"}, "offerId": "order1"}  # $12.00
        ]
        
        opportunities = self.engine._find_basic_flips("AK-47 | Redline", sell_offers, buy_orders)
        
        assert len(opportunities) == 1
        assert opportunities[0]["strategy"] == "basic_flip"
        assert opportunities[0]["buy_price_usd"] == 10.0
        assert opportunities[0]["sell_price_usd"] == 12.0

    def test_find_basic_flips_no_profit(self):
        """Prueba cuando no hay beneficio en flips básicos."""
        # Configurar las tasas de comisión correctamente
        self.engine.dmarket_fee_info = {
            "gameId": "a8db",
            "rates": [{"type": "exchange", "amount": "0.030"}]
        }
        
        sell_offers = [
            {"price": {"USD": "1200"}, "assetId": "asset1"}  # $12.00
        ]
        buy_orders = [
            {"price": {"USD": "1000"}, "offerId": "order1"}  # $10.00
        ]
        
        opportunities = self.engine._find_basic_flips("AK-47 | Redline", sell_offers, buy_orders)
        
        assert len(opportunities) == 0

    def test_find_snipes_success(self):
        """Prueba la búsqueda exitosa de snipes."""
        # Configurar las tasas de comisión correctamente
        self.engine.dmarket_fee_info = {
            "gameId": "a8db",
            "rates": [{"type": "exchange", "amount": "0.030"}]
        }
        
        # Mock del market analyzer para retornar PME de $10.00
        self.mock_analyzer.calculate_estimated_market_price.return_value = 10.0
        
        sell_offers = [
            {"price": {"USD": "800"}, "assetId": "asset1"}  # $8.00 (20% descuento)
        ]
        historical_prices = [
            {"price_usd": 10.0, "timestamp": "2023-01-01T00:00:00Z"}
        ]
        
        opportunities = self.engine._find_snipes("AK-47 | Redline", sell_offers, historical_prices)
        
        assert len(opportunities) == 1
        assert opportunities[0]["strategy"] == "snipe"
        assert opportunities[0]["offer_price_usd"] == 8.0

    def test_extract_item_attributes(self):
        """Prueba la extracción de atributos de un ítem."""
        offer = {
            "float": "0.003",
            "paintseed": "661",
            "title": "StatTrak™ AK-47 | Case Hardened (Factory New)",
            "phase": "Phase 2",
            "fade_percentage": "95.5"
        }
        
        attributes = self.engine._extract_item_attributes(offer)
        
        assert attributes["float"] == 0.003
        assert attributes["paintseed"] == 661
        assert attributes["stattrak"] is True
        assert attributes["souvenir"] is False
        assert attributes["phase"] == "Phase 2"
        assert attributes["fade_percentage"] == 95.5

    def test_extract_item_attributes_souvenir(self):
        """Prueba la extracción de atributos de un ítem Souvenir."""
        offer = {
            "title": "Souvenir AK-47 | Safari Mesh (Field-Tested)",
            "pattern": "123"
        }
        
        attributes = self.engine._extract_item_attributes(offer)
        
        assert attributes["pattern"] == 123
        assert attributes["stattrak"] is False
        assert attributes["souvenir"] is True

    def test_extract_trade_lock_info_with_lock(self):
        """Prueba la extracción de información de trade lock."""
        offer = {
            "tradeLock": {
                "daysRemaining": "3"
            }
        }
        
        trade_lock_info = self.engine._extract_trade_lock_info(offer)
        
        assert trade_lock_info["has_trade_lock"] is True
        assert trade_lock_info["days_remaining"] == 3
        assert trade_lock_info["unlock_date"] is not None

    def test_extract_trade_lock_info_no_lock(self):
        """Prueba la extracción cuando no hay trade lock."""
        offer = {
            "title": "AK-47 | Redline (Field-Tested)"
        }
        
        trade_lock_info = self.engine._extract_trade_lock_info(offer)
        
        assert trade_lock_info["has_trade_lock"] is False
        assert trade_lock_info["days_remaining"] == 0
        assert trade_lock_info["unlock_date"] is None

    def test_extract_trade_lock_info_in_title(self):
        """Prueba la detección de trade lock en el título."""
        offer = {
            "title": "AK-47 | Redline (Field-Tested) - Trade Lock"
        }
        
        trade_lock_info = self.engine._extract_trade_lock_info(offer)
        
        assert trade_lock_info["has_trade_lock"] is True

    def test_get_reference_price_no_trade_lock(self):
        """Prueba la obtención de precio de referencia sin trade lock."""
        offers = [
            {"price": {"USD": "1000"}},  # $10.00 - sin trade lock
            {"price": {"USD": "1200"}},  # $12.00 - sin trade lock
            {"price": {"USD": "800"}, "tradeLock": {"daysRemaining": "3"}}  # $8.00 - con trade lock
        ]
        
        reference_price = self.engine._get_reference_price_no_trade_lock("AK-47 | Redline", offers)
        
        # Promedio de $10.00 y $12.00 = $11.00
        assert reference_price == 11.0

    def test_get_reference_price_no_trade_lock_all_locked(self):
        """Prueba cuando todas las ofertas tienen trade lock."""
        offers = [
            {"price": {"USD": "800"}, "tradeLock": {"daysRemaining": "3"}},
            {"price": {"USD": "900"}, "title": "AK-47 | Redline - Trade Lock"}
        ]
        
        reference_price = self.engine._get_reference_price_no_trade_lock("AK-47 | Redline", offers)
        
        assert reference_price is None

    @patch('core.strategy_engine.get_db')
    def test_get_item_data_success(self, mock_get_db):
        """Prueba la obtención exitosa de datos de un ítem."""
        # Mock de la base de datos
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        mock_skin = MagicMock()
        mock_skin.precios = [
            MagicMock(price=10.0, timestamp=datetime.now(), fuente_api="dmarket")
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_skin
        
        # Mock de las respuestas de la API
        self.mock_connector.get_offers_by_title.return_value = {
            "objects": [{"price": {"USD": "1000"}, "assetId": "asset1"}]
        }
        self.mock_connector.get_buy_offers.return_value = {
            "offers": [{"price": {"USD": "1200"}, "offerId": "order1"}]
        }
        
        item_data = self.engine._get_item_data("AK-47 | Redline")
        
        assert item_data is not None
        assert item_data["title"] == "AK-47 | Redline"
        assert len(item_data["current_sell_offers"]) == 1
        assert len(item_data["current_buy_orders"]) == 1
        assert len(item_data["historical_prices"]) == 1

    @patch('core.strategy_engine.get_db')
    def test_get_item_data_api_error(self, mock_get_db):
        """Prueba cuando hay errores en la API."""
        # Mock de la base de datos
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock de respuestas de error de la API
        self.mock_connector.get_offers_by_title.return_value = {"error": "API Error"}
        self.mock_connector.get_buy_offers.return_value = {"error": "API Error"}
        
        item_data = self.engine._get_item_data("AK-47 | Redline")
        
        assert item_data is not None
        assert len(item_data["current_sell_offers"]) == 0
        assert len(item_data["current_buy_orders"]) == 0
        assert len(item_data["historical_prices"]) == 0

    def test_find_attribute_premium_flips_success(self):
        """Prueba la búsqueda exitosa de flips por atributos premium."""
        self.engine.dmarket_fee_info = {
            "rates": [{"type": "exchange", "amount": "0.030"}]
        }
        
        # Mock del market analyzer
        mock_evaluation = AttributeEvaluation(
            float_value=0.003,
            float_rarity=FloatRarity.FACTORY_NEW,
            pattern_index=661,
            pattern_rarity=AttributeRarity.EXTREMELY_RARE,
            stickers_value=50000.0,
            stickers_rarity=AttributeRarity.EXTREMELY_RARE,
            stattrak=True,
            souvenir=False,
            overall_rarity_score=95.0,
            premium_multiplier=8.0,
            special_attributes={}
        )
        self.mock_analyzer.evaluate_attribute_rarity.return_value = mock_evaluation
        
        item_data = {
            "title": "AK-47 | Case Hardened",
            "current_sell_offers": [
                {
                    "price": {"USD": "5000"},  # $50.00
                    "assetId": "asset1",
                    "float": "0.003",
                    "paintseed": "661",
                    "stickers": [{"name": "iBUYPOWER (Holo)"}]
                }
            ],
            "historical_prices": [{"price_usd": 100.0}]
        }
        
        # Mock del precio base estimado
        self.mock_analyzer.calculate_estimated_market_price.return_value = 100.0
        
        opportunities = self.engine._find_attribute_premium_flips(
            item_data, self.engine.dmarket_fee_info, self.mock_analyzer
        )
        
        assert len(opportunities) == 1
        assert opportunities[0]["strategy"] == "attribute_premium_flip"
        assert opportunities[0]["buy_price_usd"] == 50.0
        assert opportunities[0]["rarity_score"] == 95.0
        assert opportunities[0]["premium_multiplier"] == 8.0

    def test_find_attribute_premium_flips_low_rarity(self):
        """Prueba cuando los atributos no son lo suficientemente raros."""
        mock_evaluation = AttributeEvaluation(
            float_value=0.25,
            float_rarity=FloatRarity.FIELD_TESTED,
            pattern_index=500,
            pattern_rarity=AttributeRarity.COMMON,
            stickers_value=0.0,
            stickers_rarity=AttributeRarity.COMMON,
            stattrak=False,
            souvenir=False,
            overall_rarity_score=10.0,  # Muy bajo
            premium_multiplier=1.0,     # Muy bajo
            special_attributes={}
        )
        self.mock_analyzer.evaluate_attribute_rarity.return_value = mock_evaluation
        
        item_data = {
            "title": "AK-47 | Redline",
            "current_sell_offers": [
                {
                    "price": {"USD": "1000"},
                    "assetId": "asset1",
                    "float": "0.25"
                }
            ]
        }
        
        opportunities = self.engine._find_attribute_premium_flips(
            item_data, {}, self.mock_analyzer
        )
        
        assert len(opportunities) == 0

    def test_find_trade_lock_opportunities_success(self):
        """Prueba la búsqueda exitosa de oportunidades de trade lock."""
        self.engine.dmarket_fee_info = {
            "rates": [{"type": "exchange", "amount": "0.030"}]
        }
        
        item_data = {
            "title": "AK-47 | Redline",
            "current_sell_offers": [
                {"price": {"USD": "1000"}},  # $10.00 - sin trade lock
                {"price": {"USD": "1200"}},  # $12.00 - sin trade lock
                {
                    "price": {"USD": "700"},  # $7.00 - con trade lock (36% descuento)
                    "assetId": "asset1",
                    "tradeLock": {"daysRemaining": "3"}
                }
            ]
        }
        
        opportunities = self.engine._find_trade_lock_opportunities(
            item_data, self.engine.dmarket_fee_info
        )
        
        assert len(opportunities) == 1
        assert opportunities[0]["strategy"] == "trade_lock_arbitrage"
        assert opportunities[0]["buy_price_usd"] == 7.0
        assert opportunities[0]["reference_price_usd"] == 11.0  # Promedio de 10 y 12
        assert opportunities[0]["trade_lock_days"] == 3

    def test_find_trade_lock_opportunities_insufficient_discount(self):
        """Prueba cuando el descuento no es suficiente."""
        item_data = {
            "title": "AK-47 | Redline",
            "current_sell_offers": [
                {"price": {"USD": "1000"}},  # $10.00 - sin trade lock
                {
                    "price": {"USD": "900"},  # $9.00 - solo 10% descuento
                    "assetId": "asset1",
                    "tradeLock": {"daysRemaining": "3"}
                }
            ]
        }
        
        opportunities = self.engine._find_trade_lock_opportunities(item_data, {})
        
        assert len(opportunities) == 0

    def test_find_trade_lock_opportunities_too_long_lock(self):
        """Prueba cuando el bloqueo es demasiado largo."""
        # Mock del market analyzer para evaluar atributos
        mock_evaluation = MagicMock()
        mock_evaluation.overall_rarity_score = 60.0
        mock_evaluation.premium_multiplier = 1.8
        self.mock_analyzer.evaluate_attribute_rarity.return_value = mock_evaluation
        
        item_data = {
            'title': 'Test Item',
            'current_sell_offers': [
                {
                    'price': {'USD': '10000'},  # $100.00
                    'assetId': 'asset1',
                    'tradeLock': {'daysRemaining': '10'}  # Más de 7 días
                }
            ]
        }
        
        fee_info = {"rates": [{"type": "exchange", "amount": "0.030"}]}
        
        opportunities = self.engine._find_trade_lock_opportunities(item_data, fee_info)
        
        assert len(opportunities) == 0

    def test_find_volatility_opportunities_success(self):
        """Prueba la búsqueda exitosa de oportunidades de volatilidad."""
        # Mock del volatility analyzer
        mock_signal = MagicMock()
        mock_signal.signal_type = "rsi_oversold_buy"
        mock_signal.entry_price = 100.0
        mock_signal.target_price = 106.0
        mock_signal.stop_loss = 97.0
        mock_signal.expected_profit = 6.0
        mock_signal.confidence = 0.8
        mock_signal.strength.value = "strong"
        mock_signal.risk_reward_ratio = 2.0
        mock_signal.reasoning = "RSI oversold signal"
        mock_signal.timestamp.isoformat.return_value = "2023-01-01T12:00:00"
        mock_signal.indicators.rsi = 25.0
        mock_signal.indicators.bollinger_upper = 110.0
        mock_signal.indicators.bollinger_lower = 90.0
        mock_signal.indicators.bollinger_width = 20.0
        mock_signal.indicators.moving_average_short = 105.0
        mock_signal.indicators.moving_average_long = 100.0
        mock_signal.indicators.volatility_score = 15.0
        mock_signal.indicators.price_change_24h = 5.0
        mock_signal.indicators.price_change_7d = 10.0
        
        self.mock_volatility_analyzer.identify_volatility_opportunities.return_value = [mock_signal]
        
        # Configurar las tasas de comisión
        self.engine.dmarket_fee_info = {
            "gameId": "a8db",
            "rates": [{"type": "exchange", "amount": "0.030"}]
        }
        
        item_data = {
            'title': 'Test Item',
            'historical_prices': [
                {"price_usd": 100.0, "timestamp": "2023-01-01T00:00:00Z"},
                {"price_usd": 105.0, "timestamp": "2023-01-02T00:00:00Z"}
            ] * 10,  # Suficientes datos históricos
            'current_sell_offers': [
                {"price": {"USD": "10000"}, "assetId": "asset1"}  # $100.00
            ]
        }
        
        opportunities = self.engine._find_volatility_opportunities(item_data)
        
        assert len(opportunities) == 1
        op = opportunities[0]
        assert op["strategy"] == "volatility_trading"
        assert op["signal_type"] == "rsi_oversold_buy"
        assert op["entry_price_usd"] == 100.0
        assert op["target_price_usd"] == 106.0
        assert op["confidence"] == 0.8

    def test_find_volatility_opportunities_insufficient_historical_data(self):
        """Prueba cuando no hay suficientes datos históricos."""
        item_data = {
            'title': 'Test Item',
            'historical_prices': [
                {"price_usd": 100.0, "timestamp": "2023-01-01T00:00:00Z"}
            ],  # Insuficientes datos
            'current_sell_offers': [
                {"price": {"USD": "10000"}, "assetId": "asset1"}
            ]
        }
        
        opportunities = self.engine._find_volatility_opportunities(item_data)
        
        assert len(opportunities) == 0

    def test_find_volatility_opportunities_no_current_offers(self):
        """Prueba cuando no hay ofertas actuales."""
        item_data = {
            'title': 'Test Item',
            'historical_prices': [
                {"price_usd": 100.0, "timestamp": "2023-01-01T00:00:00Z"}
            ] * 15,  # Suficientes datos históricos
            'current_sell_offers': []  # Sin ofertas actuales
        }
        
        opportunities = self.engine._find_volatility_opportunities(item_data)
        
        assert len(opportunities) == 0

    def test_find_volatility_opportunities_price_too_high(self):
        """Prueba cuando el precio excede el límite para volatilidad."""
        item_data = {
            'title': 'Test Item',
            'historical_prices': [
                {"price_usd": 100.0, "timestamp": "2023-01-01T00:00:00Z"}
            ] * 15,
            'current_sell_offers': [
                {"price": {"USD": "150000"}, "assetId": "asset1"}  # $1500.00 - muy alto
            ]
        }
        
        opportunities = self.engine._find_volatility_opportunities(item_data)
        
        assert len(opportunities) == 0

    def test_find_volatility_opportunities_low_confidence(self):
        """Prueba cuando la confianza de la señal es muy baja."""
        # Mock del volatility analyzer con baja confianza
        mock_signal = MagicMock()
        mock_signal.confidence = 0.5  # Menor que min_confidence_volatility (0.7)
        mock_signal.expected_profit = 5.0
        
        self.mock_volatility_analyzer.identify_volatility_opportunities.return_value = [mock_signal]
        
        item_data = {
            'title': 'Test Item',
            'historical_prices': [{"price_usd": 100.0, "timestamp": "2023-01-01T00:00:00Z"}] * 15,
            'current_sell_offers': [{"price": {"USD": "10000"}, "assetId": "asset1"}]
        }
        
        opportunities = self.engine._find_volatility_opportunities(item_data)
        
        assert len(opportunities) == 0

    def test_find_volatility_opportunities_low_profit(self):
        """Prueba cuando el beneficio esperado es muy bajo."""
        # Mock del volatility analyzer con bajo beneficio
        mock_signal = MagicMock()
        mock_signal.confidence = 0.8
        mock_signal.expected_profit = 0.5  # Menor que min_profit_usd_volatility (1.50)
        
        self.mock_volatility_analyzer.identify_volatility_opportunities.return_value = [mock_signal]
        
        item_data = {
            'title': 'Test Item',
            'historical_prices': [{"price_usd": 100.0, "timestamp": "2023-01-01T00:00:00Z"}] * 15,
            'current_sell_offers': [{"price": {"USD": "10000"}, "assetId": "asset1"}]
        }
        
        opportunities = self.engine._find_volatility_opportunities(item_data)
        
        assert len(opportunities) == 0

    @patch.object(StrategyEngine, '_get_item_data')
    @patch.object(StrategyEngine, '_fetch_and_cache_fee_info')
    def test_run_strategies_with_volatility_success(self, mock_fetch_fees, mock_get_item_data):
        """Prueba la ejecución exitosa de estrategias incluyendo volatilidad."""
        mock_fetch_fees.return_value = True
        
        # Mock de datos del ítem
        mock_item_data = {
            'title': 'Test Item',
            'current_sell_offers': [{"price": {"USD": "10000"}, "assetId": "asset1"}],
            'current_buy_orders': [{"price": {"USD": "12000"}, "offerId": "order1"}],
            'historical_prices': [{"price_usd": 100.0, "timestamp": "2023-01-01T00:00:00Z"}] * 15
        }
        mock_get_item_data.return_value = mock_item_data
        
        # Mock de señal de volatilidad
        mock_signal = MagicMock()
        mock_signal.signal_type = "rsi_oversold_buy"
        mock_signal.entry_price = 100.0
        mock_signal.target_price = 106.0
        mock_signal.stop_loss = 97.0
        mock_signal.expected_profit = 6.0
        mock_signal.confidence = 0.8
        mock_signal.strength.value = "strong"
        mock_signal.risk_reward_ratio = 2.0
        mock_signal.reasoning = "RSI oversold signal"
        mock_signal.timestamp.isoformat.return_value = "2023-01-01T12:00:00"
        mock_signal.indicators.rsi = 25.0
        mock_signal.indicators.bollinger_upper = 110.0
        mock_signal.indicators.bollinger_lower = 90.0
        mock_signal.indicators.bollinger_width = 20.0
        mock_signal.indicators.moving_average_short = 105.0
        mock_signal.indicators.moving_average_long = 100.0
        mock_signal.indicators.volatility_score = 15.0
        mock_signal.indicators.price_change_24h = 5.0
        mock_signal.indicators.price_change_7d = 10.0
        
        self.mock_volatility_analyzer.identify_volatility_opportunities.return_value = [mock_signal]
        
        # Configurar las tasas de comisión
        self.engine.dmarket_fee_info = {
            "gameId": "a8db",
            "rates": [{"type": "exchange", "amount": "0.030"}]
        }
        
        # Configurar el mock del market analyzer para evitar errores
        self.mock_analyzer.calculate_estimated_market_price.return_value = None
        self.mock_analyzer.evaluate_attribute_rarity.return_value = MagicMock(overall_rarity_score=30.0, premium_multiplier=1.0)
        
        results = self.engine.run_strategies(["Test Item"])
        
        assert "volatility_trading" in results
        assert len(results["volatility_trading"]) == 1
        
        volatility_op = results["volatility_trading"][0]
        assert volatility_op["strategy"] == "volatility_trading"
        assert volatility_op["signal_type"] == "rsi_oversold_buy"
        assert volatility_op["confidence"] == 0.8