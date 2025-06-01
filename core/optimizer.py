"""
Módulo de Optimización de Parámetros para Trading de Skins CS2

Este módulo implementa:
- Backtesting de estrategias
- Optimización de umbrales y parámetros
- Análisis de configuraciones
- Grid search y optimización bayesiana
- Validación cruzada temporal
"""

import logging
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import numpy as np
import json
import itertools
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# Añadir el directorio raíz al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.strategy_engine import StrategyEngine
from core.market_analyzer import MarketAnalyzer
from core.dmarket_connector import DMarketAPI
from core.paper_trader import PaperTrader
from core.data_manager import get_db, SkinsMaestra, PreciosHistoricos
from utils.helpers import normalize_price_to_usd

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    """Métodos de optimización disponibles."""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"


class MetricType(Enum):
    """Tipos de métricas para optimización."""
    ROI = "roi"
    SHARPE_RATIO = "sharpe_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    MAX_DRAWDOWN = "max_drawdown"
    TOTAL_PROFIT = "total_profit"


@dataclass
class ParameterRange:
    """Definición de rango de parámetros para optimización."""
    name: str
    min_value: float
    max_value: float
    step: float = 0.1
    values: Optional[List[float]] = None
    
    def get_values(self) -> List[float]:
        """Obtener lista de valores para el parámetro."""
        if self.values:
            return self.values
        # Fix para generar rangos correctos
        values = []
        current = self.min_value
        while current <= self.max_value + 1e-10:  # Small epsilon for float comparison
            values.append(round(current, 3))
            current += self.step
        return values


@dataclass
class BacktestResult:
    """Resultado de una prueba de backtesting."""
    parameters: Dict[str, Any]
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_profit_usd: float
    total_fees_usd: float
    roi_percentage: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_trade_duration_hours: float
    best_trade_profit: float
    worst_trade_loss: float
    strategy_breakdown: Dict[str, Dict[str, Any]]
    start_date: datetime
    end_date: datetime
    execution_time_seconds: float


@dataclass
class OptimizationResult:
    """Resultado completo de optimización."""
    method: OptimizationMethod
    target_metric: MetricType
    best_parameters: Dict[str, Any]
    best_score: float
    all_results: List[BacktestResult]
    parameter_ranges: List[ParameterRange]
    optimization_time_seconds: float
    total_combinations: int
    convergence_data: Optional[Dict[str, List[float]]] = None


