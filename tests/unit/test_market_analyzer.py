# tests/unit/test_market_analyzer.py
import pytest
import os
import sys
import logging

# Añadir el directorio raíz del proyecto a sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.market_analyzer import MarketAnalyzer
# from utils.logger import configure_logging # Si se usa directamente para configurar logs en pruebas

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

# Para ejecutar: pytest tests/unit/test_market_analyzer.py