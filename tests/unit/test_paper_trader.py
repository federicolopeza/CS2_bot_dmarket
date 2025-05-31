# tests/unit/test_paper_trader.py
import pytest
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.paper_trader import (
    PaperTrader, PaperTransaction, PaperPortfolio, 
    TransactionType, TransactionStatus, create_paper_trader
)
from core.data_manager import Base

@pytest.fixture(scope="function")
def test_engine():
    """Crear un motor de BD en memoria para las pruebas."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine):
    """Crear una sesión de BD para las pruebas."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture(scope="function")
def mock_get_db(db_session):
    """Mock de get_db para usar la sesión de prueba."""
    def mock_generator():
        yield db_session
    
    with patch('core.paper_trader.get_db', side_effect=lambda: mock_generator()):
        yield

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
def expensive_opportunity():
    """Oportunidad cara para probar límites."""
    return {
        "item_title": "AWP | Dragon Lore (Factory New)",
        "strategy_type": "snipe",
        "buy_price_usd": 5000.00,
        "sell_price_usd": 5500.00,
        "estimated_profit_usd": 400.00,
        "profit_percentage": 8.0,
        "confidence": "medium"
    }

@pytest.fixture
def custom_config():
    """Configuración personalizada para pruebas."""
    return {
        "auto_execute_buys": True,
        "max_position_size_usd": 50.0,
        "max_total_exposure_pct": 70.0,
        "transaction_fee_pct": 0.1  # 10% para hacer más visible en pruebas
    }

def test_paper_trader_initialization_default():
    """Prueba la inicialización del PaperTrader con valores por defecto."""
    trader = PaperTrader()
    
    assert trader.initial_balance_usd == 1000.0
    assert trader.config["auto_execute_buys"] is True
    assert trader.config["max_position_size_usd"] == 100.0
    assert trader.config["max_total_exposure_pct"] == 80.0

def test_paper_trader_initialization_custom(custom_config):
    """Prueba la inicialización del PaperTrader con configuración personalizada."""
    trader = PaperTrader(initial_balance_usd=500.0, config=custom_config)
    
    assert trader.initial_balance_usd == 500.0
    assert trader.config["max_position_size_usd"] == 50.0
    assert trader.config["transaction_fee_pct"] == 0.1

def test_create_paper_trader_function():
    """Prueba la función de conveniencia create_paper_trader."""
    trader = create_paper_trader()
    assert isinstance(trader, PaperTrader)
    assert trader.initial_balance_usd == 1000.0
    
    trader_custom = create_paper_trader(initial_balance=2000.0)
    assert trader_custom.initial_balance_usd == 2000.0

def test_get_current_balance_empty_portfolio(mock_get_db):
    """Prueba el cálculo de balance con portfolio vacío."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    balance = trader.get_current_balance()
    
    assert balance["cash_balance"] == 1000.0
    assert balance["portfolio_value"] == 0.0
    assert balance["total_balance"] == 1000.0
    assert balance["total_invested"] == 0.0

def test_can_afford_purchase_sufficient_funds(mock_get_db):
    """Prueba que se puede permitir una compra con fondos suficientes."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    assert trader.can_afford_purchase(50.0) is True
    assert trader.can_afford_purchase(100.0) is True  # Límite de posición por defecto

def test_can_afford_purchase_insufficient_cash(mock_get_db):
    """Prueba que no se puede permitir una compra sin fondos suficientes."""
    trader = PaperTrader(initial_balance_usd=100.0)
    
    assert trader.can_afford_purchase(150.0) is False

def test_can_afford_purchase_exceeds_position_limit(mock_get_db):
    """Prueba que no se puede permitir una compra que excede el límite de posición."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    # Límite por defecto es 100.0
    assert trader.can_afford_purchase(150.0) is False

def test_can_afford_purchase_exceeds_exposure_limit(mock_get_db, custom_config):
    """Prueba que no se puede permitir una compra que excede el límite de exposición."""
    # Config con 70% de exposición máxima sobre 1000 = 700
    trader = PaperTrader(initial_balance_usd=1000.0, config=custom_config)
    
    # Simular que ya tenemos 600 invertidos
    with patch.object(trader, 'get_current_balance', return_value={
        "cash_balance": 400.0,
        "portfolio_value": 600.0,
        "total_balance": 1000.0,
        "total_invested": 600.0
    }):
        # Intentar comprar por 150 más (600 + 150 = 750 > 700 límite)
        assert trader.can_afford_purchase(150.0) is False
        # Pero 50 más debería estar bien (600 + 50 = 650 < 700)
        assert trader.can_afford_purchase(50.0) is True

def test_simulate_buy_opportunity_success(mock_get_db, sample_opportunity):
    """Prueba una compra simulada exitosa."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    result = trader.simulate_buy_opportunity(sample_opportunity)
    
    assert result["success"] is True
    assert result["item_title"] == "AK-47 | Redline (Field-Tested)"
    assert result["price_paid"] == 10.50
    assert result["strategy_type"] == "basic_flip"
    assert result["status"] == "executed"
    assert "transaction_id" in result