class ParameterOptimizer:
    """
    Optimizador de parámetros para estrategias de trading.
    
    Permite optimizar umbrales y configuraciones mediante:
    - Backtesting histórico
    - Grid search
    - Random search
    - Optimización bayesiana
    """
    
    def __init__(self, dmarket_connector: DMarketAPI):
        """
        Inicializar optimizador.
        
        Args:
            dmarket_connector: Conector a DMarket API
        """
        self.dmarket_connector = dmarket_connector
        self.market_analyzer = MarketAnalyzer()
        
        # Configuración por defecto
        self.default_config = {
            # Estrategia Basic Flip
            "basic_flip_min_profit_percentage": 0.05,
            "basic_flip_max_risk_ratio": 0.3,
            
            # Estrategia Sniping
            "snipe_discount_threshold": 0.15,
            "snipe_confidence_threshold": 0.7,
            
            # Estrategia Attribute Premium
            "attribute_min_rarity_score": 0.6,
            "attribute_min_premium_multiplier": 1.2,
            
            # Estrategia Trade Lock
            "trade_lock_min_discount": 0.1,
            "trade_lock_max_days": 7,
            
            # Estrategia Volatility
            "volatility_rsi_oversold": 30,
            "volatility_rsi_overbought": 70,
            "volatility_bb_deviation": 2.0,
            
            # Configuración general
            "max_trade_amount_usd": 50.0,
            "min_expected_profit_usd": 2.0,
            "max_portfolio_exposure": 0.8
        }
        
        logger.info("ParameterOptimizer inicializado")
    
    def run_backtest(self, 
                    parameters: Dict[str, Any],
                    start_date: datetime,
                    end_date: datetime,
                    initial_balance: float = 1000.0,
                    items_to_test: Optional[List[str]] = None) -> BacktestResult:
        """
        Ejecutar backtesting con parámetros específicos.
        
        Args:
            parameters: Parámetros a probar
            start_date: Fecha de inicio del backtest
            end_date: Fecha de fin del backtest
            initial_balance: Balance inicial para simulación
            items_to_test: Lista de ítems específicos a probar
            
        Returns:
            BacktestResult con métricas del backtest
        """
        start_time = datetime.now()
        
        # Configurar paper trader con parámetros específicos
        paper_trader = PaperTrader(initial_balance_usd=initial_balance)
        
        # Configurar strategy engine con parámetros personalizados
        config = {**self.default_config, **parameters}
        strategy_engine = StrategyEngine(
            dmarket_connector=self.dmarket_connector,
            config=config
        )
        
        # Obtener datos históricos para el período
        historical_data = self._get_historical_data(start_date, end_date, items_to_test)
        
        if not historical_data:
            logger.warning("No hay datos históricos disponibles para el período especificado")
            return self._create_empty_backtest_result(parameters, start_date, end_date, 0.0)
        
        logger.info(f"Ejecutando backtest con {len(historical_data)} puntos de datos históricos")
        
        trades_executed = 0
        strategy_stats = {
            "basic_flip": {"trades": 0, "profit": 0.0},
            "snipe": {"trades": 0, "profit": 0.0},
            "attribute_premium": {"trades": 0, "profit": 0.0},
            "trade_lock": {"trades": 0, "profit": 0.0},
            "volatility": {"trades": 0, "profit": 0.0}
        }
        
        # Procesar datos históricos día por día
        current_date = start_date
        while current_date <= end_date:
            daily_data = [d for d in historical_data 
                         if d['date'].date() == current_date.date()]
            
            if daily_data:
                # Simular oportunidades encontradas
                for data_point in daily_data:
                    opportunities = self._simulate_opportunities(
                        data_point, strategy_engine, config
                    )
                    
                    # Ejecutar trades simulados
                    for opportunity in opportunities:
                        if paper_trader.current_balance_usd >= opportunity.get('required_capital', 0):
                            # Simular ejecución del trade
                            trade_result = self._simulate_trade_execution(
                                opportunity, paper_trader, data_point
                            )
                            
                            if trade_result:
                                trades_executed += 1
                                strategy_name = opportunity.get('strategy', 'unknown')
                                if strategy_name in strategy_stats:
                                    strategy_stats[strategy_name]["trades"] += 1
                                    strategy_stats[strategy_name]["profit"] += trade_result.get('profit', 0)
            
            current_date += timedelta(days=1)
        
        # Calcular métricas finales
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return self._calculate_backtest_metrics(
            paper_trader, strategy_stats, parameters, 
            start_date, end_date, execution_time
        )
    
    def optimize_parameters(self,
                           parameter_ranges: List[ParameterRange],
                           target_metric: MetricType = MetricType.ROI,
                           method: OptimizationMethod = OptimizationMethod.GRID_SEARCH,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           max_iterations: int = 100,
                           n_jobs: int = 1) -> OptimizationResult:
        """
        Optimizar parámetros de estrategias.
        
        Args:
            parameter_ranges: Rangos de parámetros a optimizar
            target_metric: Métrica objetivo a maximizar
            method: Método de optimización
            start_date: Fecha de inicio para backtesting
            end_date: Fecha de fin para backtesting
            max_iterations: Máximo número de iteraciones
            n_jobs: Número de trabajos paralelos
            
        Returns:
            OptimizationResult con mejores parámetros encontrados
        """
        start_time = datetime.now()
        
        # Configurar fechas por defecto (últimos 3 meses)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=90)
        
        logger.info(f"Iniciando optimización de parámetros usando {method.value}")
        logger.info(f"Período de backtesting: {start_date} a {end_date}")
        logger.info(f"Métrica objetivo: {target_metric.value}")
        
        # Generar combinaciones de parámetros
        parameter_combinations = self._generate_parameter_combinations(
            parameter_ranges, method, max_iterations
        )
        
        logger.info(f"Evaluando {len(parameter_combinations)} combinaciones de parámetros")
        
        # Ejecutar backtests
        all_results = []
        
        if n_jobs == 1:
            # Ejecución secuencial
            for i, params in enumerate(parameter_combinations):
                logger.info(f"Evaluando combinación {i+1}/{len(parameter_combinations)}")
                result = self.run_backtest(params, start_date, end_date)
                all_results.append(result)
        else:
            # Ejecución paralela
            with ThreadPoolExecutor(max_workers=n_jobs) as executor:
                futures = [
                    executor.submit(self.run_backtest, params, start_date, end_date)
                    for params in parameter_combinations
                ]
                
                for i, future in enumerate(futures):
                    logger.info(f"Completando evaluación {i+1}/{len(parameter_combinations)}")
                    result = future.result()
                    all_results.append(result)
        
        # Encontrar mejores parámetros
        best_result = self._find_best_result(all_results, target_metric)
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Optimización completada en {optimization_time:.2f} segundos")
        logger.info(f"Mejor {target_metric.value}: {best_result.roi_percentage:.2f}% ROI")
        
        return OptimizationResult(
            method=method,
            target_metric=target_metric,
            best_parameters=best_result.parameters,
            best_score=self._get_metric_value(best_result, target_metric),
            all_results=all_results,
            parameter_ranges=parameter_ranges,
            optimization_time_seconds=optimization_time,
            total_combinations=len(parameter_combinations)
        )
    
    def validate_parameters(self,
                           parameters: Dict[str, Any],
                           validation_periods: int = 3,
                           period_length_days: int = 30) -> Dict[str, Any]:
        """
        Validar parámetros usando validación cruzada temporal.
        
        Args:
            parameters: Parámetros a validar
            validation_periods: Número de períodos de validación
            period_length_days: Duración de cada período en días
            
        Returns:
            Dict con métricas de validación
        """
        end_date = datetime.now(timezone.utc)
        results = []
        
        for i in range(validation_periods):
            period_end = end_date - timedelta(days=i * period_length_days)
            period_start = period_end - timedelta(days=period_length_days)
            
            result = self.run_backtest(parameters, period_start, period_end)
            results.append(result)
        
        # Calcular estadísticas de validación
        rois = [r.roi_percentage for r in results]
        win_rates = [r.win_rate for r in results]
        sharpe_ratios = [r.sharpe_ratio for r in results]
        
        return {
            "validation_periods": validation_periods,
            "avg_roi": np.mean(rois),
            "std_roi": np.std(rois),
            "avg_win_rate": np.mean(win_rates),
            "std_win_rate": np.std(win_rates),
            "avg_sharpe": np.mean(sharpe_ratios),
            "std_sharpe": np.std(sharpe_ratios),
            "consistency_score": 1.0 - (np.std(rois) / (np.mean(rois) + 1e-6)),
            "all_positive_roi": all(roi > 0 for roi in rois),
            "detailed_results": results
        }
    
    def generate_optimization_report(self, 
                                   optimization_result: OptimizationResult,
                                   output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Generar reporte detallado de optimización.
        
        Args:
            optimization_result: Resultado de optimización
            output_file: Archivo de salida opcional
            
        Returns:
            Dict con reporte completo
        """
        best_result = min(optimization_result.all_results, 
                         key=lambda x: -self._get_metric_value(x, optimization_result.target_metric))
        
        # Análisis de sensibilidad de parámetros
        sensitivity_analysis = self._analyze_parameter_sensitivity(
            optimization_result.all_results, optimization_result.parameter_ranges
        )
        
        # Top resultados
        top_results = sorted(
            optimization_result.all_results,
            key=lambda x: -self._get_metric_value(x, optimization_result.target_metric)
        )[:10]
        
        report = {
            "optimization_summary": {
                "method": optimization_result.method.value,
                "target_metric": optimization_result.target_metric.value,
                "total_combinations": optimization_result.total_combinations,
                "optimization_time_seconds": optimization_result.optimization_time_seconds,
                "best_score": optimization_result.best_score
            },
            "best_parameters": optimization_result.best_parameters,
            "best_result_details": {
                "roi_percentage": best_result.roi_percentage,
                "total_trades": best_result.total_trades,
                "win_rate": best_result.win_rate,
                "profit_factor": best_result.profit_factor,
                "sharpe_ratio": best_result.sharpe_ratio,
                "max_drawdown": best_result.max_drawdown
            },
            "parameter_sensitivity": sensitivity_analysis,
            "top_10_results": [
                {
                    "parameters": result.parameters,
                    "roi": result.roi_percentage,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades
                }
                for result in top_results
            ],
            "performance_statistics": {
                "avg_roi": np.mean([r.roi_percentage for r in optimization_result.all_results]),
                "std_roi": np.std([r.roi_percentage for r in optimization_result.all_results]),
                "avg_trades": np.mean([r.total_trades for r in optimization_result.all_results]),
                "success_rate": len([r for r in optimization_result.all_results if r.roi_percentage > 0]) / len(optimization_result.all_results)
            }
        }
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str, ensure_ascii=False)
            logger.info(f"Reporte guardado en {output_file}")
        
        return report
    
    def _get_historical_data(self, 
                           start_date: datetime, 
                           end_date: datetime,
                           items_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Obtener datos históricos para backtesting."""
        try:
            with next(get_db()) as db:
                # Query con join para obtener market_hash_name de SkinsMaestra
                query = db.query(
                    PreciosHistoricos,
                    SkinsMaestra.market_hash_name
                ).join(SkinsMaestra, PreciosHistoricos.skin_id == SkinsMaestra.id).filter(
                    PreciosHistoricos.timestamp >= start_date,
                    PreciosHistoricos.timestamp <= end_date
                )
                
                if items_filter:
                    query = query.filter(SkinsMaestra.market_hash_name.in_(items_filter))
                
                records = query.all()
                
                return [
                    {
                        'market_hash_name': record.market_hash_name,
                        'price_usd': record.PreciosHistoricos.price,
                        'volume': record.PreciosHistoricos.volume or 1,
                        'date': record.PreciosHistoricos.timestamp,
                        'source': record.PreciosHistoricos.fuente_api
                    }
                    for record in records
                ]
        except Exception as e:
            logger.error(f"Error obteniendo datos históricos: {e}")
            return []
    
    def _simulate_opportunities(self, 
                              data_point: Dict[str, Any], 
                              strategy_engine: StrategyEngine,
                              config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Simular oportunidades de trading basadas en datos históricos."""
        opportunities = []
        
        try:
            # Simular datos de ofertas basados en precio histórico
            mock_sell_offers = [
                {
                    'price': {'USD': str(int(data_point['price_usd'] * 100))},
                    'amount': 1
                }
            ]
            
            mock_buy_orders = [
                {
                    'price': {'USD': str(int(data_point['price_usd'] * 0.95 * 100))},
                    'amount': 1
                }
            ]
            
            # Evaluar cada estrategia
            if data_point['price_usd'] <= config.get('max_trade_amount_usd', 50.0):
                # Basic flip opportunity
                profit_margin = 0.05  # 5% margen mínimo
                if data_point['price_usd'] * (1 + profit_margin) < data_point['price_usd'] * 1.1:
                    opportunities.append({
                        'strategy': 'basic_flip',
                        'item_name': data_point['market_hash_name'],
                        'buy_price': data_point['price_usd'],
                        'estimated_sell_price': data_point['price_usd'] * 1.08,
                        'expected_profit': data_point['price_usd'] * 0.03,
                        'required_capital': data_point['price_usd'],
                        'confidence': 0.8
                    })
                
                # Snipe opportunity (si el precio está por debajo del promedio)
                if data_point['price_usd'] < 20.0:  # Solo para ítems baratos
                    opportunities.append({
                        'strategy': 'snipe',
                        'item_name': data_point['market_hash_name'],
                        'buy_price': data_point['price_usd'],
                        'estimated_sell_price': data_point['price_usd'] * 1.15,
                        'expected_profit': data_point['price_usd'] * 0.10,
                        'required_capital': data_point['price_usd'],
                        'confidence': 0.7
                    })
        
        except Exception as e:
            logger.error(f"Error simulando oportunidades: {e}")
        
        return opportunities
    
    def _simulate_trade_execution(self, 
                                opportunity: Dict[str, Any], 
                                paper_trader: PaperTrader,
                                data_point: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Simular ejecución de un trade."""
        try:
            # Simular compra
            buy_success = paper_trader.execute_buy(
                item_title=opportunity['item_name'],
                price_usd=opportunity['buy_price'],
                strategy=opportunity['strategy']
            )
            
            if not buy_success:
                return None
            
            # Simular venta después de un tiempo aleatorio (1-7 días)
            import random
            days_to_sell = random.randint(1, 7)
            
            # Simular fluctuación de precio
            price_change = random.uniform(-0.1, 0.1)  # ±10%
            actual_sell_price = opportunity['estimated_sell_price'] * (1 + price_change)
            
            sell_success = paper_trader.execute_sell(
                item_title=opportunity['item_name'],
                price_usd=actual_sell_price
            )
            
            if sell_success:
                profit = actual_sell_price - opportunity['buy_price']
                return {
                    'profit': profit,
                    'buy_price': opportunity['buy_price'],
                    'sell_price': actual_sell_price,
                    'strategy': opportunity['strategy'],
                    'days_held': days_to_sell
                }
        
        except Exception as e:
            logger.error(f"Error simulando ejecución de trade: {e}")
        
        return None
    
    def _generate_parameter_combinations(self, 
                                       parameter_ranges: List[ParameterRange],
                                       method: OptimizationMethod,
                                       max_iterations: int) -> List[Dict[str, Any]]:
        """Generar combinaciones de parámetros según el método especificado."""
        if method == OptimizationMethod.GRID_SEARCH:
            return self._grid_search_combinations(parameter_ranges, max_iterations)
        elif method == OptimizationMethod.RANDOM_SEARCH:
            return self._random_search_combinations(parameter_ranges, max_iterations)
        else:
            # Por simplicidad, usar random search para bayesiano
            return self._random_search_combinations(parameter_ranges, max_iterations)
    
    def _grid_search_combinations(self, 
                                parameter_ranges: List[ParameterRange],
                                max_iterations: int) -> List[Dict[str, Any]]:
        """Generar todas las combinaciones para grid search."""
        parameter_values = [param_range.get_values() for param_range in parameter_ranges]
        parameter_names = [param_range.name for param_range in parameter_ranges]
        
        combinations = list(itertools.product(*parameter_values))
        
        # Limitar a max_iterations si es necesario
        if len(combinations) > max_iterations:
            import random
            combinations = random.sample(combinations, max_iterations)
        
        return [
            dict(zip(parameter_names, combination))
            for combination in combinations
        ]
    
    def _random_search_combinations(self, 
                                  parameter_ranges: List[ParameterRange],
                                  max_iterations: int) -> List[Dict[str, Any]]:
        """Generar combinaciones aleatorias para random search."""
        import random
        combinations = []
        
        for _ in range(max_iterations):
            combination = {}
            for param_range in parameter_ranges:
                values = param_range.get_values()
                combination[param_range.name] = random.choice(values)
            combinations.append(combination)
        
        return combinations
    
    def _find_best_result(self, 
                         results: List[BacktestResult], 
                         target_metric: MetricType) -> BacktestResult:
        """Encontrar el mejor resultado según la métrica objetivo."""
        if not results:
            raise ValueError("No hay resultados para evaluar")
        
        return max(results, key=lambda x: self._get_metric_value(x, target_metric))
    
    def _get_metric_value(self, result: BacktestResult, metric: MetricType) -> float:
        """Obtener valor de métrica específica de un resultado."""
        if metric == MetricType.ROI:
            return result.roi_percentage
        elif metric == MetricType.SHARPE_RATIO:
            return result.sharpe_ratio
        elif metric == MetricType.WIN_RATE:
            return result.win_rate
        elif metric == MetricType.PROFIT_FACTOR:
            return result.profit_factor
        elif metric == MetricType.MAX_DRAWDOWN:
            return -result.max_drawdown  # Negativo porque queremos minimizar drawdown
        elif metric == MetricType.TOTAL_PROFIT:
            return result.total_profit_usd
        else:
            return result.roi_percentage
    
    def _calculate_backtest_metrics(self, 
                                  paper_trader: PaperTrader,
                                  strategy_stats: Dict[str, Dict[str, Any]],
                                  parameters: Dict[str, Any],
                                  start_date: datetime,
                                  end_date: datetime,
                                  execution_time: float) -> BacktestResult:
        """Calcular métricas finales del backtest."""
        # Obtener métricas del paper trader
        performance = paper_trader.get_performance_metrics()
        
        total_trades = sum(stats['trades'] for stats in strategy_stats.values())
        winning_trades = max(1, int(total_trades * performance.get('win_rate_percentage', 0) / 100))
        
        return BacktestResult(
            parameters=parameters,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=total_trades - winning_trades,
            total_profit_usd=performance.get('total_profit_usd', 0.0),
            total_fees_usd=performance.get('total_fees_usd', 0.0),
            roi_percentage=performance.get('roi_percentage', 0.0),
            win_rate=performance.get('win_rate_percentage', 0.0) / 100,
            profit_factor=performance.get('profit_factor', 1.0),
            sharpe_ratio=performance.get('sharpe_ratio', 0.0),
            max_drawdown=performance.get('max_drawdown_percentage', 0.0) / 100,
            avg_trade_duration_hours=24.0,  # Placeholder
            best_trade_profit=performance.get('best_trade_profit', 0.0),
            worst_trade_loss=performance.get('worst_trade_loss', 0.0),
            strategy_breakdown=strategy_stats,
            start_date=start_date,
            end_date=end_date,
            execution_time_seconds=execution_time
        )
    
    def _create_empty_backtest_result(self, 
                                    parameters: Dict[str, Any],
                                    start_date: datetime,
                                    end_date: datetime,
                                    execution_time: float) -> BacktestResult:
        """Crear resultado vacío cuando no hay datos."""
        return BacktestResult(
            parameters=parameters,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            total_profit_usd=0.0,
            total_fees_usd=0.0,
            roi_percentage=0.0,
            win_rate=0.0,
            profit_factor=1.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            avg_trade_duration_hours=0.0,
            best_trade_profit=0.0,
            worst_trade_loss=0.0,
            strategy_breakdown={},
            start_date=start_date,
            end_date=end_date,
            execution_time_seconds=execution_time
        )
    
    def _analyze_parameter_sensitivity(self, 
                                     results: List[BacktestResult],
                                     parameter_ranges: List[ParameterRange]) -> Dict[str, Dict[str, float]]:
        """Analizar sensibilidad de parámetros."""
        sensitivity = {}
        
        for param_range in parameter_ranges:
            param_name = param_range.name
            param_values = []
            metric_values = []
            
            for result in results:
                if param_name in result.parameters:
                    param_values.append(result.parameters[param_name])
                    metric_values.append(result.roi_percentage)
            
            if len(param_values) > 1:
                correlation = np.corrcoef(param_values, metric_values)[0, 1]
                sensitivity[param_name] = {
                    "correlation": correlation if not np.isnan(correlation) else 0.0,
                    "importance": abs(correlation) if not np.isnan(correlation) else 0.0,
                    "optimal_value": param_values[np.argmax(metric_values)],
                    "value_range": [min(param_values), max(param_values)]
                }
        
        return sensitivity


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
    result = optimizer.optimize_parameters(
        parameter_ranges=parameter_ranges,
        target_metric=MetricType.ROI,
        method=OptimizationMethod.RANDOM_SEARCH,
        max_iterations=20
    )
    
    # Generar reporte
    report = optimizer.generate_optimization_report(
        result, 
        output_file="optimization_report.json"
    )
    
    print(f"Mejores parámetros encontrados:")
    for param, value in result.best_parameters.items():
        print(f"  {param}: {value}")
    print(f"ROI obtenido: {result.best_score:.2f}%") 