#!/usr/bin/env python3
"""
🔥 INICIADOR DE TRADING REAL CS2 🔥
==================================

Script para lanzar el sistema de trading CS2 con DMarket API REAL.
ELIMINADA toda simulación - solo trading real con dinero real.

ADVERTENCIA: Este sistema usa dinero REAL de tu cuenta DMarket.
"""

import os
import sys
import subprocess
import time

def setup_environment():
    """Configurar el entorno para trading real."""
    print("🔥 CONFIGURANDO ENTORNO PARA TRADING REAL")
    print("=" * 60)
    
    # Intentar cargar desde archivo .env si existe
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Archivo .env cargado")
    except ImportError:
        print("⚠️ python-dotenv no instalado, usando variables de entorno del sistema")
    except Exception as e:
        print(f"⚠️ No se pudo cargar .env: {e}")
    
    # Verificar que las claves API estén disponibles
    public_key = os.getenv("DMARKET_PUBLIC_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")
    
    if not public_key or not secret_key:
        print("❌ ERROR: Claves API de DMarket no encontradas!")
        print("💡 SOLUCIÓN:")
        print("   1. Crea un archivo .env en la raíz del proyecto")
        print("   2. Añade las siguientes líneas:")
        print("      DMARKET_PUBLIC_KEY=tu_clave_publica")
        print("      DMARKET_SECRET_KEY=tu_clave_secreta")
        print("   3. O define las variables de entorno en tu sistema")
        return False
    
    print("✅ Variables de entorno configuradas")
    print("🔑 API Keys de DMarket cargadas")
    print(f"🔓 Public Key: {public_key[:10]}...{public_key[-10:]}")
    return True

def verify_real_connection():
    """Verificar conexión real con DMarket API."""
    print("\n🔌 VERIFICANDO CONEXIÓN REAL CON DMARKET")
    print("-" * 50)
    
    try:
        sys.path.insert(0, '.')
        from core.dmarket_connector import DMarketAPI
        
        # Probar conexión real
        api = DMarketAPI()
        balance_response = api.get_account_balance()
        
        if "error" in balance_response:
            print(f"❌ Error conectando con DMarket: {balance_response}")
            return False, 0.0
        
        # Extraer balance real
        if "usd" in balance_response:
            usd_cents = balance_response.get("usd", "0")
            balance_usd = float(usd_cents) / 100.0
        elif "balance" in balance_response:
            usd_cents = balance_response.get("balance", {}).get("USD", "0")
            balance_usd = float(usd_cents) / 100.0
        else:
            balance_usd = 0.0
        
        print(f"✅ Conexión exitosa con DMarket")
        print(f"💰 Balance real disponible: ${balance_usd:.2f} USD")
        
        if balance_usd < 1.0:
            print("⚠️ ADVERTENCIA: Balance muy bajo para trading")
            print("💡 Recomendación: Deposita más fondos en tu cuenta DMarket")
        
        return True, balance_usd
        
    except Exception as e:
        print(f"❌ Error verificando conexión: {e}")
        return False, 0.0

def initialize_database():
    """Inicializar base de datos para trading real."""
    print("\n🗄️ INICIALIZANDO BASE DE DATOS REAL")
    print("-" * 50)
    
    try:
        from core.data_manager import init_db
        init_db()
        print("✅ Base de datos inicializada correctamente")
        print("📊 Tablas creadas: real_transactions, real_portfolio")
        return True
    except Exception as e:
        print(f"❌ Error inicializando BD: {e}")
        return False

def test_real_trader():
    """Probar el RealTrader."""
    print("\n🔥 PROBANDO REALTRADER")
    print("-" * 50)
    
    try:
        from core.dmarket_connector import DMarketAPI
        from core.real_trader import RealTrader
        
        api = DMarketAPI()
        real_trader = RealTrader(api)
        
        balance_info = real_trader.get_real_balance()
        
        print(f"✅ RealTrader inicializado correctamente")
        print(f"💰 Cash balance: ${balance_info['cash_balance']:.2f}")
        print(f"📦 Portfolio value: ${balance_info['portfolio_value']:.2f}")
        print(f"💯 Total balance: ${balance_info['total_balance']:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ Error probando RealTrader: {e}")
        return False

def launch_real_dashboard():
    """Lanzar el dashboard para trading real."""
    print("\n🚀 LANZANDO DASHBOARD DE TRADING REAL")
    print("=" * 60)
    
    try:
        print("🌐 Iniciando servidor Streamlit...")
        print("📍 URL: http://localhost:8501")
        print("\n⚠️ RECORDATORIOS IMPORTANTES:")
        print("   🔥 Este es TRADING REAL - usa dinero REAL")
        print("   💰 Cada trade gastará dinero de tu cuenta DMarket")
        print("   📊 Balance actual sincronizado en tiempo real")
        print("   🛡️ Empieza con trades pequeños")
        print("   🔍 Revisa cada oportunidad antes de ejecutar")
        
        print("\n🎯 PASOS PARA EMPEZAR:")
        print("1. El dashboard se abrirá en tu navegador")
        print("2. Ve a '🔥 Inicio REAL' y haz clic en 'Inicializar Sistema'")
        print("3. Configura parámetros en '⚙️ Configuración'")
        print("4. ¡Inicia trading REAL en '💰 Trading en Vivo REAL'!")
        
        print("\n" + "=" * 60)
        print("⏳ Iniciando dashboard... (Ctrl+C para detener)")
        
        # Lanzar dashboard
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "dashboard/main_dashboard.py",
            "--server.address", "localhost",
            "--server.port", "8501",
            "--server.headless", "true",
            "--server.enableCORS", "false"
        ], check=True)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Dashboard detenido por el usuario")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error lanzando dashboard: {e}")
        print("💡 Intenta: pip install streamlit")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")

def main():
    """Función principal."""
    print("🔥" * 30)
    print("  SISTEMA DE TRADING CS2 REAL")
    print("    CON DMARKET API REAL")
    print("🔥" * 30)
    print()
    
    # 1. Configurar entorno
    env_ok = setup_environment()
    if not env_ok:
        print("\n❌ No se puede continuar sin claves API")
        print("💡 Configura las variables de entorno y vuelve a intentar")
        return
    
    # 2. Verificar conexión real
    connection_ok, balance = verify_real_connection()
    if not connection_ok:
        print("\n❌ No se puede continuar sin conexión a DMarket")
        return
    
    # 3. Inicializar BD
    db_ok = initialize_database()
    if not db_ok:
        print("\n❌ No se puede continuar sin base de datos")
        return
    
    # 4. Probar RealTrader
    trader_ok = test_real_trader()
    if not trader_ok:
        print("\n❌ No se puede continuar sin RealTrader")
        return
    
    print("\n🎉 ¡TODOS LOS SISTEMAS LISTOS PARA TRADING REAL!")
    print(f"💰 Balance disponible: ${balance:.2f} USD")
    
    # 5. Lanzar dashboard
    input("\n👆 Presiona ENTER para lanzar el dashboard de trading real...")
    launch_real_dashboard()

if __name__ == "__main__":
    main() 