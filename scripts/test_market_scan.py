#!/usr/bin/env python3
"""
Test del Escaneo Completo del Mercado DMarket
===========================================

Script para probar la funcionalidad de escaneo completo del mercado
sin necesidad del dashboard web.
"""

import os
import sys
from dotenv import load_dotenv

# Agregar el directorio padre al path para encontrar los módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Importar módulos
from core.dmarket_connector import DMarketAPI
from core.strategy_engine import StrategyEngine
from core.market_analyzer import MarketAnalyzer
from utils.logger import configure_logging
import logging

def main():
    print("🌍 INICIANDO ESCANEO COMPLETO DEL MERCADO DMARKET")
    print("=" * 60)
    
    # Configurar logging
    configure_logging(log_level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Cargar variables de entorno
    load_dotenv()
    
    try:
        print("📡 1. Conectando con DMarket API...")
        
        # Inicializar componentes
        dmarket_api = DMarketAPI(
            public_key=os.getenv("DMARKET_PUBLIC_KEY"),
            secret_key=os.getenv("DMARKET_SECRET_KEY")
        )
        
        print("🧠 2. Inicializando Motor de Análisis...")
        market_analyzer = MarketAnalyzer()
        
        # Configuración optimizada para escaneo completo
        strategy_config = {
            "basic_flip_min_profit_percentage": 0.01,  # 1% mínimo
            "snipe_discount_threshold": 0.05,  # 5% descuento
            "min_expected_profit_usd": 0.10,  # $0.10 mínimo
            "min_profit_usd_basic_flip": 0.10,
            "min_profit_percentage_basic_flip": 0.01,
            "min_price_usd_for_sniping": 0.25,
            "snipe_discount_percentage": 0.05,
            "delay_between_items_sec": 0.3  # Más rápido para test
        }
        
        strategy_engine = StrategyEngine(dmarket_api, market_analyzer, strategy_config)
        
        print("🔍 3. Obteniendo ítems del mercado...")
        
        # Obtener ítems del mercado
        all_market_items = []
        cursor = None
        total_pages = 0
        max_pages = 5  # Reducido para test rápido
        
        while total_pages < max_pages:
            print(f"   📄 Escaneando página {total_pages + 1}/{max_pages}...")
            
            try:
                market_response = dmarket_api.get_market_items(
                    game_id="a8db",  # CS2
                    limit=100,
                    currency="USD",
                    cursor=cursor,
                    order_by="price",
                    order_dir="asc"
                )
                
                if "error" in market_response:
                    print(f"   ❌ Error: {market_response['error']}")
                    break
                
                items = market_response.get("objects", [])
                if not items:
                    print("   ℹ️ No más ítems disponibles")
                    break
                
                # Extraer nombres únicos
                for item in items:
                    title = item.get("title", "")
                    if title and title not in all_market_items:
                        all_market_items.append(title)
                
                total_pages += 1
                cursor = market_response.get("cursor")
                
                print(f"   ✅ {len(all_market_items)} ítems únicos encontrados hasta ahora")
                
                if not cursor:
                    break
                    
            except Exception as e:
                print(f"   ⚠️ Error en página {total_pages}: {e}")
                break
        
        print(f"\n🎯 4. MERCADO ESCANEADO: {len(all_market_items)} ítems únicos")
        
        if len(all_market_items) == 0:
            print("❌ No se encontraron ítems. Verifica la conexión con DMarket.")
            return
        
        # Mostrar muestra de ítems encontrados
        print("\n📋 Muestra de ítems encontrados:")
        for i, item in enumerate(all_market_items[:10]):
            print(f"   {i+1}. {item}")
        if len(all_market_items) > 10:
            print(f"   ... y {len(all_market_items) - 10} más")
        
        print(f"\n🔬 5. Analizando {len(all_market_items)} ítems para oportunidades...")
        
        # Ejecutar análisis en lotes
        all_opportunities = []
        batch_size = 25  # Lotes pequeños para test
        
        items_to_analyze = all_market_items[:50]  # Solo primeros 50 para test
        total_batches = (len(items_to_analyze) + batch_size - 1) // batch_size
        
        for i in range(0, len(items_to_analyze), batch_size):
            batch = items_to_analyze[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            print(f"   🧪 Analizando lote {batch_num}/{total_batches}: {len(batch)} ítems...")
            
            try:
                batch_results = strategy_engine.run_strategies(batch)
                
                # Procesar resultados
                for strategy_name, opportunities in batch_results.items():
                    if opportunities:
                        print(f"      ✅ {strategy_name}: {len(opportunities)} oportunidades")
                        for opp in opportunities:
                            all_opportunities.append({
                                'strategy': strategy_name,
                                'item': opp.get('item_title'),
                                'buy_price': opp.get('buy_price_usd', opp.get('offer_price_usd', opp.get('entry_price_usd', 0))),
                                'profit': opp.get('expected_profit_usd', opp.get('potential_profit_usd', opp.get('profit_usd', 0))),
                                'profit_pct': opp.get('profit_percentage', 0) * 100 if opp.get('profit_percentage', 0) <= 1 else opp.get('profit_percentage', 0)
                            })
                
            except Exception as e:
                print(f"      ⚠️ Error analizando lote {batch_num}: {e}")
        
        print(f"\n🎉 6. ANÁLISIS COMPLETO!")
        print("=" * 60)
        
        if all_opportunities:
            print(f"✅ {len(all_opportunities)} OPORTUNIDADES ENCONTRADAS!")
            
            # Ordenar por profit
            all_opportunities.sort(key=lambda x: x['profit'], reverse=True)
            
            # Mostrar resumen por estrategia
            strategies = {}
            for opp in all_opportunities:
                strategy = opp['strategy']
                if strategy not in strategies:
                    strategies[strategy] = 0
                strategies[strategy] += 1
            
            print(f"\n📊 Resumen por Estrategia:")
            for strategy, count in strategies.items():
                print(f"   • {strategy.replace('_', ' ').title()}: {count} oportunidades")
            
            # Mostrar las mejores 10 oportunidades
            print(f"\n🏆 TOP 10 MEJORES OPORTUNIDADES:")
            for i, opp in enumerate(all_opportunities[:10]):
                print(f"   {i+1}. {opp['item'][:50]}...")
                print(f"      💰 Precio: ${opp['buy_price']:.2f} | 📈 Profit: ${opp['profit']:.2f} ({opp['profit_pct']:.1f}%)")
                print(f"      🧠 Estrategia: {opp['strategy'].replace('_', ' ').title()}")
                print()
                
            # Analizar affordability con balance de $48.99
            balance = 48.99
            affordable = [opp for opp in all_opportunities if opp['buy_price'] <= balance]
            expensive = [opp for opp in all_opportunities if opp['buy_price'] > balance]
            
            print(f"💰 ANÁLISIS DE PRESUPUESTO (Balance: ${balance}):")
            print(f"   ✅ {len(affordable)} oportunidades que PUEDES comprar")
            print(f"   💎 {len(expensive)} oportunidades que requieren más dinero")
            
            if affordable:
                total_affordable_profit = sum(opp['profit'] for opp in affordable[:5])
                print(f"   📈 Profit potencial top 5 affordable: ${total_affordable_profit:.2f}")
        
        else:
            print("⚠️ No se encontraron oportunidades en este escaneo.")
            print("💡 Esto puede pasar si:")
            print("   - El mercado está muy estable")
            print("   - Los parámetros son muy estrictos")
            print("   - Hay pocos datos históricos disponibles")
        
        print(f"\n🎯 ¡Escaneo completo terminado exitosamente!")
        print("💡 Para ver más oportunidades, usa el dashboard web en localhost:8502")
        
    except Exception as e:
        print(f"❌ Error durante el escaneo: {e}")
        logger.error(f"Error en escaneo completo: {e}")

if __name__ == "__main__":
    main() 