# core/risk_manager.py
"""
Sistema integral de gestión de riesgos para el trading bot de CS2.
Incluye límites de exposición, stop-loss automático, diversificación de portfolio,
análisis de correlación y métricas de riesgo avanzadas.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session

from core.data_manager import get_db
from core.inventory_manager import InventoryManager, InventoryItem, InventoryItemStatus

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Niveles de riesgo para diferentes tipos de operaciones."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"

class RiskAlert(Enum):
    """Tipos de alertas de riesgo."""
    EXPOSURE_LIMIT_REACHED = "exposure_limit_reached"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    CONCENTRATION_WARNING = "concentration_warning"
    CORRELATION_RISK = "correlation_risk"
    PORTFOLIO_DRAWDOWN = "portfolio_drawdown"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_RISK = "liquidity_risk"

@dataclass
class RiskMetrics:
    """Métricas de riesgo calculadas para el portfolio."""
    total_exposure_usd: float
    max_single_position_usd: float
    max_single_position_percentage: float
    portfolio_beta: float
    sharpe_ratio: float
    max_drawdown_percentage: float
    value_at_risk_95: float  # VaR al 95%
    expected_shortfall: float  # Conditional VaR
    concentration_index: float  # Herfindahl index
    correlation_risk_score: float
    liquidity_score: float
    volatility_score: float
    diversification_score: float
    overall_risk_score: float
    risk_level: RiskLevel
    timestamp: datetime

@dataclass
class StopLossOrder:
    """Orden de stop-loss para un ítem específico."""
    item_id: int
    item_title: str
    stop_loss_price_usd: float
    current_price_usd: float
    purchase_price_usd: float
    stop_loss_percentage: float
    created_at: datetime
    triggered: bool = False
    triggered_at: Optional[datetime] = None
    executed: bool = False
    executed_at: Optional[datetime] = None

@dataclass
class RiskLimits:
    """Límites de riesgo configurables."""
    max_portfolio_exposure_usd: float = 1000.0
    max_single_position_usd: float = 200.0
    max_single_position_percentage: float = 0.20  # 20%
    max_sector_concentration_percentage: float = 0.40  # 40%
    max_correlation_exposure: float = 0.60  # 60%
    stop_loss_percentage: float = 0.15  # 15%
    max_daily_loss_usd: float = 100.0
    max_drawdown_percentage: float = 0.25  # 25%
    min_liquidity_score: float = 0.3
    max_volatility_score: float = 0.8

class RiskManager:
    """
    Gestor integral de riesgos para el sistema de trading.
    """

    def __init__(
        self,
        inventory_manager: InventoryManager,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Inicializa el gestor de riesgos.
        
        Args:
            inventory_manager: Gestor de inventario para acceder a posiciones.
            config: Configuración opcional para límites y parámetros.
        """
        self.inventory_manager = inventory_manager
        self.config = config or self._get_default_config()
        self.risk_limits = self._parse_risk_limits()
        self.stop_loss_orders: List[StopLossOrder] = []
        self.risk_alerts_history: List[Dict[str, Any]] = []
        
        logger.info(f"RiskManager inicializado con límites: {self.risk_limits}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto para el gestor de riesgos."""
        return {
            # Límites de exposición
            "max_portfolio_exposure_usd": 1000.0,
            "max_single_position_usd": 200.0,
            "max_single_position_percentage": 0.20,
            "max_sector_concentration_percentage": 0.40,
            
            # Stop-loss configuration
            "default_stop_loss_percentage": 0.15,
            "adaptive_stop_loss": True,
            "stop_loss_trailing": True,
            "min_stop_loss_percentage": 0.05,
            "max_stop_loss_percentage": 0.30,
            
            # Límites de pérdidas
            "max_daily_loss_usd": 100.0,
            "max_weekly_loss_usd": 500.0,
            "max_monthly_loss_usd": 1500.0,
            "max_drawdown_percentage": 0.25,
            
            # Diversificación
            "min_diversification_score": 0.6,
            "max_correlation_exposure": 0.60,
            "sector_limits": {
                "rifles": 0.30,
                "pistols": 0.25,
                "knives": 0.40,
                "gloves": 0.30,
                "stickers": 0.20
            },
            
            # Liquidez y volatilidad
            "min_liquidity_score": 0.3,
            "max_volatility_score": 0.8,
            "liquidity_weight": 0.3,
            "volatility_weight": 0.4,
            
            # Alertas
            "enable_risk_alerts": True,
            "alert_thresholds": {
                "exposure_warning": 0.80,  # 80% del límite
                "concentration_warning": 0.75,
                "correlation_warning": 0.70,
                "volatility_warning": 0.75
            }
        }

    def _parse_risk_limits(self) -> RiskLimits:
        """Convierte la configuración en límites de riesgo estructurados."""
        return RiskLimits(
            max_portfolio_exposure_usd=self.config.get("max_portfolio_exposure_usd", 1000.0),
            max_single_position_usd=self.config.get("max_single_position_usd", 200.0),
            max_single_position_percentage=self.config.get("max_single_position_percentage", 0.20),
            max_sector_concentration_percentage=self.config.get("max_sector_concentration_percentage", 0.40),
            max_correlation_exposure=self.config.get("max_correlation_exposure", 0.60),
            stop_loss_percentage=self.config.get("default_stop_loss_percentage", 0.15),
            max_daily_loss_usd=self.config.get("max_daily_loss_usd", 100.0),
            max_drawdown_percentage=self.config.get("max_drawdown_percentage", 0.25),
            min_liquidity_score=self.config.get("min_liquidity_score", 0.3),
            max_volatility_score=self.config.get("max_volatility_score", 0.8)
        )

    def calculate_risk_metrics(self) -> RiskMetrics:
        """
        Calcula métricas comprehensivas de riesgo para el portfolio actual.
        
        Returns:
            RiskMetrics: Objeto con todas las métricas de riesgo calculadas.
        """
        logger.debug("Calculando métricas de riesgo del portfolio")
        
        try:
            # Obtener inventario actual
            inventory_summary = self.inventory_manager.get_inventory_summary()
            active_items = self.inventory_manager.get_items_by_status(
                [InventoryItemStatus.PURCHASED, InventoryItemStatus.LISTED]
            )
            
            # Calcular exposición total
            total_exposure = inventory_summary['total_invested_usd']
            
            # Calcular posición más grande
            max_position_usd = 0.0
            max_position_percentage = 0.0
            
            if active_items and total_exposure > 0:
                position_values = [item.purchase_price_usd for item in active_items]
                max_position_usd = max(position_values)
                max_position_percentage = max_position_usd / total_exposure
            
            # Calcular concentración (Herfindahl Index)
            concentration_index = self._calculate_concentration_index(active_items, total_exposure)
            
            # Calcular diversificación
            diversification_score = self._calculate_diversification_score(active_items)
            
            # Calcular correlación de riesgo
            correlation_risk_score = self._calculate_correlation_risk(active_items)
            
            # Calcular puntuación de liquidez
            liquidity_score = self._calculate_liquidity_score(active_items)
            
            # Calcular volatilidad
            volatility_score = self._calculate_volatility_score(active_items)
            
            # Calcular métricas de performance
            performance_metrics = self.inventory_manager.get_performance_metrics()
            max_drawdown = abs(performance_metrics.get('max_drawdown_percentage', 0.0))
            sharpe_ratio = performance_metrics.get('sharpe_ratio', 0.0)
            
            # Calcular VaR y Expected Shortfall (simplificado)
            var_95 = self._calculate_value_at_risk(active_items, 0.95)
            expected_shortfall = self._calculate_expected_shortfall(active_items, 0.95)
            
            # Calcular beta del portfolio (vs mercado general)
            portfolio_beta = self._calculate_portfolio_beta(active_items)
            
            # Calcular puntuación general de riesgo
            overall_risk_score = self._calculate_overall_risk_score(
                concentration_index, correlation_risk_score, volatility_score,
                max_position_percentage, max_drawdown
            )
            
            # Determinar nivel de riesgo
            risk_level = self._determine_risk_level(overall_risk_score)
            
            metrics = RiskMetrics(
                total_exposure_usd=total_exposure,
                max_single_position_usd=max_position_usd,
                max_single_position_percentage=max_position_percentage,
                portfolio_beta=portfolio_beta,
                sharpe_ratio=sharpe_ratio,
                max_drawdown_percentage=max_drawdown,
                value_at_risk_95=var_95,
                expected_shortfall=expected_shortfall,
                concentration_index=concentration_index,
                correlation_risk_score=correlation_risk_score,
                liquidity_score=liquidity_score,
                volatility_score=volatility_score,
                diversification_score=diversification_score,
                overall_risk_score=overall_risk_score,
                risk_level=risk_level,
                timestamp=datetime.now(timezone.utc)
            )
            
            logger.info(f"Métricas de riesgo calculadas: Risk Level = {risk_level.value}, "
                       f"Overall Score = {overall_risk_score:.3f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculando métricas de riesgo: {e}")
            # Retornar métricas por defecto en caso de error
            return RiskMetrics(
                total_exposure_usd=0.0,
                max_single_position_usd=0.0,
                max_single_position_percentage=0.0,
                portfolio_beta=1.0,
                sharpe_ratio=0.0,
                max_drawdown_percentage=0.0,
                value_at_risk_95=0.0,
                expected_shortfall=0.0,
                concentration_index=0.0,
                correlation_risk_score=0.0,
                liquidity_score=1.0,
                volatility_score=0.0,
                diversification_score=1.0,
                overall_risk_score=0.0,
                risk_level=RiskLevel.LOW,
                timestamp=datetime.now(timezone.utc)
            )

    def _calculate_concentration_index(self, items: List[InventoryItem], total_exposure: float) -> float:
        """Calcula el índice de concentración de Herfindahl."""
        if not items or total_exposure <= 0:
            return 0.0
        
        # Calcular peso de cada posición
        weights = []
        for item in items:
            weight = item.purchase_price_usd / total_exposure
            weights.append(weight)
        
        # Herfindahl Index = suma de pesos al cuadrado
        herfindahl = sum(w**2 for w in weights)
        return herfindahl

    def _calculate_diversification_score(self, items: List[InventoryItem]) -> float:
        """Calcula puntuación de diversificación basada en categorías de ítems."""
        if not items:
            return 1.0
        
        # Categorizar ítems por tipo (rifle, pistol, knife, etc.)
        categories = {}
        for item in items:
            category = self._categorize_item(item.item_title)
            categories[category] = categories.get(category, 0) + item.purchase_price_usd
        
        total_value = sum(categories.values())
        if total_value <= 0:
            return 1.0
        
        # Calcular distribución entre categorías
        category_weights = [value / total_value for value in categories.values()]
        
        # Penalizar concentración excesiva en una categoría
        max_weight = max(category_weights) if category_weights else 0
        num_categories = len(categories)
        
        # Score más alto = mejor diversificación
        if num_categories >= 3 and max_weight <= 0.5:
            return 0.9
        elif num_categories >= 2 and max_weight <= 0.7:
            return 0.7
        elif max_weight <= 0.8:
            return 0.5
        else:
            return 0.2

    def _categorize_item(self, item_title: str) -> str:
        """Categoriza un ítem basado en su nombre."""
        title_lower = item_title.lower()
        
        if any(weapon in title_lower for weapon in ['ak-47', 'm4a4', 'm4a1-s', 'awp', 'famas', 'galil']):
            return 'rifle'
        elif any(weapon in title_lower for weapon in ['glock', 'usp', 'p250', 'five-seven', 'cz75', 'tec-9']):
            return 'pistol'
        elif 'knife' in title_lower or '★' in item_title:
            return 'knife'
        elif 'gloves' in title_lower or '★' in item_title:
            return 'gloves'
        elif 'sticker' in title_lower:
            return 'sticker'
        else:
            return 'other'

    def _calculate_correlation_risk(self, items: List[InventoryItem]) -> float:
        """Calcula riesgo de correlación entre posiciones."""
        if len(items) <= 1:
            return 0.0
        
        # Simplificado: asumir correlación alta entre ítems de la misma categoría
        categories = {}
        total_value = 0.0
        
        for item in items:
            category = self._categorize_item(item.item_title)
            categories[category] = categories.get(category, 0) + item.purchase_price_usd
            total_value += item.purchase_price_usd
        
        if total_value <= 0:
            return 0.0
        
        # Calcular riesgo de correlación como concentración ponderada
        correlation_risk = 0.0
        for category, value in categories.items():
            weight = value / total_value
            if weight > 0.3:  # Si más del 30% está en una categoría
                correlation_risk += (weight - 0.3) * 2  # Penalizar concentración
        
        return min(correlation_risk, 1.0)  # Limitar a [0, 1]

    def _calculate_liquidity_score(self, items: List[InventoryItem]) -> float:
        """Calcula puntuación de liquidez del portfolio."""
        if not items:
            return 1.0
        
        # Simplificado: asumir liquidez basada en precio y categoría
        total_value = 0.0
        weighted_liquidity = 0.0
        
        for item in items:
            # Liquidez más alta para ítems de menor precio
            if item.purchase_price_usd <= 10:
                item_liquidity = 0.9
            elif item.purchase_price_usd <= 50:
                item_liquidity = 0.7
            elif item.purchase_price_usd <= 200:
                item_liquidity = 0.5
            else:
                item_liquidity = 0.3
            
            # Ajustar por categoría
            category = self._categorize_item(item.item_title)
            if category in ['rifle', 'pistol']:
                item_liquidity *= 1.1  # Armas más líquidas
            elif category in ['knife', 'gloves']:
                item_liquidity *= 0.8  # Menos líquidas
            
            weighted_liquidity += item_liquidity * item.purchase_price_usd
            total_value += item.purchase_price_usd
        
        return min(weighted_liquidity / total_value, 1.0) if total_value > 0 else 1.0

    def _calculate_volatility_score(self, items: List[InventoryItem]) -> float:
        """Calcula puntuación de volatilidad del portfolio."""
        if not items:
            return 0.0
        
        # Simplificado: asumir volatilidad basada en precio y categoría
        total_value = 0.0
        weighted_volatility = 0.0
        
        for item in items:
            # Volatilidad más alta para ítems caros
            if item.purchase_price_usd >= 500:
                item_volatility = 0.8
            elif item.purchase_price_usd >= 100:
                item_volatility = 0.6
            elif item.purchase_price_usd >= 50:
                item_volatility = 0.4
            else:
                item_volatility = 0.2
            
            # Ajustar por categoría
            category = self._categorize_item(item.item_title)
            if category in ['knife', 'gloves']:
                item_volatility *= 1.2  # Más volátiles
            elif category == 'sticker':
                item_volatility *= 1.4  # Muy volátiles
            
            weighted_volatility += item_volatility * item.purchase_price_usd
            total_value += item.purchase_price_usd
        
        return min(weighted_volatility / total_value, 1.0) if total_value > 0 else 0.0

    def _calculate_value_at_risk(self, items: List[InventoryItem], confidence: float) -> float:
        """Calcula Value at Risk del portfolio."""
        if not items:
            return 0.0
        
        # Simplificado: VaR basado en volatilidad promedio y distribución normal
        total_value = sum(item.purchase_price_usd for item in items)
        avg_volatility = self._calculate_volatility_score(items)
        
        # Asumir distribución normal y calcular percentil
        # Para 95% de confianza, usar 1.645 deviaciones estándar
        if confidence == 0.95:
            z_score = 1.645
        elif confidence == 0.99:
            z_score = 2.326
        else:
            z_score = 1.0
        
        var = total_value * avg_volatility * z_score * 0.1  # Factor de escala
        return min(var, total_value * 0.5)  # Limitar al 50% del portfolio

    def _calculate_expected_shortfall(self, items: List[InventoryItem], confidence: float) -> float:
        """Calcula Expected Shortfall (Conditional VaR)."""
        var = self._calculate_value_at_risk(items, confidence)
        # ES típicamente 20-30% mayor que VaR
        return var * 1.25

    def _calculate_portfolio_beta(self, items: List[InventoryItem]) -> float:
        """Calcula beta del portfolio vs mercado."""
        if not items:
            return 1.0
        
        # Simplificado: asumir beta basado en composición del portfolio
        total_value = sum(item.purchase_price_usd for item in items)
        weighted_beta = 0.0
        
        for item in items:
            # Beta más alto para ítems más especulativos
            category = self._categorize_item(item.item_title)
            if category in ['knife', 'gloves']:
                item_beta = 1.3
            elif category == 'sticker':
                item_beta = 1.5
            elif item.purchase_price_usd >= 200:
                item_beta = 1.2
            else:
                item_beta = 0.9
            
            weighted_beta += item_beta * item.purchase_price_usd
        
        return weighted_beta / total_value if total_value > 0 else 1.0

    def _calculate_overall_risk_score(
        self, 
        concentration: float, 
        correlation: float, 
        volatility: float,
        max_position_pct: float, 
        drawdown: float
    ) -> float:
        """Calcula puntuación general de riesgo."""
        # Pesos para diferentes componentes de riesgo
        weights = {
            'concentration': 0.25,
            'correlation': 0.20,
            'volatility': 0.25,
            'position_size': 0.15,
            'drawdown': 0.15
        }
        
        # Normalizar drawdown a [0,1]
        normalized_drawdown = min(drawdown / 0.5, 1.0)  # 50% drawdown = score 1.0
        
        # Calcular score ponderado
        risk_score = (
            concentration * weights['concentration'] +
            correlation * weights['correlation'] +
            volatility * weights['volatility'] +
            max_position_pct * weights['position_size'] +
            normalized_drawdown * weights['drawdown']
        )
        
        return min(risk_score, 1.0)

    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determina el nivel de riesgo basado en la puntuación."""
        if risk_score <= 0.2:
            return RiskLevel.VERY_LOW
        elif risk_score <= 0.4:
            return RiskLevel.LOW
        elif risk_score <= 0.6:
            return RiskLevel.MEDIUM
        elif risk_score <= 0.8:
            return RiskLevel.HIGH
        elif risk_score <= 0.95:
            return RiskLevel.VERY_HIGH
        else:
            return RiskLevel.EXTREME

    def evaluate_trade_risk(
        self, 
        item_title: str, 
        purchase_price_usd: float, 
        strategy: str
    ) -> Tuple[bool, float, str]:
        """
        Evalúa el riesgo de una operación propuesta.
        
        Args:
            item_title: Nombre del ítem a comprar.
            purchase_price_usd: Precio de compra propuesto.
            strategy: Estrategia de trading utilizada.
            
        Returns:
            Tuple[bool, float, str]: (aprobado, risk_score, mensaje)
        """
        logger.debug(f"Evaluando riesgo de trade: {item_title} por ${purchase_price_usd:.2f}")
        
        try:
            # Obtener métricas actuales
            current_metrics = self.calculate_risk_metrics()
            
            # Simular nuevo portfolio con la compra
            new_exposure = current_metrics.total_exposure_usd + purchase_price_usd
            new_max_position = max(current_metrics.max_single_position_usd, purchase_price_usd)
            new_max_position_pct = new_max_position / new_exposure if new_exposure > 0 else 0
            
            # Verificar límites básicos
            if new_exposure > self.risk_limits.max_portfolio_exposure_usd:
                return False, 1.0, f"Excede límite de exposición total (${new_exposure:.2f} > ${self.risk_limits.max_portfolio_exposure_usd:.2f})"
            
            if purchase_price_usd > self.risk_limits.max_single_position_usd:
                return False, 1.0, f"Excede límite de posición única (${purchase_price_usd:.2f} > ${self.risk_limits.max_single_position_usd:.2f})"
            
            if new_max_position_pct > self.risk_limits.max_single_position_percentage:
                return False, 0.9, f"Excede límite de concentración ({new_max_position_pct:.1%} > {self.risk_limits.max_single_position_percentage:.1%})"
            
            # Evaluar riesgo específico del ítem
            item_risk_score = self._evaluate_item_risk(item_title, purchase_price_usd, strategy)
            
            # Evaluar impacto en diversificación
            diversification_impact = self._evaluate_diversification_impact(item_title, purchase_price_usd)
            
            # Calcular score de riesgo combinado
            combined_risk_score = (
                item_risk_score * 0.4 +
                current_metrics.overall_risk_score * 0.3 +
                diversification_impact * 0.3
            )
            
            # Determinar aprobación
            if combined_risk_score <= 0.3:
                return True, combined_risk_score, "Riesgo bajo - Trade aprobado"
            elif combined_risk_score <= 0.6:
                return True, combined_risk_score, "Riesgo medio - Trade aprobado con monitoring"
            elif combined_risk_score <= 0.8:
                return False, combined_risk_score, f"Riesgo alto - Requiere revisión manual (score: {combined_risk_score:.3f})"
            else:
                return False, combined_risk_score, f"Riesgo muy alto - Trade rechazado (score: {combined_risk_score:.3f})"
                
        except Exception as e:
            logger.error(f"Error evaluando riesgo de trade: {e}")
            return False, 1.0, f"Error en evaluación de riesgo: {str(e)}"

    def _evaluate_item_risk(self, item_title: str, price_usd: float, strategy: str) -> float:
        """Evalúa el riesgo específico de un ítem."""
        risk_score = 0.0
        
        # Riesgo por precio
        if price_usd >= 500:
            risk_score += 0.4
        elif price_usd >= 200:
            risk_score += 0.3
        elif price_usd >= 100:
            risk_score += 0.2
        else:
            risk_score += 0.1
        
        # Riesgo por categoría
        category = self._categorize_item(item_title)
        if category in ['knife', 'gloves']:
            risk_score += 0.3  # Más volátiles
        elif category == 'sticker':
            risk_score += 0.4  # Muy volátiles
        else:
            risk_score += 0.1
        
        # Riesgo por estrategia
        strategy_risks = {
            'basic_flip': 0.1,
            'snipe': 0.2,
            'attribute_premium_flip': 0.3,
            'trade_lock_arbitrage': 0.4,
            'volatility_trading': 0.5
        }
        risk_score += strategy_risks.get(strategy, 0.3)
        
        return min(risk_score, 1.0)

    def _evaluate_diversification_impact(self, item_title: str, price_usd: float) -> float:
        """Evalúa el impacto en la diversificación del portfolio."""
        try:
            active_items = self.inventory_manager.get_items_by_status(
                [InventoryItemStatus.PURCHASED, InventoryItemStatus.LISTED]
            )
            
            if not active_items:
                return 0.1  # Primera compra, bajo impacto
            
            # Calcular concentración por categoría actual
            category_values = {}
            total_value = 0.0
            
            for item in active_items:
                cat = self._categorize_item(item.item_title)
                category_values[cat] = category_values.get(cat, 0) + item.purchase_price_usd
                total_value += item.purchase_price_usd
            
            # Simular nueva compra
            new_category = self._categorize_item(item_title)
            new_total = total_value + price_usd
            new_category_value = category_values.get(new_category, 0) + price_usd
            new_category_percentage = new_category_value / new_total
            
            # Penalizar concentración excesiva
            if new_category_percentage > 0.5:
                return 0.8
            elif new_category_percentage > 0.4:
                return 0.6
            elif new_category_percentage > 0.3:
                return 0.4
            else:
                return 0.2
                
        except Exception as e:
            logger.warning(f"Error evaluando impacto de diversificación: {e}")
            return 0.3  # Valor moderado por defecto

    def create_stop_loss_order(
        self, 
        item_id: int, 
        current_price_usd: float,
        custom_stop_percentage: Optional[float] = None
    ) -> Optional[StopLossOrder]:
        """
        Crea una orden de stop-loss para un ítem específico.
        
        Args:
            item_id: ID del ítem en inventario.
            current_price_usd: Precio actual del ítem.
            custom_stop_percentage: Porcentaje personalizado de stop-loss.
            
        Returns:
            StopLossOrder creada o None si hay error.
        """
        try:
            # Obtener información del ítem
            db: Session = next(get_db())
            item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
            
            if not item:
                logger.error(f"Ítem con ID {item_id} no encontrado")
                return None
            
            # Determinar porcentaje de stop-loss
            stop_percentage = custom_stop_percentage or self._calculate_adaptive_stop_loss(item)
            
            # Calcular precio de stop-loss
            stop_price = item.purchase_price_usd * (1 - stop_percentage)
            
            # Crear orden
            stop_order = StopLossOrder(
                item_id=item_id,
                item_title=item.item_title,
                stop_loss_price_usd=stop_price,
                current_price_usd=current_price_usd,
                purchase_price_usd=item.purchase_price_usd,
                stop_loss_percentage=stop_percentage,
                created_at=datetime.now(timezone.utc)
            )
            
            self.stop_loss_orders.append(stop_order)
            
            logger.info(f"Stop-loss creado para {item.item_title}: "
                       f"Stop @ ${stop_price:.2f} ({stop_percentage:.1%} loss)")
            
            return stop_order
            
        except Exception as e:
            logger.error(f"Error creando stop-loss para ítem {item_id}: {e}")
            return None
        finally:
            db.close()

    def _calculate_adaptive_stop_loss(self, item: InventoryItem) -> float:
        """Calcula porcentaje de stop-loss adaptativo basado en características del ítem."""
        base_stop = self.config.get("default_stop_loss_percentage", 0.15)
        
        # Ajustar por precio
        if item.purchase_price_usd >= 500:
            price_adjustment = 0.05  # Stop más amplio para ítems caros
        elif item.purchase_price_usd >= 200:
            price_adjustment = 0.02
        elif item.purchase_price_usd >= 50:
            price_adjustment = 0.0
        else:
            price_adjustment = -0.03  # Stop más estrecho para ítems baratos
        
        # Ajustar por categoría
        category = self._categorize_item(item.item_title)
        if category in ['knife', 'gloves']:
            category_adjustment = 0.05  # Más volátiles
        elif category == 'sticker':
            category_adjustment = 0.08
        else:
            category_adjustment = 0.0
        
        # Ajustar por estrategia
        strategy_adjustments = {
            'basic_flip': 0.0,
            'snipe': -0.02,  # Stops más estrechos para snipes
            'attribute_premium_flip': 0.03,
            'trade_lock_arbitrage': 0.05,
            'volatility_trading': 0.07
        }
        strategy_adjustment = strategy_adjustments.get(item.strategy_used, 0.0)
        
        # Calcular stop final
        final_stop = base_stop + price_adjustment + category_adjustment + strategy_adjustment
        
        # Aplicar límites
        min_stop = self.config.get("min_stop_loss_percentage", 0.05)
        max_stop = self.config.get("max_stop_loss_percentage", 0.30)
        
        return max(min_stop, min(final_stop, max_stop))

    def check_stop_loss_triggers(self, current_prices: Dict[str, float]) -> List[StopLossOrder]:
        """
        Verifica si alguna orden de stop-loss debe ser activada.
        
        Args:
            current_prices: Dict con precios actuales {item_title: price_usd}
            
        Returns:
            Lista de órdenes de stop-loss activadas.
        """
        triggered_orders = []
        
        for order in self.stop_loss_orders:
            if order.triggered or order.executed:
                continue
            
            current_price = current_prices.get(order.item_title)
            if current_price is None:
                continue
            
            # Verificar si se activó el stop-loss
            if current_price <= order.stop_loss_price_usd:
                order.triggered = True
                order.triggered_at = datetime.now(timezone.utc)
                order.current_price_usd = current_price
                
                triggered_orders.append(order)
                
                logger.warning(f"STOP-LOSS ACTIVADO: {order.item_title} - "
                             f"Precio: ${current_price:.2f} <= Stop: ${order.stop_loss_price_usd:.2f}")
                
                # Registrar alerta de riesgo
                self._record_risk_alert(
                    RiskAlert.STOP_LOSS_TRIGGERED,
                    f"Stop-loss activado para {order.item_title}",
                    {
                        "item_id": order.item_id,
                        "item_title": order.item_title,
                        "current_price": current_price,
                        "stop_price": order.stop_loss_price_usd,
                        "loss_percentage": (order.purchase_price_usd - current_price) / order.purchase_price_usd
                    }
                )
        
        return triggered_orders

    def _record_risk_alert(self, alert_type: RiskAlert, message: str, data: Dict[str, Any]) -> None:
        """Registra una alerta de riesgo en el historial."""
        alert_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert_type": alert_type.value,
            "message": message,
            "data": data
        }
        
        self.risk_alerts_history.append(alert_record)
        
        # Mantener solo las últimas 1000 alertas
        if len(self.risk_alerts_history) > 1000:
            self.risk_alerts_history = self.risk_alerts_history[-1000:]

    def get_risk_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen completo del estado de riesgo del portfolio.
        
        Returns:
            Dict con resumen de métricas, límites y alertas.
        """
        try:
            # Calcular métricas actuales
            current_metrics = self.calculate_risk_metrics()
            
            # Obtener alertas recientes
            recent_alerts = [
                alert for alert in self.risk_alerts_history 
                if datetime.fromisoformat(alert["timestamp"]) >= datetime.now(timezone.utc) - timedelta(days=7)
            ]
            
            # Contar órdenes de stop-loss activas
            active_stop_losses = len([o for o in self.stop_loss_orders if not o.executed])
            triggered_stop_losses = len([o for o in self.stop_loss_orders if o.triggered and not o.executed])
            
            # Calcular utilización de límites
            limit_utilization = {
                "exposure": current_metrics.total_exposure_usd / self.risk_limits.max_portfolio_exposure_usd,
                "max_position": current_metrics.max_single_position_usd / self.risk_limits.max_single_position_usd,
                "concentration": current_metrics.max_single_position_percentage / self.risk_limits.max_single_position_percentage,
                "correlation": current_metrics.correlation_risk_score / self.risk_limits.max_correlation_exposure
            }
            
            return {
                "timestamp": current_metrics.timestamp.isoformat(),
                "risk_level": current_metrics.risk_level.value,
                "overall_risk_score": current_metrics.overall_risk_score,
                "metrics": {
                    "total_exposure_usd": current_metrics.total_exposure_usd,
                    "max_single_position_usd": current_metrics.max_single_position_usd,
                    "max_single_position_percentage": current_metrics.max_single_position_percentage,
                    "portfolio_beta": current_metrics.portfolio_beta,
                    "sharpe_ratio": current_metrics.sharpe_ratio,
                    "max_drawdown_percentage": current_metrics.max_drawdown_percentage,
                    "value_at_risk_95": current_metrics.value_at_risk_95,
                    "concentration_index": current_metrics.concentration_index,
                    "diversification_score": current_metrics.diversification_score,
                    "liquidity_score": current_metrics.liquidity_score,
                    "volatility_score": current_metrics.volatility_score
                },
                "limits": {
                    "max_portfolio_exposure_usd": self.risk_limits.max_portfolio_exposure_usd,
                    "max_single_position_usd": self.risk_limits.max_single_position_usd,
                    "max_single_position_percentage": self.risk_limits.max_single_position_percentage,
                    "stop_loss_percentage": self.risk_limits.stop_loss_percentage,
                    "max_daily_loss_usd": self.risk_limits.max_daily_loss_usd,
                    "max_drawdown_percentage": self.risk_limits.max_drawdown_percentage
                },
                "limit_utilization": limit_utilization,
                "stop_loss_orders": {
                    "active": active_stop_losses,
                    "triggered": triggered_stop_losses,
                    "total": len(self.stop_loss_orders)
                },
                "recent_alerts": {
                    "count_7d": len(recent_alerts),
                    "alerts": recent_alerts[-10:]  # Últimas 10 alertas
                },
                "warnings": self._generate_risk_warnings(current_metrics, limit_utilization)
            }
            
        except Exception as e:
            logger.error(f"Error generando resumen de riesgo: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "risk_level": "unknown"
            }

    def _generate_risk_warnings(self, metrics: RiskMetrics, utilization: Dict[str, float]) -> List[str]:
        """Genera advertencias basadas en métricas y utilización de límites."""
        warnings = []
        
        # Alertas por utilización de límites
        if utilization["exposure"] > 0.8:
            warnings.append(f"Alta utilización de límite de exposición ({utilization['exposure']:.1%})")
        
        if utilization["max_position"] > 0.8:
            warnings.append(f"Posición individual cerca del límite ({utilization['max_position']:.1%})")
        
        if utilization["concentration"] > 0.8:
            warnings.append(f"Alta concentración en posición única ({utilization['concentration']:.1%})")
        
        # Alertas por métricas de riesgo
        if metrics.volatility_score > 0.7:
            warnings.append(f"Alta volatilidad del portfolio ({metrics.volatility_score:.1%})")
        
        if metrics.correlation_risk_score > 0.6:
            warnings.append(f"Alto riesgo de correlación ({metrics.correlation_risk_score:.1%})")
        
        if metrics.liquidity_score < 0.4:
            warnings.append(f"Baja liquidez del portfolio ({metrics.liquidity_score:.1%})")
        
        if metrics.max_drawdown_percentage > 0.2:
            warnings.append(f"Drawdown elevado ({metrics.max_drawdown_percentage:.1%})")
        
        if metrics.diversification_score < 0.5:
            warnings.append(f"Baja diversificación ({metrics.diversification_score:.1%})")
        
        return warnings 