#!/usr/bin/env python3
"""
Páginas Adicionales del Dashboard
================================

Implementación de todas las páginas secundarias del dashboard:
- Análisis de Mercado
- Optimización de Parámetros
- Métricas y KPIs
- Gestión de Riesgos
- Logs y Historial
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import time
import os
import sys

# Importar módulos del sistema
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.optimizer import ParameterOptimizer, ParameterRange, MetricType, OptimizationMethod
from core.volatility_analyzer import VolatilityAnalyzer

def show_market_analysis_page():
    """Página de análisis de mercado."""
    st.header("📈 Análisis de Mercado")
    
    if not st.session_state.system_initialized:
        st.warning("⚠️ Primero debes inicializar el sistema en la página de Inicio")
        return
    
    # Controles de análisis
    st.subheader("🔍 Configuración del Análisis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        items_to_analyze = st.multiselect(
            "Selecciona ítems para analizar:",
            ["AK-47 | Redline", "AWP | Asiimov", "M4A4 | Howl", "AK-47 | Vulcan", "Glock-18 | Fade"],
            default=["AK-47 | Redline", "AWP | Asiimov"]
        )
    
    with col2:
        analysis_type = st.selectbox(
            "Tipo de análisis:",
            ["Precios", "Volatilidad", "Atributos", "Tendencias"]
        )
    
    with col3:
        time_range = st.selectbox(
            "Rango de tiempo:",
            ["1 día", "3 días", "1 semana", "1 mes"]
        )
    
    if st.button("🔄 Actualizar Análisis", use_container_width=True):
        analyze_market_data(items_to_analyze, analysis_type, time_range)
    
    st.markdown("---")
    
    # Gráficos de análisis
    if analysis_type == "Precios":
        show_price_analysis(items_to_analyze)
    elif analysis_type == "Volatilidad":
        show_volatility_analysis(items_to_analyze)
    elif analysis_type == "Atributos":
        show_attribute_analysis(items_to_analyze)
    elif analysis_type == "Tendencias":
        show_trend_analysis(items_to_analyze)

def show_price_analysis(items):
    """Mostrar análisis de precios."""
    st.subheader("💰 Análisis de Precios")
    
    # Generar datos simulados
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='H')
    
    fig = go.Figure()
    
    for item in items:
        # Simular datos de precios
        base_price = np.random.uniform(20, 150)
        price_data = base_price + np.cumsum(np.random.normal(0, 1, len(dates)))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=price_data,
            mode='lines',
            name=item,
            line=dict(width=2)
        ))
    
    fig.update_layout(
        title="📊 Evolución de Precios",
        xaxis_title="Fecha",
        yaxis_title="Precio (USD)",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabla de estadísticas
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Estadísticas de Precios")
        stats_data = []
        for item in items:
            price = np.random.uniform(20, 150)
            change = np.random.uniform(-5, 10)
            stats_data.append({
                "Ítem": item,
                "Precio Actual": f"${price:.2f}",
                "Cambio 24h": f"{change:+.2f}%",
                "Volumen": f"{np.random.randint(50, 500)}"
            })
        
        df_stats = pd.DataFrame(stats_data)
        st.dataframe(df_stats, use_container_width=True)
    
    with col2:
        st.markdown("### 🎯 Oportunidades Detectadas")
        opportunities = [
            {"Ítem": "AK-47 | Redline", "Tipo": "Subvaluado", "Potencial": "+7.2%"},
            {"Ítem": "AWP | Asiimov", "Tipo": "Volatilidad", "Potencial": "+12.5%"}
        ]
        
        for opp in opportunities:
            st.markdown(f"**{opp['Ítem']}**")
            st.markdown(f"- Tipo: {opp['Tipo']}")
            st.markdown(f"- Potencial: {opp['Potencial']}")
            st.markdown("---")

def show_volatility_analysis(items):
    """Mostrar análisis de volatilidad."""
    st.subheader("📊 Análisis de Volatilidad")
    
    # Generar datos simulados de volatilidad
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de volatilidad
        fig = go.Figure()
        
        for item in items:
            volatility_data = np.random.uniform(0.1, 0.5, 30)
            dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=volatility_data,
                mode='lines+markers',
                name=item
            ))
        
        fig.update_layout(
            title="📈 Volatilidad Histórica",
            xaxis_title="Fecha",
            yaxis_title="Volatilidad",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Indicadores técnicos
        st.markdown("### 🔢 Indicadores Técnicos")
        
        for item in items:
            with st.expander(f"📊 {item}"):
                col_a, col_b = st.columns(2)
                
                with col_a:
                    rsi = np.random.uniform(20, 80)
                    st.metric("RSI", f"{rsi:.1f}", 
                             delta="Sobrecomprado" if rsi > 70 else "Sobreventa" if rsi < 30 else "Neutral")
                
                with col_b:
                    bb_position = np.random.uniform(-1, 1)
                    st.metric("Bollinger Bands", f"{bb_position:.2f}",
                             delta="Superior" if bb_position > 0.5 else "Inferior" if bb_position < -0.5 else "Medio")

def show_attribute_analysis(items):
    """Mostrar análisis de atributos."""
    st.subheader("💎 Análisis de Atributos")
    
    # Análisis de rareza de atributos
    st.markdown("### 🎯 Rareza de Atributos")
    
    attributes_data = []
    for item in items:
        float_val = np.random.uniform(0.0, 1.0)
        pattern = np.random.randint(1, 1000)
        stattrak = np.random.choice([True, False])
        
        attributes_data.append({
            "Ítem": item,
            "Float": f"{float_val:.4f}",
            "Pattern": pattern,
            "StatTrak": "Sí" if stattrak else "No",
            "Score Rareza": f"{np.random.uniform(0.1, 1.0):.2f}",
            "Premium Est.": f"{np.random.uniform(5, 50):.1f}%"
        })
    
    df_attributes = pd.DataFrame(attributes_data)
    st.dataframe(df_attributes, use_container_width=True)
    
    # Distribución de float values
    col1, col2 = st.columns(2)
    
    with col1:
        float_values = [float(attr["Float"]) for attr in attributes_data]
        fig = px.histogram(x=float_values, nbins=20, title="📊 Distribución de Float Values")
        fig.update_xaxis(title="Float Value")
        fig.update_yaxis(title="Frecuencia")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Radar chart de rareza
        categories = ['Float', 'Pattern', 'Exterior', 'Stickers', 'Rareza Global']
        
        fig = go.Figure()
        
        for item in items:
            values = np.random.uniform(0.3, 1.0, len(categories))
            values = np.append(values, values[0])  # Cerrar el polígono
            
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories + [categories[0]],
                fill='toself',
                name=item
            ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 1])
            ),
            title="🕸️ Análisis de Rareza Multi-dimensional"
        )
        
        st.plotly_chart(fig, use_container_width=True)

def show_trend_analysis(items):
    """Mostrar análisis de tendencias."""
    st.subheader("📈 Análisis de Tendencias")
    
    # Predicción de tendencias
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔮 Predicción de Precios")
        
        for item in items:
            current_price = np.random.uniform(20, 150)
            trend = np.random.choice(["📈 Alcista", "📉 Bajista", "➡️ Lateral"])
            confidence = np.random.uniform(60, 95)
            
            with st.expander(f"💎 {item}"):
                st.metric("Precio Actual", f"${current_price:.2f}")
                st.markdown(f"**Tendencia**: {trend}")
                st.markdown(f"**Confianza**: {confidence:.1f}%")
                
                # Mini gráfico de tendencia
                days = 7
                dates = pd.date_range(start=datetime.now(), end=datetime.now() + timedelta(days=days), freq='D')
                if "Alcista" in trend:
                    prices = current_price * (1 + np.cumsum(np.random.normal(0.01, 0.02, len(dates))))
                elif "Bajista" in trend:
                    prices = current_price * (1 + np.cumsum(np.random.normal(-0.01, 0.02, len(dates))))
                else:
                    prices = current_price * (1 + np.cumsum(np.random.normal(0, 0.01, len(dates))))
                
                fig = px.line(x=dates, y=prices, title=f"Predicción {item}")
                fig.update_layout(height=200, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 Señales de Trading")
        
        signals_data = []
        for item in items:
            signal_type = np.random.choice(["COMPRA", "VENTA", "MANTENER"])
            strength = np.random.choice(["Fuerte", "Moderada", "Débil"])
            timeframe = np.random.choice(["1h", "4h", "1d", "1w"])
            
            signals_data.append({
                "Ítem": item,
                "Señal": signal_type,
                "Fuerza": strength,
                "Timeframe": timeframe,
                "Score": f"{np.random.uniform(60, 95):.1f}%"
            })
        
        df_signals = pd.DataFrame(signals_data)
        st.dataframe(df_signals, use_container_width=True)
        
        # Gráfico de distribución de señales
        signal_counts = df_signals['Señal'].value_counts()
        fig = px.pie(values=signal_counts.values, names=signal_counts.index, 
                     title="📊 Distribución de Señales")
        st.plotly_chart(fig, use_container_width=True)

def analyze_market_data(items, analysis_type, time_range):
    """Analizar datos de mercado."""
    with st.spinner(f"Analizando {len(items)} ítems..."):
        time.sleep(2)  # Simular procesamiento
        st.success(f"✅ Análisis de {analysis_type} completado para {len(items)} ítems en rango de {time_range}")

def show_optimization_page():
    """Página de optimización de parámetros."""
    st.header("🧪 Optimización de Parámetros")
    
    if not st.session_state.system_initialized:
        st.warning("⚠️ Primero debes inicializar el sistema en la página de Inicio")
        return
    
    # Configuración de optimización
    st.subheader("⚙️ Configuración de Optimización")
    
    col1, col2 = st.columns(2)
    
    with col1:
        optimization_method = st.selectbox(
            "Método de Optimización:",
            ["Random Search", "Grid Search", "Bayesian Optimization"]
        )
        
        target_metric = st.selectbox(
            "Métrica Objetivo:",
            ["ROI", "Sharpe Ratio", "Win Rate", "Profit Factor"]
        )
        
        max_iterations = st.slider(
            "Máximo de Iteraciones:",
            min_value=10, max_value=1000, value=100
        )
    
    with col2:
        st.markdown("#### Parámetros a Optimizar")
        
        optimize_basic_flip = st.checkbox("Basic Flip Min Profit %", value=True)
        optimize_snipe_discount = st.checkbox("Snipe Discount Threshold", value=True)
        optimize_max_trade = st.checkbox("Max Trade Amount", value=False)
        optimize_rarity_score = st.checkbox("Attribute Rarity Score", value=True)
    
    # Rangos de parámetros
    st.markdown("---")
    st.subheader("📊 Rangos de Parámetros")
    
    param_cols = st.columns(2)
    
    with param_cols[0]:
        if optimize_basic_flip:
            st.markdown("##### Basic Flip Min Profit %")
            basic_flip_min = st.slider("Mínimo", 0.01, 0.10, 0.03, key="bf_min")
            basic_flip_max = st.slider("Máximo", 0.05, 0.20, 0.10, key="bf_max")
            basic_flip_step = st.slider("Paso", 0.005, 0.02, 0.01, key="bf_step")
        
        if optimize_snipe_discount:
            st.markdown("##### Snipe Discount Threshold")
            snipe_min = st.slider("Mínimo", 0.05, 0.15, 0.10, key="sn_min")
            snipe_max = st.slider("Máximo", 0.15, 0.30, 0.25, key="sn_max")
            snipe_step = st.slider("Paso", 0.01, 0.05, 0.02, key="sn_step")
    
    with param_cols[1]:
        if optimize_max_trade:
            st.markdown("##### Max Trade Amount")
            trade_min = st.slider("Mínimo", 10, 50, 25, key="tr_min")
            trade_max = st.slider("Máximo", 50, 200, 100, key="tr_max")
            trade_step = st.slider("Paso", 5, 25, 10, key="tr_step")
        
        if optimize_rarity_score:
            st.markdown("##### Attribute Rarity Score")
            rarity_min = st.slider("Mínimo", 0.1, 0.5, 0.3, key="ra_min")
            rarity_max = st.slider("Máximo", 0.5, 1.0, 0.8, key="ra_max")
            rarity_step = st.slider("Paso", 0.05, 0.2, 0.1, key="ra_step")
    
    # Botón de optimización
    st.markdown("---")
    
    if st.button("🚀 Iniciar Optimización", use_container_width=True):
        run_optimization(
            optimization_method, target_metric, max_iterations,
            {
                'basic_flip': (basic_flip_min, basic_flip_max, basic_flip_step) if optimize_basic_flip else None,
                'snipe_discount': (snipe_min, snipe_max, snipe_step) if optimize_snipe_discount else None,
                'max_trade': (trade_min, trade_max, trade_step) if optimize_max_trade else None,
                'rarity_score': (rarity_min, rarity_max, rarity_step) if optimize_rarity_score else None
            }
        )

def run_optimization(method, metric, iterations, param_ranges):
    """Ejecutar optimización de parámetros."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Simular optimización
    results = []
    best_score = 0
    
    for i in range(iterations):
        # Simular iteración
        progress = (i + 1) / iterations
        progress_bar.progress(progress)
        status_text.text(f"Iteración {i+1}/{iterations} - Mejor score: {best_score:.3f}")
        
        # Generar resultado simulado
        current_score = np.random.uniform(0.1, 0.8)
        if current_score > best_score:
            best_score = current_score
        
        results.append({
            'iteration': i+1,
            'score': current_score,
            'basic_flip_profit': np.random.uniform(0.03, 0.10) if param_ranges['basic_flip'] else None,
            'snipe_discount': np.random.uniform(0.10, 0.25) if param_ranges['snipe_discount'] else None
        })
        
        time.sleep(0.05)  # Simular tiempo de procesamiento
    
    status_text.text("✅ Optimización completada!")
    
    # Mostrar resultados
    st.markdown("---")
    st.subheader("📊 Resultados de Optimización")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"### 🏆 Mejor Configuración")
        st.markdown(f"**Score**: {best_score:.3f}")
        st.markdown(f"**Método**: {method}")
        st.markdown(f"**Métrica**: {metric}")
        st.markdown(f"**Iteraciones**: {iterations}")
    
    with col2:
        # Gráfico de convergencia
        scores = [r['score'] for r in results]
        fig = px.line(x=range(1, len(scores)+1), y=scores, 
                      title="📈 Convergencia de Optimización")
        fig.update_xaxis(title="Iteración")
        fig.update_yaxis(title="Score")
        st.plotly_chart(fig, use_container_width=True)

