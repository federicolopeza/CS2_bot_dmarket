# tests/unit/test_alerter.py
import pytest
import logging
from unittest.mock import patch, MagicMock
from core.alerter import Alerter, AlertLevel, AlertType, create_alerter

@pytest.fixture
def sample_opportunity():
    """Oportunidad de ejemplo para las pruebas."""
    return {
        "item_title": "AK-47 | Redline (Field-Tested)",
        "strategy_type": "basic_flip",
        "buy_price_usd": 10.50,
        "sell_price_usd": 12.00,
        "estimated_profit_usd": 1.20,
        "profit_percentage": 11.4,
        "confidence": "high",
        "details": {
            "lso_asset_id": "123456",
            "hbo_price": 12.00,
            "fee_cents": 30
        }
    }

@pytest.fixture
def low_profit_opportunity():
    """Oportunidad con profit bajo para probar umbrales."""
    return {
        "item_title": "Glock-18 | Sand Dune",
        "strategy_type": "basic_flip",
        "buy_price_usd": 0.10,
        "sell_price_usd": 0.12,
        "estimated_profit_usd": 0.01,
        "profit_percentage": 10.0,
        "confidence": "medium"
    }

@pytest.fixture
def custom_config():
    """Configuración personalizada para pruebas."""
    return {
        "enabled": True,
        "min_profit_usd_for_alert": 1.00,
        "min_profit_percentage_for_alert": 10.0,
        "alert_levels": {
            "basic_flip": "high",
            "snipe": "critical"
        }
    }

def test_alerter_initialization_default_config():
    """Prueba la inicialización del Alerter con configuración por defecto."""
    alerter = Alerter()
    
    assert alerter.config["enabled"] is True
    assert alerter.config["min_profit_usd_for_alert"] == 0.50
    assert alerter.config["min_profit_percentage_for_alert"] == 5.0
    assert "basic_flip" in alerter.config["alert_levels"]

def test_alerter_initialization_custom_config(custom_config):
    """Prueba la inicialización del Alerter con configuración personalizada."""
    alerter = Alerter(custom_config)
    
    assert alerter.config["min_profit_usd_for_alert"] == 1.00
    assert alerter.config["min_profit_percentage_for_alert"] == 10.0
    assert alerter.config["alert_levels"]["basic_flip"] == "high"

def test_create_alerter_function():
    """Prueba la función de conveniencia create_alerter."""
    alerter = create_alerter()
    assert isinstance(alerter, Alerter)
    
    custom_config = {"enabled": False}
    alerter_custom = create_alerter(custom_config)
    assert alerter_custom.config["enabled"] is False

def test_meets_alert_thresholds_success(sample_opportunity):
    """Prueba que una oportunidad válida cumple los umbrales."""
    alerter = Alerter()
    assert alerter._meets_alert_thresholds(sample_opportunity) is True

def test_meets_alert_thresholds_low_profit(low_profit_opportunity):
    """Prueba que una oportunidad con profit bajo no cumple umbrales por defecto."""
    alerter = Alerter()
    assert alerter._meets_alert_thresholds(low_profit_opportunity) is False

def test_meets_alert_thresholds_custom_config(low_profit_opportunity):
    """Prueba umbrales con configuración personalizada."""
    config = {"min_profit_usd_for_alert": 0.005, "min_profit_percentage_for_alert": 5.0}
    alerter = Alerter(config)
    assert alerter._meets_alert_thresholds(low_profit_opportunity) is True

def test_format_alert_data(sample_opportunity):
    """Prueba el formateo de datos de alerta."""
    alerter = Alerter()
    alert_data = alerter._format_alert_data(
        sample_opportunity, 
        AlertType.BASIC_FLIP, 
        AlertLevel.HIGH
    )
    
    assert alert_data["alert_type"] == "basic_flip"
    assert alert_data["alert_level"] == "high"
    assert alert_data["item_title"] == "AK-47 | Redline (Field-Tested)"
    assert alert_data["estimated_profit_usd"] == 1.20
    assert "timestamp" in alert_data
    assert alert_data["raw_opportunity"] == sample_opportunity

@patch('core.alerter.logger')
def test_send_log_alert_different_levels(mock_logger, sample_opportunity):
    """Prueba que se usen diferentes niveles de log según AlertLevel."""
    alerter = Alerter()
    
    # Probar cada nivel de alerta
    test_cases = [
        (AlertLevel.CRITICAL, mock_logger.critical),
        (AlertLevel.HIGH, mock_logger.error),
        (AlertLevel.MEDIUM, mock_logger.warning),
        (AlertLevel.LOW, mock_logger.info)
    ]
    
    for alert_level, expected_log_method in test_cases:
        alert_data = alerter._format_alert_data(
            sample_opportunity, AlertType.BASIC_FLIP, alert_level
        )
        alerter._send_log_alert(alert_data, alert_level)
        expected_log_method.assert_called()

@patch('core.alerter.logger')
def test_alert_opportunity_success(mock_logger, sample_opportunity):
    """Prueba el flujo completo de alerta para una oportunidad válida."""
    alerter = Alerter()
    alerter.alert_opportunity(sample_opportunity, AlertType.BASIC_FLIP)
    
    # Verificar que se llamó al logger (warning por defecto para basic_flip)
    mock_logger.warning.assert_called()
    mock_logger.debug.assert_called()