def test_simulate_buy_opportunity_insufficient_funds(mock_get_db, expensive_opportunity):
    """Prueba una compra simulada que falla por fondos insuficientes."""
    trader = PaperTrader(initial_balance_usd=100.0)  # Balance muy bajo
    result = trader.simulate_buy_opportunity(expensive_opportunity)
    
    assert result["success"] is False
    assert result["reason"] == "insufficient_funds_or_limits"
    assert result["item_title"] == "AWP | Dragon Lore (Factory New)"

def test_simulate_buy_opportunity_auto_execute_disabled(mock_get_db, sample_opportunity):
    """Prueba compra con auto-ejecución deshabilitada."""
    config = {"auto_execute_buys": False}
    trader = PaperTrader(initial_balance_usd=1000.0, config=config)
    result = trader.simulate_buy_opportunity(sample_opportunity)
    
    assert result["success"] is True
    assert result["status"] == "pending"

def test_simulate_sell_position_success(mock_get_db, db_session, sample_opportunity):
    """Prueba una venta simulada exitosa."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    # Primero simular una compra para tener una posición
    buy_result = trader.simulate_buy_opportunity(sample_opportunity)
    assert buy_result["success"] is True
    
    # Ahora simular la venta
    sell_result = trader.simulate_sell_position(
        sample_opportunity["item_title"], 
        12.00, 
        "take_profit"
    )
    
    assert sell_result["success"] is True
    assert sell_result["item_title"] == sample_opportunity["item_title"]
    assert sell_result["quantity_sold"] == 1
    assert sell_result["cost_basis"] == 10.50
    assert sell_result["sale_proceeds"] == 12.00
    assert sell_result["gross_profit"] == 1.50
    assert sell_result["reason"] == "take_profit"
    # Comisión por defecto es 0.05% = 0.0005 * 12.00 = 0.006
    assert abs(sell_result["commission"] - 0.006) < 0.001
    assert sell_result["net_profit"] > 0

def test_simulate_sell_position_not_found(mock_get_db):
    """Prueba venta de una posición que no existe."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    result = trader.simulate_sell_position("Nonexistent Item", 100.0)
    
    assert result["success"] is False
    assert result["reason"] == "position_not_found"
    assert result["item_title"] == "Nonexistent Item"

def test_get_portfolio_summary_empty(mock_get_db):
    """Prueba resumen de portfolio vacío."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    summary = trader.get_portfolio_summary()
    
    assert summary["total_positions"] == 0
    assert len(summary["positions"]) == 0
    assert summary["balance_info"]["cash_balance"] == 1000.0

def test_get_portfolio_summary_with_positions(mock_get_db, sample_opportunity):
    """Prueba resumen de portfolio con posiciones."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    # Simular compra
    buy_result = trader.simulate_buy_opportunity(sample_opportunity)
    assert buy_result["success"] is True
    
    summary = trader.get_portfolio_summary()
    
    assert summary["total_positions"] == 1
    assert len(summary["positions"]) == 1
    
    position = summary["positions"][0]
    assert position["item_title"] == sample_opportunity["item_title"]
    assert position["quantity"] == 1
    assert position["avg_cost_usd"] == 10.50
    assert position["strategy_type"] == "basic_flip"
    assert position["days_held"] >= 0

