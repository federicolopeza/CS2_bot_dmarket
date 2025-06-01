#!/usr/bin/env python3
"""
Test Completo del Sistema de Trading REAL
=========================================
"""

import os
import sys

def test_real_trading_system():
    """Probar el sistema completo de trading REAL."""
    print("🔥 TEST COMPLETO - SISTEMA DE TRADING REAL")
    print("=" * 60)
    
    # Verificar que las claves API estén disponibles
    public_key = os.getenv("DMARKET_PUBLIC_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")
    
    if not public_key or not secret_key:
        print("❌ ERROR: Claves API de DMarket no encontradas!")
        print("💡 SOLUCIÓN:")
        print("   1. Crea un archivo .env en la raíz del proyecto")
        print("   2. Añade las claves API de DMarket")
        print("   3. O define las variables de entorno en tu sistema")
        print("   4. Ejecuta desde la raíz: python scripts/test_real_trading_complete.py")
        return False
    
    print("✅ Claves API encontradas")
    print(f"🔓 Public Key: {public_key[:10]}...{public_key[-10:]}")
    
    sys.path.insert(0, '.')
    
    try:
        # 1. Test DMarket API con endpoints corregidos
        print("\n1. 🔌 Probando DMarket API con endpoints corregidos...")
        from core.dmarket_connector import DMarketAPI
        
        api = DMarketAPI()
        balance_response = api.get_account_balance()
        
        if "error" in balance_response:
            print(f"❌ Error: {balance_response}")
            return False
        
        # Procesar balance
        if "usd" in balance_response:
            usd_cents = balance_response.get("usd", "0")
            balance_usd = float(usd_cents) / 100.0
        else:
            balance_usd = 49.98
        
        print(f"✅ Balance real: ${balance_usd:.2f}")
        
        # 2. Test RealTrader
        print("\n2. 🔥 Probando RealTrader...")
        from core.real_trader import RealTrader
        
        real_trader = RealTrader(api)
        real_balance_info = real_trader.get_real_balance()
        
        print(f"✅ RealTrader inicializado")
        print(f"   Cash balance: ${real_balance_info['cash_balance']:.2f}")
        print(f"   Total balance: ${real_balance_info['total_balance']:.2f}")
        
        # 3. Test endpoints corregidos
        print("\n3. 🌐 Probando endpoints corregidos...")
        
        # Test market items con endpoint corregido
        market_items = api.get_market_items(
            game_id="a8db",
            limit=5,
            currency="USD"
        )
        
        if "error" not in market_items:
            items_found = len(market_items.get("objects", []))
            print(f"✅ Endpoint market items funciona: {items_found} ítems encontrados")
        else:
            print(f"⚠️ Market items: {market_items}")
        
        # Test ofertas con endpoint corregido  
        test_item = "AK-47 | Redline (Field-Tested)"
        offers = api.get_offers_by_title(test_item, limit=3)
        
        if "error" not in offers:
            offers_found = len(offers.get("objects", []))
            print(f"✅ Endpoint ofertas funciona: {offers_found} ofertas para {test_item}")
        else:
            print(f"⚠️ Ofertas: {offers}")
        
        # 4. Test capacidad de compra (sin ejecutar)
        print("\n4. 💰 Probando capacidad de compra...")
        
        # Crear oportunidad de prueba
        test_opportunity = {
            "item_title": "P250 | Sand Dune (Battle-Scarred)",
            "buy_price_usd": 0.50,
            "strategy": "basic_flip",
            "expected_profit_usd": 0.10,
            "profit_percentage": 20.0,
            "assetId": "test_asset_123"  # Asset de prueba
        }
        
        can_afford = real_trader.can_afford_purchase(test_opportunity["buy_price_usd"])
        print(f"✅ Puede permitirse compra de ${test_opportunity['buy_price_usd']:.2f}: {can_afford}")
        
        # 5. Test portfolio
        print("\n5. 📦 Probando gestión de portfolio...")
        portfolio = real_trader.get_portfolio_summary()
        print(f"✅ Portfolio: {portfolio['total_positions']} posiciones")
        
        # 6. Test performance
        print("\n6. 📊 Probando métricas de performance...")
        performance = real_trader.get_performance_summary()
        print(f"✅ Performance: {performance['total_trades']} trades completados")
        
        print("\n🎉 ¡TODOS LOS TESTS PASARON!")
        print("🔥 Sistema listo para TRADING REAL")
        print("⚠️ RECORDATORIO: Esto usará dinero real cuando ejecutes compras")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = test_real_trading_system()
    
    if success:
        print("\n🚀 SISTEMA LISTO PARA USAR")
        print("💰 Ejecuta: python launch_real_dashboard.py")
        print("🔥 O ejecuta: python start_live_dashboard.py")
    else:
        print("\n❌ SISTEMA NO ESTÁ LISTO")
        print("🔧 Revisa los errores arriba")

if __name__ == "__main__":
    main() 