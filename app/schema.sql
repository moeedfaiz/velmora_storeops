PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  price REAL NOT NULL,
  supplier_id INTEGER
);

CREATE TABLE IF NOT EXISTS suppliers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
  sku TEXT NOT NULL,
  on_hand INTEGER NOT NULL DEFAULT 0,
  reorder_point INTEGER NOT NULL DEFAULT 10,
  reorder_qty INTEGER NOT NULL DEFAULT 50,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (sku) REFERENCES products(sku)
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_name TEXT,
  status TEXT NOT NULL DEFAULT 'Created',  -- Created, Paid, Packed, Shipped, Delivered, Canceled
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  sku TEXT NOT NULL,
  qty INTEGER NOT NULL,
  price REAL NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (sku) REFERENCES products(sku)
);

CREATE TABLE IF NOT EXISTS stock_moves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT NOT NULL,
  delta INTEGER NOT NULL,                -- negative for sale, positive for restock
  reason TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (sku) REFERENCES products(sku)
);

CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  body TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
