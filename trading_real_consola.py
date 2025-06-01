#!/usr/bin/env python3
"""
🔥 TRADING REAL CS2 - CONSOLA INTERACTIVA 🔥
============================================
Sistema de consola para trading REAL de skins CS2 con DMarket API.
Sin simulación - solo trades reales con dinero real.
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Configurar path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Verificar claves API
if not os.environ.get("DMARKET_PUBLIC_KEY") or not os.environ.get("DMARKET_SECRET_KEY"):
    print("❌ ERROR: Claves API de DMarket no configuradas en .env")
    sys.exit(1)

# Imports del sistema
from core.dmarket_connector import DMarketAPI
from core.market_analyzer import MarketAnalyzer
from core.strategy_engine import StrategyEngine
from core.real_trader import RealTrader
from core.kpi_tracker import KPITracker, KPIPeriod
from core.inventory_manager import InventoryManager
from core.data_manager import get_db

class TradingConsole:
    """Consola interactiva para trading real."""
    
    def __init__(self):
        """Inicializar sistema de trading real."""
        print("🔥 INICIANDO SISTEMA DE TRADING REAL...")
        print("=" * 60)
        
        # Configurar componentes
        self.api = DMarketAPI()
        self.market_analyzer = MarketAnalyzer()
        self.inventory_manager = InventoryManager()
        self.real_trader = RealTrader(self.api)
        self.kpi_tracker = KPITracker(self.inventory_manager)
        
        # Configuración agresiva para encontrar oportunidades
        self.strategy_config = {
            "min_profit_usd_basic_flip": 0.01,       # Profit mínimo muy bajo para test
            "min_profit_percentage_basic_flip": 0.0001, # 0.01%
            "min_price_usd_for_sniping": 15.0,       # Considerar ítems desde 15 USD para snipe
            "snipe_discount_percentage": 0.001,      # 0.1% de descuento es suficiente para test
            "max_trade_amount_usd": 25.0,            # Máximo USD por trade
            "min_liquidity_basic_flip": 2,           # Mínima liquidez (ofertas compra/venta)
            "max_spread_percentage_basic_flip": 0.75, # Spread un poco más permisivo
            "min_snipe_profit_usd": 0.01,            # Profit mínimo para snipe
            # Mantener otros parámetros existentes que no se listen aquí
            "fee_percentage_dmarket": float(os.getenv("DMARKET_FEE_PERCENTAGE", "0.05")),
            "min_fee_usd_dmarket": float(os.getenv("DMARKET_MIN_FEE_USD", "0.01"))
        }
        
        self.strategy_engine = StrategyEngine(
            self.api, 
            self.market_analyzer, 
            self.strategy_config
        )
        
        # Verificar conexión
        self._verify_connection()
        
    def _verify_connection(self):
        """Verificar conexión con DMarket."""
        try:
            balance = self.api.get_account_balance()
            if "error" in balance:
                print(f"❌ Error conectando: {balance}")
                sys.exit(1)
            print("✅ Conexión DMarket verificada")
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            sys.exit(1)
    
    def show_balance(self):
        """Mostrar balance actual."""
        print("\n💰 BALANCE ACTUAL")
        print("-" * 30)
        
        balance_info = self.real_trader.get_real_balance()
        
        print(f"💵 Cash disponible: ${balance_info['cash_balance']:.2f} USD")
        print(f"📦 Valor portfolio: ${balance_info['portfolio_value']:.2f} USD")
        print(f"💯 Balance total: ${balance_info['total_balance']:.2f} USD")
        print(f"📊 Total invertido: ${balance_info['total_invested']:.2f} USD")
        
        if balance_info['total_balance'] > 0:
            roi = ((balance_info['total_balance'] - balance_info['total_invested']) / max(balance_info['total_invested'], 1)) * 100
            print(f"📈 ROI estimado: {roi:.2f}%")
    
    def show_kpis(self):
        """Mostrar KPIs completos."""
        print("\n📊 KPIs Y MÉTRICAS DE PERFORMANCE")
        print("=" * 50)
        
        try:
            # KPIs de diferentes períodos
            periods = [
                (KPIPeriod.DAILY, "📅 HOY"),
                (KPIPeriod.WEEKLY, "📈 ESTA SEMANA"),
                (KPIPeriod.MONTHLY, "📋 ESTE MES"),
                (KPIPeriod.ALL_TIME, "🎯 TODO EL TIEMPO")
            ]
            
            for period, title in periods:
                print(f"\n{title}")
                print("-" * 30)
                
                kpis = self.kpi_tracker.calculate_kpis(period)
                
                print(f"💰 Profit total: ${kpis.total_profit_usd:.2f} USD ({kpis.total_profit_percentage:.1f}%)")
                print(f"✅ Win rate: {kpis.win_rate_percentage:.1f}%")
                print(f"📊 Trades: {kpis.total_trades} (exitosos: {kpis.successful_trades})")
                print(f"💵 Profit promedio/trade: ${kpis.avg_profit_per_trade_usd:.2f}")
                print(f"📈 Profit factor: {kpis.profit_factor:.2f}")
                print(f"⏱️ Duración promedio: {kpis.avg_trade_duration_hours:.1f}h")
                
                if kpis.strategy_performance:
                    print(f"🎯 Por estrategia:")
                    for strategy, metrics in kpis.strategy_performance.items():
                        print(f"   {strategy}: ${metrics.get('profit', 0):.2f} ({metrics.get('trades', 0)} trades)")
        
        except Exception as e:
            print(f"❌ Error calculando KPIs: {e}")
    
    def scan_opportunities(self, max_items: int = 20):
        """Escanear oportunidades de mercado."""
        print(f"\n🔍 ESCANEANDO OPORTUNIDADES (máx {max_items} ítems)")
        print("=" * 60)
        
        # Lista de ítems populares para escanear
        items_to_scan = [
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Field-Tested)",
            "M4A4 | Howl (Field-Tested)",
            "Desert Eagle | Blaze (Factory New)",
            "Glock-18 | Water Elemental (Factory New)",
            "P250 | Sand Dune (Battle-Scarred)",
            "UMP-45 | Gunsmoke (Battle-Scarred)",
            "MP7 | Forest DDPAT (Battle-Scarred)",
            "Nova | Forest Leaves (Battle-Scarred)",
            "P90 | Sand Spray (Battle-Scarred)",
            "Tec-9 | Groundwater (Battle-Scarred)",
            "MAC-10 | Indigo (Battle-Scarred)"
        ]
        
        # Limitar a max_items
        items_to_scan = items_to_scan[:max_items]
        
        print(f"📋 Escaneando {len(items_to_scan)} ítems...")
        
        try:
            # Ejecutar estrategias
            opportunities_by_strategy = self.strategy_engine.run_strategies(items_to_scan)
            
            # Consolidar oportunidades
            all_opportunities = []
            for strategy_name, opportunities in opportunities_by_strategy.items():
                for opp in opportunities:
                    opp['strategy'] = strategy_name
                    all_opportunities.append(opp)
            
            print(f"\n📊 RESULTADOS DEL ESCANEO:")
            print(f"🎯 Oportunidades encontradas: {len(all_opportunities)}")
            
            # Mostrar por estrategia
            for strategy, opps in opportunities_by_strategy.items():
                if opps:
                    print(f"   📈 {strategy}: {len(opps)} oportunidades")
            
            if all_opportunities:
                print(f"\n🔥 TOP 5 MEJORES OPORTUNIDADES:")
                # Ordenar por profit esperado
                sorted_opps = sorted(all_opportunities, 
                                   key=lambda x: x.get('expected_profit_usd', 0), 
                                   reverse=True)
                
                for i, opp in enumerate(sorted_opps[:5], 1):
                    item_title = opp.get('item_title', 'N/A')
                    strategy = opp.get('strategy', 'N/A')
                    buy_price = opp.get('buy_price_usd', opp.get('entry_price_usd', 0))
                    profit = opp.get('expected_profit_usd', 0)
                    roi = opp.get('profit_percentage', 0)
                    
                    print(f"\n   {i}. {item_title}")
                    print(f"      📈 Estrategia: {strategy}")
                    print(f"      💰 Precio: ${buy_price:.2f}")
                    print(f"      📊 Profit: ${profit:.2f} ({roi:.1f}%)")
                
                return sorted_opps
            else:
                print("\n⚠️ No se encontraron oportunidades viables")
                return []
                
        except Exception as e:
            print(f"❌ Error escaneando: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def execute_trade(self, opportunity: Dict[str, Any]):
        """Ejecutar un trade real."""
        item_title = opportunity.get('item_title', 'N/A')
        buy_price = opportunity.get('buy_price_usd', opportunity.get('entry_price_usd', 0))
        profit = opportunity.get('expected_profit_usd', 0)
        strategy = opportunity.get('strategy', 'N/A')
        
        print(f"\n🚀 EJECUTANDO TRADE REAL")
        print("=" * 40)
        print(f"📦 Ítem: {item_title}")
        print(f"📈 Estrategia: {strategy}")
        print(f"💰 Precio: ${buy_price:.2f}")
        print(f"📊 Profit esperado: ${profit:.2f}")
        
        # Verificar balance
        balance_info = self.real_trader.get_real_balance()
        if buy_price > balance_info['cash_balance']:
            print(f"❌ Balance insuficiente: ${buy_price:.2f} > ${balance_info['cash_balance']:.2f}")
            return False
        
        # Confirmación
        print(f"\n⚠️ ADVERTENCIA: Esto gastará dinero REAL de tu cuenta DMarket")
        confirmation = input(f"¿Ejecutar compra de ${buy_price:.2f}? (escribe 'SI' para confirmar): ")
        
        if confirmation.upper() != 'SI':
            print("❌ Trade cancelado")
            return False
        
        try:
            # Ejecutar compra real
            result = self.real_trader.execute_real_buy(opportunity)
            
            if result.get('success'):
                print(f"✅ ¡TRADE EJECUTADO EXITOSAMENTE!")
                print(f"💳 Precio pagado: ${result.get('price_paid', buy_price):.2f}")
                print(f"🔑 Transaction ID: {result.get('transaction_id', 'N/A')}")
                return True
            else:
                print(f"❌ Error ejecutando trade: {result.get('reason', 'desconocido')}")
                return False
                
        except Exception as e:
            print(f"❌ Error en ejecución: {e}")
            return False
    
    def portfolio_summary(self):
        """Mostrar resumen del portfolio."""
        print("\n📦 RESUMEN DEL PORTFOLIO")
        print("=" * 40)
        
        try:
            summary = self.real_trader.get_portfolio_summary()
            
            print(f"💼 Total ítems: {summary.get('total_items', 0)}")
            print(f"💰 Valor total: ${summary.get('total_value', 0):.2f}")
            print(f"📈 Profit realizado: ${summary.get('realized_profit', 0):.2f}")
            print(f"📊 Profit no realizado: ${summary.get('unrealized_profit', 0):.2f}")
            
            # Mostrar ítems individuales
            items = summary.get('items', [])
            if items:
                print(f"\n📋 ÍTEMS EN PORTFOLIO:")
                for item in items[:10]:  # Mostrar primeros 10
                    print(f"   📦 {item.get('item_title', 'N/A')}")
                    print(f"      💰 Costo: ${item.get('avg_cost_usd', 0):.2f}")
                    print(f"      📅 Comprado: {item.get('acquired_at', 'N/A')}")
            
        except Exception as e:
            print(f"❌ Error obteniendo portfolio: {e}")
    
    def auto_trading_session(self, duration_minutes: int = 30):
        """Sesión de trading automático por tiempo limitado."""
        print(f"\n🤖 SESIÓN DE TRADING AUTOMÁTICO ({duration_minutes} minutos)")
        print("=" * 60)
        print("⚠️ MODO AUTOMÁTICO - Se ejecutarán trades SIN confirmación manual")
        
        confirm = input("¿Continuar con trading automático? (escribe 'AUTOMATICO'): ")
        if confirm != 'AUTOMATICO':
            print("❌ Sesión automática cancelada")
            return
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        trades_executed = 0
        
        print(f"🚀 Sesión iniciada - terminará a las {end_time.strftime('%H:%M:%S')}")
        
        while datetime.now() < end_time:
            try:
                print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - Escaneando oportunidades...")
                
                # Escanear oportunidades
                opportunities = self.scan_opportunities(max_items=10)
                
                # Ejecutar la mejor oportunidad si existe
                if opportunities:
                    best_opp = opportunities[0]
                    buy_price = best_opp.get('buy_price_usd', 0)
                    
                    # Solo ejecutar si es menor a $2 para sesión automática
                    if buy_price <= 2.0:
                        print(f"🎯 Ejecutando automáticamente: {best_opp.get('item_title')}")
                        success = self.execute_trade_auto(best_opp)
                        if success:
                            trades_executed += 1
                            print(f"✅ Trade {trades_executed} completado")
                        else:
                            print(f"❌ Trade falló")
                    else:
                        print(f"⚠️ Oportunidad muy cara para auto-trade: ${buy_price:.2f}")
                
                # Esperar antes del próximo ciclo
                print("⏳ Esperando 60 segundos...")
                time.sleep(60)
                
            except KeyboardInterrupt:
                print("\n🛑 Sesión interrumpida por usuario")
                break
            except Exception as e:
                print(f"❌ Error en sesión automática: {e}")
                time.sleep(30)
        
        print(f"\n🏁 SESIÓN AUTOMÁTICA COMPLETADA")
        print(f"📊 Trades ejecutados: {trades_executed}")
        print(f"⏱️ Duración: {(datetime.now() - start_time).total_seconds()/60:.1f} minutos")
    
    def execute_trade_auto(self, opportunity: Dict[str, Any]) -> bool:
        """Ejecutar trade automáticamente sin confirmación."""
        try:
            result = self.real_trader.execute_real_buy(opportunity)
            return result.get('success', False)
        except:
            return False
    
    def run_menu(self):
        """Menú principal de la consola."""
        while True:
            print("\n" + "🔥" * 20)
            print("  TRADING REAL CS2 - CONSOLA")
            print("🔥" * 20)
            print("\n📋 OPCIONES DISPONIBLES:")
            print("1. 💰 Ver Balance y ROI")
            print("2. 📊 Ver KPIs Completos")
            print("3. 🔍 Escanear Oportunidades")
            print("4. 🚀 Ejecutar Trade Manual")
            print("5. 📦 Ver Portfolio")
            print("6. 🤖 Sesión Trading Automático")
            print("7. ❌ Salir")
            
            try:
                choice = input("\n🎯 Selecciona opción (1-7): ").strip()
                
                if choice == '1':
                    self.show_balance()
                
                elif choice == '2':
                    self.show_kpis()
                
                elif choice == '3':
                    max_items = input("📊 Máximo ítems a escanear (default 20): ").strip()
                    max_items = int(max_items) if max_items.isdigit() else 20
                    self.scan_opportunities(max_items)
                
                elif choice == '4':
                    opportunities = self.scan_opportunities(max_items=10)
                    if opportunities:
                        print("\n🎯 Selecciona oportunidad para ejecutar:")
                        for i, opp in enumerate(opportunities[:5], 1):
                            item_title = opp.get('item_title', 'N/A')
                            profit = opp.get('expected_profit_usd', 0)
                            print(f"{i}. {item_title} (${profit:.2f} profit)")
                        
                        try:
                            opp_choice = int(input("Número de oportunidad (1-5): ")) - 1
                            if 0 <= opp_choice < len(opportunities[:5]):
                                self.execute_trade(opportunities[opp_choice])
                            else:
                                print("❌ Opción inválida")
                        except ValueError:
                            print("❌ Número inválido")
                    else:
                        print("❌ No hay oportunidades disponibles")
                
                elif choice == '5':
                    self.portfolio_summary()
                
                elif choice == '6':
                    duration = input("⏱️ Duración en minutos (default 30): ").strip()
                    duration = int(duration) if duration.isdigit() else 30
                    self.auto_trading_session(duration)
                
                elif choice == '7':
                    print("👋 ¡Hasta luego! Happy trading!")
                    break
                
                else:
                    print("❌ Opción inválida")
                    
            except KeyboardInterrupt:
                print("\n👋 ¡Hasta luego!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def main():
    """Función principal."""
    try:
        console = TradingConsole()
        console.run_menu()
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 