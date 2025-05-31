import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import requests

from core.market_scrapers import SteamMarketScraper
from utils.logger import configure_logging # Necesario si el scraper o sus pruebas loguean mucho

# Configurar logging para pruebas, si es necesario un nivel específico
# configure_logging(log_level='DEBUG') 

@pytest.fixture
def scraper():
    """Fixture para crear una instancia de SteamMarketScraper."""
    return SteamMarketScraper(appid="730", currency="1")

# Pruebas para _parse_price_string
@pytest.mark.parametrize("price_str, expected", [
    ("$10.50", Decimal("10.50")),
    ("€20,75", Decimal("20.75")),
    ("£5.99", Decimal("5.99")),
    ("CDN$ 12.34", Decimal("12.34")),
    ("1.234,56€", Decimal("1234.56")),
    ("6,789.00 USD", Decimal("6789.00")),
    ("CHF 15", Decimal("15")),
    ("1,234", Decimal("1234")),
    ("1234", Decimal("1234")),
    ("10.000", Decimal("10000")), # Común en algunos formatos europeos para miles
    ("InvalidPrice", None),
    ("", None),
    (None, None)
])
def test_parse_price_string(scraper, price_str, expected):
    assert scraper._parse_price_string(price_str) == expected

# Pruebas para _parse_volume_string
@pytest.mark.parametrize("volume_str, expected", [
    ("1,234", 1234),
    ("567", 567),
    ("1.000.000", 1000000),
    ("InvalidVolume", None),
    ("", None),
    (None, None)
])
def test_parse_volume_string(scraper, volume_str, expected):
    assert scraper._parse_volume_string(volume_str) == expected

# Pruebas para get_item_price_overview
@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_success_all_data(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "lowest_price": "$10.50",
        "median_price": "$11.00",
        "volume": "1,234"
    }
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item", delay_seconds=0)
    expected_result = {
        "market_hash_name": "Test Item",
        "lowest_price": Decimal("10.50"),
        "median_price": Decimal("11.00"),
        "volume": 1234,
        "currency_symbol": "$"
    }
    assert result == expected_result
    mock_get.assert_called_once()

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_success_no_lowest_price(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "median_price": "€11,00", # Moneda diferente para probar extracción de símbolo
        "volume": "123"
    }
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item No Lowest", delay_seconds=0)
    expected_result = {
        "market_hash_name": "Test Item No Lowest",
        "lowest_price": None,
        "median_price": Decimal("11.00"),
        "volume": 123,
        "currency_symbol": "€"
    }
    assert result == expected_result

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_success_no_median_price(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "lowest_price": "£5.99",
        "volume": "50"
    }
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item No Median", delay_seconds=0)
    expected_result = {
        "market_hash_name": "Test Item No Median",
        "lowest_price": Decimal("5.99"),
        "median_price": None,
        "volume": 50,
        "currency_symbol": "£"
    }
    assert result == expected_result

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_success_no_volume(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "lowest_price": "$1.00",
        "median_price": "$1.10"
    }
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item No Volume", delay_seconds=0)
    expected_result = {
        "market_hash_name": "Test Item No Volume",
        "lowest_price": Decimal("1.00"),
        "median_price": Decimal("1.10"),
        "volume": None,
        "currency_symbol": "$"
    }
    assert result == expected_result

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_success_no_price_data(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True} # No price fields
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item No Prices", delay_seconds=0)
    assert result is None

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_api_success_false(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": False, "message": "Some error"}
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item API Fail", delay_seconds=0)
    assert result is None

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_http_429_rate_limit(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_get.return_value = mock_response
    # Simular que raise_for_status es llamado y no lanza error para 429 (ya que se maneja antes)
    mock_response.raise_for_status = MagicMock()

    result = scraper.get_item_price_overview("Test Item Rate Limit", delay_seconds=0)
    assert result is None
    mock_response.raise_for_status.assert_not_called() # Se maneja antes de raise_for_status

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_http_500_error(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item Server Error", delay_seconds=0)
    assert result is None
    mock_response.raise_for_status.assert_called_once()

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_timeout(mock_get, scraper):
    mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

    result = scraper.get_item_price_overview("Test Item Timeout", delay_seconds=0)
    assert result is None

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_request_exception(mock_get, scraper):
    mock_get.side_effect = requests.exceptions.RequestException("Some request exception")

    result = scraper.get_item_price_overview("Test Item Req Exc", delay_seconds=0)
    assert result is None

@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_json_decode_error(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Failed to decode JSON") # ValueError es la base de JSONDecodeError
    mock_get.return_value = mock_response

    result = scraper.get_item_price_overview("Test Item JSON Error", delay_seconds=0)
    assert result is None

def test_get_item_price_overview_empty_market_hash_name(scraper):
    result = scraper.get_item_price_overview("", delay_seconds=0)
    assert result is None

@patch('core.market_scrapers.time.sleep') # Para evitar sleeps reales en pruebas
@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_currency_symbol_default_usd(mock_get, mock_sleep, scraper):
    scraper_usd = SteamMarketScraper(currency="1") # Explicitly USD
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "lowest_price": "10.50", # Sin símbolo explícito, debería usar el de USD por defecto
    }
    mock_get.return_value = mock_response
    result = scraper_usd.get_item_price_overview("Test Item USD No Symbol", delay_seconds=0)
    assert result["currency_symbol"] == "$"

@patch('core.market_scrapers.time.sleep')
@patch('core.market_scrapers.requests.get')
def test_get_item_price_overview_currency_symbol_other_currency_no_symbol(mock_get, mock_sleep, scraper):
    scraper_other = SteamMarketScraper(currency="3") # e.g., EUR, pero no es USD
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "lowest_price": "10.50", # Sin símbolo explícito
    }
    mock_get.return_value = mock_response
    result = scraper_other.get_item_price_overview("Test Item OtherCur No Symbol", delay_seconds=0)
    assert result["currency_symbol"] == "" # El default para no USD sin símbolo es "" 