@patch('core.alerter.logger')
def test_alert_opportunity_below_threshold(mock_logger, low_profit_opportunity):
    """Prueba que no se genere alerta para oportunidades bajo el umbral."""
    alerter = Alerter()
    alerter.alert_opportunity(low_profit_opportunity, AlertType.BASIC_FLIP)
    
    # Solo debería haber un debug log indicando que no cumple umbrales
    mock_logger.debug.assert_called_with(
        "Oportunidad Glock-18 | Sand Dune no cumple umbrales mínimos para alerta."
    )
    # No debería haber alertas de warning/error/etc
    mock_logger.warning.assert_not_called()
    mock_logger.error.assert_not_called()

def test_alert_opportunity_disabled():
    """Prueba que no se generen alertas cuando el alerter está deshabilitado."""
    config = {"enabled": False}
    alerter = Alerter(config)
    
    with patch('core.alerter.logger') as mock_logger:
        alerter.alert_opportunity({}, AlertType.BASIC_FLIP)
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()

def test_alert_opportunity_custom_level(sample_opportunity):
    """Prueba el uso de un nivel de alerta personalizado."""
    alerter = Alerter()
    
    with patch('core.alerter.logger') as mock_logger:
        alerter.alert_opportunity(
            sample_opportunity, 
            AlertType.BASIC_FLIP, 
            custom_level=AlertLevel.CRITICAL
        )
        mock_logger.critical.assert_called()

@patch('core.alerter.logger')
def test_alert_multiple_opportunities_success(mock_logger, sample_opportunity):
    """Prueba el manejo de múltiples oportunidades."""
    alerter = Alerter()
    opportunities = [sample_opportunity, sample_opportunity.copy()]
    
    alerter.alert_multiple_opportunities(opportunities, "Test Scan")
    
    # Debería haber alertas individuales + resumen
    assert mock_logger.warning.call_count == 2  # 2 oportunidades individuales
    mock_logger.info.assert_called()  # Resumen

@patch('core.alerter.logger')
def test_alert_multiple_opportunities_empty(mock_logger):
    """Prueba el manejo de lista vacía de oportunidades."""
    alerter = Alerter()
    alerter.alert_multiple_opportunities([], "Empty Scan")
    
    mock_logger.info.assert_called_with("No se encontraron oportunidades para alertar.")

@patch('core.alerter.logger')
def test_send_summary_alert(mock_logger, sample_opportunity):
    """Prueba la generación de resumen de alertas."""
    alerter = Alerter()
    
    # Crear oportunidades de diferentes estrategias
    opp1 = sample_opportunity.copy()
    opp1["strategy_type"] = "basic_flip"
    opp1["estimated_profit_usd"] = 1.00
    
    opp2 = sample_opportunity.copy()
    opp2["strategy_type"] = "snipe"
    opp2["estimated_profit_usd"] = 2.00
    
    opportunities = [opp1, opp2]
    alerter._send_summary_alert(opportunities, "Test Summary")
    
    # Verificar que se llamó al logger con información del resumen
    mock_logger.info.assert_called()
    call_args = mock_logger.info.call_args[0][0]
    
    assert "TEST SUMMARY" in call_args
    assert "Total de oportunidades: 2" in call_args
    assert "Profit total estimado: $3.00" in call_args
    assert "basic_flip: 1 oportunidades ($1.00)" in call_args
    assert "snipe: 1 oportunidades ($2.00)" in call_args

def test_alert_type_enum():
    """Prueba que los tipos de alerta estén correctamente definidos."""
    assert AlertType.BASIC_FLIP.value == "basic_flip"
    assert AlertType.SNIPE.value == "snipe"
    assert AlertType.ATTRIBUTE_PREMIUM.value == "attribute_premium"
    assert AlertType.VOLATILITY.value == "volatility"
    assert AlertType.TRADE_LOCK.value == "trade_lock"

def test_alert_level_enum():
    """Prueba que los niveles de alerta estén correctamente definidos."""
    assert AlertLevel.LOW.value == "low"
    assert AlertLevel.MEDIUM.value == "medium"
    assert AlertLevel.HIGH.value == "high"
    assert AlertLevel.CRITICAL.value == "critical"

def test_placeholder_methods():
    """Prueba que los métodos placeholder no fallen."""
    alerter = Alerter()
    alert_data = {"test": "data"}
    
    # Estos métodos no deberían hacer nada por ahora, pero no deberían fallar
    alerter._send_email_alert(alert_data)
    alerter._send_telegram_alert(alert_data)

def test_placeholder_methods_with_enabled_config():
    """Prueba los métodos placeholder con configuración habilitada."""
    config = {
        "email": {"enabled": True},
        "telegram": {"enabled": True}
    }
    alerter = Alerter(config)
    alert_data = {"test": "data"}
    
    with patch('core.alerter.logger') as mock_logger:
        alerter._send_email_alert(alert_data)
        alerter._send_telegram_alert(alert_data)
        
        # Deberían logear que enviarían alertas
        assert mock_logger.debug.call_count == 2 