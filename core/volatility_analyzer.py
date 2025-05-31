# core/volatility_analyzer.py
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class TrendDirection(Enum):
    """Dirección de la tendencia del precio."""
    BULLISH = "bullish"      # Tendencia alcista
    BEARISH = "bearish"      # Tendencia bajista
    SIDEWAYS = "sideways"    # Tendencia lateral
    UNKNOWN = "unknown"      # No se puede determinar

class VolatilityLevel(Enum):
    """Nivel de volatilidad del precio."""
    LOW = "low"              # Baja volatilidad
    MEDIUM = "medium"        # Volatilidad media
    HIGH = "high"            # Alta volatilidad
    EXTREME = "extreme"      # Volatilidad extrema

class SignalStrength(Enum):
    """Fuerza de la señal de trading."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"

@dataclass
class TechnicalIndicators:
    """Indicadores técnicos calculados."""
    rsi: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_width: Optional[float] = None
    moving_average_short: Optional[float] = None
    moving_average_long: Optional[float] = None
    price_change_24h: Optional[float] = None
    price_change_7d: Optional[float] = None
    volatility_score: Optional[float] = None

@dataclass
class VolatilitySignal:
    """Señal de volatilidad para trading."""
    signal_type: str
    strength: SignalStrength
    confidence: float
    entry_price: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    expected_profit: float
    risk_reward_ratio: float
    indicators: TechnicalIndicators
    reasoning: str
    timestamp: datetime

class VolatilityAnalyzer:
    """
    Analizador de volatilidad que utiliza indicadores técnicos para identificar
    oportunidades de trading basadas en movimientos de precio.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el VolatilityAnalyzer.
        
        Args:
            config: Configuración para los parámetros del análisis
        """
        self.config = self._get_default_config()
        if config:
            self.config.update(config)
        
        logger.info(f"VolatilityAnalyzer inicializado con configuración: {self.config}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Retorna configuración por defecto para el análisis de volatilidad."""
        return {
            # Parámetros para RSI
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            
            # Parámetros para Bollinger Bands
            "bb_period": 20,
            "bb_std_dev": 2,
            
            # Parámetros para Moving Averages
            "ma_short_period": 7,
            "ma_long_period": 21,
            
            # Umbrales de volatilidad
            "volatility_low_threshold": 0.05,      # 5%
            "volatility_medium_threshold": 0.15,   # 15%
            "volatility_high_threshold": 0.30,     # 30%
            
            # Parámetros de trading
            "min_profit_percentage": 0.08,         # 8% mínimo
            "max_risk_percentage": 0.05,           # 5% máximo riesgo
            "min_confidence": 0.6,                 # 60% confianza mínima
            "min_data_points": 10,                 # Mínimo puntos de datos
            
            # Risk management
            "stop_loss_percentage": 0.03,          # 3% stop loss
            "take_profit_multiplier": 2.0,         # 2:1 risk/reward ratio
        }

    def analyze_price_data(self, price_data: List[Dict[str, Any]]) -> Optional[TechnicalIndicators]:
        """
        Analiza datos de precio y calcula indicadores técnicos.
        
        Args:
            price_data: Lista de datos de precio con timestamp y price_usd
            
        Returns:
            TechnicalIndicators calculados o None si no hay suficientes datos
        """
        if len(price_data) < self.config["min_data_points"]:
            logger.debug(f"Insuficientes datos de precio: {len(price_data)} < {self.config['min_data_points']}")
            return None
        
        try:
            # Convertir a DataFrame para facilitar cálculos
            df = pd.DataFrame(price_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df['price'] = df['price_usd'].astype(float)
            
            if len(df) < self.config["min_data_points"]:
                return None
            
            indicators = TechnicalIndicators()
            
            # Calcular RSI
            indicators.rsi = self._calculate_rsi(df['price'], self.config["rsi_period"])
            
            # Calcular Bollinger Bands
            bb_upper, bb_middle, bb_lower, bb_width = self._calculate_bollinger_bands(
                df['price'], 
                self.config["bb_period"], 
                self.config["bb_std_dev"]
            )
            indicators.bollinger_upper = bb_upper
            indicators.bollinger_middle = bb_middle
            indicators.bollinger_lower = bb_lower
            indicators.bollinger_width = bb_width
            
            # Calcular Moving Averages
            indicators.moving_average_short = self._calculate_moving_average(
                df['price'], self.config["ma_short_period"]
            )
            indicators.moving_average_long = self._calculate_moving_average(
                df['price'], self.config["ma_long_period"]
            )
            
            # Calcular cambios de precio
            indicators.price_change_24h = self._calculate_price_change(df, hours=24)
            indicators.price_change_7d = self._calculate_price_change(df, days=7)
            
            # Calcular score de volatilidad
            indicators.volatility_score = self._calculate_volatility_score(df['price'])
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculando indicadores técnicos: {e}")
            return None

    def _calculate_rsi(self, prices: pd.Series, period: int) -> Optional[float]:
        """Calcula el Relative Strength Index (RSI)."""
        if len(prices) < period + 1:
            return None
        
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
            
        except Exception as e:
            logger.warning(f"Error calculando RSI: {e}")
            return None

    def _calculate_bollinger_bands(self, prices: pd.Series, period: int, std_dev: float) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Calcula las Bollinger Bands."""
        if len(prices) < period:
            return None, None, None, None
        
        try:
            rolling_mean = prices.rolling(window=period).mean()
            rolling_std = prices.rolling(window=period).std()
            
            upper_band = rolling_mean + (rolling_std * std_dev)
            lower_band = rolling_mean - (rolling_std * std_dev)
            
            # Ancho de las bandas como indicador de volatilidad
            band_width = ((upper_band - lower_band) / rolling_mean) * 100
            
            return (
                float(upper_band.iloc[-1]) if not pd.isna(upper_band.iloc[-1]) else None,
                float(rolling_mean.iloc[-1]) if not pd.isna(rolling_mean.iloc[-1]) else None,
                float(lower_band.iloc[-1]) if not pd.isna(lower_band.iloc[-1]) else None,
                float(band_width.iloc[-1]) if not pd.isna(band_width.iloc[-1]) else None
            )
            
        except Exception as e:
            logger.warning(f"Error calculando Bollinger Bands: {e}")
            return None, None, None, None

    def _calculate_moving_average(self, prices: pd.Series, period: int) -> Optional[float]:
        """Calcula la media móvil simple."""
        if len(prices) < period:
            return None
        
        try:
            ma = prices.rolling(window=period).mean()
            return float(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else None
        except Exception as e:
            logger.warning(f"Error calculando media móvil: {e}")
            return None

    def _calculate_price_change(self, df: pd.DataFrame, hours: int = None, days: int = None) -> Optional[float]:
        """Calcula el cambio de precio en un período específico."""
        try:
            current_time = df['timestamp'].iloc[-1]
            
            if hours:
                target_time = current_time - timedelta(hours=hours)
            elif days:
                target_time = current_time - timedelta(days=days)
            else:
                return None
            
            # Encontrar el precio más cercano al tiempo objetivo
            time_diff = abs(df['timestamp'] - target_time)
            closest_idx = time_diff.idxmin()
            
            current_price = df['price'].iloc[-1]
            past_price = df['price'].iloc[closest_idx]
            
            if past_price == 0:
                return None
            
            change_percentage = ((current_price - past_price) / past_price) * 100
            return float(change_percentage)
            
        except Exception as e:
            logger.warning(f"Error calculando cambio de precio: {e}")
            return None

    def _calculate_volatility_score(self, prices: pd.Series) -> Optional[float]:
        """Calcula un score de volatilidad basado en la desviación estándar."""
        try:
            if len(prices) < 2:
                return None
            
            # Calcular retornos logarítmicos
            returns = np.log(prices / prices.shift(1)).dropna()
            
            if len(returns) == 0:
                return None
            
            # Volatilidad como desviación estándar de retornos * 100
            volatility = float(returns.std() * 100)
            return volatility
            
        except Exception as e:
            logger.warning(f"Error calculando volatilidad: {e}")
            return None

    def identify_volatility_opportunities(self, item_name: str, price_data: List[Dict[str, Any]], current_price: float) -> List[VolatilitySignal]:
        """
        Identifica oportunidades de trading basadas en volatilidad.
        
        Args:
            item_name: Nombre del ítem
            price_data: Datos históricos de precio
            current_price: Precio actual del ítem
            
        Returns:
            Lista de señales de volatilidad
        """
        signals = []
        
        # Calcular indicadores técnicos
        indicators = self.analyze_price_data(price_data)
        if not indicators:
            logger.debug(f"No se pudieron calcular indicadores para {item_name}")
            return signals
        
        logger.info(f"Analizando volatilidad para {item_name} - Precio actual: ${current_price:.2f}")
        
        # Estrategia 1: RSI Oversold/Overbought
        rsi_signal = self._check_rsi_signals(item_name, current_price, indicators)
        if rsi_signal:
            signals.append(rsi_signal)
        
        # Estrategia 2: Bollinger Bands Squeeze/Breakout
        bb_signal = self._check_bollinger_signals(item_name, current_price, indicators)
        if bb_signal:
            signals.append(bb_signal)
        
        # Estrategia 3: Moving Average Crossover
        ma_signal = self._check_moving_average_signals(item_name, current_price, indicators)
        if ma_signal:
            signals.append(ma_signal)
        
        # Estrategia 4: High Volatility Breakout
        volatility_signal = self._check_volatility_breakout(item_name, current_price, indicators)
        if volatility_signal:
            signals.append(volatility_signal)
        
        return signals

    def _check_rsi_signals(self, item_name: str, current_price: float, indicators: TechnicalIndicators) -> Optional[VolatilitySignal]:
        """Verifica señales basadas en RSI."""
        if not indicators.rsi:
            return None
        
        rsi = indicators.rsi
        oversold = self.config["rsi_oversold"]
        overbought = self.config["rsi_overbought"]
        
        signal_type = None
        strength = SignalStrength.WEAK
        confidence = 0.0
        reasoning = ""
        
        if rsi <= oversold:
            signal_type = "rsi_oversold_buy"
            strength = SignalStrength.STRONG if rsi <= 20 else SignalStrength.MODERATE
            confidence = min(0.9, (oversold - rsi) / oversold + 0.5)
            reasoning = f"RSI en zona de sobreventa ({rsi:.1f}), posible rebote alcista"
            
        elif rsi >= overbought:
            signal_type = "rsi_overbought_sell"
            strength = SignalStrength.STRONG if rsi >= 80 else SignalStrength.MODERATE
            confidence = min(0.9, (rsi - overbought) / (100 - overbought) + 0.5)
            reasoning = f"RSI en zona de sobrecompra ({rsi:.1f}), posible corrección bajista"
        
        if not signal_type or confidence < self.config["min_confidence"]:
            return None
        
        # Calcular precios objetivo y stop loss
        target_price, stop_loss = self._calculate_trade_levels(current_price, signal_type)
        expected_profit = self._calculate_expected_profit(current_price, target_price, signal_type)
        risk_reward = self._calculate_risk_reward_ratio(current_price, target_price, stop_loss)
        
        return VolatilitySignal(
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            entry_price=current_price,
            target_price=target_price,
            stop_loss=stop_loss,
            expected_profit=expected_profit,
            risk_reward_ratio=risk_reward,
            indicators=indicators,
            reasoning=reasoning,
            timestamp=datetime.now()
        )

    def _check_bollinger_signals(self, item_name: str, current_price: float, indicators: TechnicalIndicators) -> Optional[VolatilitySignal]:
        """Verifica señales basadas en Bollinger Bands."""
        if not all([indicators.bollinger_upper, indicators.bollinger_lower, indicators.bollinger_width]):
            return None
        
        upper = indicators.bollinger_upper
        lower = indicators.bollinger_lower
        width = indicators.bollinger_width
        
        signal_type = None
        strength = SignalStrength.WEAK
        confidence = 0.0
        reasoning = ""
        
        # Bollinger Squeeze (baja volatilidad, posible breakout)
        if width < self.config["volatility_low_threshold"] * 100:
            signal_type = "bollinger_squeeze_breakout"
            strength = SignalStrength.MODERATE
            confidence = 0.7
            reasoning = f"Bollinger Squeeze detectado (ancho: {width:.1f}%), esperando breakout"
            
        # Precio cerca del límite inferior (posible rebote)
        elif current_price <= lower * 1.02:  # 2% de tolerancia
            signal_type = "bollinger_lower_bounce"
            strength = SignalStrength.STRONG
            confidence = 0.8
            reasoning = f"Precio cerca del límite inferior de Bollinger (${lower:.2f}), posible rebote"
            
        # Precio cerca del límite superior (posible corrección)
        elif current_price >= upper * 0.98:  # 2% de tolerancia
            signal_type = "bollinger_upper_rejection"
            strength = SignalStrength.MODERATE
            confidence = 0.7
            reasoning = f"Precio cerca del límite superior de Bollinger (${upper:.2f}), posible corrección"
        
        if not signal_type or confidence < self.config["min_confidence"]:
            return None
        
        target_price, stop_loss = self._calculate_trade_levels(current_price, signal_type)
        expected_profit = self._calculate_expected_profit(current_price, target_price, signal_type)
        risk_reward = self._calculate_risk_reward_ratio(current_price, target_price, stop_loss)
        
        return VolatilitySignal(
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            entry_price=current_price,
            target_price=target_price,
            stop_loss=stop_loss,
            expected_profit=expected_profit,
            risk_reward_ratio=risk_reward,
            indicators=indicators,
            reasoning=reasoning,
            timestamp=datetime.now()
        )

    def _check_moving_average_signals(self, item_name: str, current_price: float, indicators: TechnicalIndicators) -> Optional[VolatilitySignal]:
        """Verifica señales basadas en cruces de medias móviles."""
        if not all([indicators.moving_average_short, indicators.moving_average_long]):
            return None
        
        ma_short = indicators.moving_average_short
        ma_long = indicators.moving_average_long
        
        signal_type = None
        strength = SignalStrength.WEAK
        confidence = 0.0
        reasoning = ""
        
        # Golden Cross (MA corta cruza por encima de MA larga)
        if ma_short > ma_long and current_price > ma_short:
            signal_type = "ma_golden_cross"
            strength = SignalStrength.MODERATE
            confidence = 0.65
            reasoning = f"Golden Cross detectado (MA7: ${ma_short:.2f} > MA21: ${ma_long:.2f})"
            
        # Death Cross (MA corta cruza por debajo de MA larga)
        elif ma_short < ma_long and current_price < ma_short:
            signal_type = "ma_death_cross"
            strength = SignalStrength.MODERATE
            confidence = 0.65
            reasoning = f"Death Cross detectado (MA7: ${ma_short:.2f} < MA21: ${ma_long:.2f})"
        
        if not signal_type or confidence < self.config["min_confidence"]:
            return None
        
        target_price, stop_loss = self._calculate_trade_levels(current_price, signal_type)
        expected_profit = self._calculate_expected_profit(current_price, target_price, signal_type)
        risk_reward = self._calculate_risk_reward_ratio(current_price, target_price, stop_loss)
        
        return VolatilitySignal(
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            entry_price=current_price,
            target_price=target_price,
            stop_loss=stop_loss,
            expected_profit=expected_profit,
            risk_reward_ratio=risk_reward,
            indicators=indicators,
            reasoning=reasoning,
            timestamp=datetime.now()
        )

    def _check_volatility_breakout(self, item_name: str, current_price: float, indicators: TechnicalIndicators) -> Optional[VolatilitySignal]:
        """Verifica señales de breakout por alta volatilidad."""
        if not indicators.volatility_score:
            return None
        
        volatility = indicators.volatility_score
        high_threshold = self.config["volatility_high_threshold"] * 100
        
        if volatility < high_threshold:
            return None
        
        signal_type = "high_volatility_breakout"
        strength = SignalStrength.STRONG if volatility > high_threshold * 1.5 else SignalStrength.MODERATE
        confidence = min(0.85, volatility / (high_threshold * 2))
        reasoning = f"Alta volatilidad detectada ({volatility:.1f}%), posible movimiento significativo"
        
        if confidence < self.config["min_confidence"]:
            return None
        
        target_price, stop_loss = self._calculate_trade_levels(current_price, signal_type)
        expected_profit = self._calculate_expected_profit(current_price, target_price, signal_type)
        risk_reward = self._calculate_risk_reward_ratio(current_price, target_price, stop_loss)
        
        return VolatilitySignal(
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            entry_price=current_price,
            target_price=target_price,
            stop_loss=stop_loss,
            expected_profit=expected_profit,
            risk_reward_ratio=risk_reward,
            indicators=indicators,
            reasoning=reasoning,
            timestamp=datetime.now()
        )

    def _calculate_trade_levels(self, current_price: float, signal_type: str) -> Tuple[Optional[float], Optional[float]]:
        """Calcula niveles de precio objetivo y stop loss."""
        stop_loss_pct = self.config["stop_loss_percentage"]
        profit_multiplier = self.config["take_profit_multiplier"]
        
        if "buy" in signal_type or "bounce" in signal_type or "golden_cross" in signal_type:
            # Señal alcista
            stop_loss = current_price * (1 - stop_loss_pct)
            target_price = current_price * (1 + stop_loss_pct * profit_multiplier)
        elif "sell" in signal_type or "rejection" in signal_type or "death_cross" in signal_type:
            # Señal bajista (para short selling, no implementado en este contexto)
            stop_loss = current_price * (1 + stop_loss_pct)
            target_price = current_price * (1 - stop_loss_pct * profit_multiplier)
        else:
            # Breakout - dirección incierta, usar rangos más amplios
            stop_loss = current_price * (1 - stop_loss_pct * 1.5)
            target_price = current_price * (1 + stop_loss_pct * profit_multiplier * 1.5)
        
        return target_price, stop_loss

    def _calculate_expected_profit(self, entry_price: float, target_price: Optional[float], signal_type: str) -> float:
        """Calcula el beneficio esperado de la operación."""
        if not target_price:
            return 0.0
        
        if "buy" in signal_type or "bounce" in signal_type or "golden_cross" in signal_type or "breakout" in signal_type:
            return target_price - entry_price
        else:
            return entry_price - target_price

    def _calculate_risk_reward_ratio(self, entry_price: float, target_price: Optional[float], stop_loss: Optional[float]) -> float:
        """Calcula la relación riesgo/beneficio."""
        if not target_price or not stop_loss:
            return 0.0
        
        potential_profit = abs(target_price - entry_price)
        potential_loss = abs(entry_price - stop_loss)
        
        if potential_loss == 0:
            return float('inf')
        
        return potential_profit / potential_loss

    def get_volatility_level(self, volatility_score: float) -> VolatilityLevel:
        """Determina el nivel de volatilidad basado en el score."""
        low_threshold = self.config["volatility_low_threshold"] * 100
        medium_threshold = self.config["volatility_medium_threshold"] * 100
        high_threshold = self.config["volatility_high_threshold"] * 100
        
        if volatility_score < low_threshold:
            return VolatilityLevel.LOW
        elif volatility_score < medium_threshold:
            return VolatilityLevel.MEDIUM
        elif volatility_score < high_threshold:
            return VolatilityLevel.HIGH
        else:
            return VolatilityLevel.EXTREME 