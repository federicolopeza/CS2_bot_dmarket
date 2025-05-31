# tests/unit/test_risk_manager.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# Añadir el directorio raíz del proyecto a sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.risk_manager import (
    RiskManager, RiskLevel, RiskAlert, RiskMetrics, StopLossOrder, RiskLimits
)
from core.inventory_manager import InventoryItem, InventoryItemStatus, PurchaseSource

class TestRiskManager:
    """Pruebas unitarias para RiskManager."""

    def setup_method(self):
        """Configuración para cada prueba."""
        self.mock_inventory_manager = MagicMock()
        self.risk_manager = RiskManager(self.mock_inventory_manager)

    def test_init_default_config(self):
        """Prueba la inicialización con configuración por defecto."""
        assert self.risk_manager.config["max_portfolio_exposure_usd"] == 1000.0
        assert self.risk_manager.config["default_stop_loss_percentage"] == 0.15
        assert self.risk_manager.risk_limits.max_portfolio_exposure_usd == 1000.0
        assert len(self.risk_manager.stop_loss_orders) == 0
        assert len(self.risk_manager.risk_alerts_history) == 0

    def test_init_custom_config(self):
        """Prueba la inicialización con configuración personalizada."""
        custom_config = {
            "max_portfolio_exposure_usd": 500.0,
            "default_stop_loss_percentage": 0.10,
            "max_single_position_usd": 100.0
        }
        
        risk_manager = RiskManager(self.mock_inventory_manager, custom_config)
        
        assert risk_manager.config["max_portfolio_exposure_usd"] == 500.0
        assert risk_manager.config["default_stop_loss_percentage"] == 0.10
        assert risk_manager.risk_limits.max_portfolio_exposure_usd == 500.0
        assert risk_manager.risk_limits.max_single_position_usd == 100.0

    def test_categorize_item_rifles(self):
        """Prueba categorización de rifles."""
        assert self.risk_manager._categorize_item("AK-47 | Redline") == "rifle"
        assert self.risk_manager._categorize_item("M4A4 | Howl") == "rifle"
        assert self.risk_manager._categorize_item("AWP | Dragon Lore") == "rifle"

    def test_categorize_item_pistols(self):
        """Prueba categorización de pistolas."""
        assert self.risk_manager._categorize_item("Glock-18 | Fade") == "pistol"
        assert self.risk_manager._categorize_item("USP-S | Kill Confirmed") == "pistol"
        assert self.risk_manager._categorize_item("P250 | See Ya Later") == "pistol"

    def test_categorize_item_knives(self):
        """Prueba categorización de cuchillos."""
        assert self.risk_manager._categorize_item("★ Bayonet | Doppler") == "knife"
        assert self.risk_manager._categorize_item("Knife | Crimson Web") == "knife"
        assert self.risk_manager._categorize_item("★ Karambit") == "knife"

    def test_categorize_item_stickers(self):
        """Prueba categorización de stickers."""
        assert self.risk_manager._categorize_item("Sticker | Team Liquid") == "sticker"
        assert self.risk_manager._categorize_item("Sticker | Katowice 2014") == "sticker"

    def test_categorize_item_other(self):
        """Prueba categorización de otros ítems."""
        assert self.risk_manager._categorize_item("Music Kit | Something") == "other"
        assert self.risk_manager._categorize_item("Unknown Item") == "other"

    def test_calculate_concentration_index_empty(self):
        """Prueba cálculo de índice de concentración con portfolio vacío."""
        concentration = self.risk_manager._calculate_concentration_index([], 0.0)
        assert concentration == 0.0

    def test_calculate_concentration_index_single_item(self):
        """Prueba cálculo de concentración con un solo ítem."""
        items = [
            MagicMock(purchase_price_usd=100.0)
        ]
        concentration = self.risk_manager._calculate_concentration_index(items, 100.0)
        assert concentration == 1.0  # 100% concentración

    def test_calculate_concentration_index_multiple_items(self):
        """Prueba cálculo de concentración con múltiples ítems."""
        items = [
            MagicMock(purchase_price_usd=50.0),
            MagicMock(purchase_price_usd=30.0),
            MagicMock(purchase_price_usd=20.0)
        ]
        # Pesos: 0.5, 0.3, 0.2
        # Herfindahl = 0.5² + 0.3² + 0.2² = 0.25 + 0.09 + 0.04 = 0.38
        concentration = self.risk_manager._calculate_concentration_index(items, 100.0)
        assert abs(concentration - 0.38) < 0.01

    def test_calculate_diversification_score_empty(self):
        """Prueba cálculo de diversificación con portfolio vacío."""
        score = self.risk_manager._calculate_diversification_score([])
        assert score == 1.0

    def test_calculate_diversification_score_single_category(self):
        """Prueba diversificación con una sola categoría."""
        items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=50.0),
            MagicMock(item_title="M4A4 | Howl", purchase_price_usd=50.0)
        ]
        score = self.risk_manager._calculate_diversification_score(items)
        assert score == 0.2  # Baja diversificación, una sola categoría

    def test_calculate_diversification_score_multiple_categories(self):
        """Prueba diversificación con múltiples categorías."""
        items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=40.0),  # rifle
            MagicMock(item_title="Glock-18 | Fade", purchase_price_usd=30.0),  # pistol
            MagicMock(item_title="★ Bayonet", purchase_price_usd=30.0)  # knife
        ]
        score = self.risk_manager._calculate_diversification_score(items)
        assert score >= 0.7  # Buena diversificación

    def test_calculate_correlation_risk_single_item(self):
        """Prueba cálculo de riesgo de correlación con un ítem."""
        items = [MagicMock(item_title="AK-47 | Redline", purchase_price_usd=100.0)]
        risk = self.risk_manager._calculate_correlation_risk(items)
        assert risk == 0.0

    def test_calculate_correlation_risk_concentrated(self):
        """Prueba riesgo de correlación con concentración alta."""
        items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=70.0),
            MagicMock(item_title="M4A4 | Howl", purchase_price_usd=30.0)
        ]
        risk = self.risk_manager._calculate_correlation_risk(items)
        assert risk > 0.5  # Alto riesgo por concentración en rifles

    def test_calculate_liquidity_score_empty(self):
        """Prueba cálculo de liquidez con portfolio vacío."""
        score = self.risk_manager._calculate_liquidity_score([])
        assert score == 1.0

    def test_calculate_liquidity_score_high_price_items(self):
        """Prueba liquidez con ítems caros (menor liquidez)."""
        items = [
            MagicMock(item_title="AWP | Dragon Lore", purchase_price_usd=1000.0)
        ]
        score = self.risk_manager._calculate_liquidity_score(items)
        assert score < 0.5  # Baja liquidez para ítem caro

    def test_calculate_liquidity_score_low_price_items(self):
        """Prueba liquidez con ítems baratos (mayor liquidez)."""
        items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=5.0)
        ]
        score = self.risk_manager._calculate_liquidity_score(items)
        assert score > 0.8  # Alta liquidez para ítem barato

    def test_calculate_volatility_score_empty(self):
        """Prueba cálculo de volatilidad con portfolio vacío."""
        score = self.risk_manager._calculate_volatility_score([])
        assert score == 0.0

    def test_calculate_volatility_score_high_volatility_items(self):
        """Prueba volatilidad con ítems muy volátiles."""
        items = [
            MagicMock(item_title="Sticker | Katowice 2014", purchase_price_usd=500.0)
        ]
        score = self.risk_manager._calculate_volatility_score(items)
        assert score > 0.8  # Alta volatilidad para stickers caros

    def test_calculate_volatility_score_low_volatility_items(self):
        """Prueba volatilidad con ítems poco volátiles."""
        items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=10.0)
        ]
        score = self.risk_manager._calculate_volatility_score(items)
        assert score < 0.4  # Baja volatilidad para rifles baratos

    def test_calculate_value_at_risk_empty(self):
        """Prueba cálculo de VaR con portfolio vacío."""
        var = self.risk_manager._calculate_value_at_risk([], 0.95)
        assert var == 0.0

    def test_calculate_value_at_risk_normal(self):
        """Prueba cálculo de VaR con portfolio normal."""
        items = [
            MagicMock(purchase_price_usd=100.0)
        ]
        var = self.risk_manager._calculate_value_at_risk(items, 0.95)
        assert var > 0.0
        assert var <= 50.0  # Limitado al 50% del portfolio

    def test_calculate_expected_shortfall(self):
        """Prueba cálculo de Expected Shortfall."""
        items = [
            MagicMock(purchase_price_usd=100.0)
        ]
        es = self.risk_manager._calculate_expected_shortfall(items, 0.95)
        var = self.risk_manager._calculate_value_at_risk(items, 0.95)
        assert es == var * 1.25  # ES = 1.25 * VaR

    def test_calculate_portfolio_beta_empty(self):
        """Prueba cálculo de beta con portfolio vacío."""
        beta = self.risk_manager._calculate_portfolio_beta([])
        assert beta == 1.0

    def test_calculate_portfolio_beta_conservative(self):
        """Prueba beta con portfolio conservador."""
        items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=50.0)
        ]
        beta = self.risk_manager._calculate_portfolio_beta(items)
        assert beta == 0.9  # Beta bajo para rifles baratos

    def test_calculate_portfolio_beta_aggressive(self):
        """Prueba beta con portfolio agresivo."""
        items = [
            MagicMock(item_title="Sticker | Katowice 2014", purchase_price_usd=500.0)
        ]
        beta = self.risk_manager._calculate_portfolio_beta(items)
        assert beta == 1.5  # Beta alto para stickers

    def test_determine_risk_level_very_low(self):
        """Prueba determinación de nivel de riesgo muy bajo."""
        level = self.risk_manager._determine_risk_level(0.1)
        assert level == RiskLevel.VERY_LOW

    def test_determine_risk_level_low(self):
        """Prueba determinación de nivel de riesgo bajo."""
        level = self.risk_manager._determine_risk_level(0.3)
        assert level == RiskLevel.LOW

    def test_determine_risk_level_medium(self):
        """Prueba determinación de nivel de riesgo medio."""
        level = self.risk_manager._determine_risk_level(0.5)
        assert level == RiskLevel.MEDIUM

    def test_determine_risk_level_high(self):
        """Prueba determinación de nivel de riesgo alto."""
        level = self.risk_manager._determine_risk_level(0.7)
        assert level == RiskLevel.HIGH

    def test_determine_risk_level_very_high(self):
        """Prueba determinación de nivel de riesgo muy alto."""
        level = self.risk_manager._determine_risk_level(0.9)
        assert level == RiskLevel.VERY_HIGH

    def test_determine_risk_level_extreme(self):
        """Prueba determinación de nivel de riesgo extremo."""
        level = self.risk_manager._determine_risk_level(1.0)
        assert level == RiskLevel.EXTREME

    def test_calculate_risk_metrics_empty_portfolio(self):
        """Prueba cálculo de métricas con portfolio vacío."""
        # Mock inventario vacío
        self.mock_inventory_manager.get_inventory_summary.return_value = {
            'total_invested_usd': 0.0
        }
        self.mock_inventory_manager.get_items_by_status.return_value = []
        self.mock_inventory_manager.get_performance_metrics.return_value = {
            'max_drawdown_percentage': 0.0,
            'sharpe_ratio': 0.0
        }
        
        metrics = self.risk_manager.calculate_risk_metrics()
        
        assert metrics.total_exposure_usd == 0.0
        assert metrics.max_single_position_usd == 0.0
        assert metrics.risk_level == RiskLevel.VERY_LOW
        assert metrics.diversification_score == 1.0

    def test_calculate_risk_metrics_with_items(self):
        """Prueba cálculo de métricas con ítems en portfolio."""
        # Mock inventario con ítems
        mock_items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=50.0),
            MagicMock(item_title="Glock-18 | Fade", purchase_price_usd=30.0)
        ]
        
        self.mock_inventory_manager.get_inventory_summary.return_value = {
            'total_invested_usd': 80.0
        }
        self.mock_inventory_manager.get_items_by_status.return_value = mock_items
        self.mock_inventory_manager.get_performance_metrics.return_value = {
            'max_drawdown_percentage': 0.1,
            'sharpe_ratio': 1.2
        }
        
        metrics = self.risk_manager.calculate_risk_metrics()
        
        assert metrics.total_exposure_usd == 80.0
        assert metrics.max_single_position_usd == 50.0
        assert metrics.max_single_position_percentage == 50.0 / 80.0
        assert metrics.sharpe_ratio == 1.2
        assert isinstance(metrics.risk_level, RiskLevel)

    def test_evaluate_trade_risk_exceeds_exposure_limit(self):
        """Prueba evaluación de trade que excede límite de exposición."""
        # Mock métricas actuales
        with patch.object(self.risk_manager, 'calculate_risk_metrics') as mock_calc:
            mock_calc.return_value = MagicMock(
                total_exposure_usd=950.0,
                max_single_position_usd=100.0,
                overall_risk_score=0.3
            )
            
            approved, risk_score, message = self.risk_manager.evaluate_trade_risk(
                "AK-47 | Redline", 100.0, "basic_flip"
            )
            
            assert approved is False
            assert risk_score == 1.0
            assert "Excede límite de exposición total" in message

    def test_evaluate_trade_risk_exceeds_position_limit(self):
        """Prueba evaluación de trade que excede límite de posición única."""
        with patch.object(self.risk_manager, 'calculate_risk_metrics') as mock_calc:
            mock_calc.return_value = MagicMock(
                total_exposure_usd=100.0,
                max_single_position_usd=50.0,
                overall_risk_score=0.2
            )
            
            approved, risk_score, message = self.risk_manager.evaluate_trade_risk(
                "AWP | Dragon Lore", 250.0, "snipe"  # Excede límite de $200
            )
            
            assert approved is False
            assert risk_score == 1.0
            assert "Excede límite de posición única" in message

    def test_evaluate_trade_risk_low_risk_approved(self):
        """Prueba evaluación de trade de bajo riesgo que se aprueba."""
        with patch.object(self.risk_manager, 'calculate_risk_metrics') as mock_calc:
            mock_calc.return_value = MagicMock(
                total_exposure_usd=100.0,
                max_single_position_usd=50.0,
                overall_risk_score=0.1
            )
            
            # Mock diversification impact
            with patch.object(self.risk_manager, '_evaluate_diversification_impact', return_value=0.1):
                approved, risk_score, message = self.risk_manager.evaluate_trade_risk(
                    "AK-47 | Redline", 10.0, "basic_flip"
                )
                
                assert approved is True
                assert risk_score <= 0.3
                assert "Riesgo bajo" in message

    def test_evaluate_trade_risk_high_risk_rejected(self):
        """Prueba evaluación de trade de alto riesgo que se rechaza."""
        with patch.object(self.risk_manager, 'calculate_risk_metrics') as mock_calc:
            mock_calc.return_value = MagicMock(
                total_exposure_usd=100.0,
                max_single_position_usd=50.0,
                overall_risk_score=0.3
            )
            
            # Mock high diversification impact
            with patch.object(self.risk_manager, '_evaluate_diversification_impact', return_value=0.8):
                approved, risk_score, message = self.risk_manager.evaluate_trade_risk(
                    "Sticker | Katowice 2014", 100.0, "volatility_trading"
                )
                
                assert approved is False
                assert risk_score > 0.6
                assert "Riesgo alto" in message or "Riesgo muy alto" in message or "manual" in message

    def test_evaluate_item_risk_low_price_rifle(self):
        """Prueba evaluación de riesgo para rifle barato."""
        risk_score = self.risk_manager._evaluate_item_risk("AK-47 | Redline", 10.0, "basic_flip")
        assert risk_score < 0.31

    def test_evaluate_item_risk_expensive_knife(self):
        """Prueba evaluación de riesgo para cuchillo caro."""
        risk_score = self.risk_manager._evaluate_item_risk("★ Karambit | Doppler", 600.0, "volatility_trading")
        assert risk_score >= 0.8

    def test_evaluate_item_risk_sticker(self):
        """Prueba evaluación de riesgo para sticker."""
        risk_score = self.risk_manager._evaluate_item_risk("Sticker | Katowice 2014", 100.0, "snipe")
        assert risk_score >= 0.6

    def test_evaluate_diversification_impact_first_purchase(self):
        """Prueba impacto de diversificación para primera compra."""
        self.mock_inventory_manager.get_items_by_status.return_value = []
        
        impact = self.risk_manager._evaluate_diversification_impact("AK-47 | Redline", 50.0)
        assert impact == 0.1

    def test_evaluate_diversification_impact_high_concentration(self):
        """Prueba impacto de diversificación con alta concentración."""
        mock_items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=40.0),
            MagicMock(item_title="M4A4 | Howl", purchase_price_usd=40.0)
        ]
        self.mock_inventory_manager.get_items_by_status.return_value = mock_items
        
        # Comprar otro rifle aumentará concentración
        impact = self.risk_manager._evaluate_diversification_impact("AWP | Dragon Lore", 40.0)
        assert impact >= 0.6

    def test_evaluate_diversification_impact_good_diversification(self):
        """Prueba impacto de diversificación con buena diversificación."""
        mock_items = [
            MagicMock(item_title="AK-47 | Redline", purchase_price_usd=50.0),  # rifle
            MagicMock(item_title="Glock-18 | Fade", purchase_price_usd=50.0)   # pistol
        ]
        self.mock_inventory_manager.get_items_by_status.return_value = mock_items
        
        # Comprar un cuchillo mejora diversificación
        impact = self.risk_manager._evaluate_diversification_impact("★ Bayonet", 30.0)
        assert impact <= 0.3

    @patch('core.risk_manager.get_db')
    def test_create_stop_loss_order_success(self, mock_get_db):
        """Prueba creación exitosa de orden de stop-loss."""
        # Mock database session
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        # Mock item from database
        mock_item = MagicMock()
        mock_item.item_title = "AK-47 | Redline"
        mock_item.purchase_price_usd = 100.0
        mock_item.strategy_used = "basic_flip"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item
        
        stop_order = self.risk_manager.create_stop_loss_order(1, 90.0)
        
        assert stop_order is not None
        assert stop_order.item_id == 1
        assert stop_order.item_title == "AK-47 | Redline"
        assert stop_order.purchase_price_usd == 100.0
        assert stop_order.current_price_usd == 90.0
        assert stop_order.stop_loss_percentage > 0
        assert stop_order.triggered is False
        assert len(self.risk_manager.stop_loss_orders) == 1

    @patch('core.risk_manager.get_db')
    def test_create_stop_loss_order_item_not_found(self, mock_get_db):
        """Prueba creación de stop-loss cuando no se encuentra el ítem."""
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        stop_order = self.risk_manager.create_stop_loss_order(999, 90.0)
        
        assert stop_order is None
        assert len(self.risk_manager.stop_loss_orders) == 0

    def test_calculate_adaptive_stop_loss_basic_rifle(self):
        """Prueba cálculo de stop-loss adaptativo para rifle básico."""
        mock_item = MagicMock()
        mock_item.purchase_price_usd = 50.0
        mock_item.item_title = "AK-47 | Redline"
        mock_item.strategy_used = "basic_flip"
        
        stop_percentage = self.risk_manager._calculate_adaptive_stop_loss(mock_item)
        
        assert 0.05 <= stop_percentage <= 0.30
        assert stop_percentage == 0.15

    def test_calculate_adaptive_stop_loss_expensive_knife(self):
        """Prueba stop-loss adaptativo para cuchillo caro."""
        mock_item = MagicMock()
        mock_item.purchase_price_usd = 600.0
        mock_item.item_title = "★ Karambit | Doppler"
        mock_item.strategy_used = "volatility_trading"
        
        stop_percentage = self.risk_manager._calculate_adaptive_stop_loss(mock_item)
        
        assert stop_percentage > 0.15
        assert stop_percentage <= 0.30

    def test_calculate_adaptive_stop_loss_cheap_snipe(self):
        """Prueba stop-loss adaptativo para snipe barato."""
        mock_item = MagicMock()
        mock_item.purchase_price_usd = 10.0
        mock_item.item_title = "P250 | See Ya Later"
        mock_item.strategy_used = "snipe"
        
        stop_percentage = self.risk_manager._calculate_adaptive_stop_loss(mock_item)
        
        assert stop_percentage < 0.15
        assert stop_percentage >= 0.05

    def test_check_stop_loss_triggers_no_orders(self):
        """Prueba verificación de stop-loss sin órdenes activas."""
        current_prices = {"AK-47 | Redline": 90.0}
        triggered = self.risk_manager.check_stop_loss_triggers(current_prices)
        
        assert len(triggered) == 0

    def test_check_stop_loss_triggers_no_trigger(self):
        """Prueba verificación sin activación de stop-loss."""
        # Crear orden mock
        stop_order = StopLossOrder(
            item_id=1,
            item_title="AK-47 | Redline",
            stop_loss_price_usd=80.0,
            current_price_usd=100.0,
            purchase_price_usd=100.0,
            stop_loss_percentage=0.20,
            created_at=datetime.now(timezone.utc)
        )
        self.risk_manager.stop_loss_orders.append(stop_order)
        
        current_prices = {"AK-47 | Redline": 85.0}  # Por encima del stop
        triggered = self.risk_manager.check_stop_loss_triggers(current_prices)
        
        assert len(triggered) == 0
        assert stop_order.triggered is False

    def test_check_stop_loss_triggers_activated(self):
        """Prueba activación de stop-loss."""
        # Crear orden mock
        stop_order = StopLossOrder(
            item_id=1,
            item_title="AK-47 | Redline",
            stop_loss_price_usd=80.0,
            current_price_usd=100.0,
            purchase_price_usd=100.0,
            stop_loss_percentage=0.20,
            created_at=datetime.now(timezone.utc)
        )
        self.risk_manager.stop_loss_orders.append(stop_order)
        
        current_prices = {"AK-47 | Redline": 75.0}  # Por debajo del stop
        triggered = self.risk_manager.check_stop_loss_triggers(current_prices)
        
        assert len(triggered) == 1
        assert triggered[0] == stop_order
        assert stop_order.triggered is True
        assert stop_order.triggered_at is not None
        assert stop_order.current_price_usd == 75.0
        assert len(self.risk_manager.risk_alerts_history) == 1

    def test_check_stop_loss_triggers_already_triggered(self):
        """Prueba que no se active stop-loss ya activado."""
        # Crear orden ya activada
        stop_order = StopLossOrder(
            item_id=1,
            item_title="AK-47 | Redline",
            stop_loss_price_usd=80.0,
            current_price_usd=75.0,
            purchase_price_usd=100.0,
            stop_loss_percentage=0.20,
            created_at=datetime.now(timezone.utc),
            triggered=True,
            triggered_at=datetime.now(timezone.utc)
        )
        self.risk_manager.stop_loss_orders.append(stop_order)
        
        current_prices = {"AK-47 | Redline": 70.0}  # Aún más bajo
        triggered = self.risk_manager.check_stop_loss_triggers(current_prices)
        
        assert len(triggered) == 0

    def test_record_risk_alert(self):
        """Prueba registro de alerta de riesgo."""
        self.risk_manager._record_risk_alert(
            RiskAlert.STOP_LOSS_TRIGGERED,
            "Test alert",
            {"item_id": 1}
        )
        
        assert len(self.risk_manager.risk_alerts_history) == 1
        alert = self.risk_manager.risk_alerts_history[0]
        assert alert["alert_type"] == "stop_loss_triggered"
        assert alert["message"] == "Test alert"
        assert alert["data"]["item_id"] == 1

    def test_record_risk_alert_history_limit(self):
        """Prueba límite del historial de alertas."""
        # Añadir más de 1000 alertas
        for i in range(1050):
            self.risk_manager._record_risk_alert(
                RiskAlert.VOLATILITY_SPIKE,
                f"Alert {i}",
                {"index": i}
            )
        
        # Verificar que se mantienen solo las últimas 1000
        assert len(self.risk_manager.risk_alerts_history) == 1000
        # Verificar que se mantuvieron las más recientes
        assert self.risk_manager.risk_alerts_history[-1]["data"]["index"] == 1049

    def test_get_risk_summary_success(self):
        """Prueba obtención exitosa de resumen de riesgo."""
        # Mock calculate_risk_metrics
        mock_metrics = MagicMock()
        mock_metrics.timestamp = datetime.now(timezone.utc)
        mock_metrics.risk_level = RiskLevel.MEDIUM
        mock_metrics.overall_risk_score = 0.5
        mock_metrics.total_exposure_usd = 500.0
        mock_metrics.max_single_position_usd = 100.0
        mock_metrics.max_single_position_percentage = 0.2
        mock_metrics.volatility_score = 0.4
        mock_metrics.correlation_risk_score = 0.3
        mock_metrics.liquidity_score = 0.7
        mock_metrics.max_drawdown_percentage = 0.1
        mock_metrics.diversification_score = 0.8
        
        with patch.object(self.risk_manager, 'calculate_risk_metrics', return_value=mock_metrics):
            # Añadir algunas alertas y stop-loss orders
            self.risk_manager._record_risk_alert(RiskAlert.VOLATILITY_SPIKE, "Test", {})
            self.risk_manager.stop_loss_orders = [MagicMock(executed=False, triggered=False)]
            
            summary = self.risk_manager.get_risk_summary()
            
            assert summary["risk_level"] == "medium"
            assert summary["overall_risk_score"] == 0.5
            assert "metrics" in summary
            assert "limits" in summary
            assert "limit_utilization" in summary
            assert "stop_loss_orders" in summary
            assert "recent_alerts" in summary
            assert "warnings" in summary
            
            # Verificar métricas específicas
            assert summary["metrics"]["total_exposure_usd"] == 500.0
            assert summary["stop_loss_orders"]["active"] == 1
            assert summary["recent_alerts"]["count_7d"] == 1

    def test_get_risk_summary_error_handling(self):
        """Prueba manejo de errores en resumen de riesgo."""
        with patch.object(self.risk_manager, 'calculate_risk_metrics', side_effect=Exception("Test error")):
            summary = self.risk_manager.get_risk_summary()
            
            assert "error" in summary
            assert summary["error"] == "Test error"
            assert summary["risk_level"] == "unknown"

    def test_generate_risk_warnings_high_utilization(self):
        """Prueba generación de advertencias con alta utilización."""
        mock_metrics = MagicMock()
        mock_metrics.volatility_score = 0.8
        mock_metrics.correlation_risk_score = 0.7
        mock_metrics.liquidity_score = 0.3
        mock_metrics.max_drawdown_percentage = 0.25
        mock_metrics.diversification_score = 0.4
        
        utilization = {
            "exposure": 0.9,
            "max_position": 0.85,
            "concentration": 0.9,
            "correlation": 0.7
        }
        
        warnings = self.risk_manager._generate_risk_warnings(mock_metrics, utilization)
        
        assert len(warnings) >= 5
        assert any("exposición" in w for w in warnings)
        assert any("volatilidad" in w for w in warnings)
        assert any("correlación" in w for w in warnings)
        assert any("liquidez" in w for w in warnings)
        assert any("diversificación" in w for w in warnings)

    def test_generate_risk_warnings_low_risk(self):
        """Prueba generación de advertencias con bajo riesgo."""
        mock_metrics = MagicMock()
        mock_metrics.volatility_score = 0.3
        mock_metrics.correlation_risk_score = 0.2
        mock_metrics.liquidity_score = 0.8
        mock_metrics.max_drawdown_percentage = 0.05
        mock_metrics.diversification_score = 0.9
        
        utilization = {
            "exposure": 0.5,
            "max_position": 0.6,
            "concentration": 0.4,
            "correlation": 0.3
        }
        
        warnings = self.risk_manager._generate_risk_warnings(mock_metrics, utilization)
        
        assert len(warnings) == 0


