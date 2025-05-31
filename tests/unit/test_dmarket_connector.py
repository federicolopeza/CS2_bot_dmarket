# tests/unit/test_dmarket_connector.py

import pytest
import os
from unittest.mock import MagicMock, patch
import time # Añadido para test_make_request

# Asegúrate de que el path al directorio raíz del proyecto esté en sys.path
# para que se puedan importar los módulos del proyecto correctamente.
# Esto es común en estructuras de pruebas.
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.dmarket_connector import DMarketAPI, SIGNATURE_PREFIX
from utils.logger import logger # Descomentar si necesitas usar el logger en tests


# Clave secreta de ejemplo válida (64 bytes como hexadecimal de 128 caracteres)
VALID_SECRET_KEY_HEX = bytes(range(64)).hex() 
INVALID_SHORT_SECRET_KEY_HEX = "aabbcc"


@pytest.fixture
def mock_env_api_keys(monkeypatch):
    """Fixture para simular la presencia de claves API válidas en variables de entorno."""
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", "test_public_key_env")
    monkeypatch.setenv("DMARKET_SECRET_KEY", VALID_SECRET_KEY_HEX)

@pytest.fixture
def mock_env_public_key_only(monkeypatch):
    """Fixture para simular solo la clave pública en variables de entorno."""
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", "test_public_key_env")
    monkeypatch.delenv("DMARKET_SECRET_KEY", raising=False)

@pytest.fixture
def mock_env_invalid_secret_key(monkeypatch):
    """Fixture para simular una clave secreta inválida en variables de entorno."""
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", "test_public_key_env")
    monkeypatch.setenv("DMARKET_SECRET_KEY", INVALID_SHORT_SECRET_KEY_HEX)

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
    assert api.secret_key_hex == VALID_SECRET_KEY_HEX
    # La session no guarda directamente la clave en las cabeceras por defecto, 
    # esto se añade en _make_request
    # assert api.session.headers["X-Api-Key"] == "test_public_key_env" # Eliminado

def test_dmarketapi_initialization_missing_secret_key_env(mock_env_public_key_only, caplog):
    """Prueba que DMarketAPI falla si la secret key no está en el entorno."""
    import logging
    caplog.set_level(logging.ERROR)
    with pytest.raises(ValueError, match="DMarket Secret Key no encontrada"):
        DMarketAPI()
    assert "DMarket Secret Key no encontrada" in caplog.text

def test_dmarketapi_initialization_invalid_secret_key_env(mock_env_invalid_secret_key, caplog):
    """Prueba que DMarketAPI falla si la secret key en el entorno es inválida."""
    import logging
    caplog.set_level(logging.ERROR)
    with pytest.raises(ValueError, match="Secret Key inválida"):
        DMarketAPI()
    assert "Secret Key inválida o con formato incorrecto" in caplog.text


def test_dmarketapi_initialization_with_explicit_keys(no_api_keys_in_env):
    """Prueba que DMarketAPI se inicializa correctamente con claves explícitas."""
    api = DMarketAPI(public_key="test_public_explicit", secret_key=VALID_SECRET_KEY_HEX)
    assert api.public_key == "test_public_explicit"
    assert api.secret_key_hex == VALID_SECRET_KEY_HEX

def test_dmarketapi_initialization_no_public_key(no_api_keys_in_env):
    """Prueba que DMarketAPI falla si no hay clave pública."""
    with pytest.raises(ValueError, match="DMarket Public Key no encontrada"):
        DMarketAPI()

def test_dmarketapi_initialization_explicit_invalid_secret_key(no_api_keys_in_env, caplog):
    """Prueba que DMarketAPI falla con clave secreta explícita inválida."""
    import logging
    caplog.set_level(logging.ERROR)
    with pytest.raises(ValueError, match="Secret Key inválida"):
        DMarketAPI(public_key="test_public_explicit", secret_key=INVALID_SHORT_SECRET_KEY_HEX)
    assert "Secret Key inválida o con formato incorrecto" in caplog.text


# ----- Pruebas para el método _generate_signature -----

@pytest.fixture
def api_client_with_valid_keys(mock_env_api_keys):
    """Proporciona un cliente DMarketAPI inicializado con claves válidas."""
    return DMarketAPI()

