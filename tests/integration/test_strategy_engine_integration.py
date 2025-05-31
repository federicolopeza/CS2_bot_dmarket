# tests/integration/test_strategy_engine_integration.py
import pytest
import os
import sys
import logging
import time
from unittest.mock import patch, MagicMock

# Añadir el directorio raíz del proyecto a sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession

from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer
from core.strategy_engine import StrategyEngine, DEFAULT_GAME_ID
from core.data_manager import Base, init_db, get_db, SkinsMaestra, PreciosHistoricos
from utils.helpers import normalize_skin_name

# Configurar logger para pruebas si es necesario ver la salida
# from utils.logger import configure_logging
# configure_logging(log_level=logging.DEBUG) # O DEBUG para más detalle

# --- Configuración de Base de Datos de Prueba ---
TEST_DATABASE_URL = "sqlite:///:memory:" # Base de datos en memoria para pruebas

@pytest.fixture(scope="function") # Usar "function" para recrear BD para cada test
def db_session() -> SQLAlchemySession:
    """Crea una sesión de base de datos de prueba en memoria para cada test."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine) # Crear tablas
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Sobrescribir get_db para que use esta sesión de prueba
    # Esto es un poco más complejo que un simple override,
    # necesitamos asegurar que StrategyEngine (y cualquier otro módulo que use get_db)
    # obtenga esta sesión. Haremos esto con un patch en los tests.
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine) # Limpiar tablas después del test

# --- Fixtures para Componentes ---

@pytest.fixture(scope="function")
def mock_dmarket_api_responses():
    """
    Fixture para mockear las respuestas de requests.get/post dentro de DMarketAPI.
    Se usa con patch('core.dmarket_connector.requests').
    Permite definir side_effect para diferentes URLs.
    """
    # Este es un contenedor para los mocks, se configurará en cada test.
    # El mock real se aplicará con @patch en cada función de prueba que lo necesite.
    # Ejemplo de uso:
    #   @patch('core.dmarket_connector.requests')
    #   def test_something(mock_requests, mock_dmarket_api_responses_config_func, db_session, ...):
    #       mock_dmarket_api_responses_config_func(mock_requests, {"/fee-rates/": {"json_data": ...}})
    #       ...
    # Lo haremos más simple por ahora, mockeando los métodos del conector directamente
    # que hacen las llamadas de red, en lugar de 'requests' globalmente.
    pass # Placeholder, el mock se hará en los tests o fixtures específicas


@pytest.fixture(scope="function")
def dmarket_connector() -> DMarketAPI:
    """
    Instancia real de DMarketAPI. Las llamadas de red subyacentes
    (get_fee_rates, get_offers_by_title, etc.) serán mockeadas
    individualmente en cada test o en una fixture de configuración de escenario.
    """
    # Las claves son necesarias para la instanciación, pero no se usarán si mockeamos los métodos.
    return DMarketAPI(public_key="test_public_key", secret_key="a"*128)

@pytest.fixture(scope="function")
def market_analyzer() -> MarketAnalyzer:
    """Instancia real de MarketAnalyzer."""
    return MarketAnalyzer()

@pytest.fixture(scope="function")
def strategy_engine(
    dmarket_connector: DMarketAPI, 
    market_analyzer: MarketAnalyzer, 
    db_session: SQLAlchemySession # Para asegurar que la BD está lista
) -> StrategyEngine:
    """
    Instancia real de StrategyEngine.
    Usará el db_session de prueba a través de un patch en get_db.
    """
    # La configuración puede ser la por defecto o personalizada por test.
    config = {
        "game_id": DEFAULT_GAME_ID,
        "currency": "USD",
        "min_profit_usd_basic_flip": 0.10, # Umbrales bajos para facilitar pruebas
        "min_profit_percentage_basic_flip": 0.01, # 1%
        "min_price_usd_for_sniping": 0.50,
        "snipe_discount_percentage": 0.10, # 10%
        "delay_between_items_sec": 0.01 # Delay muy corto para pruebas
    }
    engine = StrategyEngine(
        dmarket_connector=dmarket_connector,
        market_analyzer=market_analyzer,
        config=config
    )
    return engine

# --- Funciones Auxiliares para Pruebas ---

def populate_db_with_items(session: SQLAlchemySession, items_data: list):
    """
    Puebla la base de datos con SkinsMaestra y PreciosHistoricos.
    items_data = [{
        "market_hash_name": "Item 1", 
        "historical_prices": [
            {"price_usd": 10.0, "timestamp": time.time() - 86400, "fuente_api": "DMarket"},
            {"price_usd": 10.5, "timestamp": time.time() - 3600, "fuente_api": "DMarket"}
        ]
    }, ...]
    """
    for item_info in items_data:
        skin_name_normalized = normalize_skin_name(item_info["market_hash_name"])
        skin = session.query(SkinsMaestra).filter_by(market_hash_name=skin_name_normalized).first()
        if not skin:
            skin = SkinsMaestra(
                market_hash_name=skin_name_normalized,
                game_id=DEFAULT_GAME_ID # Asumimos CS2 por ahora
            )
            session.add(skin)
            session.flush() # Para obtener skin.id si es necesario

        for price_data in item_info.get("historical_prices", []):
            # Convertir timestamp de Python (float) a objeto datetime si es necesario para el modelo
            # El modelo PreciosHistoricos espera un objeto datetime.
            # En data_manager, se usa datetime.fromtimestamp(price_data["timestamp"]).
            # Aquí, si viene como float, lo convertimos. Si ya es datetime, bien.
            from datetime import datetime # Import local para esta función
            ts = price_data["timestamp"]
            dt_object = datetime.fromtimestamp(ts) if isinstance(ts, (int, float)) else ts

            price_record = PreciosHistoricos(
                skin_id=skin.id,
                price=price_data["price_usd"],  # Changed price_usd to price
                timestamp=dt_object,
                fuente_api=price_data["fuente_api"]
            )
            session.add(price_record)
    session.commit()


# --- Tests de Integración ---

# Ejemplo de cómo se podría usar patch para get_db:
# @patch('core.strategy_engine.get_db') 
# def test_example_with_patched_get_db(mock_get_db_strategy_engine, db_session, strategy_engine, ...):
#     mock_get_db_strategy_engine.return_value = iter([db_session])
#
#     # ... resto del test ...
#
# Este patch debe aplicarse donde get_db es llamado, que es DENTRO de StrategyEngine.run_strategies.


# Escenario 1: Flip Básico Válido
@patch('core.strategy_engine.get_db') # Patch get_db usado por StrategyEngine
def test_integration_valid_basic_flip(
    mock_get_db_in_strategy_engine: MagicMock,
    db_session: SQLAlchemySession, 
    strategy_engine: StrategyEngine, 
    dmarket_connector: DMarketAPI # Para mockear sus métodos
):
    mock_get_db_in_strategy_engine.return_value = iter([db_session]) # Hacer que StrategyEngine use la sesión de prueba

    item_title = "AK-47 | Redline (Field-Tested)"
    
    # 1. Poblar BD (no necesario para flip básico puro si no se usa PME para LSO/HBO)
    # populate_db_with_items(db_session, [{"market_hash_name": item_title, "historical_prices": []}])

    # 2. Mockear respuestas del DMarketConnector
    #    - get_fee_rates: 5% fee, min $0.01
    #    - get_offers_by_title (LSO): $10.00
    #    - get_buy_offers (HBO): $12.00
    
    mock_fee_response = {
        "gameId": DEFAULT_GAME_ID, 
        "rates": [{"type": "exchange", "amount": "0.05"}], 
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }
    # Usamos patch.object para mockear métodos de la instancia del conector
    with patch.object(dmarket_connector, 'get_fee_rates', return_value=mock_fee_response) as mock_get_fees, \
         patch.object(dmarket_connector, 'get_offers_by_title', return_value={
             "objects": [{"assetId": "lso123", "price": {"USD": "1000"}}], # $10.00
             "cursor": ""
         }) as mock_get_lso, \
         patch.object(dmarket_connector, 'get_buy_offers', return_value={
             "offers": [{"offerId": "hbo456", "price": {"USD": "1200"}}], # $12.00
             "cursor": ""
         }) as mock_get_hbo:

        # 3. Ejecutar strategy_engine
        # Profit esperado: (12.00 - 10.00) - (12.00 * 0.05) = 2.00 - 0.60 = 1.40 USD
        # Umbrales: profit_usd >= 0.10, profit_percentage >= 0.01 (1%)
        # 1.40 / 10.00 = 14%
        # Debería encontrar la oportunidad.
        
        opportunities = strategy_engine.run_strategies([item_title])

        # 4. Verificaciones
        mock_get_fees.assert_called_once_with(game_id=DEFAULT_GAME_ID)
        mock_get_lso.assert_called_once_with(title=item_title, limit=100, currency="USD")
        mock_get_hbo.assert_called_once_with(title=item_title, game_id=DEFAULT_GAME_ID, limit=100, order_by="price", order_dir="desc", currency="USD")
        
        assert len(opportunities["basic_flips"]) == 1
        assert len(opportunities["snipes"]) == 0
        
        flip_op = opportunities["basic_flips"][0]
        assert flip_op["item_title"] == item_title
        assert flip_op["buy_price_usd"] == pytest.approx(10.00)
        assert flip_op["sell_price_usd"] == pytest.approx(12.00)
        assert flip_op["commission_usd"] == pytest.approx(0.60)
        assert flip_op["profit_usd"] == pytest.approx(1.40)
        assert flip_op["profit_percentage"] == pytest.approx(0.14)

# Escenario 2: Snipe Válido
@patch('core.strategy_engine.get_db')
@patch('core.dmarket_connector.DMarketAPI.get_fee_rates') # Mockear a nivel de clase/método si es más limpio
def test_integration_valid_snipe(
    mock_get_fee_rates: MagicMock, # Este mock viene de @patch a nivel de DMarketAPI
    mock_get_db_in_strategy_engine: MagicMock,
    db_session: SQLAlchemySession, 
    strategy_engine: StrategyEngine, 
    dmarket_connector: DMarketAPI,
    market_analyzer: MarketAnalyzer # MarketAnalyzer es real
):
    mock_get_db_in_strategy_engine.return_value = iter([db_session])

    item_title_snipe = "M4A1-S | Hyper Beast (Factory New)"
    pme_usd = 25.00 # PME esperado para este ítem

    # 1. Poblar BD con datos históricos que resulten en el PME esperado.
    #    MarketAnalyzer.calculate_estimated_market_price usa un promedio simple por ahora.
    #    Para PME=25, podemos usar precios históricos alrededor de 25.
    historical_data_for_snipe_item = [
        {"market_hash_name": item_title_snipe, "historical_prices": [
            {"price_usd": 24.50, "timestamp": time.time() - 86400 * 2, "fuente_api": "DMarket"},
            {"price_usd": 25.00, "timestamp": time.time() - 86400 * 1, "fuente_api": "DMarket"},
            {"price_usd": 25.50, "timestamp": time.time() - 3600, "fuente_api": "DMarket"}
        ]}
    ]
    populate_db_with_items(db_session, historical_data_for_snipe_item)
    
    # 2. Mockear respuestas del DMarketConnector
    #    - get_fee_rates: 5% fee, min $0.01 (configurado por el mock_get_fee_rates)
    #    - get_offers_by_title (oferta de snipe): $20.00 (PME es $25.00)
    #    - get_buy_offers (órdenes de compra, no críticas para snipe pero se llaman)

    mock_get_fee_rates.return_value = {
        "gameId": DEFAULT_GAME_ID, 
        "rates": [{"type": "exchange", "amount": "0.05"}], 
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }
    
    # Oferta de snipe: 20 USD. PME: 25 USD. Descuento: (25-20)/25 = 0.20 (20%)
    # Umbral de descuento de la config del engine: 0.10 (10%). Pasa.
    # Precio de oferta: 20 USD. Umbral de precio min snipe: 0.50 USD. Pasa.
    # Profit si se revende a PME: 25.00 (PME) - 20.00 (compra) - (25.00 * 0.05) (comisión) 
    # = 5.00 - 1.25 = 3.75 USD. Profit > 0. Pasa.
    
    with patch.object(dmarket_connector, 'get_offers_by_title', return_value={
             "objects": [{"assetId": "snipe123", "price": {"USD": "2000"}}], # $20.00
             "cursor": ""
         }) as mock_get_sell_offers, \
         patch.object(dmarket_connector, 'get_buy_offers', return_value={
             "offers": [], # No se necesitan HBOs para el snipe
             "cursor": ""
         }) as mock_get_buy_orders:

        # 3. Ejecutar strategy_engine
        opportunities = strategy_engine.run_strategies([item_title_snipe])

        # 4. Verificaciones
        mock_get_fee_rates.assert_called_once_with(game_id=DEFAULT_GAME_ID)
        mock_get_sell_offers.assert_called_once_with(title=item_title_snipe, limit=100, currency="USD")
        mock_get_buy_orders.assert_called_once_with(title=item_title_snipe, game_id=DEFAULT_GAME_ID, limit=100, order_by="price", order_dir="desc", currency="USD")
        
        assert len(opportunities["basic_flips"]) == 0
        assert len(opportunities["snipes"]) == 1
        
        snipe_op = opportunities["snipes"][0]
        assert snipe_op["item_title"] == item_title_snipe
        assert snipe_op["pme_usd"] == pytest.approx(pme_usd) # MarketAnalyzer debería calcular esto
        assert snipe_op["offer_price_usd"] == pytest.approx(20.00)
        assert snipe_op["discount_percentage"] == pytest.approx(0.20)
        assert snipe_op["commission_on_pme_usd"] == pytest.approx(1.25) # 5% de 25.00
        assert snipe_op["potential_profit_usd"] == pytest.approx(3.75)

# Escenario 3: Sin Oportunidades
@patch('core.strategy_engine.get_db')
@patch('core.dmarket_connector.DMarketAPI.get_fee_rates')
def test_integration_no_opportunities_found(
    mock_get_fee_rates: MagicMock,
    mock_get_db_in_strategy_engine: MagicMock,
    db_session: SQLAlchemySession, 
    strategy_engine: StrategyEngine, 
    dmarket_connector: DMarketAPI
):
    mock_get_db_in_strategy_engine.return_value = iter([db_session])
    item_title_no_ops = "Glock-18 | Water Elemental (Minimal Wear)"
    pme_usd_no_ops = 15.00 # PME de referencia

    # 1. Poblar BD (opcional, pero bueno para que PME sea calculable)
    historical_data_no_ops = [
        {"market_hash_name": item_title_no_ops, "historical_prices": [
            {"price_usd": 14.80, "timestamp": time.time() - 86400, "fuente_api": "DMarket"},
            {"price_usd": 15.20, "timestamp": time.time() - 3600, "fuente_api": "DMarket"}
        ]}
    ]
    populate_db_with_items(db_session, historical_data_no_ops)

    # 2. Mockear respuestas del DMarketConnector
    mock_get_fee_rates.return_value = {
        "gameId": DEFAULT_GAME_ID, 
        "rates": [{"type": "exchange", "amount": "0.05"}], 
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }

    #   - Para Flip: LSO = $14.00, HBO = $14.50. Profit = (14.50-14.00) - (14.50*0.05) = 0.50 - 0.725 = -0.225 (No)
    #   - Para Snipe: Oferta LSO = $14.00. PME = $15.00. Descuento = (15-14)/15 = 1/15 = ~6.6%. Umbral 10% (No)
    
    with patch.object(dmarket_connector, 'get_offers_by_title', return_value={
             "objects": [{"assetId": "lso789", "price": {"USD": "1400"}}], # $14.00
             "cursor": ""
         }) as mock_get_sell_offers, \
         patch.object(dmarket_connector, 'get_buy_offers', return_value={
             "offers": [{"offerId": "hbo101", "price": {"USD": "1450"}}], # $14.50
             "cursor": ""
         }) as mock_get_buy_orders:

        # 3. Ejecutar strategy_engine
        opportunities = strategy_engine.run_strategies([item_title_no_ops])

        # 4. Verificaciones
        mock_get_fee_rates.assert_called_once_with(game_id=DEFAULT_GAME_ID)
        mock_get_sell_offers.assert_called_once_with(title=item_title_no_ops, limit=100, currency="USD")
        mock_get_buy_orders.assert_called_once_with(title=item_title_no_ops, game_id=DEFAULT_GAME_ID, limit=100, order_by="price", order_dir="desc", currency="USD")
        
        assert len(opportunities["basic_flips"]) == 0, f"Se encontraron flips inesperados: {opportunities['basic_flips']}"
        assert len(opportunities["snipes"]) == 0, f"Se encontraron snipes inesperados: {opportunities['snipes']}"

# Más escenarios seguirán...
# Escenario 4: Datos Incompletos de DMarket
@patch('core.strategy_engine.get_db')
@patch('core.dmarket_connector.DMarketAPI.get_fee_rates')
def test_integration_incomplete_dmarket_data(
    mock_get_fee_rates: MagicMock,
    mock_get_db_in_strategy_engine: MagicMock,
    db_session: SQLAlchemySession,
    strategy_engine: StrategyEngine,
    dmarket_connector: DMarketAPI
):
    mock_get_db_in_strategy_engine.return_value = iter([db_session])

    item_ok = "AK-47 | Redline (Field-Tested)"  # Debería procesarse bien
    item_bad_lso = "P250 | Sand Dune (Factory New)"  # Simulará LSO vacío
    item_bad_hbo = "UMP-45 | Corporal (Minimal Wear)"  # Simulará HBO vacío
    # Item con error simulado en LSO (ej. DMarket devuelve error 500)
    item_error_lso = "Five-SeveN | Case Hardened (Well-Worn)"

    all_items_to_check = [item_ok, item_bad_lso, item_bad_hbo, item_error_lso]

    # 1. Poblar BD (solo para el item_ok, para que tenga una oportunidad de flip)
    # No se necesita PME para este test, así que historical_prices puede estar vacío.
    populate_db_with_items(db_session, [{
        "market_hash_name": item_ok,
        "historical_prices": []
    }])

    # 2. Mockear respuestas del DMarketConnector
    mock_get_fee_rates.return_value = {
        "gameId": DEFAULT_GAME_ID,
        "rates": [{"type": "exchange", "amount": "0.05"}],
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }

    # Usaremos un logger para capturar advertencias o errores
    # Esto es útil para verificar que el sistema maneja errores de API grácilmente
    # y loguea la información apropiada.
    # Necesitaríamos configurar el logger de strategy_engine para que escriba a un buffer
    # o usar caplog de pytest.
    # Por simplicidad, aquí nos enfocaremos en que no crashee y procese otros items.

    def mock_lso_logic(title, limit, currency):
        if title == item_ok:
            return {"objects": [{"assetId": "lso_ok", "price": {"USD": "1000"}}], "cursor": ""}  # $10.00
        elif title == item_bad_lso:
            return {"objects": [], "cursor": ""}  # LSO vacío
        elif title == item_error_lso:
            # Simular un error de la API de DMarket para get_offers_by_title
            # DMarketAPI podría lanzar una excepción específica o devolver None/dict vacío con error
            # Asumamos que DMarketAPI.get_offers_by_title devuelve None en caso de error de red/API
            # y loguea el error internamente.
            # O, si DMarketAPI propaga la excepción, StrategyEngine debería capturarla.
            # Para este test, vamos a hacer que devuelva None, y StrategyEngine debería manejarlo.
            return None
        # Para item_bad_hbo, LSO es normal
        return {"objects": [{"assetId": f"lso_{title.replace(' ', '_')}", "price": {"USD": "500"}}], "cursor": ""}

    def mock_hbo_logic(title, game_id, limit, order_by, order_dir, currency):
        if title == item_ok:
            return {"offers": [{"offerId": "hbo_ok", "price": {"USD": "1200"}}], "cursor": ""}  # $12.00
        elif title == item_bad_hbo:
            return {"offers": [], "cursor": ""}  # HBO vacío
        # Para item_bad_lso y item_error_lso, HBO es normal
        return {"offers": [{"offerId": f"hbo_{title.replace(' ', '_')}", "price": {"USD": "600"}}], "cursor": ""}


    with patch.object(dmarket_connector, 'get_offers_by_title', side_effect=mock_lso_logic) as mock_lso, \
         patch.object(dmarket_connector, 'get_buy_offers', side_effect=mock_hbo_logic) as mock_hbo:

        # 3. Ejecutar strategy_engine
        # Esperamos que no crashee y que procese los items que pueda.
        opportunities = strategy_engine.run_strategies(all_items_to_check)

        # 4. Verificaciones
        # Fees se llama para cada item donde LSO y HBO son obtenibles (incluso si vacíos)
        # y no hay error previo en la obtención de datos de DMarket.
        # item_ok: LSO ok, HBO ok -> fees llamado
        # item_bad_lso: LSO vacío, HBO ok -> fees llamado
        # item_bad_hbo: LSO ok, HBO vacío -> fees llamado
        # item_error_lso: LSO error (None) -> no se debería llamar a fees para este item, ni a HBO.
        # Fees are fetched once at the beginning if not cached.
        assert mock_get_fee_rates.call_count == 1

        assert mock_lso.call_count == len(all_items_to_check)
        # item_error_lso: LSO error (None), pero HBO se llama igualmente.
        assert mock_hbo.call_count == len(all_items_to_check) # HBO se llama para todos los items, incluso si LSO falla

        # Debería haber 1 flip para item_ok
        assert len(opportunities["basic_flips"]) == 1, f"Flips: {opportunities['basic_flips']}"
        assert opportunities["basic_flips"][0]["item_title"] == item_ok
        assert len(opportunities["snipes"]) == 0

        # Verificar que los items con datos incompletos o erróneos no generaron oportunidades
        for flip in opportunities["basic_flips"]:
            assert flip["item_title"] not in [item_bad_lso, item_bad_hbo, item_error_lso]
        for snipe in opportunities["snipes"]:
            assert snipe["item_title"] not in [item_bad_lso, item_bad_hbo, item_error_lso]

# Escenario 5: Sin Datos Históricos en BD para Snipe
@patch('core.strategy_engine.get_db')
@patch('core.dmarket_connector.DMarketAPI.get_fee_rates')
def test_integration_no_historical_data_for_snipe(
    mock_get_fee_rates: MagicMock,
    mock_get_db_in_strategy_engine: MagicMock,
    db_session: SQLAlchemySession,
    strategy_engine: StrategyEngine,
    dmarket_connector: DMarketAPI,
    market_analyzer: MarketAnalyzer # Real MarketAnalyzer
):
    mock_get_db_in_strategy_engine.return_value = iter([db_session])

    item_no_history = "Tec-9 | Isaac (Factory New)"

    # 1. Poblar BD: NO poblamos datos históricos para item_no_history
    # Asegurarnos de que el item existe en SkinsMaestra para que sea procesado
    populate_db_with_items(db_session, [{
        "market_hash_name": item_no_history,
        "historical_prices": [] # Vacío a propósito
    }])
    # Verificar que MarketAnalyzer.calculate_estimated_market_price devuelve None o 0
    # o algún indicador de que no hay PME, cuando no hay datos.
    # El comportamiento actual de MarketAnalyzer es devolver None si no hay precios.
    # Para esta prueba, simulamos que no hay ofertas actuales tampoco para asegurar que PME sea None
    pme_calculated = market_analyzer.calculate_estimated_market_price(
        market_hash_name=item_no_history, 
        historical_prices=[], 
        current_offers=[]
    )
    assert pme_calculated is None, "PME debería ser None si no hay datos históricos ni ofertas actuales para calcularlo"

    # 2. Mockear respuestas del DMarketConnector
    mock_get_fee_rates.return_value = {
        "gameId": DEFAULT_GAME_ID,
        "rates": [{"type": "exchange", "amount": "0.05"}],
        "minCommission": {"amount": "0.01", "currency": "USD"}
    }

    #   - get_offers_by_title: Devolver una oferta barata, ej $1.00
    #   - get_buy_offers: No crítico, pero se llama.
    # Aunque haya una oferta barata, sin PME, no debería haber snipe.

    with patch.object(dmarket_connector, 'get_offers_by_title', return_value={
             "objects": [{"assetId": "cheap_offer_123", "price": {"USD": "100"}}], # $1.00
             "cursor": ""
         }) as mock_get_sell_offers, \
         patch.object(dmarket_connector, 'get_buy_offers', return_value={
             "offers": [], # No se necesitan HBOs
             "cursor": ""
         }) as mock_get_buy_orders:

        # 3. Ejecutar strategy_engine
        opportunities = strategy_engine.run_strategies([item_no_history])

        # 4. Verificaciones
        mock_get_fee_rates.assert_called_once_with(game_id=DEFAULT_GAME_ID)
        mock_get_sell_offers.assert_called_once_with(title=item_no_history, limit=100, currency="USD")
        mock_get_buy_orders.assert_called_once_with(title=item_no_history, game_id=DEFAULT_GAME_ID, limit=100, order_by="price", order_dir="desc", currency="USD")
        
        assert len(opportunities["basic_flips"]) == 0, f"Se encontraron flips inesperados: {opportunities['basic_flips']}"
        assert len(opportunities["snipes"]) == 0, f"Se encontraron snipes inesperados para item sin PME: {opportunities['snipes']}"

# Nota: La importación de datetime dentro de populate_db_with_items
# es para evitar un error si el archivo se ejecuta directamente sin pytest y el path no está bien configurado para utils.
# En el contexto de pytest, debería funcionar sin problemas.