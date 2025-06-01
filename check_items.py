#!/usr/bin/env python3
import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('cs2_trading.db')
cursor = conn.cursor()

# Revisar armas en la BD
cursor.execute("SELECT name FROM skins_maestra WHERE name LIKE '%AK-47%' OR name LIKE '%M4A4%' LIMIT 10")
weapons = cursor.fetchall()

print("🔫 Armas en la BD:")
for weapon in weapons:
    print(f"- {weapon[0]}")

# Revisar qué se está escaneando actualmente
cursor.execute("SELECT name FROM skins_maestra LIMIT 10")
all_items = cursor.fetchall()

print("\n📋 Primeros 10 ítems en la BD:")
for item in all_items:
    print(f"- {item[0]}")

# Contar tipos de ítems
cursor.execute("SELECT COUNT(*) FROM skins_maestra WHERE name LIKE '%Sticker%'")
sticker_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM skins_maestra WHERE name LIKE '%AK-47%' OR name LIKE '%M4A%' OR name LIKE '%AWP%'")
weapon_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM skins_maestra")
total_count = cursor.fetchone()[0]

print(f"\n📊 Estadísticas:")
print(f"- Total ítems: {total_count}")
print(f"- Stickers: {sticker_count}")  
print(f"- Armas principales: {weapon_count}")

conn.close() 