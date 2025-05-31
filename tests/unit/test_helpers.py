import pytest
import logging
from unittest.mock import patch

from utils.helpers import normalize_price_to_usd, normalize_skin_name, SUPPORTED_CURRENCIES

# Pruebas para normalize_price_to_usd

def test_normalize_price_usd_direct():
    """Prueba que la moneda USD se devuelve sin cambios."""
    assert normalize_price_to_usd(100.0, "USD") == 100.0
    assert normalize_price_to_usd(50.50, "usd") == 50.50 # Prueba insensibilidad a mayúsculas/minúsculas

def test_normalize_price_other_supported_currency_placeholder(caplog):
    """Prueba el placeholder para otras monedas soportadas (actualmente ninguna)."""
    # Si añadiéramos "EUR" a SUPPORTED_CURRENCIES pero sin lógica de conversión:
    with patch('utils.helpers.SUPPORTED_CURRENCIES', ["USD", "EUR"]):
        with caplog.at_level(logging.WARNING):
            assert normalize_price_to_usd(100.0, "EUR") is None
            assert "La conversión de EUR a USD aún no está implementada" in caplog.text

def test_normalize_price_unsupported_currency(caplog):
    """Prueba que una moneda no listada en SUPPORTED_CURRENCIES (y no USD) devuelve None y loguea error."""
    original_supported = list(SUPPORTED_CURRENCIES) # Copia para no modificar globalmente
    if "GPB" in original_supported: # Asegurarse que no esté accidentalmente
        original_supported.remove("GPB")

    with patch('utils.helpers.SUPPORTED_CURRENCIES', original_supported):
        with caplog.at_level(logging.ERROR):
            assert normalize_price_to_usd(100.0, "GPB") is None # GPB no está en SUPPORTED_CURRENCIES
            assert "Moneda no soportada para conversión a USD: GPB" in caplog.text

def test_normalize_price_case_insensitivity_for_unsupported(caplog):
    """Prueba que la verificación de moneda no soportada también es insensible a mayúsculas/minúsculas."""
    original_supported = list(SUPPORTED_CURRENCIES)
    if "jpy" in original_supported or "JPY" in original_supported:
        if "JPY" in original_supported: original_supported.remove("JPY")
        if "jpy" in original_supported: original_supported.remove("jpy")
        
    with patch('utils.helpers.SUPPORTED_CURRENCIES', original_supported):
        with caplog.at_level(logging.ERROR):
            assert normalize_price_to_usd(100.0, "jpy") is None
            assert "Moneda no soportada para conversión a USD: JPY" in caplog.text # El log normaliza a mayúsculas

# Pruebas para normalize_skin_name

def test_normalize_skin_name_strips_whitespace():
    """Prueba que se eliminan los espacios en blanco al inicio y al final."""
    assert normalize_skin_name("  AK-47 | Redline  ") == "AK-47 | Redline"
    assert normalize_skin_name("USP-S | Kill Confirmed  ") == "USP-S | Kill Confirmed"
    assert normalize_skin_name("  Glock-18 | Water Elemental") == "Glock-18 | Water Elemental"

def test_normalize_skin_name_no_change():
    """Prueba que un nombre ya normalizado no se modifica."""
    assert normalize_skin_name("P250 | Sand Dune") == "P250 | Sand Dune"

def test_normalize_skin_name_empty_string():
    """Prueba que una cadena vacía devuelve una cadena vacía."""
    assert normalize_skin_name("") == ""
    assert normalize_skin_name("   ") == "" # Solo espacios también

def test_normalize_skin_name_non_string_input(caplog):
    """Prueba que una entrada no string devuelve la entrada original y loguea una advertencia."""
    with caplog.at_level(logging.WARNING):
        assert normalize_skin_name(123) == 123
        assert "normalize_skin_name esperaba un string, pero recibió <class 'int'>" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        assert normalize_skin_name(None) is None
        assert "normalize_skin_name esperaba un string, pero recibió <class 'NoneType'>" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        assert normalize_skin_name(["lista"]) == ["lista"]
        assert "normalize_skin_name esperaba un string, pero recibió <class 'list'>" in caplog.text 