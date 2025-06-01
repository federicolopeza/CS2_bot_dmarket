#!/usr/bin/env python3
"""
🎯 Lanzador del Dashboard CS2 Trading System
============================================

Script simple para iniciar el dashboard web del sistema de trading.
Perfecto para usuarios junior que quieren usar el sistema visualmente.

USO:
    python run_dashboard.py

REQUISITOS:
    - Python 3.9+
    - pip install -r requirements.txt
    - Archivo .env con las API keys (opcional para demo)
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def main():
    """Función principal para lanzar el dashboard."""
    
    print("🎯 Sistema de Trading CS2 - Lanzador del Dashboard")
    print("=" * 60)
    
    # Verificar Python
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 9):
        print("❌ Error: Se requiere Python 3.9 o superior")
        print(f"   Versión actual: {python_version.major}.{python_version.minor}")
        return 1
    
    print(f"✅ Python {python_version.major}.{python_version.minor} detectado")
    
    # Verificar directorio
    project_root = Path(__file__).parent
    dashboard_path = project_root / "dashboard" / "main_dashboard.py"
    
    if not dashboard_path.exists():
        print("❌ Error: No se encontró el archivo del dashboard")
        print(f"   Esperado en: {dashboard_path}")
        return 1
    
    print("✅ Archivos del dashboard encontrados")
    
    # Verificar dependencias
    print("\n🔍 Verificando dependencias...")
    try:
        import streamlit
        import plotly
        import pandas
        print("✅ Todas las dependencias están instaladas")
    except ImportError as e:
        print(f"❌ Error: Dependencia faltante: {e}")
        print("\n💡 Para instalar dependencias:")
        print("   pip install -r requirements.txt")
        return 1
    
    # Verificar archivo .env (opcional)
    env_path = project_root / ".env"
    if env_path.exists():
        print("✅ Archivo .env encontrado (API keys configuradas)")
    else:
        print("⚠️ Archivo .env no encontrado (modo demo activado)")
        print("💡 Para trading real, crea un archivo .env con:")
        print("   DMARKET_PUBLIC_KEY=tu_public_key")
        print("   DMARKET_SECRET_KEY=tu_secret_key")
    
    # Lanzar dashboard
    print("\n🚀 Iniciando dashboard...")
    print("🌐 El dashboard se abrirá en tu navegador en unos segundos...")
    print("\n" + "=" * 60)
    print("📖 INSTRUCCIONES DE USO:")
    print("1. El dashboard se abrirá en http://localhost:8501")
    print("2. Haz clic en '🔧 Inicializar Sistema' en la página de Inicio")
    print("3. Configura los parámetros en la página '⚙️ Configuración'")
    print("4. Inicia Paper Trading en '📊 Trading en Vivo'")
    print("5. Observa las métricas y resultados en tiempo real")
    print("\n💡 TIP: Comienza siempre con Paper Trading para probar sin riesgo")
    print("=" * 60)
    print("\n⏳ Iniciando... (Ctrl+C para detener)")
    
    try:
        # Cambiar al directorio del dashboard
        os.chdir(dashboard_path.parent)
        
        # Ejecutar streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            "main_dashboard.py",
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ]
        
        process = subprocess.run(cmd)
        return process.returncode
        
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard detenido por el usuario")
        print("✅ ¡Gracias por usar el Sistema de Trading CS2!")
        return 0
    except Exception as e:
        print(f"\n❌ Error al iniciar el dashboard: {e}")
        print("\n🔧 Posibles soluciones:")
        print("1. Verificar que streamlit esté instalado: pip install streamlit")
        print("2. Verificar permisos de archivos")
        print("3. Verificar que el puerto 8501 esté disponible")
        return 1

if __name__ == "__main__":
    exit_code = main()
    
    if exit_code != 0:
        print(f"\n❌ El programa terminó con código de error: {exit_code}")
        input("Presiona Enter para salir...")
    
    sys.exit(exit_code) 