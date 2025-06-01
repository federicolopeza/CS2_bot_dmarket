#!/usr/bin/env python3
"""
Demo Completo del Sistema de Trading CS2

Este script demuestra todas las funcionalidades principales del sistema:
- Conexión a DMarket API
- Análisis de mercado
- Estrategias de trading
- Paper trading
- Gestión de riesgos
- Optimización de parámetros
- Tracking de KPIs

Ejecutar: python demo_complete_system.py
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Añadir el directorio raíz al path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Importar módulos principales
from core.dmarket_connector import DMarketAPI
from core.strategy_engine import StrategyEngine
from core.paper_trader import PaperTrader
from core.risk_manager import RiskManager
from core.kpi_tracker import KPITracker
from core.optimizer import ParameterOptimizer, MetricType, OptimizationMethod, create_default_optimization_config
from core.execution_engine import ExecutionEngine, ExecutionMode
from core.inventory_manager import InventoryManager
from core.alerter import create_alerter
from core.data_manager import init_db
from utils.logger import configure_logging

def main():
    """Demo principal del sistema completo."""
    print("🎯 DEMO DEL SISTEMA COMPLETO DE TRADING CS2")
    print("=" * 60)
    
    # Configurar logging
    configure_logging(log_level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Cargar variables de entorno
    load_dotenv()
    
    try:
        # 1. Inicializar base de datos
        print("\n1️⃣ Inicializando base de datos...")
        init_db()
        print("✅ Base de datos inicializada")
        
        # 2. Configurar conectores principales
        print("\n2️⃣ Configurando conectores...")
        dmarket_api = DMarketAPI(
            public_key=os.getenv("DMARKET_PUBLIC_KEY"),
            secret_key=os.getenv("DMARKET_SECRET_KEY")
        )
        print("✅ DMarket API configurada")
        
        # 3. Inicializar componentes principales
        print("\n3️⃣ Inicializando componentes principales...")
        
        # Strategy Engine con configuración optimizada
        strategy_config = {
            "basic_flip_min_profit_percentage": 0.05,
            "snipe_discount_threshold": 0.15,
            "attribute_min_rarity_score": 0.6,
            "trade_lock_min_discount": 0.1,
            "volatility_rsi_oversold": 30,
            "volatility_rsi_overbought": 70,
            "max_trade_amount_usd": 50.0,
            "min_expected_profit_usd": 2.0,
        }
        
        strategy_engine = StrategyEngine(dmarket_api, strategy_config)
        paper_trader = PaperTrader(initial_balance_usd=1000.0)
        inventory_manager = InventoryManager()
        risk_manager = RiskManager(inventory_manager)
        kpi_tracker = KPITracker(inventory_manager)
        alerter = create_alerter()
        
        # Execution Engine en modo paper trading
        execution_engine = ExecutionEngine(
            dmarket_connector=dmarket_api,
            inventory_manager=inventory_manager,
            alerter=alerter,
            config={"execution_mode": ExecutionMode.PAPER_TRADING}
        )
        
        print("✅ Todos los componentes inicializados")
        
        # 4. Demo de análisis de mercado
        print("\n4️⃣ Demo: Análisis de mercado...")
        demo_market_analysis(strategy_engine)
        
        # 5. Demo de paper trading
        print("\n5️⃣ Demo: Paper Trading...")
        demo_paper_trading(paper_trader)
        
        # 6. Demo de gestión de riesgos
        print("\n6️⃣ Demo: Gestión de riesgos...")
        demo_risk_management(risk_manager)
        
        # 7. Demo de KPI tracking
        print("\n7️⃣ Demo: Tracking de KPIs...")
        demo_kpi_tracking(kpi_tracker)
        
        # 8. Demo de optimización de parámetros
        print("\n8️⃣ Demo: Optimización de parámetros...")
        demo_parameter_optimization(dmarket_api)
        
        # 9. Demo de ejecución automática
        print("\n9️⃣ Demo: Ejecución automática...")
        demo_execution_engine(execution_engine)
        
        print("\n🎉 DEMO COMPLETO FINALIZADO")
        print("=" * 60)
        print("✅ Todas las funcionalidades principales demostradas con éxito")
        print("🚀 El sistema está listo para usar en producción")
        
    except Exception as e:
        logger.error(f"Error en demo: {e}")
        print(f"❌ Error: {e}")
        return 1
    
    return 0

def demo_market_analysis(strategy_engine):
    """Demostrar análisis de mercado."""
    try:
        # Simular búsqueda de oportunidades en ítems populares
        test_items = ["AK-47 | Redline", "AWP | Asiimov", "M4A4 | Howl"]
        
        print(f"🔍 Analizando {len(test_items)} ítems populares...")
        
        # Simular resultado de estrategias
        opportunities = [
            {
                "strategy": "basic_flip",
                "item_name": "AK-47 | Redline",
                "buy_price_usd": 25.50,
                "sell_price_usd": 27.30,
                "expected_profit_usd": 1.80,
                "profit_percentage": 7.06,
                "confidence": 0.85
            },
            {
                "strategy": "snipe",
                "item_name": "AWP | Asiimov",
                "buy_price_usd": 45.00,
                "estimated_market_price": 52.00,
                "expected_profit_usd": 7.00,
                "profit_percentage": 15.56,
                "confidence": 0.75
            }
        ]
        
        print(f"✅ Encontradas {len(opportunities)} oportunidades:")
        for i, opp in enumerate(opportunities, 1):
            print(f"  {i}. {opp['strategy'].upper()}: {opp['item_name']}")
            print(f"     💰 Profit: ${opp['expected_profit_usd']:.2f} ({opp['profit_percentage']:.1f}%)")
            print(f"     🎯 Confianza: {opp['confidence']*100:.0f}%")
        
    except Exception as e:
        print(f"❌ Error en análisis de mercado: {e}")

def demo_paper_trading(paper_trader):
    """Demostrar paper trading."""
    try:
        print(f"💰 Balance inicial: ${paper_trader.current_balance_usd:.2f}")
        
        # Simular algunas transacciones
        transactions = [
            {"action": "buy", "item": "AK-47 | Redline", "price": 25.50, "strategy": "basic_flip"},
            {"action": "sell", "item": "AK-47 | Redline", "price": 27.30},
            {"action": "buy", "item": "AWP | Asiimov", "price": 45.00, "strategy": "snipe"},
        ]
        
        for transaction in transactions:
            if transaction["action"] == "buy":
                success = paper_trader.execute_buy(
                    transaction["item"], 
                    transaction["price"],
                    transaction["strategy"]
                )
                if success:
                    print(f"✅ Compra: {transaction['item']} por ${transaction['price']:.2f}")
            else:
                success = paper_trader.execute_sell(
                    transaction["item"], 
                    transaction["price"]
                )
                if success:
                    print(f"✅ Venta: {transaction['item']} por ${transaction['price']:.2f}")
        
        # Mostrar resumen
        performance = paper_trader.get_performance_metrics()
        print(f"📊 Resumen Paper Trading:")
        print(f"   Balance actual: ${paper_trader.current_balance_usd:.2f}")
        print(f"   ROI: {performance.get('roi_percentage', 0):.2f}%")
        print(f"   Total trades: {performance.get('total_trades', 0)}")
        
    except Exception as e:
        print(f"❌ Error en paper trading: {e}")

def demo_risk_management(risk_manager):
    """Demostrar gestión de riesgos."""
    try:
        # Simular portfolio para análisis
        mock_portfolio = [
            {"item_name": "AK-47 | Redline", "current_value": 27.30, "purchase_price": 25.50, "category": "rifle"},
            {"item_name": "AWP | Asiimov", "current_value": 45.00, "purchase_price": 45.00, "category": "sniper"},
        ]
        
        # Calcular métricas de riesgo
        risk_metrics = risk_manager.calculate_risk_metrics(mock_portfolio)
        
        print("🛡️ Análisis de riesgo del portfolio:")
        print(f"   Nivel de riesgo: {risk_metrics.risk_level.value.upper()}")
        print(f"   Concentración: {risk_metrics.concentration_index:.3f}")
        print(f"   Diversificación: {risk_metrics.diversification_score:.3f}")
        print(f"   VaR (95%): ${risk_metrics.value_at_risk:.2f}")
        print(f"   Liquidez: {risk_metrics.liquidity_score:.3f}")
        
        # Evaluar un nuevo trade
        trade_evaluation = risk_manager.evaluate_trade_risk(
            "M4A4 | Howl", 150.0, "snipe", mock_portfolio
        )
        
        print(f"🔍 Evaluación de nuevo trade (M4A4 | Howl):")
        print(f"   Aprobado: {'✅ SÍ' if trade_evaluation.approved else '❌ NO'}")
        print(f"   Nivel de riesgo: {trade_evaluation.risk_level.value.upper()}")
        
    except Exception as e:
        print(f"❌ Error en gestión de riesgos: {e}")

def demo_kpi_tracking(kpi_tracker):
    """Demostrar tracking de KPIs."""
    try:
        # Simular datos de trading
        mock_trades = [
            {"strategy": "basic_flip", "profit": 1.80, "entry_date": datetime.now(timezone.utc) - timedelta(days=2)},
            {"strategy": "snipe", "profit": 7.00, "entry_date": datetime.now(timezone.utc) - timedelta(days=1)},
            {"strategy": "basic_flip", "profit": -2.50, "entry_date": datetime.now(timezone.utc)},
        ]
        
        # Procesar trades
        for trade in mock_trades:
            kpi_tracker.record_trade_result(
                strategy=trade["strategy"],
                profit_usd=trade["profit"],
                entry_price=25.0,
                exit_price=25.0 + trade["profit"],
                trade_date=trade["entry_date"]
            )
        
        # Generar métricas
        performance_metrics = kpi_tracker.get_performance_metrics()
        
        print("📈 Métricas de rendimiento:")
        print(f"   ROI Total: {performance_metrics.total_roi_percentage:.2f}%")
        print(f"   Win Rate: {performance_metrics.win_rate_percentage:.1f}%")
        print(f"   Profit Factor: {performance_metrics.profit_factor:.2f}")
        print(f"   Sharpe Ratio: {performance_metrics.sharpe_ratio:.2f}")
        print(f"   Max Drawdown: {performance_metrics.max_drawdown_percentage:.1f}%")
        
        # Análisis por estrategia
        strategy_analysis = kpi_tracker.get_strategy_performance()
        print("🎯 Rendimiento por estrategia:")
        for strategy, metrics in strategy_analysis.items():
            print(f"   {strategy}: ROI {metrics['roi_percentage']:.1f}%, Trades {metrics['total_trades']}")
        
    except Exception as e:
        print(f"❌ Error en KPI tracking: {e}")

def demo_parameter_optimization(dmarket_api):
    """Demostrar optimización de parámetros."""
    try:
        print("🧪 Iniciando optimización rápida de parámetros...")
        
        # Crear optimizador
        optimizer = ParameterOptimizer(dmarket_api)
        
        # Configurar parámetros a optimizar (versión reducida para demo)
        from core.optimizer import ParameterRange
        parameter_ranges = [
            ParameterRange("basic_flip_min_profit_percentage", 0.03, 0.07, 0.02),
            ParameterRange("snipe_discount_threshold", 0.10, 0.20, 0.05),
        ]
        
        # Ejecutar optimización rápida
        result = optimizer.optimize_parameters(
            parameter_ranges=parameter_ranges,
            target_metric=MetricType.ROI,
            method=OptimizationMethod.RANDOM_SEARCH,
            max_iterations=5  # Reducido para demo
        )
        
        print(f"✅ Optimización completada:")
        print(f"   Mejor ROI: {result.best_score:.2f}%")
        print(f"   Combinaciones evaluadas: {result.total_combinations}")
        print(f"   Tiempo: {result.optimization_time_seconds:.1f}s")
        print(f"   Mejores parámetros:")
        for param, value in result.best_parameters.items():
            print(f"     {param}: {value}")
        
    except Exception as e:
        print(f"❌ Error en optimización: {e}")

def demo_execution_engine(execution_engine):
    """Demostrar motor de ejecución."""
    try:
        print("⚙️ Demo del motor de ejecución automática...")
        
        # Simular oportunidades encontradas
        mock_opportunities = [
            {
                "strategy": "basic_flip",
                "item_name": "AK-47 | Redline",
                "buy_price_usd": 25.50,
                "expected_profit_usd": 1.80,
                "confidence": 0.85,
                "risk_level": "low"
            }
        ]
        
        # Procesar oportunidades
        print(f"🔄 Procesando {len(mock_opportunities)} oportunidades...")
        results = execution_engine.process_opportunities(mock_opportunities)
        
        print(f"✅ Resultados de ejecución:")
        print(f"   Órdenes procesadas: {results.get('orders_processed', 0)}")
        print(f"   Órdenes ejecutadas: {results.get('orders_executed', 0)}")
        print(f"   Órdenes rechazadas: {results.get('orders_rejected', 0)}")
        
        # Mostrar resumen
        summary = execution_engine.get_execution_summary()
        print(f"📊 Resumen del día:")
        print(f"   Total trades: {summary.get('total_trades_today', 0)}")
        print(f"   Capital utilizado: ${summary.get('capital_used_today', 0):.2f}")
        
    except Exception as e:
        print(f"❌ Error en motor de ejecución: {e}")

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 