# core/kpi_tracker.py
"""
Sistema de seguimiento de KPIs (Key Performance Indicators) para el trading bot de CS2.
Calcula métricas de rendimiento, eficiencia y rentabilidad del sistema.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.data_manager import get_db
from core.inventory_manager import InventoryManager, InventoryItem, InventoryItemStatus

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class KPIPeriod(Enum):
    """Períodos para cálculo de KPIs."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"

@dataclass
class KPIMetrics:
    """Métricas KPI calculadas para un período específico."""
    # Métricas de rentabilidad
    total_profit_usd: float
    total_profit_percentage: float
    realized_profit_usd: float
    unrealized_profit_usd: float
    
    # Métricas de performance
    win_rate_percentage: float
    avg_profit_per_trade_usd: float
    avg_loss_per_trade_usd: float
    profit_factor: float  # Ganancias totales / Pérdidas totales
    
    # Métricas de actividad
    total_trades: int
    successful_trades: int
    failed_trades: int
    avg_trade_duration_hours: float
    
    # Métricas de capital
    capital_deployed_usd: float
    capital_efficiency: float  # Profit / Capital desplegado
    capital_utilization: float  # Capital usado / Capital disponible
    
    # Métricas por estrategia
    strategy_performance: Dict[str, Dict[str, float]]
    
    # Métricas de tiempo
    period: KPIPeriod
    start_date: datetime
    end_date: datetime
    timestamp: datetime

