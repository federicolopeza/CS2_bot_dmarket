# core/alerter.py
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from enum import Enum

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Niveles de alerta para diferentes tipos de oportunidades."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertType(Enum):
    """Tipos de alertas según la estrategia."""
    BASIC_FLIP = "basic_flip"
    SNIPE = "snipe"
    ATTRIBUTE_PREMIUM = "attribute_premium"
    VOLATILITY = "volatility"
    TRADE_LOCK = "trade_lock"
    
    # Tipos específicos para execution engine
    OPPORTUNITY_FOUND = "opportunity_found"
    EXECUTION_SUCCESS = "execution_success"
    EXECUTION_FAILED = "execution_failed"
    SYSTEM_ERROR = "system_error"
    RISK_WARNING = "risk_warning"

class Alerter:
    """
    Clase para manejar alertas y notificaciones de oportunidades de trading.
    
    Versión inicial enfocada en logging detallado, con estructura expandible
    para futuras integraciones con email, Telegram, etc.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el sistema de alertas.
        
        Args:
            config: Configuración opcional para el alerter.
                   Puede incluir umbrales, canales de notificación, etc.
        """
        self.config = config or self._get_default_config()
        logger.info("Alerter inicializado con configuración.")

    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto para el alerter."""
        return {
            "enabled": True,
            "log_all_opportunities": True,
            "min_profit_usd_for_alert": 0.50,  # Mínimo profit para generar alerta
            "min_profit_percentage_for_alert": 5.0,  # Mínimo % de profit para alerta
            "alert_levels": {
                AlertType.BASIC_FLIP.value: AlertLevel.MEDIUM.value,
                AlertType.SNIPE.value: AlertLevel.HIGH.value,
                AlertType.ATTRIBUTE_PREMIUM.value: AlertLevel.HIGH.value,
                AlertType.VOLATILITY.value: AlertLevel.MEDIUM.value,
                AlertType.TRADE_LOCK.value: AlertLevel.LOW.value,
                
                # Niveles para execution engine
                AlertType.OPPORTUNITY_FOUND.value: AlertLevel.MEDIUM.value,
                AlertType.EXECUTION_SUCCESS.value: AlertLevel.HIGH.value,
                AlertType.EXECUTION_FAILED.value: AlertLevel.HIGH.value,
                AlertType.SYSTEM_ERROR.value: AlertLevel.CRITICAL.value,
                AlertType.RISK_WARNING.value: AlertLevel.MEDIUM.value,
            },
            # Configuración futura para otros canales
            "email": {
                "enabled": False,
                "smtp_server": None,
                "recipients": []
            },
            "telegram": {
                "enabled": False,
                "bot_token": None,
                "chat_ids": []
            }
        }

    def alert_opportunity(
        self, 
        opportunity: Dict[str, Any], 
        alert_type: AlertType,
        custom_level: Optional[AlertLevel] = None
    ) -> None:
        """
        Genera una alerta para una oportunidad encontrada.
        
        Args:
            opportunity: Diccionario con los detalles de la oportunidad.
            alert_type: Tipo de estrategia que generó la oportunidad.
            custom_level: Nivel de alerta personalizado (opcional).
        """
        if not self.config.get("enabled", True):
            return

        # Determinar nivel de alerta
        alert_level = custom_level or AlertLevel(
            self.config["alert_levels"].get(alert_type.value, AlertLevel.MEDIUM.value)
        )

        # Verificar si cumple los umbrales mínimos
        if not self._meets_alert_thresholds(opportunity):
            logger.debug(f"Oportunidad {opportunity.get('item_title', 'N/A')} no cumple umbrales mínimos para alerta.")
            return

        # Generar alerta
        alert_data = self._format_alert_data(opportunity, alert_type, alert_level)
        
        # Enviar por diferentes canales
        self._send_log_alert(alert_data, alert_level)
        
        # Futuras implementaciones
        # self._send_email_alert(alert_data)
        # self._send_telegram_alert(alert_data)

    def alert_multiple_opportunities(
        self, 
        opportunities: List[Dict[str, Any]], 
        summary_title: str = "Oportunidades Encontradas"
    ) -> None:
        """
        Genera alertas para múltiples oportunidades, incluyendo un resumen.
        
        Args:
            opportunities: Lista de oportunidades encontradas.
            summary_title: Título para el resumen de oportunidades.
        """
        if not opportunities:
            logger.info("No se encontraron oportunidades para alertar.")
            return

        # Alertar cada oportunidad individualmente
        for opp in opportunities:
            alert_type = AlertType(opp.get('strategy_type', AlertType.BASIC_FLIP.value))
            self.alert_opportunity(opp, alert_type)

        # Generar resumen
        self._send_summary_alert(opportunities, summary_title)

    def _meets_alert_thresholds(self, opportunity: Dict[str, Any]) -> bool:
        """Verifica si la oportunidad cumple los umbrales mínimos para generar alerta."""
        profit_usd = opportunity.get('estimated_profit_usd', 0)
        profit_percentage = opportunity.get('profit_percentage', 0)
        
        min_profit_usd = self.config.get('min_profit_usd_for_alert', 0)
        min_profit_percentage = self.config.get('min_profit_percentage_for_alert', 0)
        
        return (profit_usd >= min_profit_usd and profit_percentage >= min_profit_percentage)

    def _format_alert_data(
        self, 
        opportunity: Dict[str, Any], 
        alert_type: AlertType, 
        alert_level: AlertLevel
    ) -> Dict[str, Any]:
        """Formatea los datos de la oportunidad para la alerta."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert_type": alert_type.value,
            "alert_level": alert_level.value,
            "item_title": opportunity.get('item_title', 'N/A'),
            "strategy_type": opportunity.get('strategy_type', alert_type.value),
            "buy_price_usd": opportunity.get('buy_price_usd', 0),
            "sell_price_usd": opportunity.get('sell_price_usd', 0),
            "estimated_profit_usd": opportunity.get('estimated_profit_usd', 0),
            "profit_percentage": opportunity.get('profit_percentage', 0),
            "confidence": opportunity.get('confidence', 'medium'),
            "details": opportunity.get('details', {}),
            "raw_opportunity": opportunity
        }

    def _send_log_alert(self, alert_data: Dict[str, Any], alert_level: AlertLevel) -> None:
        """Envía la alerta a través del sistema de logging."""
        item_title = alert_data['item_title']
        strategy = alert_data['strategy_type']
        profit_usd = alert_data['estimated_profit_usd']
        profit_pct = alert_data['profit_percentage']
        buy_price = alert_data['buy_price_usd']
        sell_price = alert_data['sell_price_usd']

        alert_message = (
            f"🚨 OPORTUNIDAD {alert_level.value.upper()} - {strategy.upper()} 🚨\n"
            f"Ítem: {item_title}\n"
            f"Compra: ${buy_price:.2f} → Venta: ${sell_price:.2f}\n"
            f"Profit: ${profit_usd:.2f} ({profit_pct:.1f}%)\n"
            f"Confianza: {alert_data['confidence']}"
        )

        # Usar diferentes niveles de log según la importancia
        if alert_level == AlertLevel.CRITICAL:
            logger.critical(alert_message)
        elif alert_level == AlertLevel.HIGH:
            logger.error(alert_message)  # Usar error para que destaque
        elif alert_level == AlertLevel.MEDIUM:
            logger.warning(alert_message)
        else:
            logger.info(alert_message)

        # Log detallado en DEBUG
        logger.debug(f"Detalles completos de la alerta: {json.dumps(alert_data, indent=2)}")

    def _send_summary_alert(self, opportunities: List[Dict[str, Any]], title: str) -> None:
        """Envía un resumen de múltiples oportunidades."""
        total_opportunities = len(opportunities)
        total_profit = sum(opp.get('estimated_profit_usd', 0) for opp in opportunities)
        
        # Agrupar por estrategia
        by_strategy = {}
        for opp in opportunities:
            strategy = opp.get('strategy_type', 'unknown')
            if strategy not in by_strategy:
                by_strategy[strategy] = []
            by_strategy[strategy].append(opp)

        summary_message = (
            f"📊 {title.upper()} 📊\n"
            f"Total de oportunidades: {total_opportunities}\n"
            f"Profit total estimado: ${total_profit:.2f}\n"
            f"Desglose por estrategia:"
        )

        for strategy, opps in by_strategy.items():
            strategy_profit = sum(opp.get('estimated_profit_usd', 0) for opp in opps)
            summary_message += f"\n  - {strategy}: {len(opps)} oportunidades (${strategy_profit:.2f})"

        logger.info(summary_message)

    def send_alert(
        self,
        alert_level: AlertLevel,
        alert_type: AlertType,
        message: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Envía una alerta genérica.
        
        Args:
            alert_level: Nivel de la alerta.
            alert_type: Tipo de alerta.
            message: Mensaje principal de la alerta.
            additional_data: Datos adicionales opcionales.
        """
        if not self.config.get("enabled", True):
            return
        
        alert_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert_type": alert_type.value,
            "alert_level": alert_level.value,
            "message": message,
            "additional_data": additional_data or {}
        }
        
        # Formatear mensaje para logging
        formatted_message = f"🔔 {alert_level.value.upper()} - {alert_type.value.upper()}: {message}"
        
        if additional_data:
            formatted_message += f"\nDetalles: {json.dumps(additional_data, indent=2)}"
        
        # Enviar según el nivel
        if alert_level == AlertLevel.CRITICAL:
            logger.critical(formatted_message)
        elif alert_level == AlertLevel.HIGH:
            logger.error(formatted_message)
        elif alert_level == AlertLevel.MEDIUM:
            logger.warning(formatted_message)
        else:
            logger.info(formatted_message)

    # Métodos placeholder para futuras implementaciones
    def _send_email_alert(self, alert_data: Dict[str, Any]) -> None:
        """Placeholder para alertas por email."""
        if self.config.get("email", {}).get("enabled", False):
            logger.debug("Email alert would be sent here")
            # TODO: Implementar envío de email

    def _send_telegram_alert(self, alert_data: Dict[str, Any]) -> None:
        """Placeholder para alertas por Telegram."""
        if self.config.get("telegram", {}).get("enabled", False):
            logger.debug("Telegram alert would be sent here")
            # TODO: Implementar envío de Telegram

# Función de conveniencia para uso directo
def create_alerter(config: Optional[Dict[str, Any]] = None) -> Alerter:
    """Crea una instancia del Alerter con configuración opcional."""
    return Alerter(config)

if __name__ == "__main__":
    # Ejemplo de uso
    from utils.logger import configure_logging
    configure_logging(log_level=logging.DEBUG)

    # Crear alerter
    alerter = create_alerter()

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

    # Generar alerta
    alerter.alert_opportunity(example_opportunity, AlertType.BASIC_FLIP)

    # Ejemplo de múltiples oportunidades
    opportunities = [example_opportunity]
    alerter.alert_multiple_opportunities(opportunities, "Escaneo de Mercado Completado") 