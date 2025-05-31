"""Módulo de utilidades y funciones de ayuda para el proyecto."""

import logging

logger = logging.getLogger(__name__) # Usar el logger del proyecto si está configurado, o uno básico

SUPPORTED_CURRENCIES = ["USD"] # Inicialmente solo soportamos USD directamente

def normalize_price_to_usd(price: float, currency: str) -> float | None:
    """Convierte un precio dado en una moneda específica a USD.
    
    Actualmente, solo soporta USD directamente. Para otras monedas,
    registrará una advertencia y devolverá None, indicando que la conversión no es posible aún.
    
    Args:
        price: El precio a convertir.
        currency: El código de la moneda del precio (ej. "USD", "EUR").
        
    Returns:
        El precio en USD, o None si la conversión no es soportada.
    """
    if currency.upper() == "USD":
        return price
    elif currency.upper() in SUPPORTED_CURRENCIES: # Placeholder para futuras monedas
        # Aquí iría la lógica de conversión si tuviéramos tasas de cambio
        logger.warning(f"La conversión de {currency.upper()} a USD aún no está implementada. Se requiere tasa de cambio.")
        return None # O podría devolver el precio original con una advertencia más fuerte
    else:
        logger.error(f"Moneda no soportada para conversión a USD: {currency.upper()}")
        return None

def normalize_skin_name(name: str) -> str:
    """Normaliza el nombre de una skin.
    
    Actualmente, solo elimina espacios en blanco al inicio y al final.
    Podría expandirse para manejar caracteres especiales, mayúsculas/minúsculas, etc.
    
    Args:
        name: El nombre de la skin a normalizar.
        
    Returns:
        El nombre de la skin normalizado.
    """
    if not isinstance(name, str):
        logger.warning(f"normalize_skin_name esperaba un string, pero recibió {type(name)}. Devolviendo como está.")
        return name
    return name.strip()

# Ejemplo de uso (se puede eliminar o mover a pruebas)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    print(f"Precio EUR (no soportado): {normalize_price_to_usd(100, 'EUR')}")
    print(f"Precio USD: {normalize_price_to_usd(50.25, 'USD')}")
    print(f"Precio usd (minúsculas): {normalize_price_to_usd(50.25, 'usd')}")
    print(f"Precio XYZ (desconocido): {normalize_price_to_usd(10, 'XYZ')}")
    
    print(f"Nombre skin: '{normalize_skin_name('  AK-47 | Redline  ')}'")
    print(f"Nombre skin (sin cambios): '{normalize_skin_name('USP-S | Kill Confirmed')}'")
    print(f"Nombre skin (no string): {normalize_skin_name(123)}") 