# demo_execution_engine.py
"""
Script de demostración del ExecutionEngine integrado con todos los módulos del sistema.
Muestra el flujo completo desde la detección de oportunidades hasta la ejecución de trades.
"""

import logging
import time
from typing import Dict, List, Any

from utils.logger import configure_logging
from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer
from core.strategy_engine import StrategyEngine
from core.alerter import Alerter
from core.inventory_manager import InventoryManager
from core.execution_engine import ExecutionEngine, ExecutionMode

def create_mock_opportunities() -> Dict[str, List[Dict[str, Any]]]:
    """Crea oportunidades simuladas para la demostración."""
    return {
        "basic_flips": [
            {
                "strategy": "basic_flip",
                "item_title": "AK-47 | Redline (Field-Tested)",
                "buy_price_usd": 4.50,
                "sell_price_usd": 5.25,
                "profit_usd": 0.75,
                "profit_percentage": 0.167,
                "lso_details": {"assetId": "demo_asset_001"},
                "hbo_details": {"offerId": "demo_order_001"},
                "commission_usd": 0.15,
                "timestamp": time.time()
            }
        ],
        "snipes": [
            {
                "strategy": "snipe",
                "item_title": "M4A4 | Howl (Minimal Wear)",
                "pme_usd": 45.00,
                "offer_price_usd": 3.20,  # Precio muy bajo para auto-ejecución
                "discount_percentage": 0.93,
                "potential_profit_usd": 40.50,
                "offer_details": {"assetId": "demo_asset_002"},
                "commission_on_pme_usd": 2.25,
                "timestamp": time.time()
            }
        ],
        "attribute_flips": [
            {
                "strategy": "attribute_premium_flip",
                "item_title": "AWP | Dragon Lore (Battle-Scarred)",
                "asset_id": "demo_asset_003",
                "buy_price_usd": 15.75,
                "estimated_sell_price_usd": 22.00,
                "potential_profit_usd": 5.15,
                "profit_percentage": 0.327,
                "rarity_score": 85.0,
                "premium_multiplier": 1.4,
                "confidence": "high"
            }
        ],
        "trade_lock_arbitrage": [],
        "volatility_trading": []
    }

