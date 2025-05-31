import logging
import logging.handlers
import sys
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "logs"
LOG_FILENAME = "cs2_trading_bot.log"

def configure_logging(
    log_level=logging.INFO,
    log_to_console=True,
    log_to_file=True,
    max_bytes=10*1024*1024, # 10 MB
    backup_count=5
):
    """
    Configura el logger raíz del proyecto. 
    Esta función debe llamarse una vez al inicio de la aplicación.
    """
    root_logger = logging.getLogger() # Obtener el logger RAÍZ
    root_logger.setLevel(log_level)

    # Limpiar handlers existentes del logger raíz para evitar duplicación si se llama varias veces
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if log_to_file:
        if not os.path.exists(LOG_DIR):
            try:
                os.makedirs(LOG_DIR)
            except OSError as e:
                if e.errno != os.errno.EEXIST:
                    print(f"CRITICAL: Error al crear directorio de logs {LOG_DIR}: {e}") 
                else:
                    pass 
        
        log_file_path = os.path.join(LOG_DIR, LOG_FILENAME)
        
        file_handler = TimedRotatingFileHandler(
            log_file_path,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding='utf-8',
            delay=False
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

if __name__ == "__main__":
    configure_logging(log_level=logging.DEBUG)
    
    # Logger específico del módulo actual (utils.logger)
    module_logger = logging.getLogger(__name__)
    module_logger.debug("Este es un mensaje de debug desde el logger del módulo (utils.logger).")
    
    # Logger para otra parte de la aplicación
    app_part_logger = logging.getLogger("my_app_feature")
    app_part_logger.info("Este es un mensaje de info desde my_app_feature.")
    app_part_logger.warning("Advertencia desde my_app_feature.")

    module_logger.info(f"Logs deberían estar en {os.path.join(LOG_DIR, LOG_FILENAME)}") 