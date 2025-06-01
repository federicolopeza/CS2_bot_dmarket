# 🎯 Guía de Inicio Rápido - Dashboard CS2 Trading

## 🚀 ¡Bienvenido! - Para Programadores Junior

Esta es una **guía super simple** para que puedas usar el sistema de trading CS2 de forma visual, sin necesidad de entender todo el código complejo que hay detrás.

---

## 📋 Paso 1: Preparación (Solo la primera vez)

### 1.1 Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 1.2 Configurar API Keys (Opcional)
Si tienes API keys de DMarket, crea un archivo `.env`:
```
DMARKET_PUBLIC_KEY=tu_public_key_aqui
DMARKET_SECRET_KEY=tu_secret_key_aqui
```

**🔴 IMPORTANTE**: Si no tienes API keys, ¡no te preocupes! El sistema funciona en **modo demo** con datos simulados.

---

## 🎮 Paso 2: Iniciar el Dashboard

### Opción A: Script Automático (Recomendado)
```bash
python run_dashboard.py
```

### Opción B: Manual
```bash
cd dashboard
streamlit run main_dashboard.py
```

---

## 🌐 Paso 3: Usar el Dashboard

### 3.1 Abrir en el Navegador
- El dashboard se abre automáticamente en: `http://localhost:8501`
- Si no se abre, copia esa URL en tu navegador

### 3.2 Pantalla Principal
Verás algo así:
```
🎯 Sistema de Trading CS2 - Dashboard
=====================================

🏠 Inicio | ⚙️ Configuración | 📊 Trading en Vivo | ...
```

---

## 🔧 Paso 4: Configuración Inicial

### 4.1 Inicializar el Sistema
1. Ve a la página **🏠 Inicio**
2. Haz clic en **🔧 Inicializar Sistema**
3. Espera a que aparezca: ✅ Sistema inicializado correctamente!

### 4.2 Configurar Parámetros
1. Ve a **⚙️ Configuración**
2. Ajusta los sliders según tu preferencia:
   - **Profit Mínimo**: 5% (para empezar)
   - **Descuento Requerido**: 15% (conservador)
   - **Monto Máximo por Trade**: $50 (seguro)

3. Haz clic en **💾 Guardar Configuración**

---

## 💰 Paso 5: Iniciar Paper Trading (Simulación)

### 5.1 Activar Trading
1. Ve a **📊 Trading en Vivo**
2. Haz clic en **▶️ Iniciar Trading**
3. ¡Ya está! El sistema empezará a buscar oportunidades

### 5.2 Buscar Oportunidades
1. Haz clic en **🔍 Buscar Oportunidades**
2. Verás una lista de posibles trades
3. Cada oportunidad muestra:
   - **Ítem**: Qué skin comprar/vender
   - **Profit**: Cuánto ganarías
   - **Confianza**: Qué tan seguro es

### 5.3 Ejecutar Trades
1. Encuentra una oportunidad que te guste
2. Haz clic en **💰 Ejecutar Trade**
3. ¡El trade se ejecuta automáticamente!

---

## 📊 Paso 6: Monitorear Resultados

### 6.1 Ver Métricas
Ve a **📋 Métricas & KPIs** para ver:
- 💰 **ROI Total**: Cuánto has ganado en %
- 🎯 **Win Rate**: % de trades exitosos
- 📈 **Gráficos**: Evolución de tu balance

### 6.2 Gestión de Riesgos
Ve a **🛡️ Gestión de Riesgos** para:
- Ver el nivel de riesgo actual
- Configurar límites de seguridad
- Revisar alertas importantes

---

## 🧪 Paso 7: Optimización (Avanzado)

### 7.1 Optimizar Parámetros
1. Ve a **🧪 Optimización**
2. Selecciona qué parámetros optimizar
3. Haz clic en **🚀 Iniciar Optimización**
4. Espera a que encuentre la mejor configuración

---

## 🚨 Consejos de Seguridad

### ⚠️ SIEMPRE COMIENZA CON PAPER TRADING
- **Paper Trading = Simulación** (no pierdes dinero real)
- **Live Trading = Dinero real** (solo cuando estés seguro)

