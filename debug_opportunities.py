#!/usr/bin/env python3
"""
Debug de Oportunidades - Ver estructura detallada
===============================================
"""

import os
import sys
import sqlite3
import json
from typing import List

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar variables de entorno
os.environ["DMARKET_PUBLIC_KEY"] = "24c344f13198fe32736392f7dd020fb24b3f99e1f7534f001dbddaeec8054db9"
os.environ["DMARKET_SECRET_KEY"] = "f55eca4dc581ae9b24d8611d6c8576822f1ccc1b2c5ebdf6410836fe0647ad0c24c344f13198fe32736392f7dd020fb24b3f99e1f7534f001dbddaeec8054db9"

from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer
from core.strategy_engine import StrategyEngine

def main():
    print("🔍 DEBUG DE OPORTUNIDADES")
    print("=" * 40)
    
    # Solo analizar 1 ítem para debug detallado
    test_items = ["Desert Eagle | Tilted (Factory New)"]
    
    print(f"🎯 Analizando: {test_items[0]}")
    
    # Configurar sistema
    dmarket_api = DMarketAPI()
    market_analyzer = MarketAnalyzer()
    
    # Configuración muy permisiva
    strategy_config = {
        "min_profit_usd_basic_flip": 0.01,
        "min_profit_percentage_basic_flip": 0.001,  # 0.1%
        "min_price_usd_for_sniping": 0.01,
        "snipe_discount_percentage": 0.01,  # 1%
        "min_expected_profit_usd": 0.01,
        "max_trade_amount_usd": 100.0,
    }
    
    strategy_engine = StrategyEngine(dmarket_api, market_analyzer, strategy_config)
    
    # Buscar oportunidades
    opportunities_by_strategy = strategy_engine.run_strategies(test_items)
    
    print(f"\n📊 Resultados:")
    for strategy_name, opportunities in opportunities_by_strategy.items():
        if opportunities:
            print(f"\n🎯 {strategy_name}: {len(opportunities)} oportunidades")
            
            # Mostrar las primeras 3 oportunidades con detalles completos
            for i, opp in enumerate(opportunities[:3], 1):
                print(f"\n🔥 Oportunidad #{i} - Estructura completa:")
                print("=" * 50)
                
                # Mostrar todos los campos disponibles
                for key, value in opp.items():
                    print(f"  {key}: {value}")
                
                print("\n🔍 Campos financieros específicos:")
                buy_price = opp.get('buy_price_usd', opp.get('entry_price_usd', opp.get('snipe_price_usd', 'N/A')))
                sell_price = opp.get('sell_price_usd', opp.get('target_price_usd', opp.get('estimated_market_price_usd', 'N/A')))
                profit = opp.get('expected_profit_usd', opp.get('profit_usd', 'N/A'))
                
                print(f"  💰 Precio Compra: {buy_price}")
                print(f"  💵 Precio Venta: {sell_price}")
                print(f"  📊 Profit: {profit}")
                
                # Verificar si hay datos de ofertas
                if 'offer_data' in opp:
                    print(f"\n📋 Datos de oferta:")
                    offer_data = opp['offer_data']
                    if isinstance(offer_data, dict):
                        print(f"  - Precio oferta: {offer_data.get('price', 'N/A')}")
                        print(f"  - Asset ID: {offer_data.get('assetId', 'N/A')}")
                    else:
                        print(f"  - Offer data: {offer_data}")
    
    # Verificar conexión API directamente
    print(f"\n🌐 TEST DE API DIRECTO:")
    print("=" * 30)
    
    # Probar obtener ofertas directamente
    offers_response = dmarket_api.get_offers_by_title(test_items[0])
    
    if 'objects' in offers_response and offers_response['objects']:
        print(f"✅ API devuelve {len(offers_response['objects'])} ofertas")
        
        # Mostrar primera oferta
        first_offer = offers_response['objects'][0]
        print(f"\n📋 Primera oferta:")
        print(f"  - Precio: {first_offer.get('price', {}).get('USD', 'N/A')} USD")
        print(f"  - Asset ID: {first_offer.get('assetId', 'N/A')}")
        print(f"  - Título: {first_offer.get('title', 'N/A')}")
        
        # Convertir precio a formato usado por el sistema
        if 'price' in first_offer and 'USD' in first_offer['price']:
            price_cents = int(first_offer['price']['USD'])
            price_usd = price_cents / 100.0
            print(f"  - Precio convertido: ${price_usd:.2f}")
    else:
        print("❌ API no devuelve ofertas o hay error")
        print(f"Respuesta: {offers_response}")

if __name__ == "__main__":
    main() 