def test_generate_signature_success(api_client_with_valid_keys):
    """Prueba la creación exitosa de una firma Ed25519."""
    string_to_sign = "GET/exchange/v1/market/items?param=value1678886400" 
    
    # Mockear crypto_sign para devolver una firma predecible
    # crypto_sign devuelve el mensaje firmado (firma + mensaje original)
    # La firma son los primeros 64 bytes.
    mock_signature_bytes = bytes(range(64)) 
    mock_signed_message = mock_signature_bytes + string_to_sign.encode('utf-8')

    with patch('core.dmarket_connector.crypto_sign', return_value=mock_signed_message) as mock_crypto_sign:
        signature_hex = api_client_with_valid_keys._generate_signature(string_to_sign)
    
    mock_crypto_sign.assert_called_once_with(string_to_sign.encode('utf-8'), api_client_with_valid_keys.secret_key_bytes)
    assert isinstance(signature_hex, str)
    assert len(signature_hex) == 128 # Ed25519 produce una firma de 64 bytes -> 128 caracteres hexadecimales
    assert signature_hex == mock_signature_bytes.hex()
    try:
        bytes.fromhex(signature_hex) # Verificar que sea hexadecimal válido
    except ValueError:
        pytest.fail("La firma no es un string hexadecimal válido.")

def test_generate_signature_nacl_exception(api_client_with_valid_keys, caplog):
    """Prueba que _generate_signature maneja excepciones de nacl.bindings.crypto_sign."""
    import logging
    caplog.set_level(logging.ERROR)
    string_to_sign = "test_string"
    with patch('core.dmarket_connector.crypto_sign', side_effect=Exception("NaCl Error")) as mock_crypto_sign:
        signature_hex = api_client_with_valid_keys._generate_signature(string_to_sign)
    
    assert signature_hex is None
    assert "Error crítico al generar firma Ed25519" in caplog.text
    assert "NaCl Error" in caplog.text
    mock_crypto_sign.assert_called_once()

# ----- Pruebas para el método _make_request (antes _request) -----

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
        "offset": "0" # DMarket usa 'cursor', pero el mock puede ser genérico
    }
    mock_resp.text = '{"objects": [], "total": 0}' 
    return mock_resp