class KPITracker:
    """
    Tracker de KPIs para el sistema de trading.
    """

    def __init__(self, inventory_manager: InventoryManager):
        """
        Inicializa el tracker de KPIs.
        
        Args:
            inventory_manager: Gestor de inventario para acceder a datos.
        """
        self.inventory_manager = inventory_manager
        logger.info("KPITracker inicializado")

    def calculate_kpis(self, period: KPIPeriod = KPIPeriod.ALL_TIME) -> KPIMetrics:
        """
        Calcula KPIs para el período especificado.
        
        Args:
            period: Período para calcular KPIs.
            
        Returns:
            KPIMetrics: Métricas calculadas.
        """
        logger.debug(f"Calculando KPIs para período: {period.value}")
        
        try:
            # Determinar fechas del período
            start_date, end_date = self._get_period_dates(period)
            
            # Obtener datos del período
            all_items = self._get_items_for_period(start_date, end_date)
            sold_items = [item for item in all_items if item.status == InventoryItemStatus.SOLD]
            active_items = [item for item in all_items if item.status in [
                InventoryItemStatus.PURCHASED, InventoryItemStatus.LISTED
            ]]
            
            # Calcular métricas de rentabilidad
            total_profit = self._calculate_total_profit(all_items)
            realized_profit = self._calculate_realized_profit(sold_items)
            unrealized_profit = self._calculate_unrealized_profit(active_items)
            
            # Calcular porcentaje de ganancia total
            total_invested = sum(item.purchase_price_usd for item in all_items)
            total_profit_percentage = (total_profit / total_invested * 100) if total_invested > 0 else 0.0
            
            # Calcular métricas de performance
            win_rate = self._calculate_win_rate(sold_items)
            avg_profit_per_trade = self._calculate_avg_profit_per_trade(sold_items, profit_only=True)
            avg_loss_per_trade = self._calculate_avg_loss_per_trade(sold_items)
            profit_factor = self._calculate_profit_factor(sold_items)
            
            # Calcular métricas de actividad
            total_trades = len(all_items)
            successful_trades = len([item for item in sold_items if self._is_profitable_trade(item)])
            failed_trades = len(sold_items) - successful_trades
            avg_duration = self._calculate_avg_trade_duration(sold_items)
            
            # Calcular métricas de capital
            capital_deployed = total_invested
            capital_efficiency = (total_profit / capital_deployed) if capital_deployed > 0 else 0.0
            capital_utilization = self._calculate_capital_utilization(active_items)
            
            # Calcular performance por estrategia
            strategy_performance = self._calculate_strategy_performance(all_items)
            
            return KPIMetrics(
                total_profit_usd=total_profit,
                total_profit_percentage=total_profit_percentage,
                realized_profit_usd=realized_profit,
                unrealized_profit_usd=unrealized_profit,
                win_rate_percentage=win_rate,
                avg_profit_per_trade_usd=avg_profit_per_trade,
                avg_loss_per_trade_usd=avg_loss_per_trade,
                profit_factor=profit_factor,
                total_trades=total_trades,
                successful_trades=successful_trades,
                failed_trades=failed_trades,
                avg_trade_duration_hours=avg_duration,
                capital_deployed_usd=capital_deployed,
                capital_efficiency=capital_efficiency,
                capital_utilization=capital_utilization,
                strategy_performance=strategy_performance,
                period=period,
                start_date=start_date,
                end_date=end_date,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error calculando KPIs: {e}")
            # Retornar métricas vacías en caso de error
            now = datetime.now(timezone.utc)
            return KPIMetrics(
                total_profit_usd=0.0,
                total_profit_percentage=0.0,
                realized_profit_usd=0.0,
                unrealized_profit_usd=0.0,
                win_rate_percentage=0.0,
                avg_profit_per_trade_usd=0.0,
                avg_loss_per_trade_usd=0.0,
                profit_factor=0.0,
                total_trades=0,
                successful_trades=0,
                failed_trades=0,
                avg_trade_duration_hours=0.0,
                capital_deployed_usd=0.0,
                capital_efficiency=0.0,
                capital_utilization=0.0,
                strategy_performance={},
                period=period,
                start_date=now,
                end_date=now,
                timestamp=now
            )

    def _get_period_dates(self, period: KPIPeriod) -> Tuple[datetime, datetime]:
        """Obtiene fechas de inicio y fin para el período especificado."""
        now = datetime.now(timezone.utc)
        
        if period == KPIPeriod.ALL_TIME:
            # Desde el inicio de los tiempos hasta ahora
            start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end_date = now
        elif period == KPIPeriod.DAILY:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == KPIPeriod.WEEKLY:
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = now
        elif period == KPIPeriod.MONTHLY:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == KPIPeriod.QUARTERLY:
            quarter = (now.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            start_date = now.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == KPIPeriod.YEARLY:
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        else:
            start_date = now
            end_date = now
            
        return start_date, end_date

    def _get_items_for_period(self, start_date: datetime, end_date: datetime) -> List[InventoryItem]:
        """Obtiene ítems comprados en el período especificado."""
        try:
            db: Session = next(get_db())
            items = db.query(InventoryItem).filter(
                InventoryItem.purchase_date >= start_date,
                InventoryItem.purchase_date <= end_date
            ).all()
            return items
        except Exception as e:
            logger.error(f"Error obteniendo ítems para período: {e}")
            return []
        finally:
            db.close()

    def _calculate_total_profit(self, items: List[InventoryItem]) -> float:
        """Calcula ganancia total (realizada + no realizada)."""
        total_profit = 0.0
        
        for item in items:
            if item.status == InventoryItemStatus.SOLD:
                # Ganancia realizada
                profit = (item.sold_price_usd or 0.0) - item.purchase_price_usd
                total_profit += profit
            elif item.status in [InventoryItemStatus.PURCHASED, InventoryItemStatus.LISTED]:
                # Ganancia no realizada (estimada con precio actual - usar precio de compra como estimación)
                current_value = item.purchase_price_usd  # Simplificación temporal
                unrealized_profit = current_value - item.purchase_price_usd
                total_profit += unrealized_profit
                
        return total_profit

    def _calculate_realized_profit(self, sold_items: List[InventoryItem]) -> float:
        """Calcula ganancia realizada de ítems vendidos."""
        realized_profit = 0.0
        
        for item in sold_items:
            if item.sold_price_usd:
                profit = item.sold_price_usd - item.purchase_price_usd
                realized_profit += profit
                
        return realized_profit

    def _calculate_unrealized_profit(self, active_items: List[InventoryItem]) -> float:
        """Calcula ganancia no realizada de ítems activos."""
        unrealized_profit = 0.0
        
        for item in active_items:
            current_value = item.purchase_price_usd  # Simplificación temporal
            profit = current_value - item.purchase_price_usd
            unrealized_profit += profit
            
        return unrealized_profit

    def _calculate_win_rate(self, sold_items: List[InventoryItem]) -> float:
        """Calcula tasa de éxito (% de trades rentables)."""
        if not sold_items:
            return 0.0
            
        profitable_trades = sum(1 for item in sold_items if self._is_profitable_trade(item))
        return (profitable_trades / len(sold_items)) * 100

    def _is_profitable_trade(self, item: InventoryItem) -> bool:
        """Determina si un trade fue rentable."""
        if item.sold_price_usd is None:
            return False
        return item.sold_price_usd > item.purchase_price_usd

    def _calculate_avg_profit_per_trade(self, sold_items: List[InventoryItem], profit_only: bool = False) -> float:
        """Calcula ganancia promedio por trade."""
        if not sold_items:
            return 0.0
            
        if profit_only:
            # Solo trades rentables
            profitable_items = [item for item in sold_items if self._is_profitable_trade(item)]
            if not profitable_items:
                return 0.0
            total_profit = sum((item.sold_price_usd or 0) - item.purchase_price_usd for item in profitable_items)
            return total_profit / len(profitable_items)
        else:
            # Todos los trades
            total_profit = sum((item.sold_price_usd or 0) - item.purchase_price_usd for item in sold_items)
            return total_profit / len(sold_items)

    def _calculate_avg_loss_per_trade(self, sold_items: List[InventoryItem]) -> float:
        """Calcula pérdida promedio por trade (solo trades perdedores)."""
        losing_items = [item for item in sold_items if not self._is_profitable_trade(item)]
        
        if not losing_items:
            return 0.0
            
        total_loss = sum((item.sold_price_usd or 0) - item.purchase_price_usd for item in losing_items)
        return abs(total_loss / len(losing_items))  # Retornar valor absoluto

    def _calculate_profit_factor(self, sold_items: List[InventoryItem]) -> float:
        """Calcula factor de ganancia (ganancias totales / pérdidas totales)."""
        if not sold_items:
            return 0.0
            
        total_gains = 0.0
        total_losses = 0.0
        
        for item in sold_items:
            profit = (item.sold_price_usd or 0) - item.purchase_price_usd
            if profit > 0:
                total_gains += profit
            else:
                total_losses += abs(profit)
                
        if total_losses == 0:
            return float('inf') if total_gains > 0 else 0.0
            
        return total_gains / total_losses

    def _calculate_avg_trade_duration(self, sold_items: List[InventoryItem]) -> float:
        """Calcula duración promedio de trades en horas."""
        if not sold_items:
            return 0.0
            
        total_duration_hours = 0.0
        valid_items = 0
        
        for item in sold_items:
            if item.sold_date and item.purchase_date:
                duration = item.sold_date - item.purchase_date
                total_duration_hours += duration.total_seconds() / 3600
                valid_items += 1
                
        return total_duration_hours / valid_items if valid_items > 0 else 0.0

    def _calculate_capital_utilization(self, active_items: List[InventoryItem]) -> float:
        """Calcula utilización de capital (capital usado / capital total disponible)."""
        # Obtener balance disponible
        try:
            summary = self.inventory_manager.get_inventory_summary()
            available_balance = summary.get('available_balance_usd', 0.0)
            invested_amount = summary.get('total_invested_usd', 0.0)
            
            total_capital = available_balance + invested_amount
            
            if total_capital <= 0:
                return 0.0
                
            return (invested_amount / total_capital) * 100
            
        except Exception as e:
            logger.warning(f"Error calculando utilización de capital: {e}")
            return 0.0

    def _calculate_strategy_performance(self, items: List[InventoryItem]) -> Dict[str, Dict[str, float]]:
        """Calcula performance por estrategia."""
        strategy_stats = {}
        
        # Agrupar por estrategia
        strategies = {}
        for item in items:
            strategy = item.strategy_used or "unknown"
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(item)
        
        # Calcular métricas por estrategia
        for strategy, strategy_items in strategies.items():
            sold_items = [item for item in strategy_items if item.status == InventoryItemStatus.SOLD]
            
            # Calcular métricas básicas
            total_trades = len(strategy_items)
            total_profit = self._calculate_total_profit(strategy_items)
            win_rate = self._calculate_win_rate(sold_items)
            avg_profit = self._calculate_avg_profit_per_trade(sold_items) if sold_items else 0.0
            
            # Calcular capital utilizado
            capital_used = sum(item.purchase_price_usd for item in strategy_items)
            roi = (total_profit / capital_used * 100) if capital_used > 0 else 0.0
            
            strategy_stats[strategy] = {
                "total_trades": total_trades,
                "total_profit_usd": total_profit,
                "win_rate_percentage": win_rate,
                "avg_profit_per_trade_usd": avg_profit,
                "capital_used_usd": capital_used,
                "roi_percentage": roi
            }
            
        return strategy_stats

    def get_performance_dashboard(self) -> Dict[str, Any]:
        """
        Genera un dashboard completo de performance.
        
        Returns:
            Dict con métricas de múltiples períodos y comparaciones.
        """
        logger.debug("Generando dashboard de performance")
        
        try:
            # Calcular KPIs para diferentes períodos
            daily_kpis = self.calculate_kpis(KPIPeriod.DAILY)
            weekly_kpis = self.calculate_kpis(KPIPeriod.WEEKLY)
            monthly_kpis = self.calculate_kpis(KPIPeriod.MONTHLY)
            all_time_kpis = self.calculate_kpis(KPIPeriod.ALL_TIME)
            
            # Calcular tendencias
            trends = self._calculate_trends()
            
            # Top performers
            top_performers = self._get_top_performing_items()
            worst_performers = self._get_worst_performing_items()
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "kpis": {
                    "daily": self._kpi_metrics_to_dict(daily_kpis),
                    "weekly": self._kpi_metrics_to_dict(weekly_kpis),
                    "monthly": self._kpi_metrics_to_dict(monthly_kpis),
                    "all_time": self._kpi_metrics_to_dict(all_time_kpis)
                },
                "trends": trends,
                "top_performers": top_performers,
                "worst_performers": worst_performers,
                "strategy_comparison": all_time_kpis.strategy_performance,
                "summary": {
                    "current_status": self._get_current_status_summary(),
                    "key_insights": self._generate_key_insights(all_time_kpis),
                    "recommendations": self._generate_recommendations(all_time_kpis)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generando dashboard: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _kpi_metrics_to_dict(self, kpis: KPIMetrics) -> Dict[str, Any]:
        """Convierte KPIMetrics a diccionario."""
        return {
            "total_profit_usd": kpis.total_profit_usd,
            "total_profit_percentage": kpis.total_profit_percentage,
            "realized_profit_usd": kpis.realized_profit_usd,
            "unrealized_profit_usd": kpis.unrealized_profit_usd,
            "win_rate_percentage": kpis.win_rate_percentage,
            "avg_profit_per_trade_usd": kpis.avg_profit_per_trade_usd,
            "avg_loss_per_trade_usd": kpis.avg_loss_per_trade_usd,
            "profit_factor": kpis.profit_factor,
            "total_trades": kpis.total_trades,
            "successful_trades": kpis.successful_trades,
            "failed_trades": kpis.failed_trades,
            "avg_trade_duration_hours": kpis.avg_trade_duration_hours,
            "capital_deployed_usd": kpis.capital_deployed_usd,
            "capital_efficiency": kpis.capital_efficiency,
            "capital_utilization": kpis.capital_utilization,
            "period": kpis.period.value,
            "start_date": kpis.start_date.isoformat(),
            "end_date": kpis.end_date.isoformat()
        }

    def _calculate_trends(self) -> Dict[str, Any]:
        """Calcula tendencias de performance."""
        try:
            # Obtener KPIs de los últimos 7 días
            daily_profits = []
            for i in range(7):
                date = datetime.now(timezone.utc) - timedelta(days=i)
                start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                items = self._get_items_for_period(start_date, end_date)
                daily_profit = self._calculate_realized_profit([
                    item for item in items if item.status == InventoryItemStatus.SOLD
                ])
                daily_profits.append({
                    "date": start_date.isoformat(),
                    "profit_usd": daily_profit
                })
            
            # Calcular tendencia
            recent_avg = sum(day["profit_usd"] for day in daily_profits[:3]) / 3
            older_avg = sum(day["profit_usd"] for day in daily_profits[4:]) / 3
            
            trend_direction = "up" if recent_avg > older_avg else "down" if recent_avg < older_avg else "stable"
            trend_percentage = ((recent_avg - older_avg) / older_avg * 100) if older_avg != 0 else 0.0
            
            return {
                "daily_profits": list(reversed(daily_profits)),
                "trend_direction": trend_direction,
                "trend_percentage": trend_percentage,
                "recent_avg_daily_profit": recent_avg
            }
            
        except Exception as e:
            logger.warning(f"Error calculando tendencias: {e}")
            return {"error": str(e)}

    def _get_top_performing_items(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Obtiene los ítems con mejor performance."""
        try:
            db: Session = next(get_db())
            sold_items = db.query(InventoryItem).filter(
                InventoryItem.status == InventoryItemStatus.SOLD,
                InventoryItem.sold_price_usd.isnot(None)
            ).all()
            
            # Calcular profit para cada ítem y ordenar
            item_profits = []
            for item in sold_items:
                profit = (item.sold_price_usd or 0) - item.purchase_price_usd
                profit_percentage = (profit / item.purchase_price_usd * 100) if item.purchase_price_usd > 0 else 0
                
                item_profits.append({
                    "item_title": item.item_title,
                    "purchase_price_usd": item.purchase_price_usd,
                    "sold_price_usd": item.sold_price_usd,
                    "profit_usd": profit,
                    "profit_percentage": profit_percentage,
                    "strategy_used": item.strategy_used,
                    "trade_duration_hours": (
                        (item.sold_date - item.purchase_date).total_seconds() / 3600
                        if item.sold_date and item.purchase_date else 0
                    )
                })
            
            # Ordenar por profit_percentage descendente y tomar top 5
            top_items = sorted(item_profits, key=lambda x: x["profit_percentage"], reverse=True)[:limit]
            return top_items
            
        except Exception as e:
            logger.warning(f"Error obteniendo top performers: {e}")
            return []
        finally:
            db.close()

    def _get_worst_performing_items(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Obtiene los ítems con peor performance."""
        try:
            db: Session = next(get_db())
            sold_items = db.query(InventoryItem).filter(
                InventoryItem.status == InventoryItemStatus.SOLD,
                InventoryItem.sold_price_usd.isnot(None)
            ).all()
            
            # Calcular profit para cada ítem y ordenar
            item_profits = []
            for item in sold_items:
                profit = (item.sold_price_usd or 0) - item.purchase_price_usd
                profit_percentage = (profit / item.purchase_price_usd * 100) if item.purchase_price_usd > 0 else 0
                
                item_profits.append({
                    "item_title": item.item_title,
                    "purchase_price_usd": item.purchase_price_usd,
                    "sold_price_usd": item.sold_price_usd,
                    "profit_usd": profit,
                    "profit_percentage": profit_percentage,
                    "strategy_used": item.strategy_used,
                    "trade_duration_hours": (
                        (item.sold_date - item.purchase_date).total_seconds() / 3600
                        if item.sold_date and item.purchase_date else 0
                    )
                })
            
            # Ordenar por profit_percentage ascendente y tomar bottom 5
            worst_items = sorted(item_profits, key=lambda x: x["profit_percentage"])[:limit]
            return worst_items
            
        except Exception as e:
            logger.warning(f"Error obteniendo worst performers: {e}")
            return []
        finally:
            db.close()

    def _get_current_status_summary(self) -> Dict[str, Any]:
        """Obtiene resumen del estado actual."""
        try:
            summary = self.inventory_manager.get_inventory_summary()
            return {
                "total_items": summary.get('total_items', 0),
                "total_invested_usd": summary.get('total_invested_usd', 0.0),
                "available_balance_usd": summary.get('available_balance_usd', 0.0),
                "items_for_sale": summary.get('items_for_sale', 0),
                "items_sold": summary.get('items_sold', 0),
                "current_portfolio_value_usd": summary.get('current_portfolio_value_usd', 0.0)
            }
        except Exception as e:
            logger.warning(f"Error obteniendo estado actual: {e}")
            return {}

    def _generate_key_insights(self, kpis: KPIMetrics) -> List[str]:
        """Genera insights clave basados en KPIs."""
        insights = []
        
        # Insight de rentabilidad
        if kpis.total_profit_percentage > 20:
            insights.append(f"📈 Excelente rentabilidad: {kpis.total_profit_percentage:.1f}% de ganancia total")
        elif kpis.total_profit_percentage > 10:
            insights.append(f"✅ Buena rentabilidad: {kpis.total_profit_percentage:.1f}% de ganancia total")
        elif kpis.total_profit_percentage > 0:
            insights.append(f"🔍 Rentabilidad modesta: {kpis.total_profit_percentage:.1f}% de ganancia total")
        else:
            insights.append(f"⚠️ Portfolio en pérdidas: {kpis.total_profit_percentage:.1f}%")
        
        # Insight de win rate
        if kpis.win_rate_percentage > 80:
            insights.append(f"🎯 Excelente tasa de éxito: {kpis.win_rate_percentage:.1f}%")
        elif kpis.win_rate_percentage > 60:
            insights.append(f"👍 Buena tasa de éxito: {kpis.win_rate_percentage:.1f}%")
        elif kpis.win_rate_percentage > 40:
            insights.append(f"⚖️ Tasa de éxito moderada: {kpis.win_rate_percentage:.1f}%")
        else:
            insights.append(f"📉 Baja tasa de éxito: {kpis.win_rate_percentage:.1f}%")
        
        # Insight de profit factor
        if kpis.profit_factor > 2.0:
            insights.append(f"💪 Excelente factor de ganancia: {kpis.profit_factor:.2f}")
        elif kpis.profit_factor > 1.5:
            insights.append(f"✅ Buen factor de ganancia: {kpis.profit_factor:.2f}")
        elif kpis.profit_factor > 1.0:
            insights.append(f"⚡ Factor de ganancia positivo: {kpis.profit_factor:.2f}")
        else:
            insights.append(f"⚠️ Factor de ganancia bajo: {kpis.profit_factor:.2f}")
        
        # Insight de estrategias
        if kpis.strategy_performance:
            best_strategy = max(kpis.strategy_performance.items(), 
                              key=lambda x: x[1].get('roi_percentage', 0))
            insights.append(f"🏆 Mejor estrategia: {best_strategy[0]} "
                          f"(ROI: {best_strategy[1].get('roi_percentage', 0):.1f}%)")
        
        return insights

    def _generate_recommendations(self, kpis: KPIMetrics) -> List[str]:
        """Genera recomendaciones basadas en KPIs."""
        recommendations = []
        
        # Recomendaciones basadas en win rate
        if kpis.win_rate_percentage < 50:
            recommendations.append("🔧 Considera revisar y ajustar las estrategias de trading")
            recommendations.append("📊 Analiza los trades perdedores para identificar patrones")
        
        # Recomendaciones basadas en profit factor
        if kpis.profit_factor < 1.2:
            recommendations.append("💰 Mejora la gestión de riesgos para aumentar el profit factor")
            recommendations.append("🎯 Considera implementar stop-losses más estrictos")
        
        # Recomendaciones basadas en duración de trades
        if kpis.avg_trade_duration_hours > 72:  # Más de 3 días
            recommendations.append("⏰ Los trades están tomando mucho tiempo - considera estrategias más ágiles")
        
        # Recomendaciones basadas en capital
        if kpis.capital_utilization < 50:
            recommendations.append("📈 Capital subutilizado - considera aumentar la actividad de trading")
        elif kpis.capital_utilization > 90:
            recommendations.append("⚠️ Alto riesgo de concentración - diversifica más el portfolio")
        
        # Recomendaciones basadas en estrategias
        if kpis.strategy_performance:
            strategies_count = len(kpis.strategy_performance)
            if strategies_count == 1:
                recommendations.append("🔄 Considera diversificar con múltiples estrategias")
            
            # Identificar estrategias poco rentables
            poor_strategies = [
                name for name, perf in kpis.strategy_performance.items()
                if perf.get('roi_percentage', 0) < 0
            ]
            if poor_strategies:
                recommendations.append(f"❌ Considera pausar estrategias poco rentables: {', '.join(poor_strategies)}")
        
        return recommendations 