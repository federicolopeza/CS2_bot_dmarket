# core/execution_engine.py
import logging
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass

from core.dmarket_connector import DMarketAPI
from core.inventory_manager import InventoryManager, PurchaseSource, InventoryItemStatus
from core.alerter import Alerter, AlertLevel, AlertType

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class ExecutionMode(Enum):
    """Modos de ejecución del trading."""
    PAPER_TRADING = "paper_trading"     # Solo simulación
    LIVE_TRADING = "live_trading"       # Trading real
    HYBRID = "hybrid"                   # Ambos (paper tracking + live execution)

class ExecutionStatus(Enum):
    """Estados de ejecución de una orden."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class RiskLevel(Enum):
    """Niveles de riesgo para las estrategias."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

@dataclass
class ExecutionOrder:
    """Representa una orden de ejecución."""
    id: str
    strategy: str
    action: str  # "buy" o "sell"
    item_title: str
    asset_id: Optional[str]
    price_usd: float
    opportunity_data: Dict[str, Any]
    risk_level: RiskLevel
    created_at: datetime
    status: ExecutionStatus = ExecutionStatus.PENDING
    execution_attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    error_message: Optional[str] = None
    actual_execution_price: Optional[float] = None

class ExecutionEngine:
    """Motor de ejecución para trading automático."""
    
    def __init__(
        self,
        dmarket_connector: DMarketAPI,
        inventory_manager: InventoryManager,
        alerter: Alerter,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Inicializa el motor de ejecución.
        
        Args:
            dmarket_connector: Conector a la API de DMarket.
            inventory_manager: Gestor de inventario.
            alerter: Sistema de alertas.
            config: Configuración del motor.
        """
        self.connector = dmarket_connector
        self.inventory_manager = inventory_manager
        self.alerter = alerter
        self.config = config or self._get_default_config()
        
        # Estado interno
        self.active_orders: List[ExecutionOrder] = []
        self.execution_history: List[ExecutionOrder] = []
        self.is_running = False
        self.total_executed_today = 0.0
        self.last_reset_date = datetime.now(timezone.utc).date()
        
        logger.info(f"ExecutionEngine inicializado en modo {self.config['execution_mode']}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Obtiene la configuración por defecto."""
        return {
            # Modo de ejecución
            "execution_mode": ExecutionMode.PAPER_TRADING.value,
            
            # Límites de riesgo
            "max_daily_spending_usd": 100.0,
            "max_single_trade_usd": 50.0,
            "max_portfolio_exposure_percentage": 80.0,
            "max_concurrent_orders": 5,
            
            # Configuración de ejecución
            "retry_attempts": 3,
            "retry_delay_seconds": 5.0,
            "order_timeout_minutes": 30,
            "price_tolerance_percentage": 0.02,  # 2% de tolerancia en precios
            
            # Balance mínimo requerido
            "min_balance_usd": 10.0,
            
            # Estrategias habilitadas para ejecución automática
            "enabled_strategies": {
                "basic_flip": True,
                "snipe": True,
                "attribute_premium_flip": True,
                "trade_lock_arbitrage": True,
                "volatility_trading": True
            },
            
            # Filtros de riesgo
            "risk_filters": {
                "min_profit_usd": 0.50,
                "min_profit_percentage": 0.05,  # 5%
                "max_price_usd": 500.0,
                "blacklist_items": [],
                "whitelist_strategies": []
            },
            
            # Configuración de confirmaciones
            "require_manual_confirmation": True,
            "auto_confirm_below_usd": 5.0
        }

    def _reset_daily_limits_if_needed(self):
        """Resetea los límites diarios si ha pasado un día."""
        current_date = datetime.now(timezone.utc).date()
        if current_date > self.last_reset_date:
            self.total_executed_today = 0.0
            self.last_reset_date = current_date
            logger.info("Límites diarios reseteados")

    def _check_risk_limits(self, order: ExecutionOrder) -> Tuple[bool, str]:
        """
        Verifica si una orden cumple con los límites de riesgo.
        
        Returns:
            Tuple[bool, str]: (aprobada, mensaje)
        """
        self._reset_daily_limits_if_needed()
        
        # Verificar límite diario
        if self.total_executed_today + order.price_usd > self.config["max_daily_spending_usd"]:
            return False, f"Excede límite diario (${self.total_executed_today:.2f} + ${order.price_usd:.2f} > ${self.config['max_daily_spending_usd']:.2f})"
        
        # Verificar límite por trade
        if order.price_usd > self.config["max_single_trade_usd"]:
            return False, f"Excede límite por trade (${order.price_usd:.2f} > ${self.config['max_single_trade_usd']:.2f})"
        
        # Verificar órdenes concurrentes
        active_buy_orders = [o for o in self.active_orders if o.action == "buy" and o.status == ExecutionStatus.EXECUTING]
        if len(active_buy_orders) >= self.config["max_concurrent_orders"]:
            return False, f"Máximo de órdenes concurrentes alcanzado ({len(active_buy_orders)}/{self.config['max_concurrent_orders']})"
        
        # Verificar estrategia habilitada
        if not self.config["enabled_strategies"].get(order.strategy, False):
            return False, f"Estrategia {order.strategy} no habilitada para ejecución automática"
        
        # Verificar filtros de riesgo
        opportunity = order.opportunity_data
        if opportunity.get("profit_usd", 0) < self.config["risk_filters"]["min_profit_usd"]:
            return False, f"Profit insuficiente (${opportunity.get('profit_usd', 0):.2f} < ${self.config['risk_filters']['min_profit_usd']:.2f})"
        
        # Verificar ítem en lista negra
        if order.item_title in self.config["risk_filters"]["blacklist_items"]:
            return False, f"Ítem {order.item_title} está en la lista negra"
        
        return True, "Orden aprobada"

    def _check_balance(self) -> Tuple[bool, float]:
        """
        Verifica el balance disponible en DMarket.
        
        Returns:
            Tuple[bool, float]: (suficiente, balance_usd)
        """
        try:
            balance_response = self.connector.get_account_balance()
            
            if "error" in balance_response:
                logger.error(f"Error obteniendo balance: {balance_response}")
                return False, 0.0
            
            usd_balance = 0.0
            for currency in balance_response.get("wallet", []):
                if currency.get("currency") == "USD":
                    usd_balance = float(currency.get("balance", 0)) / 100.0  # Convertir de centavos
                    break
            
            min_balance = self.config["min_balance_usd"]
            return usd_balance >= min_balance, usd_balance
            
        except Exception as e:
            logger.error(f"Error verificando balance: {e}")
            return False, 0.0

    def _execute_buy_order(self, order: ExecutionOrder) -> Tuple[bool, Dict[str, Any]]:
        """
        Ejecuta una orden de compra.
        
        Returns:
            Tuple[bool, Dict]: (éxito, response_data)
        """
        logger.info(f"Ejecutando orden de compra: {order.item_title} por ${order.price_usd:.2f}")
        
        if self.config["execution_mode"] == ExecutionMode.PAPER_TRADING.value:
            # Simulación
            logger.info("Modo paper trading - simulando compra")
            return True, {
                "simulated": True,
                "message": "Compra simulada exitosa",
                "asset_id": order.asset_id or f"sim_{int(time.time())}"
            }
        
        # Ejecución real
        if not order.asset_id:
            return False, {"error": "Asset ID requerido para compra real"}
        
        try:
            response = self.connector.buy_item(order.asset_id, order.price_usd)
            
            if "error" not in response:
                logger.info(f"Compra exitosa: {response}")
                return True, response
            else:
                logger.error(f"Error en compra: {response}")
                return False, response
                
        except Exception as e:
            logger.error(f"Excepción durante compra: {e}")
            return False, {"error": "ExecutionException", "message": str(e)}

    def _execute_sell_order(self, order: ExecutionOrder) -> Tuple[bool, Dict[str, Any]]:
        """
        Ejecuta una orden de venta.
        
        Returns:
            Tuple[bool, Dict]: (éxito, response_data)
        """
        logger.info(f"Ejecutando orden de venta: {order.item_title} por ${order.price_usd:.2f}")
        
        if self.config["execution_mode"] == ExecutionMode.PAPER_TRADING.value:
            # Simulación
            logger.info("Modo paper trading - simulando venta")
            return True, {
                "simulated": True,
                "message": "Venta simulada exitosa",
                "offer_id": f"sim_offer_{int(time.time())}"
            }
        
        # Ejecución real
        if not order.asset_id:
            return False, {"error": "Asset ID requerido para venta real"}
        
        try:
            response = self.connector.create_sell_offer(order.asset_id, order.price_usd)
            
            if "error" not in response:
                logger.info(f"Oferta de venta creada: {response}")
                return True, response
            else:
                logger.error(f"Error creando oferta: {response}")
                return False, response
                
        except Exception as e:
            logger.error(f"Excepción durante venta: {e}")
            return False, {"error": "ExecutionException", "message": str(e)}

    def create_buy_order_from_opportunity(self, opportunity: Dict[str, Any]) -> Optional[ExecutionOrder]:
        """
        Crea una orden de compra a partir de una oportunidad de trading.
        
        Args:
            opportunity: Diccionario con datos de la oportunidad.
            
        Returns:
            ExecutionOrder creada o None si no es válida.
        """
        try:
            # Extraer datos de la oportunidad
            strategy = opportunity.get("strategy", "unknown")
            item_title = opportunity.get("item_title", "Unknown Item")
            
            # Determinar precio y asset_id según el tipo de estrategia
            asset_id = None
            price_usd = 0.0
            
            if strategy == "basic_flip":
                asset_id = opportunity.get("lso_details", {}).get("assetId")
                price_usd = opportunity.get("buy_price_usd", 0.0)
            elif strategy == "snipe":
                asset_id = opportunity.get("offer_details", {}).get("assetId")
                price_usd = opportunity.get("offer_price_usd", 0.0)
            elif strategy == "attribute_premium_flip":
                asset_id = opportunity.get("asset_id")
                price_usd = opportunity.get("buy_price_usd", 0.0)
            elif strategy == "trade_lock_arbitrage":
                asset_id = opportunity.get("asset_id")
                price_usd = opportunity.get("buy_price_usd", 0.0)
            else:
                logger.warning(f"Estrategia {strategy} no soportada para ejecución automática")
                return None
            
            if not asset_id or price_usd <= 0:
                logger.warning(f"Datos insuficientes para crear orden: asset_id={asset_id}, price=${price_usd}")
                return None
            
            # Determinar nivel de riesgo
            profit_percentage = opportunity.get("profit_percentage", 0.0)
            if profit_percentage >= 0.20:  # 20%+
                risk_level = RiskLevel.LOW
            elif profit_percentage >= 0.10:  # 10-20%
                risk_level = RiskLevel.MEDIUM
            elif profit_percentage >= 0.05:  # 5-10%
                risk_level = RiskLevel.HIGH
            else:
                risk_level = RiskLevel.VERY_HIGH
            
            # Crear orden
            order = ExecutionOrder(
                id=f"buy_{strategy}_{int(time.time())}_{asset_id[:8]}",
                strategy=strategy,
                action="buy",
                item_title=item_title,
                asset_id=asset_id,
                price_usd=price_usd,
                opportunity_data=opportunity,
                risk_level=risk_level,
                created_at=datetime.now(timezone.utc)
            )
            
            logger.info(f"Orden de compra creada: {order.id} - {item_title} por ${price_usd:.2f}")
            return order
            
        except Exception as e:
            logger.error(f"Error creando orden de compra: {e}")
            return None

    def execute_order(self, order: ExecutionOrder) -> bool:
        """
        Ejecuta una orden específica.
        
        Returns:
            bool: True si la ejecución fue exitosa.
        """
        logger.info(f"Iniciando ejecución de orden {order.id}")
        
        # Actualizar estado
        order.status = ExecutionStatus.EXECUTING
        order.execution_attempts += 1
        order.last_attempt_at = datetime.now(timezone.utc)
        
        try:
            # Verificar límites de riesgo
            risk_approved, risk_message = self._check_risk_limits(order)
            if not risk_approved:
                order.status = ExecutionStatus.FAILED
                order.error_message = f"Riesgo rechazado: {risk_message}"
                logger.warning(f"Orden {order.id} rechazada por riesgo: {risk_message}")
                
                # Enviar alerta
                self.alerter.send_alert(
                    AlertLevel.MEDIUM,
                    AlertType.EXECUTION_FAILED,
                    f"Orden rechazada por riesgo: {order.item_title}",
                    {"order_id": order.id, "reason": risk_message}
                )
                return False
            
            # Verificar balance (solo para órdenes de compra reales)
            if order.action == "buy" and self.config["execution_mode"] != ExecutionMode.PAPER_TRADING.value:
                balance_ok, current_balance = self._check_balance()
                if not balance_ok:
                    order.status = ExecutionStatus.FAILED
                    order.error_message = f"Balance insuficiente: ${current_balance:.2f}"
                    logger.error(f"Balance insuficiente para orden {order.id}: ${current_balance:.2f}")
                    return False
                
                if current_balance < order.price_usd:
                    order.status = ExecutionStatus.FAILED
                    order.error_message = f"Fondos insuficientes: ${current_balance:.2f} < ${order.price_usd:.2f}"
                    logger.error(f"Fondos insuficientes para orden {order.id}")
                    return False
            
            # Ejecutar según el tipo de acción
            if order.action == "buy":
                success, response = self._execute_buy_order(order)
            elif order.action == "sell":
                success, response = self._execute_sell_order(order)
            else:
                order.status = ExecutionStatus.FAILED
                order.error_message = f"Acción desconocida: {order.action}"
                logger.error(f"Acción desconocida en orden {order.id}: {order.action}")
                return False
            
            if success:
                # Ejecución exitosa
                order.status = ExecutionStatus.COMPLETED
                order.completion_time = datetime.now(timezone.utc)
                order.actual_execution_price = order.price_usd  # Podría ajustarse según response
                
                # Actualizar límites
                if order.action == "buy":
                    self.total_executed_today += order.price_usd
                
                # Registrar en inventory manager
                if order.action == "buy":
                    source = PurchaseSource.DMARKET if self.config["execution_mode"] != ExecutionMode.PAPER_TRADING.value else PurchaseSource.PAPER_TRADING
                    self.inventory_manager.add_purchased_item(
                        item_title=order.item_title,
                        purchase_price_usd=order.price_usd,
                        purchase_source=source,
                        strategy_used=order.strategy,
                        asset_id=order.asset_id,
                        notes=f"Auto-ejecutado por ExecutionEngine. Order ID: {order.id}"
                    )
                
                # Enviar alerta de éxito
                alert_level = AlertLevel.HIGH if order.price_usd > self.config["max_single_trade_usd"] * 0.5 else AlertLevel.MEDIUM
                self.alerter.send_alert(
                    alert_level,
                    AlertType.EXECUTION_SUCCESS,
                    f"Orden ejecutada exitosamente: {order.item_title}",
                    {
                        "order_id": order.id,
                        "strategy": order.strategy,
                        "price_usd": order.price_usd,
                        "execution_mode": self.config["execution_mode"]
                    }
                )
                
                logger.info(f"Orden {order.id} ejecutada exitosamente")
                return True
                
            else:
                # Ejecución fallida
                order.status = ExecutionStatus.FAILED
                order.error_message = response.get("message", "Error desconocido")
                
                # Enviar alerta de fallo
                self.alerter.send_alert(
                    AlertLevel.HIGH,
                    AlertType.EXECUTION_FAILED,
                    f"Fallo en ejecución: {order.item_title}",
                    {
                        "order_id": order.id,
                        "error": order.error_message,
                        "attempts": order.execution_attempts
                    }
                )
                
                logger.error(f"Fallo en ejecución de orden {order.id}: {order.error_message}")
                return False
                
        except Exception as e:
            order.status = ExecutionStatus.FAILED
            order.error_message = f"Excepción durante ejecución: {str(e)}"
            logger.exception(f"Excepción durante ejecución de orden {order.id}: {e}")
            
            # Alerta crítica
            self.alerter.send_alert(
                AlertLevel.CRITICAL,
                AlertType.SYSTEM_ERROR,
                f"Excepción crítica en ejecución: {order.item_title}",
                {"order_id": order.id, "exception": str(e)}
            )
            return False

    def process_opportunities(self, opportunities: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Procesa oportunidades de trading y crea órdenes de ejecución.
        
        Args:
            opportunities: Dict con oportunidades por estrategia.
            
        Returns:
            Dict con resumen del procesamiento.
        """
        logger.info("Procesando oportunidades para ejecución")
        
        total_opportunities = sum(len(opps) for opps in opportunities.values())
        orders_created = 0
        orders_executed = 0
        errors = []
        
        if total_opportunities == 0:
            logger.info("No hay oportunidades para procesar")
            return {
                "total_opportunities": 0,
                "orders_created": 0,
                "orders_executed": 0,
                "errors": []
            }
        
        # Procesar cada estrategia
        for strategy, strategy_opportunities in opportunities.items():
            if not strategy_opportunities:
                continue
                
            logger.info(f"Procesando {len(strategy_opportunities)} oportunidades de {strategy}")
            
            for opportunity in strategy_opportunities:
                try:
                    # Crear orden de compra
                    order = self.create_buy_order_from_opportunity(opportunity)
                    if not order:
                        continue
                    
                    orders_created += 1
                    self.active_orders.append(order)
                    
                    # Decidir si ejecutar automáticamente
                    should_execute = self._should_auto_execute(order)
                    
                    if should_execute:
                        success = self.execute_order(order)
                        if success:
                            orders_executed += 1
                        else:
                            errors.append(f"Fallo ejecutando {order.id}: {order.error_message}")
                    else:
                        logger.info(f"Orden {order.id} creada pero requiere confirmación manual")
                        
                        # Enviar alerta para confirmación manual
                        self.alerter.send_alert(
                            AlertLevel.MEDIUM,
                            AlertType.OPPORTUNITY_FOUND,
                            f"Orden requiere confirmación: {order.item_title}",
                            {
                                "order_id": order.id,
                                "strategy": order.strategy,
                                "price_usd": order.price_usd,
                                "profit_usd": opportunity.get("profit_usd", 0),
                                "risk_level": order.risk_level.value
                            }
                        )
                        
                except Exception as e:
                    error_msg = f"Error procesando oportunidad {strategy}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        # Mover órdenes completadas/fallidas al historial
        self._cleanup_orders()
        
        result = {
            "total_opportunities": total_opportunities,
            "orders_created": orders_created,
            "orders_executed": orders_executed,
            "active_orders": len([o for o in self.active_orders if o.status in [ExecutionStatus.PENDING, ExecutionStatus.EXECUTING]]),
            "errors": errors
        }
        
        logger.info(f"Procesamiento completado: {result}")
        return result

    def _should_auto_execute(self, order: ExecutionOrder) -> bool:
        """
        Determina si una orden debe ejecutarse automáticamente.
        
        Returns:
            bool: True si debe ejecutarse automáticamente.
        """
        # Verificar configuración global
        if self.config["require_manual_confirmation"]:
            # Auto-confirmar solo si está por debajo del umbral
            return order.price_usd <= self.config["auto_confirm_below_usd"]
        
        # Verificar nivel de riesgo
        if order.risk_level == RiskLevel.VERY_HIGH:
            return False
        
        return True

    def _cleanup_orders(self):
        """Mueve órdenes completadas/fallidas al historial."""
        completed_statuses = [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.TIMEOUT]
        
        orders_to_move = [o for o in self.active_orders if o.status in completed_statuses]
        for order in orders_to_move:
            self.active_orders.remove(order)
            self.execution_history.append(order)
        
        if orders_to_move:
            logger.debug(f"Movidas {len(orders_to_move)} órdenes al historial")

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen del estado de ejecución.
        
        Returns:
            Dict con estadísticas de ejecución.
        """
        self._reset_daily_limits_if_needed()
        
        # Contar órdenes por estado
        active_by_status = {}
        for order in self.active_orders:
            status = order.status.value
            active_by_status[status] = active_by_status.get(status, 0) + 1
        
        # Estadísticas del historial (último día)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_history = [o for o in self.execution_history if o.created_at >= yesterday]
        
        completed_orders = [o for o in recent_history if o.status == ExecutionStatus.COMPLETED]
        failed_orders = [o for o in recent_history if o.status == ExecutionStatus.FAILED]
        
        total_profit = 0.0
        for order in completed_orders:
            profit = order.opportunity_data.get("profit_usd", 0.0)
            total_profit += profit
        
        return {
            "execution_mode": self.config["execution_mode"],
            "active_orders": len(self.active_orders),
            "orders_by_status": active_by_status,
            "daily_spending_usd": self.total_executed_today,
            "daily_limit_usd": self.config["max_daily_spending_usd"],
            "remaining_budget_usd": max(0, self.config["max_daily_spending_usd"] - self.total_executed_today),
            "recent_stats": {
                "total_orders_24h": len(recent_history),
                "completed_24h": len(completed_orders),
                "failed_24h": len(failed_orders),
                "success_rate_24h": len(completed_orders) / len(recent_history) * 100 if recent_history else 0,
                "total_profit_24h": total_profit
            }
        } 