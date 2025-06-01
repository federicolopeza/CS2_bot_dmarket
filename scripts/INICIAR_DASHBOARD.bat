@echo off
echo.
echo ========================================
echo   🎯 CS2 Trading System Dashboard
echo ========================================
echo.
echo ⏳ Inicializando sistema...
echo.

:: Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python no está instalado o no está en el PATH
    echo.
    echo 💡 Por favor instala Python 3.9+ desde: https://python.org
    pause
    exit /b 1
)

:: Verificar si pip está disponible
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: pip no está disponible
    pause
    exit /b 1
)

:: Instalar dependencias si no están instaladas
echo 🔍 Verificando dependencias...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo 📦 Instalando dependencias por primera vez...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Error al instalar dependencias
        pause
        exit /b 1
    )
    echo ✅ Dependencias instaladas correctamente
) else (
    echo ✅ Dependencias ya están instaladas
)

echo.
echo 🚀 Iniciando dashboard...
echo.
echo 📖 INSTRUCCIONES:
echo 1. El dashboard se abrirá en tu navegador
echo 2. Si no se abre automáticamente, ve a: http://localhost:8501
echo 3. Haz clic en "🔧 Inicializar Sistema" para empezar
echo 4. Usa Paper Trading para probar sin riesgo
echo.
echo ⚠️  Para detener: Presiona Ctrl+C en esta ventana
echo.
echo ========================================
echo.

:: Ejecutar el dashboard
python run_dashboard.py

echo.
echo 👋 ¡Gracias por usar CS2 Trading System!
pause 