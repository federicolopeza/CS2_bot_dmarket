"""
Optimizador de Parámetros para Estrategias de Trading REAL
=========================================================

Sistema para optimizar parámetros de estrategias usando TRADING REAL.
ELIMINADA toda simulación - usa RealTrader con DMarket API.
"""

import logging
import numpy as np
import random
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.strategy_engine import StrategyEngine
from core.real_trader import RealTrader  # CAMBIADO DE PaperTrader a RealTrader
from core.market_analyzer import MarketAnalyzer
from core.dmarket_connector import DMarketAPI
from core.data_manager import get_db, PreciosHistoricos, SkinsMaestra
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Tipos de métricas para optimización."""
    TOTAL_RETURN = "total_return"
    SHARPE_RATIO = "sharpe_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    MAX_DRAWDOWN = "max_drawdown"
    AVERAGE_TRADE = "average_trade"
    TRADES_PER_DAY = "trades_per_day"

class OptimizationMethod(Enum):
    """Métodos de optimización disponibles."""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    GENETIC_ALGORITHM = "genetic_algorithm"
    BAYESIAN_OPTIMIZATION = "bayesian_optimization"

@dataclass
class ParameterRange:
    """Definición de rango para un parámetro."""
    name: str
    min_value: float
    max_value: float
    step: Optional[float] = None
    values: Optional[List[Union[float, int, str]]] = None
    
@dataclass
class OptimizationResult:
    """Resultado de una optimización."""
    best_parameters: Dict[str, Any]
    best_score: float
    all_results: List[Dict[str, Any]]
    optimization_time: float
    total_evaluations: int

class ParameterOptimizer:
    """
    Optimizador de parámetros para estrategias de trading REAL.
    ELIMINADAS todas las simulaciones - usa RealTrader real.
    """

    def __init__(self, 
                 dmarket_api: DMarketAPI,
                 strategy_engine: StrategyEngine, 
                 market_analyzer: MarketAnalyzer,
                 config: Optional[Dict[str, Any]] = None):
        """
        Inicializar el optimizador para trading REAL.
        
        Args:
            dmarket_api: Instancia del conector DMarket
            strategy_engine: Motor de estrategias
            market_analyzer: Analizador de mercado
            config: Configuración del optimizador
        """
        self.dmarket_api = dmarket_api
        self.strategy_engine = strategy_engine
        self.market_analyzer = market_analyzer
        
        self.config = config or self._get_default_config()
        
        # Configuración específica para trading real
        self.real_trader_config = {
            "max_position_size_usd": 25.0,  # Límite por posición
            "max_total_exposure_pct": 60.0,  # Máximo 60% del capital en riesgo
            "require_manual_confirmation": True,  # Confirmación manual para optimización
            "auto_confirm_below_usd": 2.0,  # Auto-confirmar solo trades muy pequeños
            "stop_loss_pct": -10.0,
            "take_profit_pct": 15.0
        }
        
        logger.info("🔥 ParameterOptimizer inicializado para TRADING REAL")
        logger.warning("⚠️ ADVERTENCIA: Las optimizaciones usarán dinero REAL")

    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto del optimizador para trading real."""
        return {
            # Configuración para trading real
            "use_real_trading": True,  # SIEMPRE real
            "max_optimization_trades": 20,  # Límite de trades reales durante optimización
            "max_optimization_amount_usd": 100.0,  # Máximo a gastar en optimización
            "optimization_trade_size_usd": 5.0,  # Tamaño pequeño por trade
            
            # Configuración de optimización
            "max_evaluations": 50,  # Reducido para trading real
            "parallel_evaluations": 2,  # Máximo 2 evaluaciones paralelas
            "timeout_per_evaluation": 300,  # 5 minutos por evaluación
            
            # Configuración de backtesting (usando datos históricos)
            "backtest_days": 7,  # Solo 7 días de datos
            "min_trades_for_evaluation": 3,  # Mínimo trades para evaluar
            
            # Configuración de métricas
            "primary_metric": MetricType.TOTAL_RETURN,
            "secondary_metrics": [MetricType.WIN_RATE, MetricType.SHARPE_RATIO],
            
            # Configuración de validación
            "validation_split": 0.3,
            "cross_validation_folds": 2,  # Reducido para trading real
            
            # Configuración de logging
            "log_all_evaluations": True,
            "save_intermediate_results": True
        }

    def optimize_strategy_parameters(self,
                                   strategy_name: str,
                                   parameter_ranges: List[ParameterRange],
                                   method: OptimizationMethod = OptimizationMethod.GRID_SEARCH,
                                   target_metric: MetricType = MetricType.TOTAL_RETURN,
                                   **kwargs) -> OptimizationResult:
        """
        Optimizar parámetros de una estrategia usando TRADING REAL.
        
        ADVERTENCIA: Esto ejecutará trades REALES para evaluar parámetros.
        """
        logger.warning("🔥 INICIANDO OPTIMIZACIÓN CON TRADING REAL")
        logger.warning("💰 Esto ejecutará trades REALES con dinero REAL")
        
        start_time = time.time()
        
        # Verificar balance antes de optimizar
        initial_balance = self._get_current_balance()
        if initial_balance < self.config["max_optimization_amount_usd"]:
            raise ValueError(f"Balance insuficiente para optimización: ${initial_balance:.2f} < ${self.config['max_optimization_amount_usd']:.2f}")
        
        logger.info(f"💰 Balance inicial para optimización: ${initial_balance:.2f}")
        
        try:
            if method == OptimizationMethod.GRID_SEARCH:
                result = self._grid_search_real(strategy_name, parameter_ranges, target_metric)
            elif method == OptimizationMethod.RANDOM_SEARCH:
                result = self._random_search_real(strategy_name, parameter_ranges, target_metric, **kwargs)
            elif method == OptimizationMethod.GENETIC_ALGORITHM:
                result = self._genetic_algorithm_real(strategy_name, parameter_ranges, target_metric, **kwargs)
            else:
                raise ValueError(f"Método de optimización no soportado para trading real: {method}")
            
            optimization_time = time.time() - start_time
            result.optimization_time = optimization_time
            
            final_balance = self._get_current_balance()
            total_spent = initial_balance - final_balance
            
            logger.info(f"🔥 OPTIMIZACIÓN REAL COMPLETADA")
            logger.info(f"⏰ Tiempo: {optimization_time:.2f} segundos")
            logger.info(f"💰 Dinero gastado: ${total_spent:.2f}")
            logger.info(f"🎯 Mejor score: {result.best_score:.4f}")
            logger.info(f"📊 Evaluaciones: {result.total_evaluations}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error en optimización real: {e}")
            raise

    def _get_current_balance(self) -> float:
        """Obtener balance actual real de DMarket."""
        try:
            balance_response = self.dmarket_api.get_account_balance()
            if "error" in balance_response:
                logger.error(f"Error obteniendo balance: {balance_response}")
                return 0.0
            
            if "usd" in balance_response:
                usd_cents = balance_response.get("usd", "0")
                return float(usd_cents) / 100.0
            elif "balance" in balance_response:
                usd_cents = balance_response.get("balance", {}).get("USD", "0")
                return float(usd_cents) / 100.0
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error obteniendo balance real: {e}")
            return 0.0

    def _grid_search_real(self, strategy_name: str, parameter_ranges: List[ParameterRange], 
                         target_metric: MetricType) -> OptimizationResult:
        """Grid search usando trading REAL."""
        logger.warning("🔥 EJECUTANDO GRID SEARCH CON DINERO REAL")
        
        # Generar todas las combinaciones de parámetros
        parameter_combinations = self._generate_parameter_combinations(parameter_ranges)
        
        # Limitar combinaciones para trading real
        max_combinations = min(len(parameter_combinations), self.config["max_evaluations"])
        if len(parameter_combinations) > max_combinations:
            logger.warning(f"⚠️ Limitando combinaciones de {len(parameter_combinations)} a {max_combinations} para trading real")
            parameter_combinations = parameter_combinations[:max_combinations]
        
        results = []
        trades_executed = 0
        total_spent = 0.0
        
        for i, params in enumerate(parameter_combinations):
            logger.info(f"🔄 Evaluando combinación {i+1}/{len(parameter_combinations)}: {params}")
            
            # Verificar límites de trading real
            if trades_executed >= self.config["max_optimization_trades"]:
                logger.warning("⚠️ Límite de trades alcanzado, deteniendo optimización")
                break
                
            if total_spent >= self.config["max_optimization_amount_usd"]:
                logger.warning("⚠️ Límite de gasto alcanzado, deteniendo optimización")
                break
            
            try:
                # Evaluar parámetros con trading real
                score, evaluation_data = self._evaluate_parameters_real(strategy_name, params, target_metric)
                
                result_data = {
                    "parameters": params.copy(),
                    "score": score,
                    "trades_executed": evaluation_data.get("trades_executed", 0),
                    "money_spent": evaluation_data.get("money_spent", 0.0),
                    "evaluation_time": evaluation_data.get("evaluation_time", 0),
                    "metrics": evaluation_data.get("metrics", {})
                }
                
                results.append(result_data)
                trades_executed += evaluation_data.get("trades_executed", 0)
                total_spent += evaluation_data.get("money_spent", 0.0)
                
                logger.info(f"✅ Score: {score:.4f}, Trades: {evaluation_data.get('trades_executed', 0)}, Gastado: ${evaluation_data.get('money_spent', 0.0):.2f}")
                
            except Exception as e:
                logger.error(f"❌ Error evaluando parámetros {params}: {e}")
                continue
        
        # Encontrar mejores parámetros
        if not results:
            raise ValueError("No se pudieron evaluar parámetros con trading real")
        
        best_result = max(results, key=lambda x: x["score"])
        
        return OptimizationResult(
            best_parameters=best_result["parameters"],
            best_score=best_result["score"],
            all_results=results,
            optimization_time=0,  # Se calculará fuera
            total_evaluations=len(results)
        )

    def _evaluate_parameters_real(self, strategy_name: str, parameters: Dict[str, Any], 
                                 target_metric: MetricType) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluar parámetros ejecutando trades REALES.
        
        ADVERTENCIA: Esto ejecuta trades REALES con dinero REAL.
        """
        start_time = time.time()
        
        logger.info(f"🔥 EVALUANDO PARÁMETROS CON TRADING REAL: {parameters}")
        
        # Crear RealTrader para esta evaluación
        real_trader = RealTrader(self.dmarket_api, config=self.real_trader_config)
        
        # Configurar strategy engine con nuevos parámetros
        original_config = self.strategy_engine.config.copy()
        self.strategy_engine.config.update(parameters)
        
        initial_balance = real_trader.get_real_balance()["total_balance"]
        
        try:
            # Ejecutar trades reales para evaluar
            evaluation_data = self._execute_real_evaluation_trades(
                strategy_name, real_trader, parameters
            )
            
            final_balance = real_trader.get_real_balance()["total_balance"]
            money_spent = initial_balance - final_balance
            
            # Calcular métricas
            metrics = self._calculate_real_metrics(evaluation_data, initial_balance, final_balance)
            
            # Obtener score según métrica objetivo
            score = self._get_metric_score(metrics, target_metric)
            
            evaluation_time = time.time() - start_time
            
            result_data = {
                "trades_executed": evaluation_data.get("trades_count", 0),
                "money_spent": money_spent,
                "evaluation_time": evaluation_time,
                "metrics": metrics,
                "initial_balance": initial_balance,
                "final_balance": final_balance
            }
            
            logger.info(f"✅ Evaluación completada: Score={score:.4f}, Trades={evaluation_data.get('trades_count', 0)}, Gastado=${money_spent:.2f}")
            
            return score, result_data
            
        finally:
            # Restaurar configuración original
            self.strategy_engine.config = original_config

    def _execute_real_evaluation_trades(self, strategy_name: str, real_trader: RealTrader, 
                                       parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecutar trades REALES para evaluar parámetros.
        
        ESTO USA DINERO REAL - SER MUY CUIDADOSO.
        """
        logger.warning("💰 EJECUTANDO TRADES REALES PARA EVALUACIÓN")
        
        # Lista pequeña de ítems baratos para evaluación
        evaluation_items = [
            "P250 | Sand Dune (Battle-Scarred)",
            "Nova | Walnut (Battle-Scarred)",
            "MAC-10 | Candy Apple (Battle-Scarred)",
            "Chroma Case",
            "Chroma 2 Case"
        ]
        
        trades_data = []
        trades_executed = 0
        max_evaluation_trades = 5  # Máximo 5 trades por evaluación
        
        logger.info(f"🎯 Buscando oportunidades en {len(evaluation_items)} ítems baratos...")
        
        try:
            # Buscar oportunidades con los parámetros a evaluar
            strategy_results = self.strategy_engine.run_strategies(evaluation_items)
            
            all_opportunities = []
            for strategy, opportunities in strategy_results.items():
                if opportunities:
                    all_opportunities.extend(opportunities)
            
            # Filtrar por balance y límites
            affordable_opportunities = []
            current_balance = real_trader.get_real_balance()["cash_balance"]
            
            for opp in all_opportunities:
                buy_price = opp.get("buy_price_usd", 0)
                if (buy_price <= self.config["optimization_trade_size_usd"] and 
                    buy_price <= current_balance * 0.1):  # Máximo 10% del balance por trade
                    affordable_opportunities.append(opp)
            
            # Limitar a las mejores oportunidades
            affordable_opportunities.sort(key=lambda x: x.get("expected_profit_usd", 0), reverse=True)
            affordable_opportunities = affordable_opportunities[:max_evaluation_trades]
            
            logger.info(f"📊 Encontradas {len(affordable_opportunities)} oportunidades evaluables")
            
            # Ejecutar trades reales
            for i, opportunity in enumerate(affordable_opportunities):
                if trades_executed >= max_evaluation_trades:
                    break
                
                try:
                    logger.info(f"🔥 Ejecutando trade real {i+1}/{len(affordable_opportunities)}")
                    
                    # EJECUTAR COMPRA REAL
                    trade_result = real_trader.execute_real_buy(opportunity)
                    
                    if trade_result.get("success", False):
                        trades_executed += 1
                        trades_data.append({
                            "opportunity": opportunity,
                            "result": trade_result,
                            "success": True
                        })
                        logger.info(f"✅ Trade real exitoso #{trades_executed}")
                    else:
                        logger.warning(f"⚠️ Trade real falló: {trade_result.get('reason', 'Unknown')}")
                        trades_data.append({
                            "opportunity": opportunity,
                            "result": trade_result,
                            "success": False
                        })
                
                except Exception as e:
                    logger.error(f"❌ Error ejecutando trade real: {e}")
                    continue
            
            return {
                "trades_count": trades_executed,
                "trades_data": trades_data,
                "opportunities_found": len(all_opportunities),
                "opportunities_affordable": len(affordable_opportunities)
            }
            
        except Exception as e:
            logger.error(f"❌ Error en evaluación de trades reales: {e}")
            return {
                "trades_count": 0,
                "trades_data": [],
                "error": str(e)
            }

    def _calculate_real_metrics(self, evaluation_data: Dict[str, Any], 
                               initial_balance: float, final_balance: float) -> Dict[str, float]:
        """Calcular métricas basadas en trades reales ejecutados."""
        trades_data = evaluation_data.get("trades_data", [])
        trades_count = evaluation_data.get("trades_count", 0)
        
        if trades_count == 0:
            return {
                "total_return": 0.0,
                "win_rate": 0.0,
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "average_trade": 0.0,
                "trades_per_day": 0.0
            }
        
        # Calcular métricas básicas
        total_return = final_balance - initial_balance
        return_percentage = (total_return / initial_balance) * 100 if initial_balance > 0 else 0
        
        successful_trades = sum(1 for trade in trades_data if trade.get("success", False))
        win_rate = (successful_trades / trades_count) * 100 if trades_count > 0 else 0
        
        # Métricas adicionales
        avg_trade = total_return / trades_count if trades_count > 0 else 0
        
        # Para Sharpe ratio necesitaríamos múltiples observaciones, usar approximación simple
        sharpe_ratio = return_percentage / 10.0 if return_percentage > 0 else 0  # Aproximación simple
        
        return {
            "total_return": total_return,
            "return_percentage": return_percentage,
            "win_rate": win_rate,
            "sharpe_ratio": sharpe_ratio,
            "profit_factor": max(1.0, abs(total_return) + 1) if total_return > 0 else 0.1,
            "max_drawdown": min(0, total_return),  # Simplificado
            "average_trade": avg_trade,
            "trades_per_day": trades_count,  # Para evaluación corta
            "trades_executed": trades_count,
            "successful_trades": successful_trades
        }

    def _get_metric_score(self, metrics: Dict[str, float], target_metric: MetricType) -> float:
        """Obtener score según la métrica objetivo."""
        if target_metric == MetricType.TOTAL_RETURN:
            return metrics.get("total_return", 0.0)
        elif target_metric == MetricType.WIN_RATE:
            return metrics.get("win_rate", 0.0) / 100.0  # Normalizar a 0-1
        elif target_metric == MetricType.SHARPE_RATIO:
            return max(0, metrics.get("sharpe_ratio", 0.0))
        elif target_metric == MetricType.PROFIT_FACTOR:
            return metrics.get("profit_factor", 0.0)
        elif target_metric == MetricType.AVERAGE_TRADE:
            return metrics.get("average_trade", 0.0)
        else:
            return metrics.get("total_return", 0.0)  # Default

    def _generate_parameter_combinations(self, parameter_ranges: List[ParameterRange]) -> List[Dict[str, Any]]:
        """Generar todas las combinaciones posibles de parámetros."""
        combinations = []
        for param_range in parameter_ranges:
            values = param_range.get_values()
            if values:
                for value in values:
                    combinations.append({param_range.name: value})
        return combinations


