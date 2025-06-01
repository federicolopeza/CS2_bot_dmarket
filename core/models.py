from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Index
from sqlalchemy.sql import func
from datetime import datetime, timezone
from enum import Enum
from core.data_manager import Base

class TransactionType(Enum):
    """Tipos de transacciones en trading real."""
    BUY = "buy"
    SELL = "sell"

class TransactionStatus(Enum):
    """Estados de las transacciones en trading real."""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class RealTransaction(Base):
    """Modelo para transacciones REALES ejecutadas en DMarket."""
    __tablename__ = 'real_transactions'
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(String(10), nullable=False)  # 'buy' o 'sell'
    item_title = Column(String(255), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    price_usd = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    asset_id = Column(String(100), nullable=True)  # ID del asset en DMarket
    opportunity_data = Column(Text, nullable=True)  # JSON con datos de la oportunidad
    dmarket_response = Column(Text, nullable=True)  # JSON con respuesta de DMarket
    status = Column(String(20), default='pending')  # pending, executed, failed, cancelled
    executed_at = Column(DateTime(timezone=True), nullable=True)
    actual_profit_usd = Column(Float, nullable=True)  # Profit real al vender
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

class RealPortfolio(Base):
    """Modelo para portfolio REAL de ítems poseídos."""
    __tablename__ = 'real_portfolio'
    
    id = Column(Integer, primary_key=True, index=True)
    item_title = Column(String(255), nullable=False)
    strategy_type = Column(String(50), nullable=False)  # Estrategia que llevó a la compra
    quantity = Column(Integer, default=1)
    avg_cost_usd = Column(Float, nullable=False)  # Costo promedio por ítem
    asset_id = Column(String(100), nullable=True)  # ID del asset en DMarket
    opportunity_data = Column(Text, nullable=True)  # JSON con datos originales
    acquired_at = Column(DateTime(timezone=True), default=func.now())
    last_updated = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Índices para optimizar búsquedas
    __table_args__ = (
        Index('idx_real_portfolio_item_title', 'item_title'),
        Index('idx_real_portfolio_strategy', 'strategy_type'),
    ) 