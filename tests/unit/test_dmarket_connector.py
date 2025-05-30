# tests/unit/test_dmarket_connector.py

import pytest
import os
from unittest.mock import MagicMock, patch # unittest.mock es útil directamente también

# Asegúrate de que el path al directorio raíz del proyecto esté en sys.path
# para que se puedan importar los módulos del proyecto correctamente.
# Esto es común en estructuras de pruebas.
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.dmarket_connector import DMarketAPI
# Asumimos que utils.logger.py existe y el logger se puede importar/usar.
# from utils.logger import logger # Descomentar si necesitas usar el logger en tests


@pytest.fixture
def mock_env_api_keys(monkeypatch):
    """Fixture para simular la presencia de claves API en variables de entorno."""
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", "test_public_key_env")
    monkeypatch.setenv("DMARKET_SECRET_KEY", "test_secret_key_env")

@pytest.fixture
def mock_env_public_key_only(monkeypatch):
    """Fixture para simular solo la clave pública en variables de entorno."""
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", "test_public_key_env")
    monkeypatch.delenv("DMARKET_SECRET_KEY", raising=False) # Asegurar que no exista

@pytest.fixture
def no_api_keys_in_env(monkeypatch):
    """Fixture para simular la ausencia de claves API en variables de entorno."""
    monkeypatch.delenv("DMARKET_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("DMARKET_SECRET_KEY", raising=False)

# ----- Pruebas de Inicialización de DMarketAPI -----

def test_dmarketapi_initialization_with_env_keys(mock_env_api_keys):
    """Prueba que DMarketAPI se inicializa correctamente usando claves de entorno."""
    api = DMarketAPI()
    assert api.public_key == "test_public_key_env"
    assert api.secret_key == "test_secret_key_env"
    assert api.session.headers["X-Api-Key"] == "test_public_key_env"

def test_dmarketapi_initialization_with_public_key_only_env(mock_env_public_key_only, caplog):
    """Prueba que DMarketAPI se inicializa con solo clave pública (advierte por secreta)."""
    # caplog es un fixture de pytest para capturar logs
    import logging
    caplog.set_level(logging.WARNING)
    api = DMarketAPI()
    assert api.public_key == "test_public_key_env"
    assert api.secret_key is None
    assert "DMarket Secret Key no encontrada" in caplog.text

def test_dmarketapi_initialization_with_explicit_keys(no_api_keys_in_env):
    """Prueba que DMarketAPI se inicializa correctamente con claves explícitas."""
    api = DMarketAPI(public_key="test_public_explicit", secret_key="test_secret_explicit")
    assert api.public_key == "test_public_explicit"
    assert api.secret_key == "test_secret_explicit"

def test_dmarketapi_initialization_no_public_key(no_api_keys_in_env):
    """Prueba que DMarketAPI falla si no hay clave pública."""
    with pytest.raises(ValueError, match="DMarket Public Key no encontrada"):
        DMarketAPI()

# ----- Pruebas para el método _create_signature -----

@pytest.fixture
def api_client_with_keys(mock_env_api_keys):
    """Proporciona un cliente DMarketAPI inicializado con ambas claves."""
    return DMarketAPI()

def test_create_signature_success(api_client_with_keys):
    """Prueba la creación exitosa de una firma."""
    method = "GET"
    path = "/exchange/v1/market/items"
    body_str = ""
    timestamp_str = "1678886400" # Ejemplo de timestamp
    
    # El resultado esperado dependerá de la secret_key ("test_secret_key_env") y los datos
    # Se puede calcular manualmente una vez para verificar o mockear hmac.new
    # Por ahora, solo verificamos que se ejecute y devuelva un string hexadecimal
    signature = api_client_with_keys._create_signature(method, path, body_str, timestamp_str)
    assert isinstance(signature, str)
    assert len(signature) == 64 # HMAC-SHA256 produce un hash de 64 caracteres hexadecimales
    try:
        int(signature, 16) # Verificar que sea hexadecimal
    except ValueError:
        pytest.fail("La firma no es un string hexadecimal válido.")

def test_create_signature_no_secret_key(mock_env_public_key_only):
    """Prueba que _create_signature falla si no hay clave secreta."""
    api = DMarketAPI() # Se inicializará con solo la clave pública
    with pytest.raises(ValueError, match="DMarket Secret Key no está configurada"):
        api._create_signature("GET", "/path", "", "12345")

# ----- Pruebas para el método get_market_items -----

@pytest.fixture
def mock_response_success():
    """Crea un mock de respuesta exitosa para requests.Session.request."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "objects": [
            {"title": "AK-47 | Redline", "price": {"USD": "1000"}, "itemId": "item1"},
            {"title": "AWP | Asiimov", "price": {"USD": "5000"}, "itemId": "item2"}
        ],
        "total": 2,
        "limit": 2,
        "offset": "0"
    }
    mock_resp.text = '{"objects": [], "total": 0}' # Texto para caso de no ser JSON
    return mock_resp

@pytest.fixture
def mock_response_http_error_401():
    """Crea un mock de respuesta de error HTTP 401."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error": "Unauthorized", "message": "Invalid API key or signature"}'
    mock_resp.headers = {'Content-Type': 'application/json'}
    # Simular que response.json() funciona si el contenido es JSON válido
    mock_resp.json.return_value = {"error": "Unauthorized", "message": "Invalid API key or signature"}
    
    # Configurar raise_for_status para que lance HTTPError como lo haría requests
    import requests
    http_error = requests.exceptions.HTTPError("401 Client Error: Unauthorized for url", response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_error
    return mock_resp

@pytest.fixture
def mock_response_http_error_429():
    """Crea un mock de respuesta de error HTTP 429 (Rate Limit)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = '{"error": "Too Many Requests", "message": "Rate limit exceeded"}'
    mock_resp.headers = {'Content-Type': 'application/json'}
    mock_resp.json.return_value = {"error": "Too Many Requests", "message": "Rate limit exceeded"}
    import requests
    http_error = requests.exceptions.HTTPError("429 Client Error: Too Many Requests for url", response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_error
    return mock_resp

def test_get_market_items_success(api_client_with_keys, mocker, mock_response_success):
    """Prueba get_market_items con una respuesta exitosa de la API."""
    # Mockear el método request de la sesión de requests usada por DMarketAPI._request
    mocker.patch.object(api_client_with_keys.session, 'request', return_value=mock_response_success)
    
    result = api_client_with_keys.get_market_items(game_id="csgo", title="AK-47")
    
    api_client_with_keys.session.request.assert_called_once() # Verificar que se llamó a request
    args, kwargs = api_client_with_keys.session.request.call_args
    assert args[0] == "GET" # Método
    assert args[1].endswith("/exchange/v1/market/items") # URL
    assert kwargs["params"]["gameId"] == "csgo"
    assert kwargs["params"]["title"] == "AK-47"
    
    assert "error" not in result
    assert len(result["objects"]) == 2
    assert result["objects"][0]["title"] == "AK-47 | Redline"

def test_get_market_items_http_error_401(api_client_with_keys, mocker, mock_response_http_error_401, caplog):
    """Prueba get_market_items con un error HTTP 401 (Unauthorized)."""
    import logging
    caplog.set_level(logging.ERROR)
    mocker.patch.object(api_client_with_keys.session, 'request', return_value=mock_response_http_error_401)
    
    result = api_client_with_keys.get_market_items(game_id="csgo", title="RestrictedItem")
    
    api_client_with_keys.session.request.assert_called_once()
    assert "error" in result
    assert result["error"] == "HTTPError"
    assert result["status_code"] == 401
    assert "Invalid API key or signature" in result["message"]
    assert "Error HTTP: 401" in caplog.text

def test_get_market_items_http_error_429_rate_limit(api_client_with_keys, mocker, mock_response_http_error_429, caplog):
    """Prueba get_market_items con un error HTTP 429 (Rate Limit)."""
    import logging
    caplog.set_level(logging.WARNING)
    mocker.patch.object(api_client_with_keys.session, 'request', return_value=mock_response_http_error_429)

    result = api_client_with_keys.get_market_items(game_id="csgo", title="AnyItem")

    api_client_with_keys.session.request.assert_called_once()
    assert "error" in result
    assert result["error"] == "HTTPError"
    assert result["status_code"] == 429
    assert "Rate limit exceeded" in result["message"]
    assert "Rate limit (429) excedido" in caplog.text # Verificar el log específico del conector

# Se podrían añadir más pruebas para _request directamente, probando diferentes métodos HTTP,
# manejo de `add_auth_headers=True`, diferentes excepciones de requests (ConnectionError, Timeout), etc.

# Ejemplo: Probar que _request añade cabeceras de autenticación correctamente
@patch.object(DMarketAPI, '_create_signature', return_value="mocked_signature_value") # Mockear la creación de firma
def test_request_with_auth_headers(mock_create_signature_method, api_client_with_keys, mocker):
    """Prueba que _request añade correctamente las cabeceras de autenticación."""
    mock_session_response = MagicMock()
    mock_session_response.status_code = 200
    mock_session_response.json.return_value = {"data": "authenticated_stuff"}
    mocker.patch.object(api_client_with_keys.session, 'request', return_value=mock_session_response)

    timestamp_before = int(time.time())
    api_client_with_keys._request("POST", "/private/endpoint", json_data={"payload": "test"}, add_auth_headers=True)
    timestamp_after = int(time.time())

    mock_create_signature_method.assert_called_once()
    args_call_request, kwargs_call_request = api_client_with_keys.session.request.call_args
    
    called_headers = kwargs_call_request["headers"]
    assert "X-Api-Key" in called_headers
    assert "X-Sign-Date" in called_headers
    assert "X-Request-Sign" in called_headers
    assert called_headers["X-Request-Sign"] == "mocked_signature_value"
    
    # Verificar que el timestamp en la cabecera es reciente
    sign_date = int(called_headers["X-Sign-Date"])
    assert timestamp_before <= sign_date <= timestamp_after

    # Verificar que el cuerpo se pasó correctamente para la firma
    # _create_signature es mockeado, pero podemos ver qué se le pasó
    args_call_signature, _ = mock_create_signature_method.call_args
    assert args_call_signature[0] == "POST" # method
    assert args_call_signature[1] == "/private/endpoint" # path
    assert args_call_signature[2] == '{"payload":"test"}' # body_str (JSON compacto)
    assert abs(int(args_call_signature[3]) - timestamp_before) <= 2 # timestamp_str


# Para ejecutar las pruebas, navega al directorio raíz del proyecto en la terminal y ejecuta:
# pytest
# o para más detalle:
# pytest -v
# o para ver logs capturados:
# pytest -s 