def create_default_optimization_config() -> List[ParameterRange]:
    """Crear configuración de optimización por defecto."""
    return [
        ParameterRange("basic_flip_min_profit_percentage", 0.02, 0.10, 0.01),
        ParameterRange("snipe_discount_threshold", 0.10, 0.25, 0.05),
        ParameterRange("attribute_min_rarity_score", 0.5, 0.8, 0.1),
        ParameterRange("trade_lock_min_discount", 0.05, 0.20, 0.05),
        ParameterRange("volatility_rsi_oversold", 20, 40, 5),
        ParameterRange("volatility_rsi_overbought", 60, 80, 5),
        ParameterRange("max_trade_amount_usd", 20.0, 100.0, 20.0),
        ParameterRange("min_expected_profit_usd", 1.0, 5.0, 1.0)
    ]


if __name__ == "__main__":
    # Ejemplo de uso
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    # Inicializar conectores
    dmarket_connector = DMarketAPI(
        public_key=os.getenv("DMARKET_PUBLIC_KEY"),
        secret_key=os.getenv("DMARKET_SECRET_KEY")
    )
    
    # Crear optimizador
    optimizer = ParameterOptimizer(dmarket_connector)
    
    # Configurar rangos de parámetros
    parameter_ranges = create_default_optimization_config()
    
    # Ejecutar optimización
    result = optimizer.optimize_strategy_parameters(
        strategy_name="basic_flip",
        parameter_ranges=parameter_ranges,
        method=OptimizationMethod.GRID_SEARCH,
        target_metric=MetricType.TOTAL_RETURN
    )
    
    # Generar reporte
    report = optimizer.generate_optimization_report(
        result, 
        output_file="optimization_report.json"
    )
    
    print(f"Mejores parámetros encontrados:")
    for param, value in result.best_parameters.items():
        print(f"  {param}: {value}")
    print(f"TOTAL RETURN obtenido: {result.best_score:.2f}%") 