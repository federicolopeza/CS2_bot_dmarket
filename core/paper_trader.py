# core/paper_trader.py
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, func
from sqlalchemy.orm import Session
from core.data_manager import Base, get_db

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class TransactionType(Enum):
    """Tipos de transacciones en paper trading."""
    BUY = "buy"
    SELL = "sell"

class TransactionStatus(Enum):
    """Estados de las transacciones simuladas."""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class PaperTransaction(Base):
    """Modelo para almacenar transacciones simuladas."""
    __tablename__ = "paper_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(String, nullable=False)  # buy/sell
    item_title = Column(String, nullable=False)
    strategy_type = Column(String, nullable=False)  # basic_flip, snipe, etc.
    
    # Precios y cantidades
    price_usd = Column(Float, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    
    # Información de la oportunidad original
    opportunity_data = Column(Text, nullable=True)  # JSON con datos completos
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    executed_at = Column(DateTime, nullable=True)
    
    # Estado y resultados
    status = Column(String, nullable=False)
    actual_profit_usd = Column(Float, nullable=True)  # Profit real al cerrar posición
    notes = Column(Text, nullable=True)

    def __init__(self, **kwargs):
        # Establecer valor por defecto para status si no se proporciona
        if 'status' not in kwargs:
            kwargs['status'] = TransactionStatus.PENDING.value
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<PaperTransaction(type='{self.transaction_type}', item='{self.item_title}', price=${self.price_usd})>"

class PaperPortfolio(Base):
    """Modelo para el portfolio simulado."""
    __tablename__ = "paper_portfolio"

    id = Column(Integer, primary_key=True, index=True)
    item_title = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    avg_cost_usd = Column(Float, nullable=False)  # Costo promedio de compra
    total_invested_usd = Column(Float, nullable=False)
    
    # Información adicional
    strategy_type = Column(String, nullable=False)
    first_purchase_at = Column(DateTime, nullable=False)
    last_updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Metadatos
    metadata_json = Column(Text, nullable=True)  # Información adicional como atributos del ítem

    def __repr__(self):
        return f"<PaperPortfolio(item='{self.item_title}', qty={self.quantity}, avg_cost=${self.avg_cost_usd})>"

class PaperTrader:
    """
    Clase para manejar el paper trading (simulación de transacciones).
    
    Permite registrar oportunidades, simular compras/ventas, y trackear
    el rendimiento de las estrategias sin riesgo financiero real.
    """

    def __init__(self, initial_balance_usd: float = 1000.0, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el paper trader.
        
        Args:
            initial_balance_usd: Balance inicial simulado en USD.
            config: Configuración opcional para el paper trader.
        """
        self.initial_balance_usd = initial_balance_usd
        # Fusionar configuración personalizada con valores por defecto
        default_config = self._get_default_config()
        if config:
            default_config.update(config)
        self.config = default_config
        logger.info(f"PaperTrader inicializado con balance inicial de ${initial_balance_usd:.2f}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto para el paper trader."""
        return {
            "auto_execute_buys": True,  # Ejecutar compras automáticamente
            "auto_execute_sells": False,  # No ejecutar ventas automáticamente (requiere trigger manual)
            "max_position_size_usd": 100.0,  # Máximo a invertir en un solo ítem
            "max_total_exposure_pct": 80.0,  # Máximo % del balance a usar
            "hold_time_hours": 24,  # Tiempo máximo para mantener una posición antes de vender
            "stop_loss_pct": -10.0,  # Stop loss en % (negativo)
            "take_profit_pct": 15.0,  # Take profit en %
            "transaction_fee_pct": 0.05,  # Comisión simulada por transacción (5%)
        }

    def get_current_balance(self) -> Dict[str, float]:
        """
        Calcula el balance actual (cash + valor de posiciones).
        
        Returns:
            Dict con cash_balance, portfolio_value, total_balance
        """
        with next(get_db()) as db:
            # Calcular cash disponible
            total_invested = db.query(PaperPortfolio).with_entities(
                func.sum(PaperPortfolio.total_invested_usd)
            ).scalar() or 0.0
            
            cash_balance = self.initial_balance_usd - total_invested
            
            # Calcular valor del portfolio (simplificado - usar costo de compra por ahora)
            portfolio_value = total_invested
            
            return {
                "cash_balance": cash_balance,
                "portfolio_value": portfolio_value,
                "total_balance": cash_balance + portfolio_value,
                "total_invested": total_invested
            }

    def can_afford_purchase(self, price_usd: float, quantity: int = 1) -> bool:
        """Verifica si se puede permitir una compra."""
        total_cost = price_usd * quantity
        balance_info = self.get_current_balance()
        
        # Verificar cash disponible
        if balance_info["cash_balance"] < total_cost:
            return False
        
        # Verificar límite de posición individual
        if total_cost > self.config["max_position_size_usd"]:
            return False
        
        # Verificar exposición total
        max_exposure = self.initial_balance_usd * (self.config["max_total_exposure_pct"] / 100.0)
        if balance_info["total_invested"] + total_cost > max_exposure:
            return False
        
        return True

    def simulate_buy_opportunity(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simula la compra de una oportunidad identificada.
        
        Args:
            opportunity: Diccionario con los detalles de la oportunidad.
            
        Returns:
            Dict con el resultado de la simulación.
        """
        item_title = opportunity.get("item_title", "Unknown")
        buy_price = opportunity.get("buy_price_usd", 0)
        strategy_type = opportunity.get("strategy_type", "unknown")
        
        logger.info(f"Simulando compra de {item_title} a ${buy_price:.2f} (estrategia: {strategy_type})")
        
        # Verificar si se puede permitir la compra
        if not self.can_afford_purchase(buy_price):
            result = {
                "success": False,
                "reason": "insufficient_funds_or_limits",
                "item_title": item_title,
                "attempted_price": buy_price
            }
            logger.warning(f"No se puede simular compra de {item_title}: {result['reason']}")
            return result
        
        # Crear transacción de compra
        with next(get_db()) as db:
            transaction = PaperTransaction(
                transaction_type=TransactionType.BUY.value,
                item_title=item_title,
                strategy_type=strategy_type,
                price_usd=buy_price,
                quantity=1,
                opportunity_data=json.dumps(opportunity),
                status=TransactionStatus.EXECUTED.value if self.config["auto_execute_buys"] else TransactionStatus.PENDING.value,
                executed_at=datetime.now(timezone.utc) if self.config["auto_execute_buys"] else None
            )
            db.add(transaction)
            
            # Actualizar portfolio si se ejecuta automáticamente
            if self.config["auto_execute_buys"]:
                self._update_portfolio_after_buy(db, item_title, buy_price, strategy_type, opportunity)
            
            db.commit()
            db.refresh(transaction)
            
            result = {
                "success": True,
                "transaction_id": transaction.id,
                "item_title": item_title,
                "price_paid": buy_price,
                "strategy_type": strategy_type,
                "status": transaction.status,
                "balance_after": self.get_current_balance()
            }
            
            logger.info(f"Compra simulada exitosa: {item_title} por ${buy_price:.2f}")
            return result

    def simulate_sell_position(self, item_title: str, sell_price_usd: float, reason: str = "manual") -> Dict[str, Any]:
        """
        Simula la venta de una posición en el portfolio.
        
        Args:
            item_title: Nombre del ítem a vender.
            sell_price_usd: Precio de venta.
            reason: Razón de la venta (manual, take_profit, stop_loss, etc.).
            
        Returns:
            Dict con el resultado de la venta.
        """
        with next(get_db()) as db:
            # Buscar posición en portfolio
            position = db.query(PaperPortfolio).filter(
                PaperPortfolio.item_title == item_title
            ).first()
            
            if not position:
                return {
                    "success": False,
                    "reason": "position_not_found",
                    "item_title": item_title
                }
            
            # Calcular profit/loss
            cost_basis = position.avg_cost_usd * position.quantity
            sale_proceeds = sell_price_usd * position.quantity
            gross_profit = sale_proceeds - cost_basis
            
            # Aplicar comisión
            commission = sale_proceeds * (self.config["transaction_fee_pct"] / 100.0)
            net_profit = gross_profit - commission
            
            # Crear transacción de venta
            sell_transaction = PaperTransaction(
                transaction_type=TransactionType.SELL.value,
                item_title=item_title,
                strategy_type=position.strategy_type,
                price_usd=sell_price_usd,
                quantity=position.quantity,
                status=TransactionStatus.EXECUTED.value,
                executed_at=datetime.now(timezone.utc),
                actual_profit_usd=net_profit,
                notes=f"Sold for reason: {reason}"
            )
            db.add(sell_transaction)
            
            # Remover posición del portfolio
            db.delete(position)
            
            db.commit()
            
            result = {
                "success": True,
                "item_title": item_title,
                "quantity_sold": position.quantity,
                "cost_basis": cost_basis,
                "sale_proceeds": sale_proceeds,
                "gross_profit": gross_profit,
                "commission": commission,
                "net_profit": net_profit,
                "profit_percentage": (net_profit / cost_basis) * 100 if cost_basis > 0 else 0,
                "reason": reason,
                "balance_after": self.get_current_balance()
            }
            
            logger.info(f"Venta simulada: {item_title} por ${sell_price_usd:.2f}, profit neto: ${net_profit:.2f}")
            return result

    def _update_portfolio_after_buy(self, db: Session, item_title: str, price_usd: float, strategy_type: str, opportunity: Dict[str, Any]):
        """Actualiza el portfolio después de una compra."""
        existing_position = db.query(PaperPortfolio).filter(
            PaperPortfolio.item_title == item_title
        ).first()
        
        if existing_position:
            # Actualizar posición existente (promedio de costos)
            total_cost_old = existing_position.avg_cost_usd * existing_position.quantity
            total_cost_new = total_cost_old + price_usd
            new_quantity = existing_position.quantity + 1
            
            existing_position.avg_cost_usd = total_cost_new / new_quantity
            existing_position.quantity = new_quantity
            existing_position.total_invested_usd = total_cost_new
            existing_position.last_updated_at = datetime.now(timezone.utc)
        else:
            # Crear nueva posición
            new_position = PaperPortfolio(
                item_title=item_title,
                quantity=1,
                avg_cost_usd=price_usd,
                total_invested_usd=price_usd,
                strategy_type=strategy_type,
                first_purchase_at=datetime.now(timezone.utc),
                metadata_json=json.dumps(opportunity.get("details", {}))
            )
            db.add(new_position)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen del portfolio actual."""
        with next(get_db()) as db:
            positions = db.query(PaperPortfolio).all()
            balance_info = self.get_current_balance()
            
            portfolio_items = []
            for position in positions:
                # Asegurar que ambos datetime sean timezone-aware
                now_utc = datetime.now(timezone.utc)
                first_purchase = position.first_purchase_at
                if first_purchase.tzinfo is None:
                    first_purchase = first_purchase.replace(tzinfo=timezone.utc)
                
                portfolio_items.append({
                    "item_title": position.item_title,
                    "quantity": position.quantity,
                    "avg_cost_usd": position.avg_cost_usd,
                    "total_invested": position.total_invested_usd,
                    "strategy_type": position.strategy_type,
                    "days_held": (now_utc - first_purchase).days
                })
            
            return {
                "balance_info": balance_info,
                "positions": portfolio_items,
                "total_positions": len(portfolio_items)
            }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen del rendimiento histórico."""
        with next(get_db()) as db:
            # Transacciones completadas
            completed_sales = db.query(PaperTransaction).filter(
                PaperTransaction.transaction_type == TransactionType.SELL.value,
                PaperTransaction.status == TransactionStatus.EXECUTED.value
            ).all()
            
            total_trades = len(completed_sales)
            if total_trades == 0:
                return {
                    "total_trades": 0,
                    "total_profit_usd": 0,
                    "avg_profit_per_trade": 0,
                    "win_rate": 0,
                    "profitable_trades": 0,
                    "losing_trades": 0
                }
            
            profits = [trade.actual_profit_usd for trade in completed_sales if trade.actual_profit_usd is not None]
            total_profit = sum(profits)
            profitable_trades = len([p for p in profits if p > 0])
            losing_trades = len([p for p in profits if p < 0])
            
            return {
                "total_trades": total_trades,
                "total_profit_usd": total_profit,
                "avg_profit_per_trade": total_profit / total_trades if total_trades > 0 else 0,
                "win_rate": (profitable_trades / total_trades) * 100 if total_trades > 0 else 0,
                "profitable_trades": profitable_trades,
                "losing_trades": losing_trades,
                "best_trade": max(profits) if profits else 0,
                "worst_trade": min(profits) if profits else 0
            }

# Función de conveniencia
def create_paper_trader(initial_balance: float = 1000.0, config: Optional[Dict[str, Any]] = None) -> PaperTrader:
    """Crea una instancia del PaperTrader."""
    return PaperTrader(initial_balance, config)

if __name__ == "__main__":
    # Ejemplo de uso
    from utils.logger import configure_logging
    from core.data_manager import init_db
    
    configure_logging(log_level=logging.DEBUG)
    init_db()  # Asegurar que las tablas existen
    
    # Crear paper trader
    trader = create_paper_trader(initial_balance=1000.0)
    
    # Ejemplo de oportunidad
    example_opportunity = {
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
    
    # Simular compra
    buy_result = trader.simulate_buy_opportunity(example_opportunity)
    print(f"Resultado de compra: {buy_result}")
    
    # Ver portfolio
    portfolio = trader.get_portfolio_summary()
    print(f"Portfolio: {portfolio}")
    
    # Simular venta
    if buy_result["success"]:
        sell_result = trader.simulate_sell_position(
            example_opportunity["item_title"], 
            12.00, 
            "take_profit"
        )
        print(f"Resultado de venta: {sell_result}")
        
        # Ver rendimiento
        performance = trader.get_performance_summary()
        print(f"Rendimiento: {performance}") 