#!/usr/bin/env python3
"""
Real Trader - Ejecución de Trades REALES en DMarket
==================================================
Sistema para ejecutar compras y ventas REALES usando la API de DMarket.
Reemplaza completamente al PaperTrader para trading en vivo.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import json

from core.dmarket_connector import DMarketAPI
from core.data_manager import get_db
from core.models import (
    RealTransaction, RealPortfolio, 
    TransactionType, TransactionStatus
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class RealTrader:
    """
    Clase para ejecutar trades REALES en DMarket.
    Maneja compras, ventas y gestión de portfolio real.
    """

    def __init__(self, dmarket_api: DMarketAPI, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el RealTrader.
        
        Args:
            dmarket_api: Instancia del conector DMarket configurado
            config: Configuración opcional para el real trader
        """
        self.dmarket_api = dmarket_api
        self.config = config or self._get_default_config()
        
        # Verificar conexión con DMarket
        balance_check = self.dmarket_api.get_account_balance()
        if "error" in balance_check:
            raise Exception(f"No se puede conectar con DMarket: {balance_check}")
        
        logger.info("✅ RealTrader inicializado con conexión DMarket verificada")

    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto para el real trader."""
        return {
            "max_position_size_usd": 25.0,  # Ajustado al balance real
            "max_total_exposure_pct": 80.0,
            "require_manual_confirmation": False,  # Auto-ejecutar para trading en vivo
            "auto_confirm_below_usd": 5.0,
            "stop_loss_pct": -15.0,
            "take_profit_pct": 20.0,
            "max_concurrent_orders": 10,
            "order_timeout_minutes": 30
        }

    def get_real_balance(self) -> Dict[str, float]:
        """Obtener balance REAL de DMarket."""
        try:
            balance_response = self.dmarket_api.get_account_balance()
            
            if "error" in balance_response:
                logger.error(f"Error obteniendo balance real: {balance_response}")
                return {"cash_balance": 0.0, "total_balance": 0.0}
            
            # Procesar respuesta
            if "usd" in balance_response:
                usd_cents = balance_response.get("usd", "0")
                cash_balance = float(usd_cents) / 100.0
            elif "balance" in balance_response:
                usd_cents = balance_response.get("balance", {}).get("USD", "0")
                cash_balance = float(usd_cents) / 100.0
            else:
                cash_balance = 0.0
            
            # Obtener valor del portfolio
            portfolio_value = self.get_portfolio_value()
            total_balance = cash_balance + portfolio_value
            
            return {
                "cash_balance": cash_balance,
                "portfolio_value": portfolio_value,
                "total_balance": total_balance,
                "total_invested": portfolio_value
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo balance real: {e}")
            return {"cash_balance": 0.0, "total_balance": 0.0}

    def get_portfolio_value(self) -> float:
        """Calcular valor actual del portfolio real."""
        try:
            db: Session = next(get_db())
            try:
                # Obtener todas las posiciones activas
                positions = db.query(RealPortfolio).filter(
                    RealPortfolio.quantity > 0
                ).all()
                
                total_value = 0.0
                for position in positions:
                    # Para una estimación rápida, usar el costo promedio
                    # En una implementación completa, se obtendría el precio actual del mercado
                    estimated_value = position.avg_cost_usd * position.quantity
                    total_value += estimated_value
                
                return total_value
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error calculando valor del portfolio: {e}")
            return 0.0

    def can_afford_purchase(self, price_usd: float) -> bool:
        """Verificar si se puede permitir una compra REAL."""
        try:
            balance_info = self.get_real_balance()
            cash_available = balance_info["cash_balance"]
            
            # Verificar cash disponible
            if price_usd > cash_available:
                logger.warning(f"Cash insuficiente: ${price_usd:.2f} > ${cash_available:.2f}")
                return False
            
            # Verificar límite de posición individual
            if price_usd > self.config["max_position_size_usd"]:
                logger.warning(f"Excede límite de posición: ${price_usd:.2f} > ${self.config['max_position_size_usd']:.2f}")
                return False
            
            # Verificar límite de exposición total
            max_exposure = balance_info["total_balance"] * (self.config["max_total_exposure_pct"] / 100.0)
            current_invested = balance_info["total_invested"]
            
            if (current_invested + price_usd) > max_exposure:
                logger.warning(f"Excede límite de exposición: ${current_invested + price_usd:.2f} > ${max_exposure:.2f}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verificando capacidad de compra: {e}")
            return False

    def execute_real_buy(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar compra REAL en DMarket."""
        try:
            item_title = opportunity.get("item_title", opportunity.get("item_name", "Unknown"))
            buy_price = opportunity.get("buy_price_usd", 0)
            strategy_type = opportunity.get("strategy", "unknown")
            asset_id = opportunity.get("assetId", opportunity.get("asset_id"))
            
            logger.info(f"🔥 EJECUTANDO COMPRA REAL: {item_title} por ${buy_price:.2f}")
            
            # Verificar si se puede permitir
            if not self.can_afford_purchase(buy_price):
                return {
                    "success": False,
                    "reason": "insufficient_funds_or_limits",
                    "item_title": item_title,
                    "attempted_price": buy_price
                }
            
            # Verificar que tenemos asset_id
            if not asset_id:
                logger.error(f"No se encontró asset_id para {item_title}")
                return {
                    "success": False,
                    "reason": "missing_asset_id",
                    "item_title": item_title
                }
            
            # EJECUTAR COMPRA REAL EN DMARKET
            buy_response = self.dmarket_api.buy_item(asset_id)
            
            if "error" in buy_response:
                logger.error(f"Error en compra real: {buy_response}")
                return {
                    "success": False,
                    "reason": f"dmarket_error: {buy_response.get('error')}",
                    "item_title": item_title,
                    "asset_id": asset_id
                }
            
            # Si llegamos aquí, la compra fue exitosa
            logger.info(f"✅ COMPRA REAL EXITOSA: {item_title}")
            
            # Registrar transacción en BD
            db: Session = next(get_db())
            try:
                transaction = RealTransaction(
                    transaction_type=TransactionType.BUY.value,
                    item_title=item_title,
                    strategy_type=strategy_type,
                    price_usd=buy_price,
                    quantity=1,
                    asset_id=asset_id,
                    opportunity_data=json.dumps(opportunity),
                    dmarket_response=json.dumps(buy_response),
                    status=TransactionStatus.EXECUTED.value,
                    executed_at=datetime.now(timezone.utc)
                )
                db.add(transaction)
                
                # Actualizar portfolio
                self._update_portfolio_after_buy(db, item_title, buy_price, strategy_type, asset_id, opportunity)
                
                db.commit()
                db.refresh(transaction)
                
                return {
                    "success": True,
                    "transaction_id": transaction.id,
                    "item_title": item_title,
                    "price_paid": buy_price,
                    "strategy_type": strategy_type,
                    "asset_id": asset_id,
                    "dmarket_response": buy_response,
                    "balance_after": self.get_real_balance()
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error ejecutando compra real: {e}")
            return {
                "success": False,
                "reason": f"exception: {str(e)}",
                "item_title": item_title,
                "error": str(e)
            }

    def execute_real_sell(self, item_title: str, sell_price_usd: float, reason: str = "manual") -> Dict[str, Any]:
        """Ejecutar venta REAL en DMarket."""
        try:
            logger.info(f"🔥 EJECUTANDO VENTA REAL: {item_title} por ${sell_price_usd:.2f}")
            
            db: Session = next(get_db())
            try:
                # Buscar posición en portfolio real
                position = db.query(RealPortfolio).filter(
                    RealPortfolio.item_title == item_title,
                    RealPortfolio.quantity > 0
                ).first()
                
                if not position:
                    return {
                        "success": False,
                        "reason": "position_not_found",
                        "item_title": item_title
                    }
                
                # Obtener asset_id de la posición
                asset_id = position.asset_id
                if not asset_id:
                    logger.error(f"No asset_id encontrado para posición {item_title}")
                    return {
                        "success": False,
                        "reason": "missing_asset_id_in_position",
                        "item_title": item_title
                    }
                
                # EJECUTAR VENTA REAL EN DMARKET
                sell_response = self.dmarket_api.create_sell_offer(asset_id, sell_price_usd)
                
                if "error" in sell_response:
                    logger.error(f"Error en venta real: {sell_response}")
                    return {
                        "success": False,
                        "reason": f"dmarket_error: {sell_response.get('error')}",
                        "item_title": item_title,
                        "asset_id": asset_id
                    }
                
                # Calcular profit/loss
                cost_basis = position.avg_cost_usd * position.quantity
                sale_proceeds = sell_price_usd * position.quantity
                gross_profit = sale_proceeds - cost_basis
                
                # DMarket tiene sus propias comisiones reales
                commission = sale_proceeds * 0.05  # Aproximación de comisión DMarket
                net_profit = gross_profit - commission
                
                logger.info(f"✅ VENTA REAL EXITOSA: {item_title}, Profit: ${net_profit:.2f}")
                
                # Registrar transacción de venta
                sell_transaction = RealTransaction(
                    transaction_type=TransactionType.SELL.value,
                    item_title=item_title,
                    strategy_type=position.strategy_type,
                    price_usd=sell_price_usd,
                    quantity=position.quantity,
                    asset_id=asset_id,
                    status=TransactionStatus.EXECUTED.value,
                    executed_at=datetime.now(timezone.utc),
                    actual_profit_usd=net_profit,
                    dmarket_response=json.dumps(sell_response),
                    notes=f"Sold for reason: {reason}"
                )
                db.add(sell_transaction)
                
                # Actualizar portfolio (remover posición)
                db.delete(position)
                
                db.commit()
                db.refresh(sell_transaction)
                
                return {
                    "success": True,
                    "transaction_id": sell_transaction.id,
                    "item_title": item_title,
                    "quantity_sold": position.quantity,
                    "cost_basis": cost_basis,
                    "sale_proceeds": sale_proceeds,
                    "gross_profit": gross_profit,
                    "commission": commission,
                    "net_profit": net_profit,
                    "reason": reason,
                    "asset_id": asset_id,
                    "dmarket_response": sell_response,
                    "balance_after": self.get_real_balance()
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error ejecutando venta real: {e}")
            return {
                "success": False,
                "reason": f"exception: {str(e)}",
                "item_title": item_title,
                "error": str(e)
            }

    def _update_portfolio_after_buy(self, db: Session, item_title: str, buy_price: float, 
                                  strategy_type: str, asset_id: str, opportunity: Dict[str, Any]):
        """Actualizar portfolio después de compra real."""
        try:
            # Buscar posición existente
            existing_position = db.query(RealPortfolio).filter(
                RealPortfolio.item_title == item_title
            ).first()
            
            if existing_position:
                # Actualizar posición existente
                total_cost = (existing_position.avg_cost_usd * existing_position.quantity) + buy_price
                existing_position.quantity += 1
                existing_position.avg_cost_usd = total_cost / existing_position.quantity
                existing_position.last_updated = datetime.now(timezone.utc)
            else:
                # Crear nueva posición
                new_position = RealPortfolio(
                    item_title=item_title,
                    strategy_type=strategy_type,
                    quantity=1,
                    avg_cost_usd=buy_price,
                    asset_id=asset_id,
                    opportunity_data=json.dumps(opportunity),
                    acquired_at=datetime.now(timezone.utc),
                    last_updated=datetime.now(timezone.utc)
                )
                db.add(new_position)
                
        except Exception as e:
            logger.error(f"Error actualizando portfolio: {e}")

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Obtener resumen del portfolio REAL."""
        try:
            db: Session = next(get_db())
            try:
                positions = db.query(RealPortfolio).filter(
                    RealPortfolio.quantity > 0
                ).all()
                
                portfolio_positions = []
                for position in positions:
                    portfolio_positions.append({
                        "item_title": position.item_title,
                        "strategy_type": position.strategy_type,
                        "quantity": position.quantity,
                        "avg_cost_usd": position.avg_cost_usd,
                        "asset_id": position.asset_id,
                        "acquired_at": position.acquired_at,
                        "days_held": (datetime.now(timezone.utc) - position.acquired_at).days
                    })
                
                balance_info = self.get_real_balance()
                
                return {
                    "total_positions": len(positions),
                    "positions": portfolio_positions,
                    "balance_info": balance_info
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error obteniendo resumen de portfolio: {e}")
            return {"total_positions": 0, "positions": [], "balance_info": {}}

    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtener resumen de rendimiento REAL."""
        try:
            db: Session = next(get_db())
            try:
                # Obtener todas las transacciones completadas
                completed_trades = db.query(RealTransaction).filter(
                    RealTransaction.transaction_type == TransactionType.SELL.value,
                    RealTransaction.status == TransactionStatus.EXECUTED.value
                ).all()
                
                if not completed_trades:
                    return {
                        "total_trades": 0,
                        "total_profit_usd": 0.0,
                        "avg_profit_per_trade": 0.0,
                        "win_rate": 0.0,
                        "profitable_trades": 0,
                        "losing_trades": 0,
                        "best_trade": 0.0,
                        "worst_trade": 0.0
                    }
                
                profits = [trade.actual_profit_usd or 0.0 for trade in completed_trades]
                total_profit = sum(profits)
                profitable_trades = sum(1 for p in profits if p > 0)
                losing_trades = len(profits) - profitable_trades
                
                return {
                    "total_trades": len(completed_trades),
                    "total_profit_usd": total_profit,
                    "avg_profit_per_trade": total_profit / len(completed_trades),
                    "win_rate": (profitable_trades / len(completed_trades)) * 100,
                    "profitable_trades": profitable_trades,
                    "losing_trades": losing_trades,
                    "best_trade": max(profits) if profits else 0.0,
                    "worst_trade": min(profits) if profits else 0.0
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error obteniendo rendimiento: {e}")
            return {"total_trades": 0, "total_profit_usd": 0.0} 