def show_metrics_page():
    """Página de métricas y KPIs."""
    st.header("📋 Métricas & KPIs")
    
    if not st.session_state.system_initialized:
        st.warning("⚠️ Primero debes inicializar el sistema en la página de Inicio")
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        roi = np.random.uniform(5, 25)
        st.metric("📈 ROI Total", f"{roi:.1f}%", f"+{roi/10:.1f}%")
    
    with col2:
        win_rate = np.random.uniform(60, 85)
        st.metric("🎯 Win Rate", f"{win_rate:.1f}%", f"+{np.random.uniform(1, 5):.1f}%")
    
    with col3:
        profit_factor = np.random.uniform(1.2, 2.5)
        st.metric("💰 Profit Factor", f"{profit_factor:.2f}", f"+{np.random.uniform(0.1, 0.3):.2f}")
    
    with col4:
        sharpe_ratio = np.random.uniform(0.8, 2.2)
        st.metric("📊 Sharpe Ratio", f"{sharpe_ratio:.2f}", f"+{np.random.uniform(0.1, 0.3):.2f}")
    
    # Gráficos de rendimiento
    st.markdown("---")
    st.subheader("📊 Análisis de Rendimiento")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Evolución del balance
        days = 30
        dates = pd.date_range(start=datetime.now() - timedelta(days=days), end=datetime.now(), freq='D')
        balance_evolution = 1000 * (1 + np.cumsum(np.random.normal(0.01, 0.02, len(dates))))
        
        fig = px.line(x=dates, y=balance_evolution, title="💰 Evolución del Balance")
        fig.update_xaxis(title="Fecha")
        fig.update_yaxis(title="Balance (USD)")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Distribución de profits por trade
        profits = np.random.normal(5, 10, 100)
        fig = px.histogram(x=profits, nbins=20, title="📊 Distribución de Profits por Trade")
        fig.update_xaxis(title="Profit (USD)")
        fig.update_yaxis(title="Frecuencia")
        st.plotly_chart(fig, use_container_width=True)
    
    # Métricas por estrategia
    st.markdown("---")
    st.subheader("🎯 Rendimiento por Estrategia")
    
    strategies_data = [
        {"Estrategia": "Basic Flip", "Trades": 45, "ROI": "12.3%", "Win Rate": "78%", "Avg Profit": "$3.2"},
        {"Estrategia": "Sniping", "Trades": 23, "ROI": "18.7%", "Win Rate": "65%", "Avg Profit": "$8.1"},
        {"Estrategia": "Attribute Premium", "Trades": 12, "ROI": "25.4%", "Win Rate": "58%", "Avg Profit": "$15.3"},
        {"Estrategia": "Trade Lock", "Trades": 18, "ROI": "15.2%", "Win Rate": "72%", "Avg Profit": "$5.8"},
        {"Estrategia": "Volatility", "Trades": 31, "ROI": "9.8%", "Win Rate": "68%", "Avg Profit": "$4.1"}
    ]
    
    df_strategies = pd.DataFrame(strategies_data)
    st.dataframe(df_strategies, use_container_width=True)
    
    # Gráfico comparativo de estrategias
    col1, col2 = st.columns(2)
    
    with col1:
        roi_values = [float(s["ROI"].replace('%', '')) for s in strategies_data]
        fig = px.bar(x=[s["Estrategia"] for s in strategies_data], y=roi_values,
                     title="📈 ROI por Estrategia")
        fig.update_xaxis(title="Estrategia")
        fig.update_yaxis(title="ROI (%)")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        trades_count = [s["Trades"] for s in strategies_data]
        fig = px.pie(values=trades_count, names=[s["Estrategia"] for s in strategies_data],
                     title="📊 Distribución de Trades")
        st.plotly_chart(fig, use_container_width=True)

