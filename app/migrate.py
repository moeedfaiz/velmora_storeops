import sqlite3, os
from .config import DB_PATH, ensure_dirs

def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def ensure_tables(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      email TEXT,
      phone TEXT,
      address TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
      sku TEXT PRIMARY KEY,
      name TEXT,
      price REAL NOT NULL DEFAULT 0,
      threshold INTEGER NOT NULL DEFAULT 0
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
      sku TEXT PRIMARY KEY REFERENCES products(sku) ON DELETE CASCADE,
      qty INTEGER NOT NULL DEFAULT 0
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      customer_id INTEGER REFERENCES customers(id),
      status TEXT NOT NULL DEFAULT 'Pending',
      total REAL NOT NULL DEFAULT 0,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
      sku TEXT NOT NULL REFERENCES products(sku),
      qty INTEGER NOT NULL,
      price REAL NOT NULL
    )""")

def migrate_columns(cur):
    if not col_exists(cur, "products", "price"):
        cur.execute("ALTER TABLE products ADD COLUMN price REAL NOT NULL DEFAULT 0")
    if not col_exists(cur, "products", "threshold"):
        cur.execute("ALTER TABLE products ADD COLUMN threshold INTEGER NOT NULL DEFAULT 0")

    if not col_exists(cur, "inventory", "qty"):
        cur.execute("ALTER TABLE inventory ADD COLUMN qty INTEGER NOT NULL DEFAULT 0")
        # best-effort backfill from legacy 'quantity'
        if col_exists(cur, "inventory", "quantity"):
            cur.execute("UPDATE inventory SET qty = quantity WHERE quantity IS NOT NULL")

    if not col_exists(cur, "orders", "total"):
        cur.execute("ALTER TABLE orders ADD COLUMN total REAL NOT NULL DEFAULT 0")

    if not col_exists(cur, "order_items", "price"):
        cur.execute("ALTER TABLE order_items ADD COLUMN price REAL NOT NULL DEFAULT 0")

def migrate():
    ensure_dirs()
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        ensure_tables(cur)
        migrate_columns(cur)
        con.commit()
        print("Migration OK.")
    finally:
        con.close()

if __name__ == "__main__":
    migrate()
