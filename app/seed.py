# /app/seed.py
import os, sqlite3, datetime as dt, os.path

DB_PATH  = os.environ.get("DB_PATH", "/data/velmora.db")
SOPS_DIR = os.environ.get("SOPS_DIR", "/app/data/sops")  # Copilot docs dir (markdown/txt)
now = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# ---------------------------
# Helpers: safe, idempotent
# ---------------------------
def column_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def add_column_if_missing(cur, table, col, col_def_sql):
    if not column_exists(cur, table, col):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def_sql}")

def upsert(cur, sql, params):
    cur.execute(sql, params)

# ---------------------------
# Ensure core tables exist
# ---------------------------
BASE_SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS customers(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  address TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products(
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  price REAL NOT NULL DEFAULT 0,
  threshold INTEGER NOT NULL DEFAULT 5,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory(
  sku TEXT PRIMARY KEY REFERENCES products(sku) ON DELETE CASCADE,
  qty INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending',
  total REAL NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items(
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  sku TEXT NOT NULL REFERENCES products(sku) ON DELETE RESTRICT,
  qty INTEGER NOT NULL,
  price REAL NOT NULL,
  PRIMARY KEY(order_id, sku)
);
"""

# Optional: Copilot knowledge docs table
KNOWLEDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_docs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  body  TEXT NOT NULL,
  path  TEXT NOT NULL UNIQUE,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# --------------------------
# Clothing catalog (variants)
# --------------------------
products = [
  # Men T-Shirts & Polos
  ("MEN-TSH-CLS-BLK-M",   "Men Classic Tee Black M",          1999, 5),
  ("MEN-TSH-CLS-WHT-L",   "Men Classic Tee White L",          1999, 5),
  ("MEN-TSH-CLS-NVY-XL",  "Men Classic Tee Navy XL",          1999, 5),
  ("MEN-POLO-STR-NVY-L",  "Men Striped Polo Navy L",          2799, 5),

  # Men Hoodies / Winter
  ("MEN-HDY-LOGO-BLK-L",  "Men Logo Hoodie Black L",          4499, 4),
  ("MEN-HDY-LOGO-GRY-M",  "Men Logo Hoodie Grey M",           4499, 4),

  # Men Bottoms
  ("MEN-JNS-SLIM-32",     "Men Slim Jeans W32",               4999, 4),
  ("MEN-JNS-SLIM-34",     "Men Slim Jeans W34",               4999, 4),
  ("MEN-CHN-OLV-32",      "Men Chinos Olive W32",             3899, 4),

  # Ethnic (PK)
  ("MEN-SHALKAM-COTN-L",  "Men Shalwar Kameez Cotton L",      5999, 3),
  ("WOM-ABAYA-BLK-M",     "Women Abaya Black M",              8999, 2),
  ("WOM-DUP-ORG-ONE",     "Women Dupatta Organza (One Size)", 1499, 5),

  # Women Dresses / Kurtas
  ("WOM-DRS-FLR-S",       "Women Floral Dress S",             6999, 4),
  ("WOM-DRS-FLR-M",       "Women Floral Dress M",             6999, 4),
  ("WOM-KUR-COT-RED-M",   "Women Cotton Kurta Red M",         3499, 4),
  ("WOM-KUR-COT-TEAL-L",  "Women Cotton Kurta Teal L",        3499, 4),

  # Kids
  ("KID-TSH-STAR-RED-8",  "Kids Star Tee Red (Age 8)",        1499, 5),
  ("KID-TSH-STAR-BLU-10", "Kids Star Tee Blue (Age 10)",      1499, 5),

  # Footwear
  ("FOOT-SNK-WHT-42",     "Sneakers White EU42",              6499, 2),
  ("FOOT-SNK-WHT-43",     "Sneakers White EU43",              6499, 2),
  ("FOOT-SND-BRN-41",     "Sandals Brown EU41",               3499, 2),

  # Accessories
  ("ACC-BLT-LEA-34",      "Leather Belt 34",                   1799, 3),
  ("ACC-BLT-LEA-36",      "Leather Belt 36",                   1799, 3),
  ("ACC-WAL-LEA-BRN",     "Leather Wallet Brown",              1999, 3),
  ("ACC-CAP-BLK",         "Baseball Cap Black",                 999, 3),
  ("BAG-TOTE-CAN-NTL",    "Tote Bag Canvas Natural",           1299, 2),
]

start_stock = {
  "MEN-TSH-CLS-BLK-M":   18,
  "MEN-TSH-CLS-WHT-L":   25,
  "MEN-TSH-CLS-NVY-XL":  10,
  "MEN-POLO-STR-NVY-L":   6,

  "MEN-HDY-LOGO-BLK-L":   4,
  "MEN-HDY-LOGO-GRY-M":   2,

  "MEN-JNS-SLIM-32":      7,
  "MEN-JNS-SLIM-34":      0,
  "MEN-CHN-OLV-32":       8,

  "MEN-SHALKAM-COTN-L":   3,
  "WOM-ABAYA-BLK-M":      1,
  "WOM-DUP-ORG-ONE":     22,

  "WOM-DRS-FLR-S":        5,
  "WOM-DRS-FLR-M":        4,
  "WOM-KUR-COT-RED-M":   12,
  "WOM-KUR-COT-TEAL-L":   9,

  "KID-TSH-STAR-RED-8":  15,
  "KID-TSH-STAR-BLU-10": 12,

  "FOOT-SNK-WHT-42":      2,
  "FOOT-SNK-WHT-43":      1,
  "FOOT-SND-BRN-41":      3,

  "ACC-BLT-LEA-34":       5,
  "ACC-BLT-LEA-36":       2,
  "ACC-WAL-LEA-BRN":      7,
  "ACC-CAP-BLK":          0,
  "BAG-TOTE-CAN-NTL":     9,
}

customers = [
  ("Muhammad Moeed Abbasi", "moeedabbasi310103@gmail.com", "03125658590", "House no 2, Lane 9A, Sector H, DHA2, ISB"),
  ("Ayesha Khan",           "ayesha.khan@example.com",      "03001234567", "G-11/3 Islamabad"),
  ("Hassan Raza",           "hassan.raza@example.com",      "03339887766", "Bahria Phase 7"),
  ("Zainab Ali",            "z.ali@example.com",            "03075553322", "F-7 Markaz"),
  ("Bilal Ahmed",           "bilal.ahmed@example.com",      "03451239876", "Wapda Town Lahore"),
  ("Fatima Noor",           "fatima.noor@example.com",      "03119998877", "Gulshan-e-Iqbal Karachi"),
  ("Usman Tariq",           "usman.tariq@example.com",      "03218887766", "DHA Phase 5 Karachi"),
  ("Sana Yousaf",           "sana.yousaf@example.com",      "03001112220", "Askari 10 Lahore"),
]

sample_orders = [
  (0, [("MEN-TSH-CLS-BLK-M", 2, None), ("ACC-WAL-LEA-BRN", 1, None)], "confirmed"),
  (1, [("WOM-KUR-COT-RED-M", 1, None), ("WOM-DRS-FLR-M", 1, None)],  "packed"),
  (2, [("MEN-JNS-SLIM-32", 1, None), ("MEN-HDY-LOGO-GRY-M", 1, None)], "pending"),
  (3, [("FOOT-SNK-WHT-43", 1, None), ("ACC-BLT-LEA-36", 1, None)],     "confirmed"),
  (4, [("MEN-SHALKAM-COTN-L", 1, None), ("ACC-CAP-BLK", 1, None)],     "pending"),
  (5, [("WOM-ABAYA-BLK-M", 1, None), ("BAG-TOTE-CAN-NTL", 1, None)],   "delivered"),
  (6, [("MEN-CHN-OLV-32", 1, None), ("MEN-POLO-STR-NVY-L", 1, None)],  "confirmed"),
  (7, [("KID-TSH-STAR-BLU-10", 2, None), ("KID-TSH-STAR-RED-8", 1, None)], "confirmed"),
]

with sqlite3.connect(DB_PATH) as con:
    con.execute("PRAGMA foreign_keys=ON;")
    cur = con.cursor()

    # Create tables if new DB
    cur.executescript(BASE_SCHEMA)
    cur.executescript(KNOWLEDGE_SCHEMA)

    # ---- Migrations for existing DBs (add missing columns, no data loss) ----
    # customers
    add_column_if_missing(cur, "customers", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # products
    add_column_if_missing(cur, "products", "price", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "products", "threshold", "INTEGER NOT NULL DEFAULT 5")
    add_column_if_missing(cur, "products", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # inventory
    add_column_if_missing(cur, "inventory", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP")
    add_column_if_missing(cur, "inventory", "qty", "INTEGER NOT NULL DEFAULT 0")  # if very old schema

    # orders
    add_column_if_missing(cur, "orders", "status", "TEXT NOT NULL DEFAULT 'pending'")
    add_column_if_missing(cur, "orders", "total", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "orders", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # order_items – ensure columns exist (old DBs may have them already)
    # (order_id, sku, qty, price) are required; if any is missing, SQLite can't add NOT NULL without default,
    # but most legacy schemas already match; we skip here intentionally.

    # ---- Seed / Upsert data ----
    for sku, name, price, thr in products:
        upsert(cur,
            "INSERT OR IGNORE INTO products(sku,name,price,threshold,created_at) VALUES(?,?,?,?,?)",
            (sku, name, price, thr, now)
        )
        upsert(cur, "UPDATE products SET name=?, price=?, threshold=? WHERE sku=?",
               (name, price, thr, sku))

    for sku, qty in start_stock.items():
        upsert(cur,
            "INSERT INTO inventory(sku,qty,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(sku) DO UPDATE SET qty=excluded.qty, updated_at=excluded.updated_at",
            (sku, qty, now)
        )

    for name, email, phone, addr in customers:
        upsert(cur,
            "INSERT OR IGNORE INTO customers(name,email,phone,address,created_at) VALUES(?,?,?,?,?)",
            (name, email, phone, addr, now)
        )

    # Map customer names -> ids
    cur.execute("SELECT id,name FROM customers")
    name2id = {n: i for i, n in cur.fetchall()}

    for cust_idx, items, status in sample_orders:
        cid = name2id[customers[cust_idx][0]]
        cur.execute("INSERT INTO orders(customer_id,status,created_at,total) VALUES(?,?,?,0)",
                    (cid, status, now))
        oid = cur.lastrowid

        total = 0.0
        for sku, qty, price_override in items:
            cur.execute("SELECT price FROM products WHERE sku=?", (sku,))
            row = cur.fetchone()
            price = float(price_override if price_override is not None else (row[0] if row else 0.0))
            total += price * qty
            cur.execute("INSERT OR REPLACE INTO order_items(order_id,sku,qty,price) VALUES(?,?,?,?)",
                        (oid, sku, qty, price))
            cur.execute("UPDATE inventory SET qty=MAX(0, qty-?) , updated_at=? WHERE sku=?",
                        (qty, now, sku))
        cur.execute("UPDATE orders SET total=? WHERE id=?", (total, oid))

    # ---- Ingest Copilot docs (markdown/txt) from SOPS_DIR ----
    if os.path.isdir(SOPS_DIR):
        count_docs = 0
        for root, _, files in os.walk(SOPS_DIR):
            for fname in files:
                fl = fname.lower()
                if fl.endswith((".md", ".markdown", ".txt")):
                    path = os.path.join(root, fname)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                            body = fh.read()
                        title = os.path.splitext(os.path.basename(path))[0]
                        upsert(cur,
                            "INSERT OR REPLACE INTO knowledge_docs(title, body, path, created_at) VALUES(?,?,?,?)",
                            (title, body, path, now)
                        )
                        count_docs += 1
                    except Exception as e:
                        print("Skipped doc:", path, "->", e)
        print(f"Ingested/updated knowledge docs: {count_docs}")
    else:
        print(f"SOPS_DIR not found or not a dir: {SOPS_DIR}")

    con.commit()

# Quick stats
with sqlite3.connect(DB_PATH) as con:
    cur = con.cursor()
    def c(q):
        try:
            return cur.execute(q).fetchone()[0]
        except Exception:
            return "n/a"
    stats = {
        "customers":      c("SELECT COUNT(*) FROM customers"),
        "products":       c("SELECT COUNT(*) FROM products"),
        "inventory rows": c("SELECT COUNT(*) FROM inventory"),
        "orders":         c("SELECT COUNT(*) FROM orders"),
        "order items":    c("SELECT COUNT(*) FROM order_items"),
        "knowledge docs": c("SELECT COUNT(*) FROM knowledge_docs"),
    }
    print("DB:", DB_PATH, "at", now)
    for k, v in stats.items():
        print(f"{k}: {v}")
