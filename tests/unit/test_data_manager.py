import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

import core.data_manager # Importar el módulo para parchear
from core.data_manager import Base, init_db, SkinsMaestra, PreciosHistoricos, add_or_update_skin, add_price_record, get_db, get_skin_by_market_hash_name, get_skin_by_id, get_latest_price_for_skin, get_price_history_for_skin

DATABASE_URL_TEST = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_engine_fixture():
    """Fixture para crear un engine de BD en memoria para pruebas."""
    engine = create_engine(DATABASE_URL_TEST)
    Base.metadata.create_all(engine) # Crear tablas
    yield engine
    Base.metadata.drop_all(engine) # Limpiar tablas

@pytest.fixture(scope="function")
def db_session_fixture(test_engine_fixture):
    """Fixture para crear una sesión de BD para pruebas, usando test_engine_fixture."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine_fixture)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def mock_data_manager_globals(test_engine_fixture):
    """ Parchea el engine y SessionLocal globales en core.data_manager.
        Usa el mismo engine que db_session_fixture para consistencia si se usa get_db.
    """
    TestSessionLocalForPatch = sessionmaker(autocommit=False, autoflush=False, bind=test_engine_fixture)
    
    # Aplicar los parches de forma anidada para mayor claridad y posible compatibilidad con el linter
    with patch.object(core.data_manager, 'engine', test_engine_fixture) as mock_engine:
        with patch.object(core.data_manager, 'SessionLocal', TestSessionLocalForPatch) as mock_session_local:
            yield # Permite que la prueba se ejecute con los globales parcheados


def test_init_db(mock_data_manager_globals):
    """Prueba que init_db crea las tablas correctamente usando el engine parcheado."""
    # init_db usará el core.data_manager.engine parcheado
    engine_under_test = core.data_manager.engine
    inspector = inspect(engine_under_test)

    # Asegurarse de que las tablas estén limpias antes de la prueba específica de init_db
    # Aunque el fixture del engine limpia al final, queremos un estado conocido al inicio de esta prueba.
    Base.metadata.drop_all(bind=engine_under_test)
    inspector = inspect(engine_under_test) # Re-inspeccionar
    assert not inspector.has_table(SkinsMaestra.__tablename__), "Tabla SkinsMaestra no debería existir antes de init_db"
    assert not inspector.has_table(PreciosHistoricos.__tablename__), "Tabla PreciosHistoricos no debería existir antes de init_db"

    init_db() # Llamar a la función

    inspector = inspect(engine_under_test) # Re-inspeccionar
    assert inspector.has_table(SkinsMaestra.__tablename__), "Tabla SkinsMaestra debería existir después de init_db"
    assert inspector.has_table(PreciosHistoricos.__tablename__), "Tabla PreciosHistoricos debería existir después de init_db"

    # Probar idempotencia
    try:
        init_db()
    except Exception as e:
        pytest.fail(f"init_db no es idempotente. Falló con: {e}")

# --- Pruebas para add_or_update_skin --- 

def test_add_new_skin(db_session_fixture, mock_data_manager_globals):
    """Prueba añadir una skin completamente nueva."""
    skin_data = {
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "name": "AK-47 | Redline",
        "type": "Rifle",
        "exterior": "Field-Tested",
        "rarity": "Classified",
        "image_url": "http://example.com/ak_redline.png"
    }
    
    db = db_session_fixture
    added_skin = add_or_update_skin(db, skin_data)
    
    assert added_skin is not None
    assert added_skin.id is not None
    assert added_skin.market_hash_name == skin_data["market_hash_name"]
    assert added_skin.name == skin_data["name"]
    assert added_skin.type == skin_data["type"]
    assert added_skin.exterior == skin_data["exterior"]
    assert added_skin.rarity == skin_data["rarity"]
    assert added_skin.image_url == skin_data["image_url"]
    assert added_skin.game_id == "a8db" # Default

    # Verificar que se guardó en la BD
    retrieved_skin = db.query(SkinsMaestra).filter(SkinsMaestra.market_hash_name == skin_data["market_hash_name"]).first()
    assert retrieved_skin is not None
    assert retrieved_skin.name == skin_data["name"]

def test_update_existing_skin(db_session_fixture, mock_data_manager_globals):
    """Prueba actualizar una skin existente."""
    db = db_session_fixture
    initial_skin_data = {
        "market_hash_name": "USP-S | Kill Confirmed (Minimal Wear)",
        "name": "USP-S | Kill Confirmed",
        "type": "Pistol",
        "exterior": "Minimal Wear",
        "rarity": "Covert"
    }
    # Añadir la skin inicial
    add_or_update_skin(db, initial_skin_data)

    updated_skin_data = {
        "market_hash_name": "USP-S | Kill Confirmed (Minimal Wear)", # Mismo market_hash_name
        "name": "USP-S | KC Updated", # Nombre cambiado
        "image_url": "http://example.com/usps_kc_updated.png" # Nueva URL de imagen
    }
    
    updated_skin = add_or_update_skin(db, updated_skin_data)
    
    assert updated_skin is not None
    assert updated_skin.name == updated_skin_data["name"]
    assert updated_skin.image_url == updated_skin_data["image_url"]
    # Campos no actualizados deben permanecer igual
    assert updated_skin.type == initial_skin_data["type"]
    assert updated_skin.exterior == initial_skin_data["exterior"]
    assert updated_skin.rarity == initial_skin_data["rarity"]

def test_add_or_update_skin_requires_market_hash_name(db_session_fixture, mock_data_manager_globals):
    """Prueba que add_or_update_skin levanta ValueError si falta market_hash_name."""
    db = db_session_fixture
    with pytest.raises(ValueError, match="market_hash_name es requerido"):
        add_or_update_skin(db, {"name": "Skin sin market_hash_name"})

# --- Pruebas para add_price_record --- 

def test_add_price_record_new(db_session_fixture, mock_data_manager_globals):
    """Prueba añadir un registro de precio para una skin."""
    db = db_session_fixture
    # Primero crear una skin
    skin = add_or_update_skin(db, {"market_hash_name": "Glock-18 | Water Elemental (Minimal Wear)", "name": "Glock-18 | Water Elemental"})
    
    price_data = {
        "price": 10.50,
        "currency": "EUR",
        "volume": 100
    }
    
    price_record = add_price_record(db, skin.id, price_data)
    
    assert price_record is not None
    assert price_record.id is not None
    assert price_record.skin_id == skin.id
    assert price_record.price == price_data["price"]
    assert price_record.currency == price_data["currency"]
    assert price_record.volume == price_data["volume"]
    assert price_record.fuente_api == "DMarket" # Default
    assert price_record.timestamp is not None

    # Verificar en BD
    retrieved_price = db.query(PreciosHistoricos).filter(PreciosHistoricos.id == price_record.id).first()
    assert retrieved_price is not None
    assert retrieved_price.price == price_data["price"]

def test_add_price_record_requires_price(db_session_fixture, mock_data_manager_globals):
    """Prueba que add_price_record levanta ValueError si falta el precio."""
    db = db_session_fixture
    skin = add_or_update_skin(db, {"market_hash_name": "P250 | Sand Dune (Factory New)"})
    
    with pytest.raises(ValueError, match="El campo 'price' es requerido"):
        add_price_record(db, skin.id, {"currency": "USD"})

def test_get_db(mock_data_manager_globals):
    """Prueba la función get_db para obtener una sesión."""
    # mock_data_manager_globals asegura que SessionLocal en core.data_manager está parcheado
    try:
        db_gen = get_db()
        db = next(db_gen)
        assert db is not None
        # Intentar una operación simple
        assert db.query(SkinsMaestra).count() >= 0 
    except Exception as e:
        pytest.fail(f"get_db falló al obtener una sesión o la sesión no es válida: {e}")
    finally:
        if 'db' in locals() and db:
            # Cerrar la sesión explícitamente si se abrió
            # Aunque el generador lo haría, es bueno ser explícito en la prueba
            try:
                next(db_gen) # Para ejecutar el finally del generador
            except StopIteration:
                pass # Esperado
            except Exception as e:
                pytest.fail(f"Error al cerrar la sesión de get_db: {e}")

# --- Pruebas para Funciones de Consulta ---

def test_get_skin_by_market_hash_name(db_session_fixture, mock_data_manager_globals):
    """Prueba obtener una skin por su market_hash_name."""
    db = db_session_fixture
    skin_data = {"market_hash_name": "AWP | Dragon Lore (Factory New)", "name": "AWP | Dragon Lore"}
    add_or_update_skin(db, skin_data) # Añadir skin de prueba
    
    # Probar obtenerla
    retrieved_skin = get_skin_by_market_hash_name(db, skin_data["market_hash_name"])
    assert retrieved_skin is not None
    assert retrieved_skin.name == skin_data["name"]
    
    # Probar con un nombre que no existe
    non_existent_skin = get_skin_by_market_hash_name(db, "Skin que no existe")
    assert non_existent_skin is None

def test_get_skin_by_id(db_session_fixture, mock_data_manager_globals):
    """Prueba obtener una skin por su ID."""
    db = db_session_fixture
    skin_data = {"market_hash_name": "M4A4 | Howl (Factory New)", "name": "M4A4 | Howl"}
    added_skin = add_or_update_skin(db, skin_data)
    
    retrieved_skin = get_skin_by_id(db, added_skin.id)
    assert retrieved_skin is not None
    assert retrieved_skin.market_hash_name == skin_data["market_hash_name"]
    
    # Probar con un ID que no existe
    non_existent_skin = get_skin_by_id(db, 99999)
    assert non_existent_skin is None

def test_get_latest_price_for_skin(db_session_fixture, mock_data_manager_globals):
    """Prueba obtener el último precio de una skin."""
    db = db_session_fixture
    skin = add_or_update_skin(db, {"market_hash_name": "Karambit | Fade (Factory New)"})
    
    # Añadir algunos precios con timestamps diferentes (usando datetime directamente)
    # Recordar que PreciosHistoricos usa default=lambda: datetime.datetime.now(timezone.utc)
    # Para la prueba, podemos establecerlos explícitamente para controlar el orden.
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    price1_data = {"price": 2000.00, "timestamp": now - timedelta(hours=2)}
    price2_data = {"price": 2050.00, "timestamp": now - timedelta(hours=1)} # Más reciente
    price3_data = {"price": 1900.00, "timestamp": now - timedelta(hours=3)}

    # Añadimos registros de precio directamente sin usar add_price_record para controlar el timestamp
    db.add(PreciosHistoricos(skin_id=skin.id, price=price1_data["price"], timestamp=price1_data["timestamp"]))    
    db.add(PreciosHistoricos(skin_id=skin.id, price=price2_data["price"], timestamp=price2_data["timestamp"]))    
    db.add(PreciosHistoricos(skin_id=skin.id, price=price3_data["price"], timestamp=price3_data["timestamp"]))    
    db.commit()
    
    latest_price = get_latest_price_for_skin(db, skin.id)
    assert latest_price is not None
    assert latest_price.price == price2_data["price"]
    
    # Probar con una skin sin precios
    skin_no_prices = add_or_update_skin(db, {"market_hash_name": "Nova | Sin Precios"})
    assert get_latest_price_for_skin(db, skin_no_prices.id) is None

def test_get_price_history_for_skin(db_session_fixture, mock_data_manager_globals):
    """Prueba obtener el historial de precios de una skin."""
    db = db_session_fixture
    skin = add_or_update_skin(db, {"market_hash_name": "Bayonet | Doppler (Factory New)"})
    
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    prices_to_add = [
        {"price": 800, "timestamp": now - timedelta(minutes=30)}, # Más reciente
        {"price": 790, "timestamp": now - timedelta(minutes=60)},
        {"price": 810, "timestamp": now - timedelta(minutes=10)}  # Aún más reciente
    ]
    
    for p_data in prices_to_add:
        db.add(PreciosHistoricos(skin_id=skin.id, price=p_data["price"], timestamp=p_data["timestamp"]))    
    db.commit()
    
    # Probar con límite default (100)
    history = get_price_history_for_skin(db, skin.id)
    assert len(history) == 3
    assert history[0].price == 810 # El más reciente primero
    assert history[1].price == 800
    assert history[2].price == 790
    
    # Probar con límite
    limited_history = get_price_history_for_skin(db, skin.id, limit=2)
    assert len(limited_history) == 2
    assert limited_history[0].price == 810
    assert limited_history[1].price == 800
    
    # Probar con una skin sin precios
    skin_no_prices = add_or_update_skin(db, {"market_hash_name": "UMP-45 | Sin Historial"})
    assert len(get_price_history_for_skin(db, skin_no_prices.id)) == 0 