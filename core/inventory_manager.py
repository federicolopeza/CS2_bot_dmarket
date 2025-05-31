# core/inventory_manager.py
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Session, relationship
from core.data_manager import Base, get_db

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class InventoryItemStatus(Enum):
    """Estados posibles de un ítem en el inventario."""
    PURCHASED = "purchased"           # Comprado, en inventario
    TRADE_LOCKED = "trade_locked"     # Bloqueado para trading
    LISTED = "listed"                 # Listado para venta
    SOLD = "sold"                     # Vendido exitosamente
    FAILED_SALE = "failed_sale"       # Fallo en la venta
    WITHDRAWN = "withdrawn"           # Retirado de la venta

class PurchaseSource(Enum):
    """Fuente de la compra del ítem."""
    DMARKET = "dmarket"
    STEAM_MARKET = "steam_market"
    PAPER_TRADING = "paper_trading"
    MANUAL = "manual"

class InventoryItem(Base):
    """Modelo para ítems en el inventario."""
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    
    # Información básica del ítem
    item_title = Column(String, nullable=False, index=True)
    asset_id = Column(String, nullable=True, index=True)  # ID del ítem en la plataforma
    
    # Información de compra
    purchase_price_usd = Column(Float, nullable=False)
    purchase_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    purchase_source = Column(String, nullable=False)  # dmarket, steam_market, etc.
    strategy_used = Column(String, nullable=True)     # basic_flip, snipe, etc.
    
    # Estado actual
    status = Column(String, nullable=False, default=InventoryItemStatus.PURCHASED.value)
    trade_lock_until = Column(DateTime, nullable=True)  # Fecha hasta cuando está bloqueado
    
    # Información de venta (si aplica)
    listed_price_usd = Column(Float, nullable=True)
    listed_date = Column(DateTime, nullable=True)
    sold_price_usd = Column(Float, nullable=True)
    sold_date = Column(DateTime, nullable=True)
    
    # Comisiones y gastos
    purchase_fee_usd = Column(Float, default=0.0, nullable=False)
    listing_fee_usd = Column(Float, default=0.0, nullable=False)
    sale_fee_usd = Column(Float, default=0.0, nullable=False)
    
    # Metadatos adicionales
    item_attributes = Column(Text, nullable=True)      # JSON con atributos del ítem
    notes = Column(Text, nullable=True)                # Notas adicionales
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(self, 'status') or self.status is None:
            self.status = InventoryItemStatus.PURCHASED.value

