import pytest
from unittest.mock import patch, MagicMock
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Asegurarse de que los módulos del proyecto se puedan importar
import sys
# Añadir el directorio raíz del proyecto al sys.path
# Esto asume que tests/integration/test_populate_db.py está dos niveles por debajo de la raíz (cs2/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.data_manager import Base # get_db, init_db son parcheados
from populate_db import populate_dmarket_data, configure_logging as actual_configure_logging
# from utils.logger import LOG_DIR # No se usa activamente por ahora

# Configurar un logger para las pruebas si es necesario, o dejar que populate_db lo haga.
# Por ahora, dejaremos que populate_db configure su propio logging y lo capturemos si es necesario.

@pytest.fixture(scope="function")
def db_session():
    """Crea una sesión de base de datos SQLite en memoria para las pruebas."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal_test = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal_test()
    
    def get_db_override():
        try:
            yield session
        finally:
            session.close()
            
    def init_db_override():
        Base.metadata.create_all(engine)

    # Aplicar parches
    # Es importante parchear donde se busca el objeto, no donde está definido.
    # populate_db.py importa get_db e init_db directamente de core.data_manager.
    # Por lo tanto, necesitamos parchearlos en el namespace de populate_db.
    # Y también en core.data_manager si otras partes (no en este test directo) pudieran llamarlos.
    with patch('populate_db.get_db', new=get_db_override), \
         patch('populate_db.init_db', new=init_db_override), \
         patch('core.data_manager.get_db', new=get_db_override), \
         patch('core.data_manager.init_db', new=init_db_override):
        yield session
    
    # Limpieza después de la prueba si es necesario (aunque en memoria se pierde)
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def mock_dmarket_api():
    """Parchea DMarketAPI para simular respuestas de la API."""
    # Parchear en el módulo donde se instancia DMarketAPI, que es populate_db
    with patch('populate_db.DMarketAPI') as mock_api_class: # Cambiado de core.dmarket_connector a populate_db
        mock_instance = MagicMock()
        mock_api_class.return_value = mock_instance
        # Configurar un mock para get_market_items por defecto
        mock_instance.get_market_items.return_value = {"objects": [], "cursor": ""}
        yield mock_instance

@pytest.fixture(scope="function")
def mock_env_vars():
    """Parchea las variables de entorno para DMarket API keys."""
    with patch.dict(os.environ, {
        "DMARKET_PUBLIC_KEY": "test_public_key",
        "DMARKET_SECRET_KEY": "test_secret_key"
    }):
        # Parchear las globales dentro del módulo populate_db donde se usan
        with patch('populate_db.API_KEY', 'test_public_key'), \
             patch('populate_db.API_SECRET', 'test_secret_key'):
            yield

@pytest.fixture(autouse=True)
def configure_test_logging():
    """Asegura que el logging esté configurado para capturar la salida de populate_db."""
    # Llama a la función de configuración de logging real del módulo populate_db
    # para que los logs dentro de populate_dmarket_data() se emitan.
    # Podríamos querer redirigir esto o silenciarlo en el futuro si es muy verboso.
    actual_configure_logging(log_level='DEBUG', log_to_file=False, log_to_console=True) 
    # Opcional: si las pruebas crean archivos de log y queremos limpiarlos:
    # log_file_path = os.path.join(LOG_DIR, "cs2_trading_bot.log")
    # if os.path.exists(log_file_path):
    #     try: os.remove(log_file_path)
    #     except OSError: pass


# --- Casos de Prueba --- #

def test_populate_empty_response(db_session, mock_dmarket_api, mock_env_vars):
    """Prueba que el script maneja una respuesta vacía de la API sin errores y sin añadir datos."""
    from core.data_manager import SkinsMaestra, PreciosHistoricos # Importar aquí para acceso a db_session
    populate_dmarket_data() # Llamar a la función principal del script
    
    # Verificar que no se añadieron skins ni precios
    skins_count = db_session.query(SkinsMaestra).count()
    prices_count = db_session.query(PreciosHistoricos).count()
    
    assert skins_count == 0, "No deberían haberse añadido skins con una respuesta vacía."
    assert prices_count == 0, "No deberían haberse añadido precios con una respuesta vacía."
    mock_dmarket_api.get_market_items.assert_called_once() # Se debe llamar una vez

def test_populate_single_page_successful(db_session, mock_dmarket_api, mock_env_vars):
    """Prueba la población exitosa con una única página de datos de la API."""
    mock_item_1 = {
        "itemId": "item_123", "title": "AK-47 | Redline (Field-Tested)",
        "price": {"USD": "5500"}, "image": "url1.png",
        "extra": {"exterior": "Field-Tested", "itemType": "Rifle", "quality": "Mil-Spec Grade"}
    }
    mock_item_2 = {
        "itemId": "item_456", "title": "USP-S | Kill Confirmed (Minimal Wear)",
        "price": {"USD": "12000"}, "image": "url2.png",
        "extra": {"exterior": "Minimal Wear", "itemType": "Pistol", "quality": "Covert"}
    }
    
    mock_dmarket_api.get_market_items.return_value = {
        "objects": [mock_item_1, mock_item_2],
        "cursor": "" # Sin cursor, indica última página
    }
    
    populate_dmarket_data()
    
    from core.data_manager import SkinsMaestra, PreciosHistoricos
    
    # Verificar skins
    skins = db_session.query(SkinsMaestra).order_by(SkinsMaestra.name).all()
    assert len(skins) == 2
    
    assert skins[0].market_hash_name == "AK-47 | Redline (Field-Tested)"
    assert skins[0].name == "AK-47 | Redline (Field-Tested)" # Asumiendo normalización simple
    assert skins[0].image_url == "url1.png"
    assert skins[0].type == "Rifle"
    assert skins[0].exterior == "Field-Tested"
    assert skins[0].rarity == "Mil-Spec Grade"
    
    assert skins[1].market_hash_name == "USP-S | Kill Confirmed (Minimal Wear)"
    assert skins[1].name == "USP-S | Kill Confirmed (Minimal Wear)"
    assert skins[1].image_url == "url2.png"
    assert skins[1].type == "Pistol"
    assert skins[1].exterior == "Minimal Wear"
    assert skins[1].rarity == "Covert"
    
    # Verificar precios
    precios_skin1 = db_session.query(PreciosHistoricos).filter(PreciosHistoricos.skin_id == skins[0].id).all()
    assert len(precios_skin1) == 1
    assert precios_skin1[0].price == 55.00 # 5500 centavos / 100
    assert precios_skin1[0].currency == "USD"
    
    precios_skin2 = db_session.query(PreciosHistoricos).filter(PreciosHistoricos.skin_id == skins[1].id).all()
    assert len(precios_skin2) == 1
    assert precios_skin2[0].price == 120.00 # 12000 centavos / 100
    assert precios_skin2[0].currency == "USD"
    
    mock_dmarket_api.get_market_items.assert_called_once_with(
        game_id="a8db", currency="USD", cursor=None, limit=10 # Asumiendo limit por defecto en populate_db
    )

def test_populate_multiple_pages_successful(db_session, mock_dmarket_api, mock_env_vars):
    """Prueba la población exitosa con múltiples páginas de datos de la API."""
    mock_item_page1_1 = {
        "itemId": "p1_item1", "title": "AWP | Dragon Lore (Factory New)",
        "price": {"USD": "500000"}, "image": "url_dl.png",
        "extra": {"exterior": "Factory New", "itemType": "Sniper Rifle", "quality": "Covert"}
    }
    mock_item_page2_1 = {
        "itemId": "p2_item1", "title": "Karambit | Doppler (Ruby)",
        "price": {"USD": "120000"}, "image": "url_karambit.png",
        "extra": {"exterior": "Factory New", "itemType": "Knife", "quality": "Covert"}
    }

    # Configurar respuestas sucesivas para get_market_items
    mock_dmarket_api.get_market_items.side_effect = [
        {
            "objects": [mock_item_page1_1],
            "cursor": "next_page_cursor_123"
        },
        {
            "objects": [mock_item_page2_1],
            "cursor": "" # Sin cursor en la segunda respuesta, fin de paginación
        }
    ]
    
    populate_dmarket_data()
    
    from core.data_manager import SkinsMaestra, PreciosHistoricos
    
    # Verificar skins (deberían ser 2 en total de ambas páginas)
    skins_count = db_session.query(SkinsMaestra).count()
    assert skins_count == 2, "Deberían haberse añadido skins de ambas páginas."

    # Verificar que los datos específicos están allí (opcionalmente más detallado)
    skin_awp = db_session.query(SkinsMaestra).filter(SkinsMaestra.market_hash_name == "AWP | Dragon Lore (Factory New)").first()
    skin_karambit = db_session.query(SkinsMaestra).filter(SkinsMaestra.market_hash_name == "Karambit | Doppler (Ruby)").first()
    
    assert skin_awp is not None
    assert skin_karambit is not None
    
    # Verificar precios
    precio_awp = db_session.query(PreciosHistoricos).filter(PreciosHistoricos.skin_id == skin_awp.id).first()
    assert precio_awp.price == 5000.00
    
    precio_karambit = db_session.query(PreciosHistoricos).filter(PreciosHistoricos.skin_id == skin_karambit.id).first()
    assert precio_karambit.price == 1200.00
    
    # Verificar llamadas a la API
    assert mock_dmarket_api.get_market_items.call_count == 2
    mock_dmarket_api.get_market_items.assert_any_call(
        game_id="a8db", currency="USD", cursor=None, limit=10
    )
    mock_dmarket_api.get_market_items.assert_any_call(
        game_id="a8db", currency="USD", cursor="next_page_cursor_123", limit=10
    )

def test_populate_api_error_response(db_session, mock_dmarket_api, mock_env_vars, caplog):
    """Prueba cómo el script maneja una respuesta de error de la API."""
    mock_dmarket_api.get_market_items.return_value = {
        "error": "APIGenericError", 
        "message": "Simulated API error occurred"
    }
    
    populate_dmarket_data()
    
    from core.data_manager import SkinsMaestra, PreciosHistoricos
    skins_count = db_session.query(SkinsMaestra).count()
    prices_count = db_session.query(PreciosHistoricos).count()
    
    assert skins_count == 0, "No deberían haberse añadido skins si la API devuelve un error."
    assert prices_count == 0, "No deberían haberse añadido precios si la API devuelve un error."
    
    mock_dmarket_api.get_market_items.assert_called_once() # Se intenta una vez
    
    # Verificar que se logueó el error
    assert "Error al obtener ítems de DMarket: Simulated API error occurred" in caplog.text
    # O, para ser más específico con el nivel de log:
    # error_logged = any(
    #     record.levelname == 'ERROR' and 
    #     "Error al obtener ítems de DMarket: Simulated API error occurred" in record.message 
    #     for record in caplog.records
    # )
    # assert error_logged, "El error de la API debería haber sido logueado."

def test_populate_item_data_issues(db_session, mock_dmarket_api, mock_env_vars, caplog):
    """Prueba cómo el script maneja ítems con datos faltantes o malformados."""
    mock_item_valid = {
        "itemId": "valid_001", "title": "Glock-18 | Water Elemental",
        "price": {"USD": "850"}, "image": "glock_we.png",
        "extra": {"exterior": "Field-Tested", "itemType": "Pistol", "quality": "Restricted"}
    }
    mock_item_no_title = { 
        "itemId": "invalid_002",
        "price": {"USD": "1000"}, "image": "no_title.png",
        "extra": {"exterior": "Well-Worn", "itemType": "Rifle", "quality": "Mil-Spec"}
    }
    mock_item_no_usd_price = { 
        "itemId": "invalid_003", "title": "P250 | Sand Dune",
        "price": {"EUR": "50"}, 
        "image": "p250_sand_dune.png",
        "extra": {"exterior": "Battle-Scarred", "itemType": "Pistol", "quality": "Consumer Grade"}
    }
    mock_item_price_not_dict = { 
        "itemId": "invalid_004", "title": "MP9 | Hypnotic",
        "price": "unexpected_string_format", 
        "image": "mp9_hypnotic.png",
        "extra": {"exterior": "Minimal Wear", "itemType": "SMG", "quality": "Restricted"}
    }
    mock_item_price_value_not_convertible_to_float = { 
        "itemId": "invalid_006", "title": "MAC-10 | Neon Rider",
        "price": {"USD": "not_a_number"}, 
        "image": "mac10_neon.png",
        "extra": {"exterior": "Factory New", "itemType": "SMG", "quality": "Covert"}
    }

    mock_dmarket_api.get_market_items.return_value = {
        "objects": [
            mock_item_valid, 
            mock_item_no_title, 
            mock_item_no_usd_price,
            mock_item_price_not_dict,
            mock_item_price_value_not_convertible_to_float
        ],
        "cursor": ""
    }
    
    populate_dmarket_data()
    
    from core.data_manager import SkinsMaestra, PreciosHistoricos
    
    # Skins esperadas: mock_item_valid y mock_item_price_value_not_convertible_to_float
    skins = db_session.query(SkinsMaestra).order_by(SkinsMaestra.market_hash_name).all()
    assert len(skins) == 2, f"Se esperaban 2 skins, se obtuvieron {len(skins)}"
    
    # Verificar las skins guardadas
    assert skins[0].market_hash_name == "Glock-18 | Water Elemental"
    assert skins[1].market_hash_name == "MAC-10 | Neon Rider"

    # Solo el ítem válido debería tener un registro de precio.
    prices = db_session.query(PreciosHistoricos).all()
    assert len(prices) == 1, "Solo el precio del ítem válido debería haber sido añadido."
    
    # Verificar que el precio añadido corresponde a la skin válida
    if prices:
        assert prices[0].price == 8.50
        assert prices[0].skin_id == skins[0].id 
    else:
        pytest.fail("No se encontró el precio del ítem válido en la BD.")

    logs_text = caplog.text
    assert "Ítem omitido por falta de 'title': invalid_002" in logs_text
    assert "Precio USD no encontrado para P250 | Sand Dune. Datos de precio: {'EUR': '50'}" in logs_text
    assert "Precio USD no encontrado para MP9 | Hypnotic. Datos de precio: unexpected_string_format" in logs_text
    assert "Valor de precio no es un número válido para MAC-10 | Neon Rider: not_a_number" in logs_text

# Más pruebas se añadirán aquí... 