def demo_execution_engine():
    """Demostración principal del ExecutionEngine."""
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 INICIANDO DEMOSTRACIÓN DEL EXECUTION ENGINE 🚀")
    
    # ========================================================================================
    # 1. INICIALIZACIÓN DE COMPONENTES
    # ========================================================================================
    logger.info("\n" + "="*80)
    logger.info("FASE 1: INICIALIZANDO COMPONENTES DEL SISTEMA")
    logger.info("="*80)
    
    # Crear componentes mock/simulados
    mock_connector = DMarketAPI()  # Se inicializará en modo mock si no hay credenciales
    market_analyzer = MarketAnalyzer()
    alerter = Alerter()
    inventory_manager = InventoryManager()
    
    logger.info("✅ Componentes básicos inicializados")
    
    # Configurar ExecutionEngine en modo PAPER_TRADING
    execution_config = {
        "execution_mode": ExecutionMode.PAPER_TRADING.value,
        "max_daily_spending_usd": 50.0,
        "max_single_trade_usd": 10.0,
        "max_concurrent_orders": 5,
        "require_manual_confirmation": True,
        "auto_confirm_below_usd": 5.0,
        "enabled_strategies": {
            "basic_flip": True,
            "snipe": True,
            "attribute_premium_flip": False,  # Deshabilitada para demo
            "trade_lock_arbitrage": False,
            "volatility_trading": False
        }
    }
    
    execution_engine = ExecutionEngine(
        mock_connector,
        inventory_manager,
        alerter,
        execution_config
    )
    
    logger.info("✅ ExecutionEngine inicializado en modo PAPER_TRADING")
    logger.info(f"   - Límite diario: ${execution_config['max_daily_spending_usd']}")
    logger.info(f"   - Límite por trade: ${execution_config['max_single_trade_usd']}")
    logger.info(f"   - Auto-confirmación hasta: ${execution_config['auto_confirm_below_usd']}")
    
    # ========================================================================================
    # 2. SIMULACIÓN DE DETECCIÓN DE OPORTUNIDADES
    # ========================================================================================
    logger.info("\n" + "="*80)
    logger.info("FASE 2: DETECCIÓN DE OPORTUNIDADES DE TRADING")
    logger.info("="*80)
    
    # Simular oportunidades encontradas por el strategy engine
    opportunities = create_mock_opportunities()
    
    total_opportunities = sum(len(opps) for opps in opportunities.values())
    logger.info(f"🎯 Encontradas {total_opportunities} oportunidades de trading:")
    
    for strategy, opps in opportunities.items():
        if opps:
            logger.info(f"   - {strategy}: {len(opps)} oportunidades")
            for opp in opps:
                profit = opp.get('profit_usd', opp.get('potential_profit_usd', 0))
                price = opp.get('buy_price_usd', opp.get('offer_price_usd', 0))
                logger.info(f"     * {opp['item_title']}: ${price:.2f} → Profit: ${profit:.2f}")
    
    # ========================================================================================
    # 3. PROCESAMIENTO DE OPORTUNIDADES
    # ========================================================================================
    logger.info("\n" + "="*80)
    logger.info("FASE 3: PROCESAMIENTO Y EVALUACIÓN DE RIESGOS")
    logger.info("="*80)
    
    # Procesar oportunidades con el execution engine
    processing_result = execution_engine.process_opportunities(opportunities)
    
    logger.info("📊 RESULTADOS DEL PROCESAMIENTO:")
    logger.info(f"   - Oportunidades procesadas: {processing_result['total_opportunities']}")
    logger.info(f"   - Órdenes creadas: {processing_result['orders_created']}")
    logger.info(f"   - Órdenes ejecutadas automáticamente: {processing_result['orders_executed']}")
    logger.info(f"   - Órdenes activas pendientes: {processing_result['active_orders']}")
    
    if processing_result['errors']:
        logger.warning(f"   - Errores encontrados: {len(processing_result['errors'])}")
        for error in processing_result['errors']:
            logger.warning(f"     * {error}")
    
    # ========================================================================================
    # 4. REVISIÓN DE ÓRDENES ACTIVAS
    # ========================================================================================
    logger.info("\n" + "="*80)
    logger.info("FASE 4: GESTIÓN DE ÓRDENES ACTIVAS")
    logger.info("="*80)
    
    # Mostrar órdenes activas
    active_orders = execution_engine.active_orders
    if active_orders:
        logger.info(f"📋 ÓRDENES ACTIVAS ({len(active_orders)}):")
        for order in active_orders:
            logger.info(f"   - Order ID: {order.id}")
            logger.info(f"     * Ítem: {order.item_title}")
            logger.info(f"     * Estrategia: {order.strategy}")
            logger.info(f"     * Precio: ${order.price_usd:.2f}")
            logger.info(f"     * Estado: {order.status.value}")
            logger.info(f"     * Nivel de riesgo: {order.risk_level.value}")
            logger.info(f"     * Intentos de ejecución: {order.execution_attempts}")
            
            # Simular ejecución manual de órdenes pendientes
            if order.status.value == "pending" and order.price_usd <= 10.0:  # Solo órdenes pequeñas
                logger.info(f"   → Ejecutando orden {order.id} manualmente...")
                success = execution_engine.execute_order(order)
                if success:
                    logger.info(f"   ✅ Orden {order.id} ejecutada exitosamente")
                else:
                    logger.info(f"   ❌ Fallo en ejecución de orden {order.id}: {order.error_message}")
    else:
        logger.info("📋 No hay órdenes activas")
    
    # ========================================================================================
    # 5. RESUMEN FINAL Y ESTADÍSTICAS
    # ========================================================================================
    logger.info("\n" + "="*80)
    logger.info("FASE 5: RESUMEN FINAL Y ESTADÍSTICAS")
    logger.info("="*80)
    
    # Obtener resumen de ejecución
    execution_summary = execution_engine.get_execution_summary()
    
    logger.info("📈 RESUMEN DE EJECUCIÓN:")
    logger.info(f"   - Modo de ejecución: {execution_summary['execution_mode']}")
    logger.info(f"   - Órdenes activas: {execution_summary['active_orders']}")
    logger.info(f"   - Gastos del día: ${execution_summary['daily_spending_usd']:.2f}")
    logger.info(f"   - Límite diario: ${execution_summary['daily_limit_usd']:.2f}")
    logger.info(f"   - Presupuesto restante: ${execution_summary['remaining_budget_usd']:.2f}")
    
    recent_stats = execution_summary['recent_stats']
    logger.info("\n📊 ESTADÍSTICAS RECIENTES (24h):")
    logger.info(f"   - Total de órdenes: {recent_stats['total_orders_24h']}")
    logger.info(f"   - Órdenes completadas: {recent_stats['completed_24h']}")
    logger.info(f"   - Órdenes fallidas: {recent_stats['failed_24h']}")
    logger.info(f"   - Tasa de éxito: {recent_stats['success_rate_24h']:.1f}%")
    logger.info(f"   - Profit total: ${recent_stats['total_profit_24h']:.2f}")
    
    # Resumen del inventario
    logger.info("\n🎒 RESUMEN DEL INVENTARIO:")
    try:
        inventory_summary = inventory_manager.get_inventory_summary()
        logger.info(f"   - Total de ítems: {inventory_summary['total_items']}")
        logger.info(f"   - Inversión total: ${inventory_summary['total_invested_usd']:.2f}")
        logger.info(f"   - Profit realizado: ${inventory_summary['total_realized_profit_usd']:.2f}")
        logger.info(f"   - ROI: {inventory_summary['roi_percentage']:.2f}%")
        
        if inventory_summary['items_by_status']:
            logger.info("   - Ítems por estado:")
            for status, count in inventory_summary['items_by_status'].items():
                logger.info(f"     * {status}: {count}")
    except Exception as e:
        logger.warning(f"   - No se pudo obtener resumen del inventario: {e}")
        logger.info("   - Ejecutar 'python -c \"from core.inventory_manager import create_tables; create_tables()\"' para crear las tablas")
    
    # ========================================================================================
    # 6. CONCLUSIÓN
    # ========================================================================================
    logger.info("\n" + "="*80)
    logger.info("🎉 DEMOSTRACIÓN COMPLETADA EXITOSAMENTE")
    logger.info("="*80)
    
    logger.info("✅ ExecutionEngine demostrado con éxito:")
    logger.info("   - Detección automática de oportunidades")
    logger.info("   - Evaluación de riesgos y límites")
    logger.info("   - Creación y gestión de órdenes")
    logger.info("   - Ejecución automática y manual")
    logger.info("   - Integración con InventoryManager y Alerter")
    logger.info("   - Tracking completo de estadísticas")
    
    logger.info("\n🚀 El sistema está listo para trading en vivo!")
    logger.info("   (Cambiar execution_mode a 'live_trading' para trading real)")

if __name__ == "__main__":
    # Configurar logging
    configure_logging(log_level=logging.INFO)
    
    try:
        demo_execution_engine()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error en la demostración: {e}", exc_info=True) 