### 🛡️ Límites Recomendados para Principiantes
- **Monto máximo por trade**: $10-50
- **Exposición del portfolio**: máximo 50%
- **Stop loss**: 10-15%

### 📈 Qué Buscar
- **ROI positivo** después de varios trades
- **Win rate** mayor al 60%
- **Profit factor** mayor a 1.5

---

## 🆘 Solución de Problemas

### Error: "Sistema No Inicializado"
- Ve a **🏠 Inicio** → **🔧 Inicializar Sistema**

### Error: "No hay oportunidades"
- Haz clic en **🔍 Buscar Oportunidades**
- Espera unos segundos y vuelve a intentar

### El dashboard no carga
```bash
# Reinstalar dependencias
pip install -r requirements.txt

# Verificar puerto
python run_dashboard.py
```

### Trading muy lento
- Reduce el número de ítems analizados
- Aumenta el monto mínimo de profit

---

## 📖 Explicación Simple de las Estrategias

### 1. **Basic Flip** 📈
- **Qué hace**: Compra barato, vende caro
- **Ejemplo**: Compra un AK-47 a $25, véndelo a $27
- **Riesgo**: Bajo
- **Tiempo**: Rápido (minutos a horas)

### 2. **Sniping** 🎯
- **Qué hace**: Encuentra ítems muy baratos
- **Ejemplo**: Compra un ítem 20% más barato que su precio normal
- **Riesgo**: Medio
- **Tiempo**: Medio (horas a días)

### 3. **Attribute Premium** 💎
- **Qué hace**: Busca ítems con características especiales
- **Ejemplo**: AK-47 con float 0.01 (muy bueno) vendido como normal
- **Riesgo**: Alto
- **Tiempo**: Lento (días a semanas)

### 4. **Trade Lock Arbitrage** 🔒
- **Qué hace**: Aprovecha descuentos por bloqueos
- **Ejemplo**: Ítems 15% más baratos porque no se pueden tradear por 7 días
- **Riesgo**: Bajo
- **Tiempo**: 7 días fijos

### 5. **Volatility Trading** 📊
- **Qué hace**: Usa análisis técnico como RSI, Bollinger Bands
- **Ejemplo**: Compra cuando RSI < 30 (sobreventa)
- **Riesgo**: Variable
- **Tiempo**: Variable

---

## 🎯 Tu Primer Test de Trading

### Test Recomendado para Principiantes:

1. **Configuración Inicial**:
   - Balance inicial: $1000 (simulado)
   - Profit mínimo: 5%
   - Máximo por trade: $50
   - Solo estrategias Basic Flip y Sniping

2. **Objetivo del Test**:
   - Ejecutar 10 trades
   - Lograr ROI positivo
   - Win rate > 60%

3. **Duración**:
   - 1-2 horas de paper trading

4. **Si el test es exitoso**:
   - Aumenta el monto por trade
   - Prueba más estrategias
   - Considera live trading (con dinero real)

---

## 📞 ¿Necesitas Ayuda?

### 📝 Documentación Técnica
- `Project_Progress.md` - Estado completo del proyecto
- `ESTADO_FINAL_PROYECTO.md` - Resumen ejecutivo
- `readme.md` - Guía técnica completa

### 🔍 Logs y Debugging
- Ve a **📝 Logs y Historial** en el dashboard
- Revisa la carpeta `logs/` para archivos de error

### 💡 Recuerda
- **Siempre empieza con Paper Trading**
- **El trading implica riesgo de pérdidas**
- **Solo invierte lo que puedas permitirte perder**
- **El sistema funciona mejor con configuración conservadora al inicio**

---

## 🎉 ¡Listo para Empezar!

Ahora tienes todo lo necesario para usar el sistema de trading CS2 de forma visual y segura. 

**¡Ve y ejecuta tu primer paper trading!** 🚀

---

*💡 Tip Final: Mantén esta guía abierta mientras usas el dashboard la primera vez.* 