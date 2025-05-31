# tests/unit/test_execution_engine.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# Añadir el directorio raíz del proyecto a sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.execution_engine import (
    ExecutionEngine, ExecutionOrder, ExecutionMode, ExecutionStatus, RiskLevel
)
from core.inventory_manager import PurchaseSource
from core.alerter import AlertLevel, AlertType

class TestExecutionEngine:
    """Pruebas unitarias para ExecutionEngine."""

    def setup_method(self):
        """Configuración para cada prueba."""
        self.mock_connector = MagicMock()
        self.mock_inventory_manager = MagicMock()
        self.mock_alerter = MagicMock()
        
        self.engine = ExecutionEngine(
            self.mock_connector,
            self.mock_inventory_manager,
            self.mock_alerter
        )

    def test_init_default_config(self):
        """Prueba la inicialización con configuración por defecto."""
        assert self.engine.config["execution_mode"] == ExecutionMode.PAPER_TRADING.value
        assert self.engine.config["max_daily_spending_usd"] == 100.0
        assert self.engine.config["require_manual_confirmation"] is True
        assert len(self.engine.active_orders) == 0
        assert len(self.engine.execution_history) == 0

    def test_init_custom_config(self):
        """Prueba la inicialización con configuración personalizada."""
        custom_config = {
            "execution_mode": ExecutionMode.LIVE_TRADING.value,
            "max_daily_spending_usd": 200.0,
            "require_manual_confirmation": False
        }
        
        engine = ExecutionEngine(
            self.mock_connector,
            self.mock_inventory_manager,
            self.mock_alerter,
            custom_config
        )
        
        assert engine.config["execution_mode"] == ExecutionMode.LIVE_TRADING.value
        assert engine.config["max_daily_spending_usd"] == 200.0
        assert engine.config["require_manual_confirmation"] is False

    def test_reset_daily_limits(self):
        """Prueba el reseteo de límites diarios."""
        # Simular gastos del día anterior
        self.engine.total_executed_today = 50.0
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        self.engine.last_reset_date = yesterday
        
        # Llamar al método que debería resetear
        self.engine._reset_daily_limits_if_needed()
        
        # Verificar que se reseteo
        assert self.engine.total_executed_today == 0.0
        assert self.engine.last_reset_date == datetime.now(timezone.utc).date()

    def test_check_risk_limits_daily_limit_exceeded(self):
        """Prueba verificación de límite diario excedido."""
        # Configurar límite diario bajo
        self.engine.config["max_daily_spending_usd"] = 10.0
        self.engine.total_executed_today = 8.0
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=5.0,  # Excedería el límite (8 + 5 > 10)
            opportunity_data={"profit_usd": 1.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        approved, message = self.engine._check_risk_limits(order)
        assert approved is False
        assert "límite diario" in message.lower()

    def test_check_risk_limits_single_trade_limit_exceeded(self):
        """Prueba verificación de límite por trade excedido."""
        self.engine.config["max_single_trade_usd"] = 20.0
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=25.0,  # Excede límite individual
            opportunity_data={"profit_usd": 1.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        approved, message = self.engine._check_risk_limits(order)
        assert approved is False
        assert "límite por trade" in message.lower()

    def test_check_risk_limits_strategy_disabled(self):
        """Prueba verificación con estrategia deshabilitada."""
        self.engine.config["enabled_strategies"]["basic_flip"] = False
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=5.0,
            opportunity_data={"profit_usd": 1.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        approved, message = self.engine._check_risk_limits(order)
        assert approved is False
        assert "no habilitada" in message

    def test_check_risk_limits_approved(self):
        """Prueba verificación exitosa de límites de riesgo."""
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=5.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        approved, message = self.engine._check_risk_limits(order)
        assert approved is True
        assert "aprobada" in message.lower()

    def test_check_balance_success(self):
        """Prueba verificación exitosa de balance."""
        self.mock_connector.get_account_balance.return_value = {
            "wallet": [
                {"currency": "USD", "balance": "5000"},  # $50.00
                {"currency": "EUR", "balance": "1000"}
            ]
        }
        
        sufficient, balance = self.engine._check_balance()
        assert sufficient is True
        assert balance == 50.0

    def test_check_balance_insufficient(self):
        """Prueba verificación con balance insuficiente."""
        self.engine.config["min_balance_usd"] = 20.0
        self.mock_connector.get_account_balance.return_value = {
            "wallet": [
                {"currency": "USD", "balance": "500"}  # $5.00
            ]
        }
        
        sufficient, balance = self.engine._check_balance()
        assert sufficient is False
        assert balance == 5.0

    def test_check_balance_api_error(self):
        """Prueba verificación con error de API."""
        self.mock_connector.get_account_balance.return_value = {
            "error": "API Error"
        }
        
        sufficient, balance = self.engine._check_balance()
        assert sufficient is False
        assert balance == 0.0

    def test_execute_buy_order_paper_trading(self):
        """Prueba ejecución de compra en modo paper trading."""
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=10.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        success, response = self.engine._execute_buy_order(order)
        assert success is True
        assert response["simulated"] is True
        assert "exitosa" in response["message"]

    def test_execute_buy_order_live_trading_success(self):
        """Prueba ejecución exitosa de compra en modo live."""
        self.engine.config["execution_mode"] = ExecutionMode.LIVE_TRADING.value
        self.mock_connector.buy_item.return_value = {"success": True, "orderId": "123"}
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=10.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        success, response = self.engine._execute_buy_order(order)
        assert success is True
        self.mock_connector.buy_item.assert_called_once_with("asset123", 10.0)

    def test_execute_buy_order_live_trading_no_asset_id(self):
        """Prueba ejecución de compra sin asset_id en modo live."""
        self.engine.config["execution_mode"] = ExecutionMode.LIVE_TRADING.value
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id=None,
            price_usd=10.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        success, response = self.engine._execute_buy_order(order)
        assert success is False
        assert "Asset ID requerido" in response["error"]

    def test_execute_sell_order_paper_trading(self):
        """Prueba ejecución de venta en modo paper trading."""
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="sell",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=15.0,
            opportunity_data={"profit_usd": 3.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        success, response = self.engine._execute_sell_order(order)
        assert success is True
        assert response["simulated"] is True

    def test_create_buy_order_from_basic_flip(self):
        """Prueba creación de orden desde oportunidad de basic flip."""
        opportunity = {
            "strategy": "basic_flip",
            "item_title": "AK-47 | Redline",
            "buy_price_usd": 25.0,
            "profit_usd": 3.0,
            "profit_percentage": 0.12,
            "lso_details": {"assetId": "asset123"}
        }
        
        order = self.engine.create_buy_order_from_opportunity(opportunity)
        
        assert order is not None
        assert order.strategy == "basic_flip"
        assert order.item_title == "AK-47 | Redline"
        assert order.price_usd == 25.0
        assert order.asset_id == "asset123"
        assert order.risk_level == RiskLevel.MEDIUM  # 12% profit

    def test_create_buy_order_from_snipe(self):
        """Prueba creación de orden desde oportunidad de snipe."""
        opportunity = {
            "strategy": "snipe",
            "item_title": "AWP | Dragon Lore",
            "offer_price_usd": 100.0,
            "profit_usd": 25.0,
            "profit_percentage": 0.25,
            "offer_details": {"assetId": "asset456"}
        }
        
        order = self.engine.create_buy_order_from_opportunity(opportunity)
        
        assert order is not None
        assert order.strategy == "snipe"
        assert order.price_usd == 100.0
        assert order.risk_level == RiskLevel.LOW  # 25% profit

    def test_create_buy_order_insufficient_data(self):
        """Prueba creación de orden con datos insuficientes."""
        opportunity = {
            "strategy": "basic_flip",
            "item_title": "Test Item",
            # Falta price y asset_id
        }
        
        order = self.engine.create_buy_order_from_opportunity(opportunity)
        assert order is None

    def test_create_buy_order_unsupported_strategy(self):
        """Prueba creación de orden con estrategia no soportada."""
        opportunity = {
            "strategy": "unknown_strategy",
            "item_title": "Test Item"
        }
        
        order = self.engine.create_buy_order_from_opportunity(opportunity)
        assert order is None

    def test_should_auto_execute_below_threshold(self):
        """Prueba auto-ejecución por debajo del umbral."""
        self.engine.config["require_manual_confirmation"] = True
        self.engine.config["auto_confirm_below_usd"] = 10.0
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=5.0,  # Por debajo del umbral
            opportunity_data={"profit_usd": 1.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        should_execute = self.engine._should_auto_execute(order)
        assert should_execute is True

    def test_should_auto_execute_above_threshold(self):
        """Prueba auto-ejecución por encima del umbral."""
        self.engine.config["require_manual_confirmation"] = True
        self.engine.config["auto_confirm_below_usd"] = 10.0
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=15.0,  # Por encima del umbral
            opportunity_data={"profit_usd": 1.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        should_execute = self.engine._should_auto_execute(order)
        assert should_execute is False

    def test_should_auto_execute_very_high_risk(self):
        """Prueba auto-ejecución con riesgo muy alto."""
        self.engine.config["require_manual_confirmation"] = False
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=5.0,
            opportunity_data={"profit_usd": 1.0},
            risk_level=RiskLevel.VERY_HIGH,
            created_at=datetime.now(timezone.utc)
        )
        
        should_execute = self.engine._should_auto_execute(order)
        assert should_execute is False

    def test_execute_order_success(self):
        """Prueba ejecución exitosa de orden."""
        # Configurar mocks
        self.mock_connector.get_account_balance.return_value = {
            "wallet": [{"currency": "USD", "balance": "5000"}]
        }
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=10.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        success = self.engine.execute_order(order)
        
        assert success is True
        assert order.status == ExecutionStatus.COMPLETED
        assert order.execution_attempts == 1
        assert order.completion_time is not None
        
        # Verificar que se llamó al inventory manager
        self.mock_inventory_manager.add_purchased_item.assert_called_once()
        
        # Verificar que se envió alerta de éxito
        self.mock_alerter.send_alert.assert_called()

    def test_execute_order_risk_rejected(self):
        """Prueba ejecución rechazada por riesgo."""
        # Configurar límite bajo para forzar rechazo
        self.engine.config["max_single_trade_usd"] = 5.0
        
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=10.0,  # Excede límite
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        success = self.engine.execute_order(order)
        
        assert success is False
        assert order.status == ExecutionStatus.FAILED
        assert "límite por trade" in order.error_message
        
        # Verificar alerta de fallo
        self.mock_alerter.send_alert.assert_called_with(
            AlertLevel.MEDIUM,
            AlertType.EXECUTION_FAILED,
            f"Orden rechazada por riesgo: {order.item_title}",
            {"order_id": order.id, "reason": "Excede límite por trade ($10.00 > $5.00)"}
        )

    def test_process_opportunities_empty(self):
        """Prueba procesamiento con oportunidades vacías."""
        opportunities = {
            "basic_flips": [],
            "snipes": []
        }
        
        result = self.engine.process_opportunities(opportunities)
        
        assert result["total_opportunities"] == 0
        assert result["orders_created"] == 0
        assert result["orders_executed"] == 0

    def test_process_opportunities_with_data(self):
        """Prueba procesamiento con oportunidades reales."""
        opportunities = {
            "basic_flips": [
                {
                    "strategy": "basic_flip",
                    "item_title": "AK-47 | Redline",
                    "buy_price_usd": 25.0,
                    "profit_usd": 3.0,
                    "profit_percentage": 0.12,
                    "lso_details": {"assetId": "asset123"}
                }
            ],
            "snipes": [
                {
                    "strategy": "snipe", 
                    "item_title": "AWP | Dragon Lore",
                    "offer_price_usd": 4.0,  # Precio bajo para auto-confirmar
                    "profit_usd": 1.0,
                    "profit_percentage": 0.25,
                    "offer_details": {"assetId": "asset456"}
                }
            ]
        }
        
        result = self.engine.process_opportunities(opportunities)
        
        assert result["total_opportunities"] == 2
        assert result["orders_created"] == 2
        # Solo el snipe se auto-ejecuta (precio < auto_confirm_below_usd)
        assert result["orders_executed"] == 1

    def test_cleanup_orders(self):
        """Prueba limpieza de órdenes completadas."""
        # Añadir órdenes de prueba
        completed_order = ExecutionOrder(
            id="completed",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item 1",
            asset_id="asset123",
            price_usd=10.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc),
            status=ExecutionStatus.COMPLETED
        )
        
        pending_order = ExecutionOrder(
            id="pending",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item 2",
            asset_id="asset456",
            price_usd=15.0,
            opportunity_data={"profit_usd": 3.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc),
            status=ExecutionStatus.PENDING
        )
        
        self.engine.active_orders = [completed_order, pending_order]
        
        self.engine._cleanup_orders()
        
        # Verificar que la orden completada se movió al historial
        assert len(self.engine.active_orders) == 1
        assert self.engine.active_orders[0].id == "pending"
        assert len(self.engine.execution_history) == 1
        assert self.engine.execution_history[0].id == "completed"

    def test_get_execution_summary(self):
        """Prueba obtención de resumen de ejecución."""
        # Añadir algunas órdenes de prueba
        self.engine.total_executed_today = 50.0
        
        pending_order = ExecutionOrder(
            id="pending",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=10.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc),
            status=ExecutionStatus.PENDING
        )
        self.engine.active_orders = [pending_order]
        
        summary = self.engine.get_execution_summary()
        
        assert summary["execution_mode"] == ExecutionMode.PAPER_TRADING.value
        assert summary["active_orders"] == 1
        assert summary["daily_spending_usd"] == 50.0
        assert summary["daily_limit_usd"] == 100.0
        assert summary["remaining_budget_usd"] == 50.0
        assert "recent_stats" in summary

class TestExecutionOrder:
    """Pruebas para la clase ExecutionOrder."""

    def test_execution_order_creation(self):
        """Prueba creación de ExecutionOrder."""
        order = ExecutionOrder(
            id="test_order",
            strategy="basic_flip",
            action="buy",
            item_title="Test Item",
            asset_id="asset123",
            price_usd=10.0,
            opportunity_data={"profit_usd": 2.0},
            risk_level=RiskLevel.LOW,
            created_at=datetime.now(timezone.utc)
        )
        
        assert order.id == "test_order"
        assert order.strategy == "basic_flip"
        assert order.action == "buy"
        assert order.status == ExecutionStatus.PENDING  # Valor por defecto
        assert order.execution_attempts == 0

class TestEnums:
    """Pruebas para los enums del execution engine."""

    def test_execution_mode_values(self):
        """Prueba valores del enum ExecutionMode."""
        assert ExecutionMode.PAPER_TRADING.value == "paper_trading"
        assert ExecutionMode.LIVE_TRADING.value == "live_trading"
        assert ExecutionMode.HYBRID.value == "hybrid"

    def test_execution_status_values(self):
        """Prueba valores del enum ExecutionStatus."""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.EXECUTING.value == "executing"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"
        assert ExecutionStatus.TIMEOUT.value == "timeout"

    def test_risk_level_values(self):
        """Prueba valores del enum RiskLevel."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.VERY_HIGH.value == "very_high" 