@pytest.fixture
def mock_response_http_error_401():
    """Crea un mock de respuesta de error HTTP 401."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error": "Unauthorized", "message": "Invalid API key or signature"}'
    mock_resp.headers = {'Content-Type': 'application/json'}
    mock_resp.json.return_value = {"error": "Unauthorized", "message": "Invalid API key or signature"}
    
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

def test_get_market_items_success(api_client_with_valid_keys, mocker, mock_response_success):
    """Prueba get_market_items con una respuesta exitosa de la API."""
    # Mockear _make_request directamente ya que get_market_items es un wrapper delgado
    # O mockear session.request si queremos probar la construcción de la URL en get_market_items
    
    # Vamos a mockear _make_request para simplificar, ya que su lógica interna se prueba por separado
    mock_make_request = mocker.patch.object(api_client_with_valid_keys, '_make_request', return_value=mock_response_success.json())
    
    result = api_client_with_valid_keys.get_market_items(game_id="a8db", title="AK-47")
    
    mock_make_request.assert_called_once()
    call_args = mock_make_request.call_args[1] # kwargs
    assert call_args['method'] == "GET"
    assert call_args['endpoint'] == "/exchange/v1/market/items"
    assert call_args['params']['gameId'] == "a8db"
    assert call_args['params']['title'] == "AK-47"
        
    assert "error" not in result
    assert len(result["objects"]) == 2
    assert result["objects"][0]["title"] == "AK-47 | Redline"

def test_get_market_items_http_error_401(api_client_with_valid_keys, mocker, mock_response_http_error_401, caplog):
    """Prueba get_market_items con un error HTTP 401 (Unauthorized) devuelto por _make_request."""
    import logging
    caplog.set_level(logging.ERROR) # _make_request ya loguea el error
    
    # Mock _make_request para que devuelva la estructura de error que _make_request crearía
    error_response_from_make_request = {
        "error": "HTTPError", 
        "status_code": 401, 
        "message": {"error": "Unauthorized", "message": "Invalid API key or signature"},
        "response_headers": mock_response_http_error_401.headers
    }
    mocker.patch.object(api_client_with_valid_keys, '_make_request', return_value=error_response_from_make_request)
    
    result = api_client_with_valid_keys.get_market_items(game_id="a8db", title="RestrictedItem")
    
    api_client_with_valid_keys._make_request.assert_called_once()
    assert "error" in result
    assert result["error"] == "HTTPError"
    assert result["status_code"] == 401
    assert "Invalid API key or signature" in result["message"]["message"]
    # El log vendrá de _make_request, no necesitamos replicar la aserción del log aquí si _make_request se prueba por separado.


def test_get_market_items_http_error_429_rate_limit(api_client_with_valid_keys, mocker, mock_response_http_error_429, caplog):
    """Prueba get_market_items con un error HTTP 429 (Rate Limit) devuelto por _make_request."""
    import logging
    caplog.set_level(logging.WARNING) # _make_request loguea el rate limit como warning/error

    error_response_from_make_request = {
        "error": "HTTPError", 
        "status_code": 429, 
        "message": {"error": "Too Many Requests", "message": "Rate limit exceeded"},
        "response_headers": mock_response_http_error_429.headers
    }
    mocker.patch.object(api_client_with_valid_keys, '_make_request', return_value=error_response_from_make_request)

    result = api_client_with_valid_keys.get_market_items(game_id="a8db", title="AnyItem")

    api_client_with_valid_keys._make_request.assert_called_once()
    assert "error" in result
    assert result["error"] == "HTTPError"
    assert result["status_code"] == 429
    assert "Rate limit exceeded" in result["message"]["message"]


@patch.object(DMarketAPI, '_generate_signature', return_value="mocked_hex_signature_128_chars_long_".ljust(128, '0'))
def test_make_request_constructs_headers_and_calls_generate_signature(
    mock_generate_signature_method, 
    api_client_with_valid_keys, # Usa la fixture con claves válidas
    mocker):
    """
    Prueba que _make_request llama a _generate_signature con la string correcta
    y construye las cabeceras de autenticación adecuadamente.
    """
    mock_session_response = MagicMock()
    mock_session_response.status_code = 200
    mock_session_response.json.return_value = {"data": "authenticated_stuff"}
    mock_session_response.raise_for_status = MagicMock() # Asegurar que no falle por status
    
    mocker.patch.object(api_client_with_valid_keys.session, 'request', return_value=mock_session_response)

    method = "POST"
    endpoint = "/private/endpoint"
    test_payload = {"payload_key": "test_value"}
    # json.dumps con separators produce '{"payload_key":"test_value"}'
    expected_body_str_for_sig = '{"payload_key":"test_value"}' 
    
    # Capturar el timestamp usado por _make_request
    current_time_before_call = int(time.time())
    
    api_client_with_valid_keys._make_request(method, endpoint, params={"query": "param"}, body_data=test_payload)
    
    current_time_after_call = int(time.time())

    # Verificar que _generate_signature fue llamado una vez
    mock_generate_signature_method.assert_called_once()
    
    # Verificar los argumentos pasados a _generate_signature
    args_call_signature, _ = mock_generate_signature_method.call_args
    string_to_sign_arg = args_call_signature[0]
    
    # Extraer el timestamp de la string_to_sign
    # Formato: METHOD + path_with_sorted_query + body_json_compact + timestamp
    # Ejemplo: POST/private/endpoint?query=param{"payload_key":"test_value"}TIMESTAMP
    
    # Reconstruir la parte esperada de string_to_sign sin el timestamp
    expected_string_to_sign_prefix = method.upper() + endpoint + "?query=param" + expected_body_str_for_sig
    
    assert string_to_sign_arg.startswith(expected_string_to_sign_prefix)
    
    # Extraer y validar el timestamp
    timestamp_in_string_to_sign = string_to_sign_arg[len(expected_string_to_sign_prefix):]
    assert timestamp_in_string_to_sign.isdigit()
    timestamp_val = int(timestamp_in_string_to_sign)
    assert current_time_before_call <= timestamp_val <= current_time_after_call

    # Verificar la llamada a session.request
    args_call_request, kwargs_call_request = api_client_with_valid_keys.session.request.call_args
    
    called_headers = kwargs_call_request["headers"]
    assert called_headers["X-Api-Key"] == api_client_with_valid_keys.public_key
    assert called_headers["X-Sign-Date"] == timestamp_in_string_to_sign # Debe ser el mismo timestamp
    expected_signature_header = SIGNATURE_PREFIX + "mocked_hex_signature_128_chars_long_".ljust(128, '0')
    assert called_headers["X-Request-Sign"] == expected_signature_header
    assert called_headers["Content-Type"] == "application/json; charset=utf-8"
    
    assert kwargs_call_request["json"] == test_payload


def test_make_request_handles_signature_generation_failure(api_client_with_valid_keys, mocker, caplog):
    """
    Prueba que _make_request maneja el fallo de _generate_signature 
    y no procede con la llamada a la API.
    """
    import logging
    caplog.set_level(logging.ERROR)

    mocker.patch.object(api_client_with_valid_keys, '_generate_signature', return_value=None)
    mock_session_request = mocker.patch.object(api_client_with_valid_keys.session, 'request')

    result = api_client_with_valid_keys._make_request("GET", "/some/endpoint")

    api_client_with_valid_keys._generate_signature.assert_called_once()
    mock_session_request.assert_not_called() # No se debe llamar a la API si la firma falla
    
    assert "error" in result
    assert result["error"] == "SignatureGenerationError"
    assert "Fallo al generar la firma Ed25519" in caplog.text


# Para ejecutar las pruebas, navega al directorio raíz del proyecto en la terminal y ejecuta:
# pytest
# o para más detalle:
# pytest -v
# o para ver logs capturados:
# pytest -s
# o para test específico:
# pytest tests/unit/test_dmarket_connector.py::test_nombre_de_la_funcion 