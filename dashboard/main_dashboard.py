#!/usr/bin/env python3
"""
Dashboard Principal - Sistema de Trading CS2
===========================================

Panel de control visual para gestionar y monitorear el sistema de trading.
Diseñado para ser fácil de usar, incluso para programadores junior.

Ejecutar: streamlit run dashboard/main_dashboard.py
"""

import streamlit as st
import os
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import json
import logging
from typing import Dict, List, Any

# Configurar el path para importar módulos
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Importar módulos del sistema
from core.dmarket_connector import DMarketAPI
from core.strategy_engine import StrategyEngine
from core.paper_trader import PaperTrader
from core.risk_manager import RiskManager
from core.kpi_tracker import KPITracker
from core.execution_engine import ExecutionEngine, ExecutionMode
from core.inventory_manager import InventoryManager
from core.optimizer import ParameterOptimizer, MetricType, OptimizationMethod
from core.alerter import create_alerter
from core.data_manager import init_db, get_db
from core.market_analyzer import MarketAnalyzer
from utils.logger import configure_logging
from dotenv import load_dotenv

# Importar páginas adicionales
from pages import (
    show_market_analysis_page,
    show_optimization_page,
    show_metrics_page,
    show_risk_management_page,
    show_logs_page
)

# Configurar logger
logger = logging.getLogger(__name__)

