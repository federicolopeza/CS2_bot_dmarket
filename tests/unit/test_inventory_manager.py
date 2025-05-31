# tests/unit/test_inventory_manager.py
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# Añadir el directorio raíz del proyecto a sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.inventory_manager import (
    InventoryManager, InventoryItem, PortfolioSummary,
    InventoryItemStatus, PurchaseSource
)

class TestInventoryManager:
    """Pruebas unitarias para InventoryManager."""

    def setup_method(self):
        """Configuración para cada prueba."""
        self.manager = InventoryManager()

    def test_init_default_config(self):
        """Prueba la inicialización con configuración por defecto."""
        manager = InventoryManager()
        assert manager.config is not None
        assert manager.config["auto_list_after_trade_lock"] is True
        assert manager.config["default_markup_percentage"] == 0.05

    def test_init_custom_config(self):
        """Prueba la inicialización con configuración personalizada."""
        custom_config = {"auto_list_after_trade_lock": False, "default_markup_percentage": 0.10}
        manager = InventoryManager(custom_config)
        assert manager.config["auto_list_after_trade_lock"] is False
        assert manager.config["default_markup_percentage"] == 0.10

    @patch('core.inventory_manager.get_db')
    def test_add_purchased_item_success(self, mock_get_db):
        """Prueba añadir un ítem comprado exitosamente."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        mock_db.close = MagicMock()

        # Mock del ítem creado
        mock_item = MagicMock()
        mock_item.id = 1
        mock_db.refresh.side_effect = lambda item: setattr(item, 'id', 1)

        result = self.manager.add_purchased_item(
            item_title="AK-47 | Redline",
            purchase_price_usd=25.50,
            purchase_source=PurchaseSource.DMARKET,
            strategy_used="basic_flip",
            asset_id="asset123"
        )

        assert result["success"] is True
        assert result["item_id"] == 1
        assert result["status"] == InventoryItemStatus.PURCHASED.value
        assert "AK-47 | Redline" in result["message"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch('core.inventory_manager.get_db')
    def test_add_purchased_item_with_trade_lock(self, mock_get_db):
        """Prueba añadir un ítem con trade lock."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        mock_db.close = MagicMock()

        mock_db.refresh.side_effect = lambda item: setattr(item, 'id', 2)

        result = self.manager.add_purchased_item(
            item_title="AWP | Dragon Lore",
            purchase_price_usd=2500.00,
            purchase_source=PurchaseSource.DMARKET,
            trade_lock_days=7
        )

        assert result["success"] is True
        assert result["status"] == InventoryItemStatus.TRADE_LOCKED.value
        assert result["trade_lock_until"] is not None

    @patch('core.inventory_manager.get_db')
    def test_add_purchased_item_database_error(self, mock_get_db):
        """Prueba manejo de errores de base de datos al añadir ítem."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.add.side_effect = Exception("Database error")
        mock_db.rollback = MagicMock()
        mock_db.close = MagicMock()

        result = self.manager.add_purchased_item(
            item_title="Test Item",
            purchase_price_usd=10.00,
            purchase_source=PurchaseSource.DMARKET
        )

        assert result["success"] is False
        assert "error" in result
        assert "Database error" in result["error"]
        mock_db.rollback.assert_called_once()

    @patch('core.inventory_manager.get_db')
    def test_update_item_status_success(self, mock_get_db):
        """Prueba actualizar estado de ítem exitosamente."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        # Mock del ítem existente
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.item_title = "AK-47 | Redline"
        mock_item.status = InventoryItemStatus.PURCHASED.value
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        result = self.manager.update_item_status(
            item_id=1,
            new_status=InventoryItemStatus.LISTED,
            listed_price_usd=30.00,
            listing_fee_usd=1.50
        )

        assert result["success"] is True
        assert result["item_id"] == 1
        assert result["old_status"] == InventoryItemStatus.PURCHASED.value
        assert result["new_status"] == InventoryItemStatus.LISTED.value
        assert mock_item.status == InventoryItemStatus.LISTED.value
        assert mock_item.listed_price_usd == 30.00

    @patch('core.inventory_manager.get_db')
    def test_update_item_status_item_not_found(self, mock_get_db):
        """Prueba actualizar estado cuando el ítem no existe."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.close = MagicMock()

        result = self.manager.update_item_status(
            item_id=999,
            new_status=InventoryItemStatus.SOLD
        )

        assert result["success"] is False
        assert result["error"] == "Item not found"
        assert "999" in result["message"]

    @patch('core.inventory_manager.get_db')
    def test_update_item_status_sold(self, mock_get_db):
        """Prueba actualizar estado a vendido."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.item_title = "Test Item"
        mock_item.status = InventoryItemStatus.LISTED.value
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        result = self.manager.update_item_status(
            item_id=1,
            new_status=InventoryItemStatus.SOLD,
            sold_price_usd=35.00,
            sale_fee_usd=1.75
        )

        assert result["success"] is True
        assert mock_item.status == InventoryItemStatus.SOLD.value
        assert mock_item.sold_price_usd == 35.00
        assert mock_item.sale_fee_usd == 1.75
        assert mock_item.sold_date is not None

    @patch('core.inventory_manager.get_db')
    def test_get_inventory_summary_empty(self, mock_get_db):
        """Prueba resumen de inventario vacío."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.query.return_value.all.return_value = []
        mock_db.close = MagicMock()

        summary = self.manager.get_inventory_summary()

        assert summary["total_items"] == 0
        assert summary["total_invested_usd"] == 0.0
        assert summary["total_realized_profit_usd"] == 0.0
        assert summary["items_by_status"] == {}

    @patch('core.inventory_manager.get_db')
    def test_get_inventory_summary_with_items(self, mock_get_db):
        """Prueba resumen de inventario con ítems."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        # Mock de ítems
        mock_item1 = MagicMock()
        mock_item1.purchase_price_usd = 25.00
        mock_item1.purchase_fee_usd = 1.25
        mock_item1.status = InventoryItemStatus.PURCHASED.value
        mock_item1.sold_price_usd = None
        mock_item1.sold_date = None
        mock_item1.purchase_date = datetime.now(timezone.utc) - timedelta(days=5)
        
        mock_item2 = MagicMock()
        mock_item2.purchase_price_usd = 50.00
        mock_item2.purchase_fee_usd = 2.50
        mock_item2.status = InventoryItemStatus.SOLD.value
        mock_item2.sold_price_usd = 60.00
        mock_item2.sale_fee_usd = 3.00
        mock_item2.listing_fee_usd = 0.50
        mock_item2.sold_date = datetime.now(timezone.utc) - timedelta(days=2)
        mock_item2.purchase_date = datetime.now(timezone.utc) - timedelta(days=10)
        
        mock_db.query.return_value.all.return_value = [mock_item1, mock_item2]
        mock_db.close = MagicMock()

        summary = self.manager.get_inventory_summary()

        assert summary["total_items"] == 2
        assert summary["total_invested_usd"] == 78.75  # (25+1.25) + (50+2.50)
        # Profit del item2: 60 - 3 - 50 - 2.50 - 0.50 = 4.00
        assert summary["total_realized_profit_usd"] == 4.00
        assert summary["items_by_status"][InventoryItemStatus.PURCHASED.value] == 1
        assert summary["items_by_status"][InventoryItemStatus.SOLD.value] == 1

    @patch('core.inventory_manager.get_db')
    def test_get_items_by_status(self, mock_get_db):
        """Prueba obtener ítems por estado."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.item_title = "AK-47 | Redline"
        mock_item.asset_id = "asset123"
        mock_item.purchase_price_usd = 25.00
        mock_item.purchase_date = datetime.now(timezone.utc)
        mock_item.purchase_source = PurchaseSource.DMARKET.value
        mock_item.strategy_used = "basic_flip"
        mock_item.status = InventoryItemStatus.LISTED.value
        mock_item.trade_lock_until = None
        mock_item.listed_price_usd = 30.00
        mock_item.sold_price_usd = None
        mock_item.notes = "Test notes"
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = [mock_item]
        mock_db.close = MagicMock()

        items = self.manager.get_items_by_status(InventoryItemStatus.LISTED)

        assert len(items) == 1
        assert items[0]["id"] == 1
        assert items[0]["item_title"] == "AK-47 | Redline"
        assert items[0]["status"] == InventoryItemStatus.LISTED.value
        assert items[0]["listed_price_usd"] == 30.00

    @patch('core.inventory_manager.get_db')
    def test_get_items_by_status_with_limit(self, mock_get_db):
        """Prueba obtener ítems por estado con límite."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []
        mock_db.close = MagicMock()

        items = self.manager.get_items_by_status(InventoryItemStatus.PURCHASED, limit=10)

        mock_query.limit.assert_called_once_with(10)

    @patch('core.inventory_manager.get_db')
    def test_check_trade_locks_no_expired(self, mock_get_db):
        """Prueba revisión de trade locks sin ítems expirados."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        result = self.manager.check_trade_locks()

        assert result["success"] is True
        assert result["updated_items"] == 0
        assert "0" in result["message"]

    @patch('core.inventory_manager.get_db')
    def test_check_trade_locks_with_expired(self, mock_get_db):
        """Prueba revisión de trade locks con ítems expirados."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_item1 = MagicMock()
        mock_item1.id = 1
        mock_item1.item_title = "Item 1"
        mock_item1.status = InventoryItemStatus.TRADE_LOCKED.value
        
        mock_item2 = MagicMock()
        mock_item2.id = 2
        mock_item2.item_title = "Item 2"
        mock_item2.status = InventoryItemStatus.TRADE_LOCKED.value
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_item1, mock_item2]
        mock_db.commit = MagicMock()
        mock_db.close = MagicMock()

        result = self.manager.check_trade_locks()

        assert result["success"] is True
        assert result["updated_items"] == 2
        assert mock_item1.status == InventoryItemStatus.PURCHASED.value
        assert mock_item2.status == InventoryItemStatus.PURCHASED.value
        mock_db.commit.assert_called_once()

    @patch('core.inventory_manager.get_db')
    def test_check_trade_locks_database_error(self, mock_get_db):
        """Prueba manejo de errores en revisión de trade locks."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.query.side_effect = Exception("Database error")
        mock_db.rollback = MagicMock()
        mock_db.close = MagicMock()

        result = self.manager.check_trade_locks()

        assert result["success"] is False
        assert "Database error" in result["error"]
        mock_db.rollback.assert_called_once()

    @patch('core.inventory_manager.get_db')
    def test_get_performance_metrics_no_items(self, mock_get_db):
        """Prueba métricas de rendimiento sin ítems."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.close = MagicMock()

        metrics = self.manager.get_performance_metrics(days_back=30)

        assert metrics["period_days"] == 30
        assert metrics["total_trades"] == 0
        assert metrics["successful_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["total_profit_usd"] == 0.0

    @patch('core.inventory_manager.get_db')
    def test_get_performance_metrics_with_trades(self, mock_get_db):
        """Prueba métricas de rendimiento con trades."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        # Trade exitoso
        mock_item1 = MagicMock()
        mock_item1.status = InventoryItemStatus.SOLD.value
        mock_item1.sold_price_usd = 30.00
        mock_item1.sale_fee_usd = 1.50
        mock_item1.purchase_price_usd = 25.00
        mock_item1.purchase_fee_usd = 1.25
        mock_item1.listing_fee_usd = 0.25
        # Profit: 30 - 1.50 - 25 - 1.25 - 0.25 = 2.00
        
        # Trade perdedor
        mock_item2 = MagicMock()
        mock_item2.status = InventoryItemStatus.SOLD.value
        mock_item2.sold_price_usd = 20.00
        mock_item2.sale_fee_usd = 1.00
        mock_item2.purchase_price_usd = 25.00
        mock_item2.purchase_fee_usd = 1.25
        mock_item2.listing_fee_usd = 0.25
        # Profit: 20 - 1 - 25 - 1.25 - 0.25 = -7.50
        
        # Trade no completado
        mock_item3 = MagicMock()
        mock_item3.status = InventoryItemStatus.LISTED.value
        mock_item3.sold_price_usd = None
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_item1, mock_item2, mock_item3]
        mock_db.close = MagicMock()

        metrics = self.manager.get_performance_metrics(days_back=7)

        assert metrics["total_trades"] == 3
        assert metrics["completed_trades"] == 2
        assert metrics["successful_trades"] == 1  # Solo mock_item1 tiene profit > 0
        assert metrics["win_rate"] == 50.0  # 1/2 = 50%
        assert metrics["total_profit_usd"] == -5.50  # 2.00 + (-7.50)
        assert metrics["avg_profit_per_trade"] == -2.75  # -5.50 / 2
        assert metrics["best_trade_profit"] == 2.00
        assert metrics["worst_trade_profit"] == -7.50

class TestInventoryItemModel:
    """Pruebas para el modelo InventoryItem."""

    def test_inventory_item_init_default_status(self):
        """Prueba que el estado por defecto se aplique correctamente."""
        item = InventoryItem(
            item_title="Test Item",
            purchase_price_usd=10.0,
            purchase_source=PurchaseSource.DMARKET.value
        )
        assert item.status == InventoryItemStatus.PURCHASED.value

    def test_inventory_item_init_explicit_status(self):
        """Prueba inicialización con estado explícito."""
        item = InventoryItem(
            item_title="Test Item",
            purchase_price_usd=10.0,
            purchase_source=PurchaseSource.DMARKET.value,
            status=InventoryItemStatus.LISTED.value
        )
        assert item.status == InventoryItemStatus.LISTED.value

class TestEnums:
    """Pruebas para los enums."""

    def test_inventory_item_status_values(self):
        """Prueba los valores del enum InventoryItemStatus."""
        assert InventoryItemStatus.PURCHASED.value == "purchased"
        assert InventoryItemStatus.TRADE_LOCKED.value == "trade_locked"
        assert InventoryItemStatus.LISTED.value == "listed"
        assert InventoryItemStatus.SOLD.value == "sold"
        assert InventoryItemStatus.FAILED_SALE.value == "failed_sale"
        assert InventoryItemStatus.WITHDRAWN.value == "withdrawn"

    def test_purchase_source_values(self):
        """Prueba los valores del enum PurchaseSource."""
        assert PurchaseSource.DMARKET.value == "dmarket"
        assert PurchaseSource.STEAM_MARKET.value == "steam_market"
        assert PurchaseSource.PAPER_TRADING.value == "paper_trading"
        assert PurchaseSource.MANUAL.value == "manual" 