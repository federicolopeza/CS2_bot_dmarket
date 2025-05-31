import logging
import logging.handlers
import sys
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "logs"
LOG_FILENAME = "cs2_trading_bot.log"

def setup_logger(
    log_name="CS2TradingBot",
    log_level=logging.INFO,
    log_to_console=True,
    log_to_file=True,
    max_bytes=10*1024*1024, # 10 MB
    backup_count=5
):
    """
    Configura y devuelve un logger.

    Args:
        log_name (str): Nombre del logger.
        log_level (int): Nivel de logging (ej. logging.INFO, logging.DEBUG).
        log_to_console (bool): Si es True, el log también se envía a la consola.
        log_to_file (bool): Si es True, el log también se envía a un archivo.
        max_bytes (int): Tamaño máximo del archivo de log antes de rotar.
        backup_count (int): Número de archivos de log de respaldo a mantener.

    Returns:
        logging.Logger: Instancia del logger configurado.
    """
    logger = logging.getLogger(log_name)
    logger.setLevel(log_level)

    # Evitar añadir múltiples handlers si el logger ya fue configurado
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(message)s"
    )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG) # Se podría ajustar si es necesario
        logger.addHandler(console_handler)

    if log_to_file:
        if not os.path.exists(LOG_DIR):
            try:
                os.makedirs(LOG_DIR)
            except OSError as e:
                # En caso de una condición de carrera donde otro proceso crea el directorio
                if e.errno != os.errno.EEXIST:
                    logger.error(f"Error al crear directorio de logs {LOG_DIR}: {e}", exc_info=True)
                    # Decide si quieres levantar el error o solo loguearlo y continuar sin file logging
                    # raise # Descomentar si quieres que falle la configuración del logger
                else:
                    pass # El directorio ya existe, lo cual está bien
        
        log_file_path = os.path.join(LOG_DIR, LOG_FILENAME)
        
        file_handler = TimedRotatingFileHandler(
            log_file_path,
            when="midnight",        # Rotar a medianoche
            interval=1,             # Cada día
            backupCount=7,          # Mantener 7 archivos de backup (ajustado de 5 a 7 como en el original)
            encoding='utf-8',
            delay=False
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG) # Se podría ajustar si es necesario
        logger.addHandler(file_handler)

    return logger

logger = setup_logger()

if __name__ == "__main__":
    # Ejemplo de cómo usar el logger
    logger.debug("Este es un mensaje de debug.")
    logger.info("Este es un mensaje de información.")
    logger.warning("Este es un mensaje de advertencia.")
    logger.error("Este es un mensaje de error.")
    logger.critical("Este es un mensaje crítico.")

    # Para probar la rotación de archivos, puedes descomentar y ejecutar esto varias veces:
    # for i in range(200000):
    #     logger.info(f"Línea de log de prueba número {i}")
    # print(f"Logs generados en {os.path.join(LOG_DIR, LOG_FILENAME)}") 