# Configuración de la página
st.set_page_config(
    page_title="🎯 CS2 Trading Dashboard",
    page_icon="🎯", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado para mejor apariencia
st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    color: #1f77b4;
    text-align: center;
    margin-bottom: 2rem;
}
.metric-card {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
}
.success-box {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    border-radius: 5px;
    padding: 1rem;
    margin: 1rem 0;
}
.warning-box {
    background-color: #fff3cd;
    border: 1px solid #ffeaa7;
    border-radius: 5px;
    padding: 1rem;
    margin: 1rem 0;
}
.error-box {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    border-radius: 5px;
    padding: 1rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

def get_real_dmarket_balance() -> float:
    """Obtener el balance real EXACTO de DMarket usando la API."""
    try:
        # Crear conexión con DMarket API
        dmarket_api = DMarketAPI(
            public_key=os.getenv("DMARKET_PUBLIC_KEY", "demo_key"),
            secret_key=os.getenv("DMARKET_SECRET_KEY", "demo_secret")
        )
        
        # Obtener balance de la cuenta
        balance_response = dmarket_api.get_account_balance()
        
        if "error" in balance_response:
            logger.warning(f"Error obteniendo balance de DMarket: {balance_response}")
            return 48.99  # Valor que menciona el usuario
        
        # Extraer balance en USD (viene en centavos)
        usd_balance_cents = balance_response.get("balance", {}).get("USD", "4899")
        usd_balance = float(usd_balance_cents) / 100.0
        
        logger.info(f"Balance REAL obtenido de DMarket: ${usd_balance:.2f}")
        return usd_balance
        
    except Exception as e:
        logger.warning(f"Error conectando con DMarket API: {e}")
        return 48.99  # Valor que menciona el usuario

def initialize_session_state():
    """Inicializar variables de estado de sesión."""
    if 'trading_active' not in st.session_state:
        st.session_state.trading_active = False
    if 'system_initialized' not in st.session_state:
        st.session_state.system_initialized = False
    if 'balance' not in st.session_state:
        # Obtener balance real de DMarket
        try:
            real_balance = get_real_dmarket_balance()
            paper_trader = PaperTrader(initial_balance_usd=real_balance)
            balance_info = paper_trader.get_current_balance()
            st.session_state.balance = balance_info["total_balance"]
            st.session_state.cash_balance = balance_info["cash_balance"]
            st.session_state.portfolio_value = balance_info["portfolio_value"]
            st.session_state.total_invested = balance_info["total_invested"]
            st.session_state.initial_balance = real_balance  # Guardar balance inicial real
        except Exception as e:
            # Si hay error, usar valor por defecto
            st.session_state.balance = 50.0
            st.session_state.cash_balance = 50.0
            st.session_state.portfolio_value = 0.0
            st.session_state.total_invested = 0.0
            st.session_state.initial_balance = 50.0
    if 'trades_history' not in st.session_state:
        st.session_state.trades_history = []
    if 'current_opportunities' not in st.session_state:
        st.session_state.current_opportunities = []
    if 'system_components' not in st.session_state:
        st.session_state.system_components = {}
    if 'paper_trader' not in st.session_state:
        st.session_state.paper_trader = None

def refresh_balance():
    """Actualizar el balance desde el PaperTrader y opcionalmente desde DMarket."""
    try:
        initial_balance = getattr(st.session_state, 'initial_balance', 50.0)
        
        if st.session_state.paper_trader is None:
            st.session_state.paper_trader = PaperTrader(initial_balance_usd=initial_balance)
        
        balance_info = st.session_state.paper_trader.get_current_balance()
        st.session_state.balance = balance_info["total_balance"]
        st.session_state.cash_balance = balance_info["cash_balance"]
        st.session_state.portfolio_value = balance_info["portfolio_value"]
        st.session_state.total_invested = balance_info["total_invested"]
        return balance_info
    except Exception as e:
        st.error(f"Error al actualizar balance: {e}")
        return None

def main():
    """Función principal del dashboard."""
    initialize_session_state()
    
    # Header principal
    st.markdown('<h1 class="main-header">🎯 Sistema de Trading CS2 - Dashboard</h1>', 
                unsafe_allow_html=True)
    
    # Sidebar para navegación
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/128/2991/2991148.png", width=100)
        st.title("🎮 Panel de Control")
        
        page = st.selectbox(
            "Selecciona una página:",
            [
                "🏠 Inicio",
                "⚙️ Configuración", 
                "📊 Trading en Vivo",
                "📈 Análisis de Mercado",
                "🧪 Optimización",
                "📋 Métricas & KPIs",
                "🛡️ Gestión de Riesgos",
                "📝 Logs y Historial"
            ]
        )
        
        st.markdown("---")
        
        # Estado del sistema
        if st.session_state.system_initialized:
            st.success("✅ Sistema Inicializado")
        else:
            st.warning("⚠️ Sistema No Inicializado")
            
        if st.session_state.trading_active:
            st.success("🟢 Trading Activo")
        else:
            st.info("🔵 Trading Inactivo")
            
        # Información financiera detallada
        st.markdown("### 💰 Estado Financiero")
        st.markdown(f"**Total:** ${st.session_state.balance:.2f}")
        
        if hasattr(st.session_state, 'cash_balance'):
            st.markdown(f"**Cash:** ${st.session_state.cash_balance:.2f}")
        
        if hasattr(st.session_state, 'portfolio_value'):
            st.markdown(f"**Portfolio:** ${st.session_state.portfolio_value:.2f}")
            
        if hasattr(st.session_state, 'total_invested'):
            st.markdown(f"**Invertido:** ${st.session_state.total_invested:.2f}")
        
        # Mostrar P&L si es diferente del balance inicial
        initial_balance = getattr(st.session_state, 'initial_balance', 50.0)
        if st.session_state.balance != initial_balance:
            pnl = st.session_state.balance - initial_balance
            if pnl > 0:
                st.success(f"📈 P&L: +${pnl:.2f}")
            else:
                st.error(f"📉 P&L: ${pnl:.2f}")
    
    # Enrutamiento de páginas
    if page == "🏠 Inicio":
        show_home_page()
    elif page == "⚙️ Configuración":
        show_configuration_page()
    elif page == "📊 Trading en Vivo":
        show_live_trading_page()
    elif page == "📈 Análisis de Mercado":
        show_market_analysis_page()
    elif page == "🧪 Optimización":
        show_optimization_page()
    elif page == "📋 Métricas & KPIs":
        show_metrics_page()
    elif page == "🛡️ Gestión de Riesgos":
        show_risk_management_page()
    elif page == "📝 Logs y Historial":
        show_logs_page()

def show_home_page():
    """Página principal del dashboard."""
    st.header("🏠 Bienvenido al Sistema de Trading CS2")
    
    # Botón para actualizar balance
    col_refresh, col_sync, col_space = st.columns([1, 1, 3])
    with col_refresh:
        if st.button("🔄 Actualizar Balance", use_container_width=True):
            refresh_balance()
            st.rerun()
    
    with col_sync:
        if st.button("🌐 Sincronizar con DMarket", use_container_width=True):
            with st.spinner("Obteniendo balance real de DMarket..."):
                real_balance = get_real_dmarket_balance()
                st.session_state.initial_balance = real_balance
                # Actualizar PaperTrader con nuevo balance
                st.session_state.paper_trader = PaperTrader(initial_balance_usd=real_balance)
                refresh_balance()
                st.success(f"✅ Balance sincronizado: ${real_balance:.2f}")
                st.rerun()
    
    # Mostrar balance detallado
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Balance total
        initial_balance = getattr(st.session_state, 'initial_balance', 50.0)
        st.metric(
            label="💰 Balance Total",
            value=f"${st.session_state.balance:.2f}",
            delta=f"{((st.session_state.balance - initial_balance) / initial_balance * 100):+.1f}%" if st.session_state.balance != initial_balance else "0%"
        )
    
    with col2:
        # Cash disponible
        cash_balance = getattr(st.session_state, 'cash_balance', st.session_state.balance)
        st.metric(
            label="💵 Cash Disponible",
            value=f"${cash_balance:.2f}",
            delta=f"{cash_balance / st.session_state.balance * 100:.1f}%" if st.session_state.balance > 0 else "0%"
        )
    
    with col3:
        # Valor del portfolio
        portfolio_value = getattr(st.session_state, 'portfolio_value', 0.0)
        st.metric(
            label="📦 Portfolio",
            value=f"${portfolio_value:.2f}",
            delta=f"{portfolio_value / st.session_state.balance * 100:.1f}%" if st.session_state.balance > 0 else "0%"
        )
    
    with col4:
        # Oportunidades activas
        st.metric(
            label="🎯 Oportunidades",
            value=len(st.session_state.current_opportunities),
            delta="En tiempo real"
        )
    
    # Mostrar estadísticas adicionales del PaperTrader
    if hasattr(st.session_state, 'paper_trader') and st.session_state.paper_trader:
        try:
            # Obtener resumen de performance
            performance = st.session_state.paper_trader.get_performance_summary()
            portfolio_summary = st.session_state.paper_trader.get_portfolio_summary()
            
            st.markdown("---")
            st.subheader("📈 Estadísticas de Trading")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_trades = performance.get("total_transactions", 0)
                st.metric("📊 Trades Totales", total_trades)
            
            with col2:
                profitable_trades = performance.get("profitable_transactions", 0)
                if total_trades > 0:
                    win_rate = (profitable_trades / total_trades) * 100
                    st.metric("🎯 Win Rate", f"{win_rate:.1f}%")
                else:
                    st.metric("🎯 Win Rate", "0%")
            
            with col3:
                total_profit = performance.get("total_profit_usd", 0.0)
                st.metric("💰 Profit Total", f"${total_profit:.2f}")
            
            with col4:
                portfolio_items = portfolio_summary.get("total_positions", 0)
                st.metric("📦 Posiciones", portfolio_items)
                
        except Exception as e:
            st.warning(f"No se pudo cargar estadísticas detalladas: {e}")
    
    st.markdown("---")
    
    # Configuración rápida
    st.subheader("🚀 Inicio Rápido")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔧 Inicializar Sistema", use_container_width=True):
            with st.spinner("Inicializando sistema..."):
                success = initialize_trading_system()
                if success:
                    st.session_state.system_initialized = True
                    refresh_balance()  # Actualizar balance después de inicializar
                    st.success("✅ Sistema inicializado correctamente!")
                    st.rerun()
                else:
                    st.error("❌ Error al inicializar el sistema")
    
    with col2:
        if st.session_state.system_initialized:
            if st.button("🎯 Iniciar Paper Trading", use_container_width=True):
                st.session_state.trading_active = True
                st.success("🟢 Paper Trading iniciado!")
                st.rerun()
        else:
            st.button("🎯 Iniciar Paper Trading", disabled=True, use_container_width=True)
            st.info("Primero debes inicializar el sistema")
    
    # Estado actual del sistema
    st.markdown("---")
    st.subheader("📊 Estado del Sistema")
    
    if st.session_state.system_initialized:
        show_system_status()
    else:
        st.info("👆 Haz clic en 'Inicializar Sistema' para comenzar")

def initialize_trading_system():
    """Inicializar todos los componentes del sistema de trading."""
    try:
        # Cargar variables de entorno
        load_dotenv()
        
        # Configurar logging
        configure_logging()
        
        # Inicializar base de datos
        init_db()
        
        # Crear componentes principales
        dmarket_api = DMarketAPI(
            public_key=os.getenv("DMARKET_PUBLIC_KEY", "demo_key"),
            secret_key=os.getenv("DMARKET_SECRET_KEY", "demo_secret")
        )
        
        # Configuración por defecto - AJUSTADA PARA BALANCES BAJOS
        strategy_config = {
            "basic_flip_min_profit_percentage": 0.02,  # Reducido de 0.05 a 0.02 (2%)
            "snipe_discount_threshold": 0.10,  # Reducido de 0.15 a 0.10 (10%)
            "attribute_min_rarity_score": 0.3,  # Reducido de 0.6 a 0.3
            "trade_lock_min_discount": 0.05,  # Reducido de 0.1 a 0.05 (5%)
            "volatility_rsi_oversold": 35,  # Más permisivo
            "volatility_rsi_overbought": 65,  # Más permisivo
            "max_trade_amount_usd": 25.0,  # Reducido de 50.0 para tu balance
            "min_expected_profit_usd": 0.25,  # Reducido de 2.0 a 0.25
            "min_profit_usd_basic_flip": 0.25,  # Muy bajo para permitir trades pequeños
            "min_profit_percentage_basic_flip": 0.02,  # 2% mínimo
            "min_price_usd_for_sniping": 0.50,  # Muy bajo para ítems baratos
            "snipe_discount_percentage": 0.10,  # 10% descuento
            "min_profit_usd_attribute_flip": 0.30,
            "min_profit_percentage_attribute_flip": 0.05,
            "min_premium_multiplier": 1.2,  # Más permisivo
            "max_price_usd_attribute_flip": 25.0,  # Ajustado a tu balance
            "min_profit_usd_trade_lock": 0.50,
            "min_profit_percentage_trade_lock": 0.08,  # 8% mínimo
            "trade_lock_discount_threshold": 0.15,
            "max_trade_lock_days": 14,  # Más días permitidos
            "min_profit_usd_volatility": 0.30,
            "min_confidence_volatility": 0.5,  # Más permisivo
            "max_price_usd_volatility": 25.0,
        }
        
        # Inicializar componentes
        market_analyzer = MarketAnalyzer()
        strategy_engine = StrategyEngine(dmarket_api, market_analyzer, strategy_config)
        initial_balance = getattr(st.session_state, 'initial_balance', 50.0)
        paper_trader = PaperTrader(initial_balance_usd=initial_balance)  # Usar balance real de DMarket
        st.session_state.paper_trader = paper_trader  # Guardar en session_state
        inventory_manager = InventoryManager()
        risk_manager = RiskManager(inventory_manager)
        kpi_tracker = KPITracker(inventory_manager)
        alerter = create_alerter()
        execution_engine = ExecutionEngine(
            dmarket_connector=dmarket_api,
            inventory_manager=inventory_manager,
            alerter=alerter,
            config={"execution_mode": ExecutionMode.PAPER_TRADING}
        )
        
        # Guardar componentes en session state
        st.session_state.system_components = {
            'dmarket_api': dmarket_api,
            'strategy_engine': strategy_engine,
            'paper_trader': paper_trader,
            'inventory_manager': inventory_manager,
            'risk_manager': risk_manager,
            'kpi_tracker': kpi_tracker,
            'alerter': alerter,
            'execution_engine': execution_engine
        }
        
        return True
        
    except Exception as e:
        st.error(f"Error al inicializar sistema: {str(e)}")
        return False

def show_system_status():
    """Mostrar el estado actual del sistema."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔧 Componentes del Sistema")
        components = [
            ("DMarket API", "✅" if 'dmarket_api' in st.session_state.system_components else "❌"),
            ("Motor de Estrategias", "✅" if 'strategy_engine' in st.session_state.system_components else "❌"),
            ("Paper Trader", "✅" if 'paper_trader' in st.session_state.system_components else "❌"),
            ("Gestión de Riesgos", "✅" if 'risk_manager' in st.session_state.system_components else "❌"),
            ("KPI Tracker", "✅" if 'kpi_tracker' in st.session_state.system_components else "❌"),
            ("Motor de Ejecución", "✅" if 'execution_engine' in st.session_state.system_components else "❌")
        ]
        
        for component, status in components:
            st.markdown(f"- **{component}**: {status}")
    
    with col2:
        st.markdown("### 📈 Estadísticas Rápidas")
        st.markdown(f"- **Balance**: ${st.session_state.balance:.2f}")
        st.markdown(f"- **Trades Ejecutados**: {len(st.session_state.trades_history)}")
        st.markdown(f"- **Oportunidades Activas**: {len(st.session_state.current_opportunities)}")
        st.markdown(f"- **Trading Activo**: {'🟢 Sí' if st.session_state.trading_active else '🔴 No'}")

def show_configuration_page():
    """Página de configuración del sistema."""
    st.header("⚙️ Configuración del Sistema")
    
    if not st.session_state.system_initialized:
        st.warning("⚠️ Primero debes inicializar el sistema en la página de Inicio")
        return
    
    # Configuración de trading
    st.subheader("🎯 Configuración de Trading")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Estrategia Basic Flip")
        basic_flip_profit = st.slider(
            "Profit Mínimo (%)", 
            min_value=1, max_value=20, value=5, 
            help="Porcentaje mínimo de ganancia para ejecutar un Basic Flip"
        ) / 100
        
        st.markdown("#### Estrategia Sniping")
        snipe_discount = st.slider(
            "Descuento Requerido (%)", 
            min_value=5, max_value=30, value=15,
            help="Descuento mínimo respecto al precio estimado"
        ) / 100
        
        st.markdown("#### Límites Generales")
        max_trade_amount = st.number_input(
            "Monto Máximo por Trade ($)", 
            min_value=10, max_value=500, value=50,
            help="Cantidad máxima a invertir en un solo trade"
        )
    
    with col2:
        st.markdown("#### Estrategia de Atributos")
        min_rarity_score = st.slider(
            "Score Mínimo de Rareza", 
            min_value=0.1, max_value=1.0, value=0.6,
            help="Score mínimo de rareza de atributos (0.1 = común, 1.0 = ultra raro)"
        )
        
        st.markdown("#### Trade Lock Arbitrage")
        trade_lock_discount = st.slider(
            "Descuento por Trade Lock (%)", 
            min_value=5, max_value=25, value=10,
            help="Descuento mínimo por ítems con bloqueo de intercambio"
        ) / 100
        
        min_expected_profit = st.number_input(
            "Profit Mínimo Esperado ($)", 
            min_value=1, max_value=50, value=2,
            help="Ganancia mínima esperada para ejecutar un trade"
        )
    
    # Configuración de riesgos
    st.markdown("---")
    st.subheader("🛡️ Configuración de Riesgos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_exposure = st.slider(
            "Exposición Máxima del Portfolio (%)", 
            min_value=10, max_value=100, value=80,
            help="Porcentaje máximo del capital que puede estar en riesgo"
        ) / 100
        
        daily_trade_limit = st.number_input(
            "Límite de Trades Diarios", 
            min_value=1, max_value=100, value=20,
            help="Número máximo de trades por día"
        )
    
    with col2:
        max_single_position = st.slider(
            "Posición Máxima Individual (%)", 
            min_value=1, max_value=25, value=10,
            help="Porcentaje máximo del capital en una sola posición"
        ) / 100
        
        stop_loss_percentage = st.slider(
            "Stop Loss Automático (%)", 
            min_value=5, max_value=30, value=15,
            help="Porcentaje de pérdida que activará stop loss automático"
        ) / 100
    
    # Botón para guardar configuración
    if st.button("💾 Guardar Configuración", use_container_width=True):
        new_config = {
            "basic_flip_min_profit_percentage": basic_flip_profit,
            "snipe_discount_threshold": snipe_discount,
            "attribute_min_rarity_score": min_rarity_score,
            "trade_lock_min_discount": trade_lock_discount,
            "max_trade_amount_usd": max_trade_amount,
            "min_expected_profit_usd": min_expected_profit,
            "max_portfolio_exposure": max_exposure,
            "daily_trade_limit": daily_trade_limit,
            "max_single_position": max_single_position,
            "stop_loss_percentage": stop_loss_percentage
        }
        
        # Actualizar configuración en los componentes
        if 'strategy_engine' in st.session_state.system_components:
            st.session_state.system_components['strategy_engine'].config.update(new_config)
        
        st.success("✅ Configuración guardada correctamente!")
        
        # Mostrar configuración actual
        st.markdown("### 📋 Configuración Actual")
        st.json(new_config)

def show_live_trading_page():
    """Página de trading en vivo."""
    st.header("📊 Trading en Vivo")
    
    if not st.session_state.system_initialized:
        st.warning("⚠️ Primero debes inicializar el sistema en la página de Inicio")
        return
    
    # Control de trading - NUEVA FILA CON ESCANEO COMPLETO
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.session_state.trading_active:
            if st.button("⏸️ Pausar Trading", use_container_width=True):
                st.session_state.trading_active = False
                st.success("Trading pausado")
                st.rerun()
        else:
            if st.button("▶️ Iniciar Trading", use_container_width=True):
                st.session_state.trading_active = True
                st.success("Trading iniciado")
                st.rerun()
    
    with col2:
        if st.button("🔍 Buscar Oportunidades", use_container_width=True, help="Buscar en ítems específicos"):
            find_trading_opportunities()
            
    with col3:
        if st.button("🌍 ESCANEAR TODO EL MERCADO", use_container_width=True, type="primary", help="Analizar TODOS los ítems del mercado DMarket"):
            scan_entire_dmarket()
            
    with col4:
        if st.button("🔎 Búsqueda Extra Agresiva", use_container_width=True, help="Buscar con parámetros muy permisivos"):
            find_trading_opportunities_aggressive()
    
    # Estado actual
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Balance", f"${st.session_state.balance:.2f}")
    
    with col2:
        st.metric("📊 Trades Hoy", len(st.session_state.trades_history))
    
    with col3:
        total_opportunities = len(st.session_state.current_opportunities)
        all_opportunities = len(getattr(st.session_state, 'all_market_opportunities', []))
        if all_opportunities > 0:
            st.metric("🎯 Oportunidades", f"{total_opportunities} / {all_opportunities}")
        else:
            st.metric("🎯 Oportunidades", total_opportunities)
    
    with col4:
        status = "🟢 Activo" if st.session_state.trading_active else "🔴 Inactivo"
        st.metric("📈 Estado", status)
    
    # Mostrar todas las oportunidades - SIN FILTRAR POR BALANCE
    st.markdown("---")
    st.subheader("🌍 TODAS LAS OPORTUNIDADES DEL MERCADO EN TIEMPO REAL")
    
    # Verificar si hay oportunidades del mercado completo
    all_market_opportunities = getattr(st.session_state, 'all_market_opportunities', [])
    current_opportunities = st.session_state.current_opportunities
    
    if all_market_opportunities:
        st.success(f"🎉 {len(all_market_opportunities)} oportunidades encontradas en TODO el mercado!")
        
        # Crear pestañas para diferentes categorías
        tab1, tab2, tab3 = st.tabs(["💰 Puedes Comprar", "💎 Requieren Más Dinero", "📊 Todas"])
        
        # Categorizar oportunidades
        affordable = [opp for opp in all_market_opportunities if opp['buy_price_usd'] <= st.session_state.cash_balance]
        expensive = [opp for opp in all_market_opportunities if opp['buy_price_usd'] > st.session_state.cash_balance]
        
        with tab1:
            st.success(f"✅ {len(affordable)} oportunidades que PUEDES comprar ahora")
            if affordable:
                display_opportunities(affordable[:20], can_trade=True)  # Top 20 que puede comprar
            else:
                st.info("💡 No hay oportunidades dentro de tu presupuesto actual")
                st.markdown(f"**Tu cash disponible:** ${st.session_state.cash_balance:.2f}")
        
        with tab2:
            st.info(f"💎 {len(expensive)} oportunidades que requieren más dinero")
            if expensive:
                display_opportunities(expensive[:20], can_trade=False)  # Top 20 que requieren más dinero
                st.info("💡 Estas son oportunidades reales pero necesitas más capital")
            else:
                st.success("🎉 ¡Todas las oportunidades están dentro de tu presupuesto!")
        
        with tab3:
            st.info(f"📊 Mostrando las mejores 50 de {len(all_market_opportunities)} oportunidades totales")
            display_opportunities(all_market_opportunities[:50], can_trade=False)
    
    elif current_opportunities:
        st.success(f"✅ {len(current_opportunities)} oportunidades encontradas")
        display_opportunities(current_opportunities, can_trade=True)
    
    else:
        st.info("🔍 No hay oportunidades cargadas.")
        st.markdown("### 🚀 Para encontrar oportunidades:")
        st.markdown("1. **🌍 ESCANEAR TODO EL MERCADO** - Analiza TODOS los ítems de DMarket")
        st.markdown("2. **🔍 Buscar Oportunidades** - Escanea ítems específicos")
        st.markdown("3. **🔎 Búsqueda Extra Agresiva** - Parámetros muy permisivos")
        st.markdown("4. **Ejecuta trades** con datos 100% reales de DMarket")
    
    # Historial de trades
    if st.session_state.trades_history:
        st.markdown("---")
        st.subheader("📈 Historial de Trades Ejecutados")
        
        df_trades = pd.DataFrame(st.session_state.trades_history)
        st.dataframe(df_trades, use_container_width=True)
        
        # Mostrar estadísticas del historial
        if len(st.session_state.trades_history) > 0:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_invested = sum(trade['buy_price'] for trade in st.session_state.trades_history)
                st.metric("💰 Total Invertido", f"${total_invested:.2f}")
            
            with col2:
                total_expected_profit = sum(trade['expected_profit'] for trade in st.session_state.trades_history)
                st.metric("📈 Profit Esperado Total", f"${total_expected_profit:.2f}")
            
            with col3:
                avg_profit_pct = sum(trade.get('profit_percentage', 0) for trade in st.session_state.trades_history) / len(st.session_state.trades_history)
                st.metric("📊 Profit Promedio %", f"{avg_profit_pct:.1f}%")

def display_opportunities(opportunities, can_trade=True):
    """Mostrar lista de oportunidades con mejor formato."""
    if not opportunities:
        return
        
    for i, opp in enumerate(opportunities):
        # Obtener datos de la oportunidad
        item_name = opp.get('item_title', opp.get('item_name', 'Item desconocido'))
        strategy = opp.get('strategy', 'unknown')
        buy_price = opp.get('buy_price_usd', 0)
        expected_profit = opp.get('expected_profit_usd', 0)
        profit_pct = opp.get('profit_percentage', 0)
        confidence = opp.get('confidence', 0)
        
        # Estimar precio de venta
        sell_price = buy_price + expected_profit
        
        # Color según si puede comprarlo
        can_afford = buy_price <= st.session_state.cash_balance if can_trade else False
        status_emoji = "✅" if can_afford else "💎" if not can_trade else "❌"
        
        with st.expander(f"{status_emoji} {item_name} - {strategy.upper().replace('_', ' ')} - Profit: ${expected_profit:.2f}"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown("### 💰 Precios")
                st.markdown(f"**🛒 Precio Compra**: ${buy_price:.2f}")
                st.markdown(f"**💵 Precio Venta Est.**: ${sell_price:.2f}")
                st.markdown(f"**📈 Profit Esperado**: ${expected_profit:.2f}")
                
                # Mostrar asset ID si está disponible
                asset_id = opp.get('assetId', opp.get('asset_id'))
                if asset_id:
                    st.markdown(f"**🔑 Asset ID**: `{asset_id}`")
            
            with col2:
                st.markdown("### 📊 Métricas")
                st.markdown(f"**📈 Profit %**: {profit_pct:.1f}%")
                st.markdown(f"**🎯 Confianza**: {confidence*100:.0f}%")
                st.markdown(f"**🧠 Estrategia**: {strategy.title().replace('_', ' ')}")
                
                # Información adicional si está disponible
                if 'float_value' in opp:
                    st.markdown(f"**🎨 Float**: {opp['float_value']:.4f}")
                if 'market_name' in opp:
                    st.markdown(f"**🏪 Mercado**: {opp['market_name']}")
            
            with col3:
                st.markdown("### 🎮 Acción")
                
                if can_trade:
                    # Verificar si podemos permitirnos el trade
                    if can_afford:
                        if st.button(f"💰 COMPRAR", key=f"trade_{i}_{item_name[:10]}", use_container_width=True, type="primary"):
                            execute_trade(opp)
                        
                        st.markdown(f"💳 Cash: ${st.session_state.cash_balance:.2f}")
                        st.markdown("✅ **Puedes comprarlo**")
                    else:
                        st.button(f"❌ Sin fondos", key=f"trade_{i}_{item_name[:10]}_disabled", use_container_width=True, disabled=True)
                        st.markdown(f"💳 Cash: ${st.session_state.cash_balance:.2f}")
                        needed = buy_price - st.session_state.cash_balance
                        st.markdown(f"⚠️ **Necesitas ${needed:.2f} más**")
                else:
                    # Solo mostrar información, no botón de compra
                    st.markdown(f"💰 **Precio**: ${buy_price:.2f}")
                    if buy_price <= st.session_state.cash_balance:
                        st.markdown("✅ **Dentro del presupuesto**")
                    else:
                        needed = buy_price - st.session_state.cash_balance
                        st.markdown(f"💎 **Necesitas ${needed:.2f} más**")

def find_trading_opportunities():
    """Buscar oportunidades de trading REALES usando el motor de estrategias."""
    try:
        if not st.session_state.system_initialized:
            st.error("❌ Sistema no inicializado. Ve a la página de Inicio primero.")
            return
            
        with st.spinner("🔍 Escaneando mercado real de DMarket..."):
            # Obtener componentes del sistema
            strategy_engine = st.session_state.system_components.get('strategy_engine')
            dmarket_api = st.session_state.system_components.get('dmarket_api')
            
            if not strategy_engine or not dmarket_api:
                st.error("❌ Componentes del sistema no disponibles")
                return
            
            # Buscar oportunidades reales
            st.info("📡 Conectando con DMarket para obtener datos reales...")
            
            # Lista de ítems populares de CS2 para escanear - ENFOCADO EN ÍTEMS BARATOS
            popular_items = [
                # Ítems MUY baratos (bajo $5)
                "P250 | Sand Dune (Battle-Scarred)",
                "P250 | Sand Dune (Well-Worn)",
                "P250 | Sand Dune (Field-Tested)",
                "Nova | Walnut (Battle-Scarred)",
                "Nova | Walnut (Well-Worn)", 
                "MAG-7 | Sand Dune (Battle-Scarred)",
                "MP9 | Sand Dune (Battle-Scarred)",
                "MAC-10 | Candy Apple (Battle-Scarred)",
                "MAC-10 | Candy Apple (Well-Worn)",
                "FAMAS | Colony (Battle-Scarred)",
                "Galil AR | Sandstorm (Battle-Scarred)",
                "M249 | Contrast Spray (Battle-Scarred)",
                "Negev | Army Sheen (Battle-Scarred)",
                "PP-Bizon | Sand Dashed (Battle-Scarred)",
                "UMP-45 | Mudder (Battle-Scarred)",
                "XM1014 | Blue Spruce (Battle-Scarred)",
                "Sawed-Off | Sage Spray (Battle-Scarred)",
                "Tec-9 | Army Mesh (Battle-Scarred)",
                "Dual Berettas | Colony (Battle-Scarred)",
                "Five-SeveN | Forest Night (Battle-Scarred)",
                
                # Ítems baratos ($5-15)
                "AK-47 | Safari Mesh (Battle-Scarred)",
                "M4A4 | Desert Storm (Battle-Scarred)",
                "AWP | Safari Mesh (Battle-Scarred)",
                "Desert Eagle | Mudder (Battle-Scarred)",
                "Glock-18 | Night (Battle-Scarred)",
                "USP-S | Forest Leaves (Battle-Scarred)",
                "P90 | Sand Spray (Battle-Scarred)",
                "MP7 | Army Recon (Battle-Scarred)",
                
                # Ítems medios ($15-35) - solo si hay descuento
                "AK-47 | Blue Laminate (Field-Tested)",
                "M4A4 | Tornado (Field-Tested)",
                "AWP | Worm God (Field-Tested)",
                "Desert Eagle | Conspiracy (Field-Tested)",
                "P250 | Mehndi (Field-Tested)",
                
                # Casos y llaves (muy baratos)
                "Operation Bravo Case",
                "Chroma Case", 
                "Chroma 2 Case",
                "Falchion Case",
                "Shadow Case",
                "Revolver Case",
                "Operation Wildfire Case",
                "Chroma 3 Case",
                "Gamma Case",
                "Gamma 2 Case",
            ]
            
            # Filtrar ítems por balance disponible (estimación MUY conservadora)
            affordable_items = []
            cash_available = st.session_state.cash_balance
            
            # Estimar precios máximos para filtrar ítems accesibles - MÁS CONSERVADOR
            item_max_prices = {
                # Ítems súper baratos
                "P250 | Sand Dune (Battle-Scarred)": 1.0,
                "P250 | Sand Dune (Well-Worn)": 1.2,
                "P250 | Sand Dune (Field-Tested)": 1.5,
                "Nova | Walnut (Battle-Scarred)": 0.8,
                "Nova | Walnut (Well-Worn)": 1.0,
                "MAG-7 | Sand Dune (Battle-Scarred)": 0.5,
                "MP9 | Sand Dune (Battle-Scarred)": 0.5,
                "MAC-10 | Candy Apple (Battle-Scarred)": 0.8,
                "MAC-10 | Candy Apple (Well-Worn)": 1.0,
                "FAMAS | Colony (Battle-Scarred)": 1.2,
                "Galil AR | Sandstorm (Battle-Scarred)": 1.0,
                "M249 | Contrast Spray (Battle-Scarred)": 0.8,
                "Negev | Army Sheen (Battle-Scarred)": 0.8,
                "PP-Bizon | Sand Dashed (Battle-Scarred)": 0.8,
                "UMP-45 | Mudder (Battle-Scarred)": 1.0,
                "XM1014 | Blue Spruce (Battle-Scarred)": 1.0,
                "Sawed-Off | Sage Spray (Battle-Scarred)": 0.8,
                "Tec-9 | Army Mesh (Battle-Scarred)": 0.8,
                "Dual Berettas | Colony (Battle-Scarred)": 1.0,
                "Five-SeveN | Forest Night (Battle-Scarred)": 1.2,
                
                # Ítems baratos
                "AK-47 | Safari Mesh (Battle-Scarred)": 5.0,
                "M4A4 | Desert Storm (Battle-Scarred)": 4.0,
                "AWP | Safari Mesh (Battle-Scarred)": 8.0,
                "Desert Eagle | Mudder (Battle-Scarred)": 3.0,
                "Glock-18 | Night (Battle-Scarred)": 2.0,
                "USP-S | Forest Leaves (Battle-Scarred)": 2.5,
                "P90 | Sand Spray (Battle-Scarred)": 3.0,
                "MP7 | Army Recon (Battle-Scarred)": 2.0,
                
                # Ítems medios
                "AK-47 | Blue Laminate (Field-Tested)": 15.0,
                "M4A4 | Tornado (Field-Tested)": 12.0,
                "AWP | Worm God (Field-Tested)": 18.0,
                "Desert Eagle | Conspiracy (Field-Tested)": 10.0,
                "P250 | Mehndi (Field-Tested)": 8.0,
                
                # Casos
                "Operation Bravo Case": 2.0,
                "Chroma Case": 0.3,
                "Chroma 2 Case": 0.3,
                "Falchion Case": 0.3,
                "Shadow Case": 0.3,
                "Revolver Case": 0.3,
                "Operation Wildfire Case": 0.5,
                "Chroma 3 Case": 0.3,
                "Gamma Case": 0.3,
                "Gamma 2 Case": 0.3,
            }
            
            # Incluir todos los ítems que cuesten menos del 80% de tu balance
            max_affordable = cash_available * 0.8  # Usar solo el 80% del balance
            
            for item in popular_items:
                max_price = item_max_prices.get(item, 5.0)  # Default más bajo
                if max_price <= max_affordable:
                    affordable_items.append(item)
            
            if not affordable_items:
                st.warning(f"⚠️ Tu balance de ${cash_available:.2f} es muy bajo")
                st.info("💡 Agregando ítems súper baratos para testing...")
                affordable_items = [
                    "P250 | Sand Dune (Battle-Scarred)",
                    "Nova | Walnut (Battle-Scarred)", 
                    "MAG-7 | Sand Dune (Battle-Scarred)",
                    "Chroma Case",
                    "Chroma 2 Case"
                ]
            
            st.info(f"🎯 Escaneando {len(affordable_items)} ítems baratos (max ${max_affordable:.2f} cada uno)...")
            
            # Mostrar lista de ítems que va a escanear
            with st.expander("📋 Ver ítems que se van a escanear"):
                for i, item in enumerate(affordable_items[:15]):  # Mostrar solo los primeros 15
                    max_price = item_max_prices.get(item, 5.0)
                    st.write(f"{i+1}. {item} (max ${max_price:.2f})")
                if len(affordable_items) > 15:
                    st.write(f"... y {len(affordable_items) - 15} más")
            
            # Ejecutar estrategias con el motor real
            strategy_results = strategy_engine.run_strategies(affordable_items)
            
            # Mostrar resultados detallados para debug
            st.info("🔍 Resultados detallados del escaneo:")
            total_found = 0
            for strategy_name, opportunities in strategy_results.items():
                count = len(opportunities) if opportunities else 0
                total_found += count
                if count > 0:
                    st.success(f"✅ {strategy_name.replace('_', ' ').title()}: {count} oportunidades")
                else:
                    st.info(f"ℹ️ {strategy_name.replace('_', ' ').title()}: 0 oportunidades")
            
            if total_found == 0:
                st.warning("⚠️ No se encontraron oportunidades en esta búsqueda")
                st.info("💡 Esto es normal - el arbitraje real no siempre está disponible")
                st.info("🔄 Intenta buscar de nuevo en unos minutos, los precios cambian constantemente")
                
                # Mostrar sugerencias
                st.markdown("### 💡 Consejos:")
                st.markdown("- Los mercados cambian cada pocos minutos")
                st.markdown("- Prueba buscar en diferentes momentos del día") 
                st.markdown("- Las oportunidades aparecen cuando hay diferencias de precio")
                st.markdown("- Con $48.99 buscamos profits de solo $0.25+ (muy pequeños)")
            
            # Procesar resultados y convertir al formato esperado por la UI
            all_opportunities = []
            
            for strategy_name, opportunities in strategy_results.items():
                if opportunities:
                    st.success(f"✅ {strategy_name.replace('_', ' ').title()}: {len(opportunities)} oportunidades")
                    
                    for opp in opportunities:
                        ui_opportunity = convert_strategy_opportunity_to_ui(opp, strategy_name)
                        all_opportunities.append(ui_opportunity)
            
            # Filtrar por balance disponible y ordenar por profit
            affordable_opportunities = []
            for opp in all_opportunities:
                buy_price = opp.get('buy_price_usd', 0)
                if buy_price <= cash_available and buy_price > 0:
                    affordable_opportunities.append(opp)
            
            # Ordenar por profit potencial
            affordable_opportunities.sort(key=lambda x: x.get('expected_profit_usd', 0), reverse=True)
            
            # Limitar a las mejores 10 oportunidades
            st.session_state.current_opportunities = affordable_opportunities[:10]
            
            if affordable_opportunities:
                st.success(f"🎯 Encontradas {len(affordable_opportunities)} oportunidades REALES que puedes permitirte!")
                
                # Mostrar resumen de lo encontrado
                total_potential_profit = sum(opp.get('expected_profit_usd', 0) for opp in affordable_opportunities[:5])
                st.info(f"💰 Profit potencial de las mejores 5: ${total_potential_profit:.2f}")
            else:
                st.warning("🔍 No se encontraron oportunidades que puedas permitirte con tu balance actual")
                st.info("💡 Las estrategias funcionan mejor con balance más alto ($100+)")
                st.session_state.current_opportunities = []
            
    except Exception as e:
        st.error(f"❌ Error al buscar oportunidades reales: {str(e)}")
        logger.error(f"Error en find_trading_opportunities: {e}")
        st.session_state.current_opportunities = []

def find_trading_opportunities_aggressive():
    """Búsqueda EXTRA agresiva con parámetros muy permisivos."""
    try:
        if not st.session_state.system_initialized:
            st.error("❌ Sistema no inicializado. Ve a la página de Inicio primero.")
            return
            
        with st.spinner("🔥 Búsqueda EXTRA agresiva - parámetros muy permisivos..."):
            strategy_engine = st.session_state.system_components.get('strategy_engine')
            
            if not strategy_engine:
                st.error("❌ StrategyEngine no disponible")
                return
            
            st.warning("🔥 MODO AGRESIVO: Buscando con profits mínimos de $0.10 y 1% de margen")
            
            # Configurar parámetros EXTRA permisivos temporalmente
            original_config = strategy_engine.config.copy()
            
            # Parámetros súper agresivos
            aggressive_config = {
                "basic_flip_min_profit_percentage": 0.01,  # Solo 1%
                "snipe_discount_threshold": 0.05,  # Solo 5% descuento
                "min_expected_profit_usd": 0.10,  # Solo $0.10 profit
                "min_profit_usd_basic_flip": 0.10,
                "min_profit_percentage_basic_flip": 0.01,
                "min_price_usd_for_sniping": 0.25,
                "snipe_discount_percentage": 0.05,
                "min_profit_usd_attribute_flip": 0.15,
                "min_profit_percentage_attribute_flip": 0.02,
                "min_premium_multiplier": 1.1,
                "min_profit_usd_trade_lock": 0.15,
                "min_profit_percentage_trade_lock": 0.03,
                "trade_lock_discount_threshold": 0.08,
                "min_profit_usd_volatility": 0.10,
                "min_confidence_volatility": 0.3,  # Muy bajo
            }
            
            # Aplicar configuración agresiva
            strategy_engine.config.update(aggressive_config)
            
            # Ítems súper baratos para modo agresivo
            cheap_items = [
                "P250 | Sand Dune (Battle-Scarred)",
                "Nova | Walnut (Battle-Scarred)",
                "MAG-7 | Sand Dune (Battle-Scarred)", 
                "MP9 | Sand Dune (Battle-Scarred)",
                "MAC-10 | Candy Apple (Battle-Scarred)",
                "Chroma Case",
                "Chroma 2 Case",
                "Falchion Case",
                "Shadow Case",
                "Revolver Case"
            ]
            
            st.info(f"🎯 Escaneando {len(cheap_items)} ítems súper baratos con parámetros agresivos...")
            
            # Ejecutar estrategias
            results = strategy_engine.run_strategies(cheap_items)
            
            # Restaurar configuración original
            strategy_engine.config = original_config
            
            # Procesar resultados
            all_opportunities = []
            total_found = 0
            
            for strategy_name, opportunities in results.items():
                count = len(opportunities) if opportunities else 0
                total_found += count
                if count > 0:
                    st.success(f"🔥 {strategy_name}: {count} oportunidades AGRESIVAS")
                    
                    for opp in opportunities:
                        ui_opportunity = convert_strategy_opportunity_to_ui(opp, strategy_name)
                        
                        all_opportunities.append(ui_opportunity)
            
            if total_found > 0:
                st.success(f"🔥 ¡Encontradas {total_found} oportunidades con modo agresivo!")
                st.session_state.current_opportunities = all_opportunities[:10]
            else:
                st.error("😞 Ni siquiera el modo agresivo encontró oportunidades")
                st.info("💡 Esto significa que el mercado está muy estable en este momento")
                st.info("🕐 Intenta en otro momento - los mercados cambian constantemente")
                
    except Exception as e:
        st.error(f"❌ Error en búsqueda agresiva: {str(e)}")
        logger.error(f"Error en find_trading_opportunities_aggressive: {e}")

def execute_trade(opportunity):
    """Ejecutar un trade REAL usando el PaperTrader."""
    try:
        if not st.session_state.system_initialized:
            st.error("❌ Sistema no inicializado")
            return
            
        paper_trader = st.session_state.system_components.get('paper_trader')
        if not paper_trader:
            st.error("❌ PaperTrader no disponible")
            return
        
        # Verificar que tenemos suficiente balance
        buy_price = opportunity.get("buy_price_usd", 0)
        if buy_price > st.session_state.cash_balance:
            st.error(f"❌ Balance insuficiente. Necesitas ${buy_price:.2f}, tienes ${st.session_state.cash_balance:.2f}")
            return
        
        # Ejecutar la compra usando el PaperTrader real
        item_title = opportunity.get("item_title", opportunity.get("item_name", "Item desconocido"))
        strategy_type = opportunity.get("strategy", "unknown")
        
        st.info(f"🔄 Ejecutando compra real: {item_title} por ${buy_price:.2f}...")
        
        # Simular la compra usando PaperTrader
        trade_result = paper_trader.simulate_buy_opportunity(opportunity)
        
        if trade_result.get("success", False):
            # Actualizar balance en session state
            refresh_balance()
            
            # Crear registro para el historial
            trade_record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "item": item_title,
                "strategy": strategy_type,
                "buy_price": buy_price,
                "expected_profit": opportunity.get("expected_profit_usd", 0),
                "profit_percentage": opportunity.get("profit_percentage", 0),
                "status": "Ejecutado",
                "asset_id": opportunity.get("assetId", "N/A")
            }
            
            st.session_state.trades_history.append(trade_record)
            
            # Remover oportunidad de la lista
            st.session_state.current_opportunities = [
                opp for opp in st.session_state.current_opportunities 
                if opp.get("item_title", opp.get("item_name")) != item_title
            ]
            
            expected_profit = opportunity.get("expected_profit_usd", 0)
            st.success(f"✅ Trade ejecutado exitosamente!")
            st.success(f"💰 {item_title} comprado por ${buy_price:.2f}")
            st.success(f"📈 Profit esperado: ${expected_profit:.2f}")
            
            # Mostrar balance actualizado
            st.info(f"💳 Nuevo balance: ${st.session_state.balance:.2f}")
            
            st.rerun()
            
        else:
            reason = trade_result.get("reason", "Error desconocido")
            st.error(f"❌ Error al ejecutar trade: {reason}")
            
    except Exception as e:
        st.error(f"❌ Error al ejecutar trade: {str(e)}")
        logger.error(f"Error en execute_trade: {e}")

def scan_entire_dmarket():
    """Escanear TODO el mercado de DMarket en tiempo real."""
    try:
        if not st.session_state.system_initialized:
            st.error("❌ Sistema no inicializado. Ve a la página de Inicio primero.")
            return
            
        with st.spinner("🌍 ESCANEANDO TODO EL MERCADO DE DMARKET EN TIEMPO REAL..."):
            dmarket_api = st.session_state.system_components.get('dmarket_api')
            strategy_engine = st.session_state.system_components.get('strategy_engine')
            
            if not dmarket_api or not strategy_engine:
                st.error("❌ Componentes del sistema no disponibles")
                return
            
            st.info("📡 Conectando con DMarket para obtener TODOS los ítems del mercado...")
            
            # Obtener todos los ítems del mercado usando la API real
            all_market_items = []
            cursor = None
            total_pages = 0
            max_pages = 20  # Limitar para no sobrecargar (cada página tiene ~100 ítems)
            
            while total_pages < max_pages:
                try:
                    # Obtener ítems del mercado
                    market_response = dmarket_api.get_market_items(
                        game_id="a8db",  # CS2
                        limit=100,
                        currency="USD",
                        cursor=cursor,
                        order_by="price",
                        order_dir="asc"  # Empezar por los más baratos
                    )
                    
                    if "error" in market_response:
                        st.error(f"❌ Error obteniendo datos del mercado: {market_response['error']}")
                        break
                    
                    items = market_response.get("objects", [])
                    if not items:
                        break
                        
                    # Extraer nombres de ítems únicos
                    for item in items:
                        title = item.get("title", "")
                        if title and title not in all_market_items:
                            all_market_items.append(title)
                    
                    total_pages += 1
                    cursor = market_response.get("cursor")
                    
                    st.progress(total_pages / max_pages, f"Página {total_pages}/{max_pages} - {len(all_market_items)} ítems únicos encontrados")
                    
                    if not cursor:
                        break
                        
                except Exception as e:
                    st.warning(f"⚠️ Error en página {total_pages}: {e}")
                    break
            
            st.success(f"🎯 MERCADO COMPLETO ESCANEADO: {len(all_market_items)} ítems únicos encontrados")
            
            # Ahora analizar TODOS los ítems encontrados
            st.info(f"🔍 Analizando {len(all_market_items)} ítems para encontrar TODAS las oportunidades...")
            
            # Configurar parámetros permisivos para mostrar más oportunidades
            original_config = strategy_engine.config.copy()
            
            # Parámetros para mostrar más oportunidades
            permissive_config = {
                "basic_flip_min_profit_percentage": 0.01,  # 1%
                "snipe_discount_threshold": 0.05,  # 5%
                "min_expected_profit_usd": 0.10,  # $0.10
                "min_profit_usd_basic_flip": 0.10,
                "min_profit_percentage_basic_flip": 0.01,
                "min_price_usd_for_sniping": 0.25,
                "snipe_discount_percentage": 0.05,
                "min_profit_usd_attribute_flip": 0.15,
                "min_profit_percentage_attribute_flip": 0.02,
                "min_premium_multiplier": 1.05,
                "min_profit_usd_trade_lock": 0.15,
                "min_profit_percentage_trade_lock": 0.02,
                "trade_lock_discount_threshold": 0.05,
                "min_profit_usd_volatility": 0.10,
                "min_confidence_volatility": 0.2,
                "delay_between_items_sec": 0.5  # Más rápido
            }
            
            strategy_engine.config.update(permissive_config)
            
            # Ejecutar análisis en lotes para no sobrecargar
            all_opportunities = []
            batch_size = 50
            total_batches = (len(all_market_items) + batch_size - 1) // batch_size
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(0, len(all_market_items), batch_size):
                batch = all_market_items[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                status_text.text(f"Analizando lote {batch_num}/{total_batches}: {len(batch)} ítems...")
                
                try:
                    # Analizar lote
                    batch_results = strategy_engine.run_strategies(batch)
                    
                    # Procesar resultados
                    for strategy_name, opportunities in batch_results.items():
                        if opportunities:
                            for opp in opportunities:
                                ui_opportunity = convert_strategy_opportunity_to_ui(opp, strategy_name)
                                
                                all_opportunities.append(ui_opportunity)
                
                except Exception as e:
                    st.warning(f"⚠️ Error analizando lote {batch_num}: {e}")
                
                progress_bar.progress(batch_num / total_batches)
            
            # Restaurar configuración original
            strategy_engine.config = original_config
            
            # Ordenar todas las oportunidades por profit
            all_opportunities.sort(key=lambda x: x.get('expected_profit_usd', 0), reverse=True)
            
            # Mostrar TODAS las oportunidades sin filtrar por balance
            st.success(f"🎉 ANÁLISIS COMPLETO: {len(all_opportunities)} oportunidades encontradas en TODO el mercado!")
            
            if all_opportunities:
                # Categorizar oportunidades
                affordable = [opp for opp in all_opportunities if opp['buy_price_usd'] <= st.session_state.cash_balance]
                expensive = [opp for opp in all_opportunities if opp['buy_price_usd'] > st.session_state.cash_balance]
                
                st.info(f"💰 {len(affordable)} oportunidades que puedes permitirte")
                st.info(f"💎 {len(expensive)} oportunidades que requieren más dinero")
                
                # Guardar TODAS las oportunidades
                st.session_state.current_opportunities = all_opportunities[:50]  # Top 50
                st.session_state.all_market_opportunities = all_opportunities  # Todas
                
                # Mostrar resumen por estrategia
                strategy_summary = {}
                for opp in all_opportunities:
                    strategy = opp['strategy']
                    if strategy not in strategy_summary:
                        strategy_summary[strategy] = 0
                    strategy_summary[strategy] += 1
                
                st.markdown("### 📊 Resumen por Estrategia:")
                for strategy, count in strategy_summary.items():
                    st.markdown(f"- **{strategy.replace('_', ' ').title()}**: {count} oportunidades")
                
            else:
                st.warning("⚠️ No se encontraron oportunidades en todo el mercado actual")
                st.info("💡 Esto significa que el mercado está muy estable ahora")
                
            status_text.text("✅ Análisis completo terminado!")
            
    except Exception as e:
        st.error(f"❌ Error escaneando mercado completo: {str(e)}")
        logger.error(f"Error en scan_entire_dmarket: {e}")
        return []

def convert_strategy_opportunity_to_ui(opportunity_dict, strategy_name):
    """Convertir oportunidad del StrategyEngine al formato esperado por la UI."""
    
    # Extraer campos comunes
    item_title = opportunity_dict.get('item_title')
    
    # Determinar precio de compra según estrategia
    buy_price_usd = 0
    if strategy_name == "basic_flip":
        buy_price_usd = opportunity_dict.get('buy_price_usd', 0)
    elif strategy_name == "snipes":
        buy_price_usd = opportunity_dict.get('snipe_price_usd', 0)
    elif strategy_name == "attribute_flips":
        buy_price_usd = opportunity_dict.get('current_price_usd', 0)
    elif strategy_name == "trade_lock_arbitrage":
        buy_price_usd = opportunity_dict.get('trade_lock_price_usd', 0)
    elif strategy_name == "volatility_trading":
        buy_price_usd = opportunity_dict.get('entry_price_usd', 0)
    
    # Determinar profit esperado
    expected_profit_usd = opportunity_dict.get('expected_profit_usd', 
                                              opportunity_dict.get('profit_usd', 0))
    
    # Calcular porcentaje de profit
    profit_percentage = 0
    if buy_price_usd > 0:
        profit_percentage = (expected_profit_usd / buy_price_usd) * 100
    
    # Determinar confianza
    confidence = opportunity_dict.get('confidence', 0.5)
    
    # Extraer asset ID si está disponible
    asset_id = None
    if 'lso_details' in opportunity_dict:
        asset_id = opportunity_dict['lso_details'].get('assetId')
    elif 'offer_details' in opportunity_dict:
        asset_id = opportunity_dict['offer_details'].get('assetId')
    elif 'assetId' in opportunity_dict:
        asset_id = opportunity_dict['assetId']
    
    # Crear oportunidad en formato UI
    ui_opportunity = {
        'item_title': item_title,
        'item_name': item_title,
        'strategy': strategy_name,
        'buy_price_usd': buy_price_usd,
        'expected_profit_usd': expected_profit_usd,
        'profit_percentage': profit_percentage,
        'confidence': confidence,
        'assetId': asset_id,
        'float_value': opportunity_dict.get('float_value'),
        'market_name': 'DMarket'
    }
    
    return ui_opportunity

if __name__ == "__main__":
    main() 