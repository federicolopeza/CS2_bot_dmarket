#!/usr/bin/env python3
"""
🔥 INICIO RÁPIDO - CS2 TRADING BOT
==================================
Archivo de inicio simplificado para el sistema de trading por consola.
"""

import os
import sys

def main():
    """Función principal de inicio."""
    print("🔥 CS2 TRADING BOT - INICIO RÁPIDO")
    print("=" * 50)
    
    # Verificar archivo .env
    if not os.path.exists('.env'):
        print("❌ ERROR: Archivo .env no encontrado")
        print("\n📋 PASOS PARA CONFIGURAR:")
        print("1. Crear archivo .env en la raíz del proyecto")
        print("2. Agregar tus API keys de DMarket:")
        print("   DMARKET_PUBLIC_KEY=tu_public_key")
        print("   DMARKET_SECRET_KEY=tu_secret_key")
        print("   DMARKET_FEE_PERCENTAGE=0.05")
        print("   DMARKET_MIN_FEE_USD=0.01")
        print("\n3. Ejecutar nuevamente: python start_trading.py")
        return
    
    # Verificar dependencias
    try:
        import requests
        import pandas
        import numpy
        from dotenv import load_dotenv
        import sqlalchemy
        import nacl
    except ImportError as e:
        print(f"❌ ERROR: Dependencia faltante: {e}")
        print("\n📦 INSTALAR DEPENDENCIAS:")
        print("pip install -r requirements.txt")
        return
    
    print("✅ Configuración verificada")
    print("🚀 Iniciando sistema de trading...")
    print("\n" + "=" * 50)
    
    # Importar y ejecutar el sistema principal
    try:
        from trading_real_consola import main as trading_main
        trading_main()
    except Exception as e:
        print(f"❌ ERROR al iniciar: {e}")
        print("\n🔧 SOLUCIONES:")
        print("1. Verificar API keys en .env")
        print("2. Verificar conexión a internet")
        print("3. Verificar balance en DMarket")

if __name__ == "__main__":
    main() 