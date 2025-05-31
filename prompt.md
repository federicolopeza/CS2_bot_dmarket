Título del Proyecto: Sistema de Trading de Skins de CS2 con API de DMarket

Objetivo General del Proyecto:
Desarrollar un sistema en Python robusto y modular para interactuar con la API de DMarket. El objetivo es la identificación, y potencialmente ejecución y gestión, de estrategias de trading de skins de Counter-Strike 2 (CS2) exclusivamente dentro de la plataforma DMarket. El sistema se centrará en la automatización de tareas como la consulta de precios, la gestión de inventario (si los permisos de la API y la clave lo permiten), y la posible ejecución de órdenes de compra/venta en DMarket. Se explorará la viabilidad de estrategias como el flipping a corto plazo dentro de DMarket. La gestión eficiente del capital (ej. $1000 USD) y el análisis de riesgo serán considerados para las operaciones dentro de DMarket.

Funcionalidades Clave a Desarrollar (Enfocadas en DMarket):

Módulo de Interacción con API de DMarket (`dmarket_connector.py`):
*   Implementación de una comunicación segura y resiliente con la API de DMarket (HTTPS, validación de certificados).
*   Gestión avanzada de claves API: almacenamiento seguro (ej. variables de entorno).
*   Desarrollo de funciones encapsuladas para interactuar con los siguientes endpoints de DMarket (y otros relevantes para trading y análisis dentro de DMarket):
    *   `GET /exchange/v1/market/items`: Implementar filtros detallados (juego, precio, nombre, rareza, desgaste, float, paintseed, phase, etc.). Optimizar para paginación.
    *   `POST /exchange/v1/offers-buy`: Para crear órdenes de compra límite en DMarket.
    *   `POST /exchange/v1/offers-sell`: Para crear ofertas de venta en DMarket.
    *   `GET /account/v1/inventory`: Para obtener el inventario actual en DMarket.
    *   `GET /account/v1/balance`: Para consultar saldos.
    *   (Opcional) `GET /marketplace-api/v1/price-history/{gameId}/{marketHashName}`: Para análisis de precios históricos dentro de DMarket.
    *   (Opcional) `PATCH /exchange/v1/offers/{offerId}`: Para modificar órdenes activas en DMarket.
    *   (Opcional) Endpoints para gestión de "Targets" de DMarket.
*   Manejo sofisticado de límites de tasa de la API de DMarket.
*   Manejo de errores específicos de la API de DMarket.

Módulo de Procesamiento y Almacenamiento de Datos (`data_manager.py`) - (Opcional, Enfocado en DMarket):
*   Almacenamiento de datos históricos y actuales de DMarket (precios, transacciones propias).
    *   SQLite para simplicidad inicial.
*   Diseño de la estructura de la base de datos para datos de DMarket:
    *   `SkinsMaestraDMarket`: (Información estática de skins relevantes para DMarket).
    *   `PreciosHistoricosDMarket`: (Historial de precios de DMarket si se obtiene de la API o se registra).
    *   `InventarioDMarket`: (Items del usuario en DMarket según la API).
    *   `TransaccionesDMarket`: (Registro de compras/ventas hechas a través de la API en DMarket).

Módulo de Lógica de Estrategias de Trading (`strategy_engine.py`) - (Enfocado en DMarket):
*   Estrategia de Flipping a Corto Plazo (Intra-DMarket):
    *   Identificación de artículos subvaluados en DMarket basados en su historial de precios en DMarket.
    *   Consideración de atributos (float, pattern, stickers) si son obtenibles vía API y relevantes para el precio en DMarket.
    *   (Avanzado) Colocación automática de órdenes de compra/venta en DMarket.
*   Estrategia de Holding (Intra-DMarket):
    *   Identificación de skins con potencial de apreciación basándose en datos y tendencias de DMarket.
    *   Monitoreo de precios en DMarket y alertas para puntos de entrada/salida.

Módulo de Gestión de Riesgos y Capital (`risk_controller.py`) - (Aplicado a DMarket):
*   Implementación de reglas para el capital asignado a operaciones en DMarket:
    *   Tamaño de Posición dentro de DMarket.
    *   Límite de Posiciones Activas en DMarket.
*   Stop-Loss y Take-Profit para operaciones en DMarket.
*   Cálculo y seguimiento de KPIs para actividad en DMarket.

Módulo de Notificaciones y Alertas (`alerter.py`):
*   Envío de notificaciones (Email, Telegram) para eventos relacionados con DMarket:
    *   Oportunidades de flipping detectadas en DMarket.
    *   Confirmación de órdenes ejecutadas en DMarket.
    *   Errores de API de DMarket.
    *   Resúmenes de rendimiento de actividad en DMarket.

Documentación y Configuración:
*   `README.md` actualizado y enfocado en DMarket.
*   Comentarios detallados en el código.
*   Ejemplo de archivo de configuración para parámetros de DMarket.

Tecnologías Sugeridas:
*   Lenguaje: Python 3.9+.
*   Librerías Principales: `requests`, `SQLAlchemy` (opcional), `schedule`/`APScheduler` (opcional).
*   Control de Versiones: Git y GitHub.

Estructura del Repositorio Sugerida (Simplificada):
cs2_dmarket_bot/
├── main.py
├── config/
│   ├── config.ini.example
│   └── .env.example
├── core/
│   ├── dmarket_connector.py
│   ├── data_manager.py         # Opcional
│   ├── strategy_engine.py      # Opcional
│   └── risk_controller.py      # Opcional
│   └── alerter.py              # Opcional
├── utils/
│   ├── logger.py
│   └── helpers.py              # Opcional
├── database/                   # Opcional
│   └── cs2_dmarket_data.db     # Ejemplo SQLite
├── tests/
│   ├── unit/
│   └── integration/
├── .gitignore
├── requirements.txt
└── README.md

Consideraciones Adicionales Importantes:
*   Modularidad y Escalabilidad dentro del contexto de DMarket.
*   Manejo de Errores y Logging robusto.
*   Pruebas unitarias y de integración para la funcionalidad de DMarket.
*   Legalidad y Términos de Servicio (ToS) de DMarket.
*   Seguridad de claves API.
*   Simulación vs. Ejecución Real en DMarket.

Plan de Desarrollo por Fases (Adaptado a DMarket):
*   Fase 1: Conexión DMarket y Funcionalidad Básica.
    *   Configuración del entorno.
    *   `dmarket_connector.py` (autenticación, `GET /exchange/v1/market/items`, `GET /account/v1/balance`, manejo de errores).
    *   Logging (`utils/logger.py`).
    *   Script de prueba (`test_dmarket_fetch.py`).
    *   Pruebas unitarias para `dmarket_connector.py`.
*   Fase 2: Gestión Avanzada de DMarket y Estrategias Intra-DMarket.
    *   Implementar más endpoints de DMarket (órdenes, inventario, historial de precios si es viable).
    *   (Opcional) `data_manager.py` para registrar transacciones de DMarket.
    *   (Opcional) `strategy_engine.py` para flipping/holding en DMarket.
    *   (Opcional) `risk_controller.py` para DMarket.
    *   (Opcional) `alerter.py` para DMarket.
    *   Modo simulación para estrategias en DMarket.
*   Fase 3: (Opcional) UI, Optimización y Documentación Final.
    *   Dashboard para DMarket.
    *   Optimización y pruebas.
    *   Documentación final.

Este prompt adaptado debe guiar el desarrollo del proyecto enfocado exclusivamente en la API de DMarket.