class TestRiskManagerEnums:
    """Pruebas para los enums del risk manager."""

    def test_risk_level_values(self):
        """Prueba valores del enum RiskLevel."""
        assert RiskLevel.VERY_LOW.value == "very_low"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.VERY_HIGH.value == "very_high"
        assert RiskLevel.EXTREME.value == "extreme"

    def test_risk_alert_values(self):
        """Prueba valores del enum RiskAlert."""
        assert RiskAlert.EXPOSURE_LIMIT_REACHED.value == "exposure_limit_reached"
        assert RiskAlert.STOP_LOSS_TRIGGERED.value == "stop_loss_triggered"
        assert RiskAlert.CONCENTRATION_WARNING.value == "concentration_warning"
        assert RiskAlert.CORRELATION_RISK.value == "correlation_risk"
        assert RiskAlert.PORTFOLIO_DRAWDOWN.value == "portfolio_drawdown"
        assert RiskAlert.VOLATILITY_SPIKE.value == "volatility_spike"
        assert RiskAlert.LIQUIDITY_RISK.value == "liquidity_risk"


class TestRiskManagerDataclasses:
    """Pruebas para las dataclasses del risk manager."""

    def test_risk_metrics_creation(self):
        """Prueba creación de RiskMetrics."""
        now = datetime.now(timezone.utc)
        metrics = RiskMetrics(
            total_exposure_usd=1000.0,
            max_single_position_usd=200.0,
            max_single_position_percentage=0.2,
            portfolio_beta=1.1,
            sharpe_ratio=1.5,
            max_drawdown_percentage=0.15,
            value_at_risk_95=50.0,
            expected_shortfall=62.5,
            concentration_index=0.3,
            correlation_risk_score=0.4,
            liquidity_score=0.8,
            volatility_score=0.5,
            diversification_score=0.7,
            overall_risk_score=0.45,
            risk_level=RiskLevel.MEDIUM,
            timestamp=now
        )
        
        assert metrics.total_exposure_usd == 1000.0
        assert metrics.risk_level == RiskLevel.MEDIUM
        assert metrics.timestamp == now

    def test_stop_loss_order_creation(self):
        """Prueba creación de StopLossOrder."""
        now = datetime.now(timezone.utc)
        order = StopLossOrder(
            item_id=1,
            item_title="AK-47 | Redline",
            stop_loss_price_usd=85.0,
            current_price_usd=100.0,
            purchase_price_usd=100.0,
            stop_loss_percentage=0.15,
            created_at=now
        )
        
        assert order.item_id == 1
        assert order.item_title == "AK-47 | Redline"
        assert order.stop_loss_price_usd == 85.0
        assert order.triggered is False
        assert order.executed is False
        assert order.triggered_at is None

    def test_risk_limits_creation(self):
        """Prueba creación de RiskLimits."""
        limits = RiskLimits(
            max_portfolio_exposure_usd=2000.0,
            max_single_position_usd=400.0,
            max_single_position_percentage=0.25
        )
        
        assert limits.max_portfolio_exposure_usd == 2000.0
        assert limits.max_single_position_usd == 400.0
        assert limits.max_single_position_percentage == 0.25
        assert limits.stop_loss_percentage == 0.15
 