class PortfolioSummary(Base):
    """Modelo para resúmenes de portfolio por período."""
    __tablename__ = "portfolio_summaries"

    id = Column(Integer, primary_key=True, index=True)
    
    # Período del resumen
    summary_date = Column(DateTime, nullable=False, index=True)
    period_type = Column(String, nullable=False)  # daily, weekly, monthly
    
    # Métricas del portfolio
    total_invested_usd = Column(Float, default=0.0, nullable=False)
    total_current_value_usd = Column(Float, default=0.0, nullable=False)
    total_realized_profit_usd = Column(Float, default=0.0, nullable=False)
    total_unrealized_profit_usd = Column(Float, default=0.0, nullable=False)
    
    # Estadísticas de trading
    total_items = Column(Integer, default=0, nullable=False)
    items_sold = Column(Integer, default=0, nullable=False)
    items_listed = Column(Integer, default=0, nullable=False)
    items_trade_locked = Column(Integer, default=0, nullable=False)
    
    # Rendimiento
    win_rate = Column(Float, default=0.0, nullable=False)           # % de ventas exitosas
    avg_hold_time_days = Column(Float, default=0.0, nullable=False) # Tiempo promedio de tenencia
    roi_percentage = Column(Float, default=0.0, nullable=False)     # ROI porcentual
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class InventoryManager:
    """Gestor del inventario de ítems de trading."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el gestor de inventario.
        
        Args:
            config: Configuración opcional del gestor.
        """
        self.config = config or self._get_default_config()
        logger.info("InventoryManager inicializado")

    def _get_default_config(self) -> Dict[str, Any]:
        """Obtiene la configuración por defecto."""
        return {
            "auto_list_after_trade_lock": True,
            "default_markup_percentage": 0.05,  # 5% markup por defecto
            "max_hold_time_days": 30,
            "auto_withdraw_after_days": 7,
            "update_portfolio_summary": True
        }

    def add_purchased_item(
        self,
        item_title: str,
        purchase_price_usd: float,
        purchase_source: PurchaseSource,
        strategy_used: Optional[str] = None,
        asset_id: Optional[str] = None,
        trade_lock_days: Optional[int] = None,
        item_attributes: Optional[Dict[str, Any]] = None,
        purchase_fee_usd: float = 0.0,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Añade un ítem comprado al inventario.
        
        Args:
            item_title: Nombre del ítem.
            purchase_price_usd: Precio de compra en USD.
            purchase_source: Fuente de la compra.
            strategy_used: Estrategia utilizada para la compra.
            asset_id: ID del asset en la plataforma.
            trade_lock_days: Días de bloqueo de trading.
            item_attributes: Atributos del ítem (float, pattern, etc.).
            purchase_fee_usd: Comisión de compra.
            notes: Notas adicionales.
            
        Returns:
            Dict con el resultado de la operación.
        """
        db: Session = next(get_db())
        try:
            # Calcular fecha de desbloqueo si hay trade lock
            trade_lock_until = None
            if trade_lock_days and trade_lock_days > 0:
                trade_lock_until = datetime.now(timezone.utc) + timedelta(days=trade_lock_days)
            
            # Determinar estado inicial
            initial_status = (
                InventoryItemStatus.TRADE_LOCKED if trade_lock_until
                else InventoryItemStatus.PURCHASED
            )
            
            # Crear registro del ítem
            inventory_item = InventoryItem(
                item_title=item_title,
                asset_id=asset_id,
                purchase_price_usd=purchase_price_usd,
                purchase_source=purchase_source.value,
                strategy_used=strategy_used,
                status=initial_status.value,
                trade_lock_until=trade_lock_until,
                purchase_fee_usd=purchase_fee_usd,
                item_attributes=json.dumps(item_attributes) if item_attributes else None,
                notes=notes
            )
            
            db.add(inventory_item)
            db.commit()
            db.refresh(inventory_item)
            
            logger.info(
                f"Ítem añadido al inventario: {item_title} por ${purchase_price_usd:.2f} "
                f"(ID: {inventory_item.id}, Estado: {initial_status.value})"
            )
            
            return {
                "success": True,
                "item_id": inventory_item.id,
                "status": initial_status.value,
                "trade_lock_until": trade_lock_until.isoformat() if trade_lock_until else None,
                "message": f"Ítem {item_title} añadido exitosamente al inventario"
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error añadiendo ítem al inventario: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Error añadiendo {item_title} al inventario"
            }
        finally:
            db.close()

    def update_item_status(
        self,
        item_id: int,
        new_status: InventoryItemStatus,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Actualiza el estado de un ítem en el inventario.
        
        Args:
            item_id: ID del ítem.
            new_status: Nuevo estado del ítem.
            **kwargs: Datos adicionales según el estado (listed_price_usd, sold_price_usd, etc.).
            
        Returns:
            Dict con el resultado de la operación.
        """
        db: Session = next(get_db())
        try:
            item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
            
            if not item:
                return {
                    "success": False,
                    "error": "Item not found",
                    "message": f"No se encontró el ítem con ID {item_id}"
                }
            
            old_status = item.status
            item.status = new_status.value
            
            # Actualizar campos específicos según el nuevo estado
            if new_status == InventoryItemStatus.LISTED:
                item.listed_price_usd = kwargs.get("listed_price_usd")
                item.listed_date = datetime.now(timezone.utc)
                item.listing_fee_usd = kwargs.get("listing_fee_usd", 0.0)
                
            elif new_status == InventoryItemStatus.SOLD:
                item.sold_price_usd = kwargs.get("sold_price_usd")
                item.sold_date = datetime.now(timezone.utc)
                item.sale_fee_usd = kwargs.get("sale_fee_usd", 0.0)
            
            item.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            
            logger.info(
                f"Estado del ítem {item_id} ({item.item_title}) actualizado: "
                f"{old_status} -> {new_status.value}"
            )
            
            return {
                "success": True,
                "item_id": item_id,
                "old_status": old_status,
                "new_status": new_status.value,
                "message": f"Estado actualizado para {item.item_title}"
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error actualizando estado del ítem {item_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Error actualizando estado del ítem {item_id}"
            }
        finally:
            db.close()

    def get_inventory_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen del inventario actual.
        
        Returns:
            Dict con estadísticas del inventario.
        """
        db: Session = next(get_db())
        try:
            # Obtener todos los ítems
            items = db.query(InventoryItem).all()
            
            if not items:
                return {
                    "total_items": 0,
                    "total_invested_usd": 0.0,
                    "total_current_value_usd": 0.0,
                    "total_realized_profit_usd": 0.0,
                    "items_by_status": {},
                    "avg_purchase_price_usd": 0.0,
                    "avg_hold_time_days": 0.0
                }
            
            # Contadores y acumuladores
            total_items = len(items)
            total_invested = sum(item.purchase_price_usd + item.purchase_fee_usd for item in items)
            total_realized_profit = 0.0
            items_by_status = {}
            hold_times = []
            
            for item in items:
                # Contar por estado
                status = item.status
                items_by_status[status] = items_by_status.get(status, 0) + 1
                
                # Calcular profit realizado para ítems vendidos
                if status == InventoryItemStatus.SOLD.value and item.sold_price_usd:
                    profit = (item.sold_price_usd - item.sale_fee_usd - 
                             item.purchase_price_usd - item.purchase_fee_usd - item.listing_fee_usd)
                    total_realized_profit += profit
                
                # Calcular tiempo de tenencia
                if item.sold_date:
                    hold_time = (item.sold_date - item.purchase_date).days
                    hold_times.append(hold_time)
                else:
                    hold_time = (datetime.now(timezone.utc) - item.purchase_date).days
                    hold_times.append(hold_time)
            
            # Calcular valor actual (estimado)
            current_value = total_invested + total_realized_profit  # Simplificado
            
            return {
                "total_items": total_items,
                "total_invested_usd": round(total_invested, 2),
                "total_current_value_usd": round(current_value, 2),
                "total_realized_profit_usd": round(total_realized_profit, 2),
                "roi_percentage": round((total_realized_profit / total_invested * 100) if total_invested > 0 else 0.0, 2),
                "items_by_status": items_by_status,
                "avg_purchase_price_usd": round(total_invested / total_items, 2),
                "avg_hold_time_days": round(sum(hold_times) / len(hold_times), 1) if hold_times else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen del inventario: {e}")
            return {
                "error": str(e),
                "message": "Error obteniendo resumen del inventario"
            }
        finally:
            db.close()

    def get_items_by_status(
        self,
        status: InventoryItemStatus,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene ítems filtrados por estado.
        
        Args:
            status: Estado a filtrar.
            limit: Límite de resultados.
            
        Returns:
            Lista de ítems en el estado especificado.
        """
        db: Session = next(get_db())
        try:
            query = db.query(InventoryItem).filter(InventoryItem.status == status.value)
            
            if limit:
                query = query.limit(limit)
            
            items = query.all()
            
            result = []
            for item in items:
                item_dict = {
                    "id": item.id,
                    "item_title": item.item_title,
                    "asset_id": item.asset_id,
                    "purchase_price_usd": item.purchase_price_usd,
                    "purchase_date": item.purchase_date.isoformat(),
                    "purchase_source": item.purchase_source,
                    "strategy_used": item.strategy_used,
                    "status": item.status,
                    "trade_lock_until": item.trade_lock_until.isoformat() if item.trade_lock_until else None,
                    "listed_price_usd": item.listed_price_usd,
                    "sold_price_usd": item.sold_price_usd,
                    "notes": item.notes
                }
                result.append(item_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo ítems por estado {status.value}: {e}")
            return []
        finally:
            db.close()

    def check_trade_locks(self) -> Dict[str, Any]:
        """
        Revisa y actualiza ítems que ya no están en trade lock.
        
        Returns:
            Dict con el resultado de la operación.
        """
        db: Session = next(get_db())
        try:
            now = datetime.now(timezone.utc)
            
            # Buscar ítems con trade lock que ya debería haber expirado
            expired_locks = db.query(InventoryItem).filter(
                InventoryItem.status == InventoryItemStatus.TRADE_LOCKED.value,
                InventoryItem.trade_lock_until <= now
            ).all()
            
            updated_count = 0
            for item in expired_locks:
                item.status = InventoryItemStatus.PURCHASED.value
                item.updated_at = now
                updated_count += 1
                
                logger.info(f"Trade lock expirado para {item.item_title} (ID: {item.id})")
            
            db.commit()
            
            return {
                "success": True,
                "updated_items": updated_count,
                "message": f"Actualizados {updated_count} ítems con trade lock expirado"
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error revisando trade locks: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Error revisando trade locks"
            }
        finally:
            db.close()

    def get_performance_metrics(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Calcula métricas de rendimiento del trading.
        
        Args:
            days_back: Días hacia atrás para el análisis.
            
        Returns:
            Dict con métricas de rendimiento.
        """
        db: Session = next(get_db())
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            # Obtener ítems del período
            items = db.query(InventoryItem).filter(
                InventoryItem.purchase_date >= cutoff_date
            ).all()
            
            if not items:
                return {
                    "period_days": days_back,
                    "total_trades": 0,
                    "successful_trades": 0,
                    "win_rate": 0.0,
                    "total_profit_usd": 0.0,
                    "avg_profit_per_trade": 0.0,
                    "best_trade_profit": 0.0,
                    "worst_trade_profit": 0.0
                }
            
            # Calcular métricas
            total_trades = len(items)
            successful_trades = 0
            profits = []
            
            for item in items:
                if item.status == InventoryItemStatus.SOLD.value and item.sold_price_usd:
                    profit = (item.sold_price_usd - item.sale_fee_usd - 
                             item.purchase_price_usd - item.purchase_fee_usd - item.listing_fee_usd)
                    profits.append(profit)
                    if profit > 0:
                        successful_trades += 1
            
            total_profit = sum(profits)
            win_rate = (successful_trades / len(profits) * 100) if profits else 0.0
            
            return {
                "period_days": days_back,
                "total_trades": total_trades,
                "completed_trades": len(profits),
                "successful_trades": successful_trades,
                "win_rate": round(win_rate, 2),
                "total_profit_usd": round(total_profit, 2),
                "avg_profit_per_trade": round(total_profit / len(profits), 2) if profits else 0.0,
                "best_trade_profit": round(max(profits), 2) if profits else 0.0,
                "worst_trade_profit": round(min(profits), 2) if profits else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculando métricas de rendimiento: {e}")
            return {
                "error": str(e),
                "message": "Error calculando métricas de rendimiento"
            }
        finally:
            db.close() 