def test_get_performance_summary_no_trades(mock_get_db):
    """Prueba resumen de rendimiento sin trades."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    performance = trader.get_performance_summary()
    
    assert performance["total_trades"] == 0
    assert performance["total_profit_usd"] == 0
    assert performance["avg_profit_per_trade"] == 0
    assert performance["win_rate"] == 0
    assert performance["profitable_trades"] == 0
    assert performance["losing_trades"] == 0

def test_get_performance_summary_with_trades(mock_get_db, sample_opportunity):
    """Prueba resumen de rendimiento con trades completados."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    # Simular compra y venta
    buy_result = trader.simulate_buy_opportunity(sample_opportunity)
    assert buy_result["success"] is True
    
    sell_result = trader.simulate_sell_position(
        sample_opportunity["item_title"], 
        12.00, 
        "take_profit"
    )
    assert sell_result["success"] is True
    
    performance = trader.get_performance_summary()
    
    assert performance["total_trades"] == 1
    assert performance["total_profit_usd"] > 0
    assert performance["avg_profit_per_trade"] > 0
    assert performance["win_rate"] == 100.0  # 1 trade ganador de 1 total
    assert performance["profitable_trades"] == 1
    assert performance["losing_trades"] == 0
    assert performance["best_trade"] > 0
    assert performance["worst_trade"] > 0

def test_update_portfolio_after_buy_new_position(mock_get_db, db_session, sample_opportunity):
    """Prueba actualización de portfolio con nueva posición."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    # Llamar directamente al método privado para prueba unitaria
    trader._update_portfolio_after_buy(
        db_session, 
        sample_opportunity["item_title"], 
        10.50, 
        "basic_flip", 
        sample_opportunity
    )
    db_session.commit()
    
    # Verificar que se creó la posición
    position = db_session.query(PaperPortfolio).filter(
        PaperPortfolio.item_title == sample_opportunity["item_title"]
    ).first()
    
    assert position is not None
    assert position.quantity == 1
    assert position.avg_cost_usd == 10.50
    assert position.total_invested_usd == 10.50
    assert position.strategy_type == "basic_flip"

def test_update_portfolio_after_buy_existing_position(mock_get_db, db_session, sample_opportunity):
    """Prueba actualización de portfolio con posición existente (promedio de costos)."""
    trader = PaperTrader(initial_balance_usd=1000.0)
    
    # Crear posición inicial
    initial_position = PaperPortfolio(
        item_title=sample_opportunity["item_title"],
        quantity=1,
        avg_cost_usd=8.00,
        total_invested_usd=8.00,
        strategy_type="basic_flip",
        first_purchase_at=datetime.now(timezone.utc)
    )
    db_session.add(initial_position)
    db_session.commit()
    
    # Añadir segunda compra
    trader._update_portfolio_after_buy(
        db_session, 
        sample_opportunity["item_title"], 
        12.00,  # Precio más alto
        "basic_flip", 
        sample_opportunity
    )
    db_session.commit()
    
    # Verificar promedio de costos
    position = db_session.query(PaperPortfolio).filter(
        PaperPortfolio.item_title == sample_opportunity["item_title"]
    ).first()
    
    assert position.quantity == 2
    assert position.avg_cost_usd == 10.00  # (8.00 + 12.00) / 2
    assert position.total_invested_usd == 20.00

def test_transaction_type_enum():
    """Prueba que los tipos de transacción estén correctamente definidos."""
    assert TransactionType.BUY.value == "buy"
    assert TransactionType.SELL.value == "sell"

def test_transaction_status_enum():
    """Prueba que los estados de transacción estén correctamente definidos."""
    assert TransactionStatus.PENDING.value == "pending"
    assert TransactionStatus.EXECUTED.value == "executed"
    assert TransactionStatus.CANCELLED.value == "cancelled"
    assert TransactionStatus.EXPIRED.value == "expired"

def test_paper_transaction_model():
    """Prueba el modelo PaperTransaction."""
    transaction = PaperTransaction(
        transaction_type="buy",
        item_title="Test Item",
        strategy_type="test_strategy",
        price_usd=10.0,
        quantity=1
    )
    
    assert transaction.transaction_type == "buy"
    assert transaction.item_title == "Test Item"
    assert transaction.price_usd == 10.0
    assert transaction.status == "pending"  # Valor por defecto

def test_paper_portfolio_model():
    """Prueba el modelo PaperPortfolio."""
    portfolio = PaperPortfolio(
        item_title="Test Item",
        quantity=2,
        avg_cost_usd=15.0,
        total_invested_usd=30.0,
        strategy_type="test_strategy",
        first_purchase_at=datetime.now(timezone.utc)
    )
    
    assert portfolio.item_title == "Test Item"
    assert portfolio.quantity == 2
    assert portfolio.avg_cost_usd == 15.0
    assert portfolio.total_invested_usd == 30.0 