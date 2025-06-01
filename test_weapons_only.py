#!/usr/bin/env python3
"""
Test de Escaneo Solo de Armas - Para encontrar oportunidades reales
================================================================

Script para probar el sistema de estrategias solo con armas reales
que deberían tener atributos y generar oportunidades.
"""

import os
import sys
import sqlite3
from typing import List

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar variables de entorno
os.environ["DMARKET_PUBLIC_KEY"] = "24c344f13198fe32736392f7dd020fb24b3f99e1f7534f001dbddaeec8054db9"
os.environ["DMARKET_SECRET_KEY"] = "f55eca4dc581ae9b24d8611d6c8576822f1ccc1b2c5ebdf6410836fe0647ad0c24c344f13198fe32736392f7dd020fb24b3f99e1f7534f001dbddaeec8054db9"

from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer
from core.strategy_engine import StrategyEngine

def get_weapon_items_only() -> List[str]:
    """Obtener solo armas de la base de datos (no stickers, cases, etc.)"""
    conn = sqlite3.connect('cs2_trading.db')
    cursor = conn.cursor()
    
    # Filtrar solo armas reales (excluir stickers, cases, graffiti, etc.)
    cursor.execute("""
        SELECT DISTINCT name FROM skins_maestra 
        WHERE name NOT LIKE '%Sticker%' 
        AND name NOT LIKE '%Case%' 
        AND name NOT LIKE '%Graffiti%'
        AND name NOT LIKE '%Patch%'
        AND name NOT LIKE '%Music Kit%'
        AND (
            name LIKE '%AK-47%' OR 
            name LIKE '%M4A4%' OR 
            name LIKE '%M4A1-S%' OR
            name LIKE '%AWP%' OR
            name LIKE '%Desert Eagle%' OR
            name LIKE '%Glock-%' OR
            name LIKE '%USP-S%' OR
            name LIKE '%P250%' OR
            name LIKE '%StatTrak™%'
        )
        LIMIT 10
    """)
    
    weapons = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return weapons

def main():
    print("🔫 TEST DE ESCANEO - SOLO ARMAS")
    print("=" * 50)
    
    # 1. Obtener lista de armas
    weapons = get_weapon_items_only()
    print(f"📋 Armas a escanear ({len(weapons)}):")
    for weapon in weapons:
        print(f"  - {weapon}")
    
    if not weapons:
        print("❌ No se encontraron armas en la BD")
        return
    
    print("\n🔄 Inicializando sistema...")
    
    # 2. Configurar API DMarket
    dmarket_api = DMarketAPI()
    
    # 3. Configurar analizadores con configuración más agresiva
    market_analyzer = MarketAnalyzer()
    
    # Configuración más permisiva para encontrar oportunidades
    strategy_config = {
        "min_profit_usd_basic_flip": 0.10,  # Muy bajo para testing
        "min_profit_percentage_basic_flip": 0.01,  # 1% mínimo
        "min_price_usd_for_sniping": 0.25,  # Muy bajo
        "snipe_discount_percentage": 0.05,  # 5% descuento
        "min_expected_profit_usd": 0.10,  # Muy bajo
        "max_trade_amount_usd": 50.0,  # Más alto
        "basic_flip_min_profit_percentage": 0.01,
        "snipe_discount_threshold": 0.05,
        "attribute_min_rarity_score": 0.1,  # Muy bajo
        "trade_lock_min_discount": 0.02,
        "volatility_rsi_oversold": 40,
        "volatility_rsi_overbought": 60,
        "min_profit_usd_attribute_flip": 0.10,
        "min_profit_percentage_attribute_flip": 0.02,
        "min_premium_multiplier": 1.05,  # Muy bajo
        "max_price_usd_attribute_flip": 50.0,
        "min_profit_usd_trade_lock": 0.15,
        "min_profit_percentage_trade_lock": 0.03,
        "trade_lock_discount_threshold": 0.05,
        "max_trade_lock_days": 21,
        "min_profit_usd_volatility": 0.10,
        "min_confidence_volatility": 0.3,  # Muy bajo
        "max_price_usd_volatility": 50.0,
    }
    
    strategy_engine = StrategyEngine(dmarket_api, market_analyzer, strategy_config)
    
    print("✅ Sistema inicializado")
    print("\n🎯 Buscando oportunidades en armas...")
    
    # 4. Buscar oportunidades solo en armas
    opportunities_by_strategy = strategy_engine.run_strategies(weapons)
    
    # Combinar todas las oportunidades
    all_opportunities = []
    for strategy_name, opportunities in opportunities_by_strategy.items():
        for opp in opportunities:
            opp['strategy'] = strategy_name  # Asegurar que tenga el nombre de estrategia
            all_opportunities.append(opp)
    
    print(f"\n📊 RESULTADOS:")
    print(f"⚙️  Ítems analizados: {len(weapons)}")
    print(f"🎯 Oportunidades encontradas: {len(all_opportunities)}")
    
    # Desglose por estrategia
    for strategy_name, opportunities in opportunities_by_strategy.items():
        if opportunities:
            print(f"   📈 {strategy_name}: {len(opportunities)} oportunidades")
    
    if all_opportunities:
        print("\n🎉 ¡OPORTUNIDADES ENCONTRADAS!")
        for i, opp in enumerate(all_opportunities[:5], 1):  # Mostrar solo las primeras 5
            print(f"\n🔥 Oportunidad #{i}:")
            print(f"   📦 Ítem: {opp.get('item_title', 'N/A')}")
            print(f"   📈 Estrategia: {opp.get('strategy', 'N/A')}")
            print(f"   💰 Precio compra: ${opp.get('buy_price_usd', opp.get('entry_price_usd', 0)):.2f}")
            print(f"   💵 Precio venta: ${opp.get('sell_price_usd', opp.get('target_price_usd', 0)):.2f}")
            print(f"   📊 Profit: ${opp.get('expected_profit_usd', 0):.2f}")
            print(f"   🎯 ROI: {opp.get('profit_percentage', 0):.1f}%")
    else:
        print("\n⚠️  No se encontraron oportunidades con la configuración actual")
        print("💡 Posibles razones:")
        print("   - Los precios de mercado están muy equilibrados")
        print("   - Se requiere configuración más agresiva")
        print("   - Los ítems no tienen suficiente liquidez")

if __name__ == "__main__":
    main() 