def show_risk_management_page():
    """Página de gestión de riesgos."""
    st.header("🛡️ Gestión de Riesgos")
    
    if not st.session_state.system_initialized:
        st.warning("⚠️ Primero debes inicializar el sistema en la página de Inicio")
        return
    
    # Estado actual del riesgo
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        exposure = np.random.uniform(40, 80)
        st.metric("💼 Exposición Portfolio", f"{exposure:.1f}%", 
                 delta="Alto" if exposure > 70 else "Medio" if exposure > 50 else "Bajo")
    
    with col2:
        var = np.random.uniform(5, 25)
        st.metric("⚠️ VaR (95%)", f"${var:.1f}", f"-{np.random.uniform(1, 3):.1f}")
    
    with col3:
        concentration = np.random.uniform(0.2, 0.8)
        st.metric("🎯 Concentración", f"{concentration:.2f}", 
                 delta="Alto" if concentration > 0.6 else "Medio" if concentration > 0.4 else "Bajo")
    
    with col4:
        beta = np.random.uniform(0.8, 1.5)
        st.metric("📊 Beta Portfolio", f"{beta:.2f}", f"+{np.random.uniform(0.05, 0.15):.2f}")
    
    # Análisis de riesgos
    st.markdown("---")
    st.subheader("📊 Análisis de Riesgos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribución de riesgos
        risk_categories = ["Bajo", "Medio", "Alto", "Crítico"]
        risk_values = [45, 30, 20, 5]
        
        fig = px.pie(values=risk_values, names=risk_categories, 
                     title="🛡️ Distribución de Niveles de Riesgo")
        st.plotly_chart(fig, use_container_width=True)
        
        # Límites de riesgo
        st.markdown("### ⚙️ Límites Configurados")
        st.markdown(f"- **Exposición Máxima**: 80%")
        st.markdown(f"- **Posición Individual**: 10%")
        st.markdown(f"- **Stop Loss**: 15%")
        st.markdown(f"- **Trades Diarios**: 20")
    
    with col2:
        # Evolución del riesgo
        days = 14
        dates = pd.date_range(start=datetime.now() - timedelta(days=days), end=datetime.now(), freq='D')
        risk_evolution = np.random.uniform(0.3, 0.8, len(dates))
        
        fig = px.line(x=dates, y=risk_evolution, title="📈 Evolución del Riesgo")
        fig.add_hline(y=0.7, line_dash="dash", line_color="red", 
                      annotation_text="Límite Alto")
        fig.update_xaxis(title="Fecha")
        fig.update_yaxis(title="Nivel de Riesgo")
        st.plotly_chart(fig, use_container_width=True)
    
    # Alertas de riesgo
    st.markdown("---")
    st.subheader("🚨 Alertas de Riesgo")
    
    alerts = [
        {"Tipo": "⚠️ Warning", "Mensaje": "Concentración alta en AK-47 items", "Fecha": "2024-01-15 14:30"},
        {"Tipo": "ℹ️ Info", "Mensaje": "VaR dentro de límites normales", "Fecha": "2024-01-15 12:00"},
        {"Tipo": "🔴 Critical", "Mensaje": "Stop loss activado para M4A4 | Howl", "Fecha": "2024-01-15 09:15"}
    ]
    
    for alert in alerts:
        alert_type = alert["Tipo"]
        if "Critical" in alert_type:
            st.error(f"{alert_type}: {alert['Mensaje']} - {alert['Fecha']}")
        elif "Warning" in alert_type:
            st.warning(f"{alert_type}: {alert['Mensaje']} - {alert['Fecha']}")
        else:
            st.info(f"{alert_type}: {alert['Mensaje']} - {alert['Fecha']}")

def show_logs_page():
    """Página de logs y historial."""
    st.header("📝 Logs y Historial")
    
    # Tabs para diferentes tipos de logs
    tab1, tab2, tab3, tab4 = st.tabs(["🔄 Sistema", "💰 Trades", "⚠️ Errores", "📊 Métricas"])
    
    with tab1:
        st.subheader("🔄 Logs del Sistema")
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            log_level = st.selectbox("Nivel de Log:", ["Todos", "DEBUG", "INFO", "WARNING", "ERROR"])
        
        with col2:
            date_filter = st.date_input("Fecha:", datetime.now().date())
        
        with col3:
            if st.button("🔄 Actualizar Logs"):
                st.rerun()
        
        # Logs simulados
        logs = [
            {"Timestamp": "2024-01-15 15:30:45", "Level": "INFO", "Message": "Sistema inicializado correctamente"},
            {"Timestamp": "2024-01-15 15:31:02", "Level": "INFO", "Message": "Conectado a DMarket API"},
            {"Timestamp": "2024-01-15 15:31:15", "Level": "DEBUG", "Message": "Cargando configuración de estrategias"},
            {"Timestamp": "2024-01-15 15:31:30", "Level": "WARNING", "Message": "Rate limit detectado, esperando..."},
            {"Timestamp": "2024-01-15 15:32:00", "Level": "INFO", "Message": "Búsqueda de oportunidades completada"},
        ]
        
        df_logs = pd.DataFrame(logs)
        st.dataframe(df_logs, use_container_width=True)
    
    with tab2:
        st.subheader("💰 Historial de Trades")
        
        if st.session_state.trades_history:
            df_trades = pd.DataFrame(st.session_state.trades_history)
            st.dataframe(df_trades, use_container_width=True)
            
            # Estadísticas de trades
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_profit = sum([t.get('expected_profit', 0) for t in st.session_state.trades_history])
                st.metric("💰 Profit Total", f"${total_profit:.2f}")
            
            with col2:
                avg_profit = total_profit / len(st.session_state.trades_history) if st.session_state.trades_history else 0
                st.metric("📊 Profit Promedio", f"${avg_profit:.2f}")
            
            with col3:
                st.metric("📈 Total Trades", len(st.session_state.trades_history))
        else:
            st.info("No hay trades en el historial aún.")
    
    with tab3:
        st.subheader("⚠️ Log de Errores")
        
        errors = [
            {"Timestamp": "2024-01-15 14:25:10", "Error": "ConnectionError", "Details": "Timeout conectando a DMarket API"},
            {"Timestamp": "2024-01-15 13:45:22", "Error": "ValidationError", "Details": "Parámetro de estrategia fuera de rango"},
        ]
        
        for error in errors:
            with st.expander(f"❌ {error['Error']} - {error['Timestamp']}"):
                st.code(error['Details'])
    
    with tab4:
        st.subheader("📊 Log de Métricas")
        
        # Evolución de métricas en tiempo real
        metrics_history = {
            "timestamp": pd.date_range(start=datetime.now() - timedelta(hours=6), end=datetime.now(), freq='H'),
            "balance": np.random.uniform(950, 1050, 7),
            "active_trades": np.random.randint(0, 5, 7),
            "opportunities": np.random.randint(0, 10, 7)
        }
        
        df_metrics = pd.DataFrame(metrics_history)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.line(df_metrics, x='timestamp', y='balance', title="💰 Evolución del Balance")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.line(df_metrics, x='timestamp', y='opportunities', title="🎯 Oportunidades Detectadas")
            st.plotly_chart(fig, use_container_width=True) 