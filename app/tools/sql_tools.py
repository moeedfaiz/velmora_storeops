# app/tools/sql_tools.py
import os
import sqlite3
import datetime as dt
from typing import List, Dict, Any, Optional

from ..config import DB_PATH

# =========================================================
# DB helpers
# =========================================================

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        cur = c.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL DEFAULT 0,
            threshold INTEGER DEFAULT 0
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            sku TEXT PRIMARY KEY,
            qty INTEGER DEFAULT 0,
            FOREIGN KEY(sku) REFERENCES products(sku) ON DELETE CASCADE
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            status TEXT DEFAULT 'pending',
            total REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            order_id INTEGER,
            sku TEXT,
            qty INTEGER,
            price REAL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(sku) REFERENCES products(sku),
            PRIMARY KEY(order_id, sku)
        )""")

        c.commit()

ensure_db()

# =========================================================
# Utilities
# =========================================================

def _rowdicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]

def _one_or_none(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None

def _get_product_price(c: sqlite3.Connection, sku: str) -> float:
    r = c.execute("SELECT price FROM products WHERE sku=?", (sku,)).fetchone()
    return float(r["price"]) if r else 0.0

def _ensure_inventory_row(c: sqlite3.Connection, sku: str):
    r = c.execute("SELECT 1 FROM inventory WHERE sku=?", (sku,)).fetchone()
    if not r:
        c.execute("INSERT INTO inventory (sku, qty) VALUES (?, ?)", (sku, 0))

# =========================================================
# Customers
# =========================================================

def list_customers(q: Optional[str]) -> List[Dict[str, Any]]:
    with _conn() as c:
        if q:
            rows = c.execute(
                "SELECT * FROM customers WHERE name LIKE ? OR email LIKE ? ORDER BY id DESC",
                (f"%{q}%", f"%{q}%")
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    return _rowdicts(rows)

def create_customer(name: str, email: str, phone: str, address: str) -> Dict[str, Any]:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO customers(name,email,phone,address) VALUES (?,?,?,?)",
            (name, email, phone, address)
        )
        cid = cur.lastrowid
        row = c.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    return _one_or_none(row) or {}

def update_customer(cid: int, name: str, email: str, phone: str, address: str) -> Dict[str, Any]:
    with _conn() as c:
        c.execute(
            "UPDATE customers SET name=?, email=?, phone=?, address=? WHERE id=?",
            (name, email, phone, address, cid)
        )
        row = c.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    return _one_or_none(row) or {}

def delete_customer(cid: int) -> Dict[str, Any]:
    with _conn() as c:
        c.execute("DELETE FROM customers WHERE id=?", (cid,))
    return {"ok": True, "deleted": cid}

# =========================================================
# Products & Inventory
# =========================================================

def list_products(q: Optional[str]) -> List[Dict[str, Any]]:
    with _conn() as c:
        if q:
            rows = c.execute(
                "SELECT * FROM products WHERE sku LIKE ? OR name LIKE ? ORDER BY sku",
                (f"%{q}%", f"%{q}%")
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM products ORDER BY sku").fetchall()
    return _rowdicts(rows)

def create_product(sku: str, name: str, price: float, threshold: int, qty: int = 0) -> Dict[str, Any]:
    with _conn() as c:
        c.execute("""
            INSERT INTO products(sku,name,price,threshold)
            VALUES(?,?,?,?)
            ON CONFLICT(sku) DO UPDATE SET name=excluded.name, price=excluded.price, threshold=excluded.threshold
        """, (sku, name, price, threshold))
        _ensure_inventory_row(c, sku)
        if qty is not None:
            c.execute("UPDATE inventory SET qty=? WHERE sku=?", (int(qty), sku))
        row = c.execute("""
            SELECT p.sku, p.name, p.price, p.threshold, IFNULL(i.qty,0) AS qty
            FROM products p LEFT JOIN inventory i ON p.sku=i.sku
            WHERE p.sku=?
        """, (sku,)).fetchone()
    return _one_or_none(row) or {}

def update_product(sku: str, name: str, price: float, threshold: int, qty: int) -> Dict[str, Any]:
    with _conn() as c:
        c.execute("UPDATE products SET name=?, price=?, threshold=? WHERE sku=?",
                  (name, price, threshold, sku))
        _ensure_inventory_row(c, sku)
        c.execute("UPDATE inventory SET qty=? WHERE sku=?", (int(qty), sku))
        row = c.execute("""
            SELECT p.sku, p.name, p.price, p.threshold, IFNULL(i.qty,0) AS qty
            FROM products p LEFT JOIN inventory i ON p.sku=i.sku
            WHERE p.sku=?
        """, (sku,)).fetchone()
    return _one_or_none(row) or {}

def delete_product(sku: str) -> Dict[str, Any]:
    with _conn() as c:
        c.execute("DELETE FROM order_items WHERE sku=?", (sku,))
        c.execute("DELETE FROM inventory WHERE sku=?", (sku,))
        c.execute("DELETE FROM products WHERE sku=?", (sku,))
    return {"ok": True, "deleted": sku}

def set_inventory_qty(sku: str, qty: int) -> Dict[str, Any]:
    with _conn() as c:
        # make sure product exists
        r = c.execute("SELECT 1 FROM products WHERE sku=?", (sku,)).fetchone()
        if not r:
            raise ValueError(f"Unknown SKU: {sku}")
        _ensure_inventory_row(c, sku)
        c.execute("UPDATE inventory SET qty=? WHERE sku=?", (int(qty), sku))
        row = c.execute("""
            SELECT p.sku, p.name, IFNULL(i.qty,0) AS qty, p.threshold
            FROM products p LEFT JOIN inventory i ON p.sku=i.sku
            WHERE p.sku=?
        """, (sku,)).fetchone()
    return _one_or_none(row) or {}

def list_inventory() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("""
            SELECT p.sku, p.name, p.price, p.threshold, IFNULL(i.qty,0) AS qty
            FROM products p
            LEFT JOIN inventory i ON p.sku=i.sku
            ORDER BY p.sku
        """).fetchall()
    return _rowdicts(rows)

def list_in_stock() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("""
            SELECT p.sku, p.name, IFNULL(i.qty,0) AS qty, p.threshold
            FROM products p LEFT JOIN inventory i ON p.sku=i.sku
            WHERE IFNULL(i.qty,0) > 0
            ORDER BY p.sku
        """).fetchall()
    return _rowdicts(rows)

def list_out_of_stock() -> List[Dict[str, Any]]:
    # Treat "out_of_stock" as qty <= 0 OR below threshold
    with _conn() as c:
        rows = c.execute("""
            SELECT p.sku, p.name, IFNULL(i.qty,0) AS qty, p.threshold
            FROM products p LEFT JOIN inventory i ON p.sku=i.sku
            WHERE IFNULL(i.qty,0) <= 0 OR IFNULL(i.qty,0) < p.threshold
            ORDER BY p.sku
        """).fetchall()
    return _rowdicts(rows)

# =========================================================
# Orders
# =========================================================

def list_orders(limit: int = 25) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("""
            SELECT id, customer_id, status, total, created_at
            FROM orders
            ORDER BY id DESC
            LIMIT ?
        """, (int(limit),)).fetchall()
    return _rowdicts(rows)

def get_order(order_id: int) -> Dict[str, Any]:
    with _conn() as c:
        order = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            return {}
        items = c.execute("""
            SELECT oi.sku, oi.qty, oi.price, p.name
            FROM order_items oi
            LEFT JOIN products p ON oi.sku = p.sku
            WHERE oi.order_id=?
        """, (order_id,)).fetchall()
    out = _one_or_none(order) or {}
    out["items"] = _rowdicts(items)
    return out

def create_order(customer_id: Optional[int], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    items: [{sku, qty, price (optional)}]
    - If price is None, use product price.
    - Decrease inventory by qty (not below zero).
    """
    items = items or []
    with _conn() as c:
        # compute total (use product price when missing)
        total = 0.0
        for it in items:
            sku = it["sku"]
            qty = int(it["qty"])
            price = float(it["price"]) if it.get("price") is not None else _get_product_price(c, sku)
            total += qty * price

        cur = c.execute(
            "INSERT INTO orders(customer_id, status, total) VALUES (?, 'pending', ?)",
            (customer_id, total)
        )
        oid = cur.lastrowid

        for it in items:
            sku = it["sku"]
            qty = int(it["qty"])
            price = float(it["price"]) if it.get("price") is not None else _get_product_price(c, sku)
            c.execute(
                "INSERT INTO order_items(order_id, sku, qty, price) VALUES (?,?,?,?)",
                (oid, sku, qty, price)
            )
            _ensure_inventory_row(c, sku)
            # reduce inventory (not negative)
            r = c.execute("SELECT qty FROM inventory WHERE sku=?", (sku,)).fetchone()
            cur_qty = int(r["qty"]) if r else 0
            new_qty = max(0, cur_qty - qty)
            c.execute("UPDATE inventory SET qty=? WHERE sku=?", (new_qty, sku))

        row = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        out = _one_or_none(row) or {}
        its = c.execute("SELECT sku, qty, price FROM order_items WHERE order_id=?", (oid,)).fetchall()
        out["items"] = _rowdicts(its)
    return out

def update_order_status(order_id: int, status: str) -> Dict[str, Any]:
    with _conn() as c:
        c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        row = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    return _one_or_none(row) or {}

def delete_order(order_id: int) -> Dict[str, Any]:
    with _conn() as c:
        c.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
        c.execute("DELETE FROM orders WHERE id=?", (order_id,))
    return {"ok": True, "deleted": order_id}

def get_order_status(order_id: int) -> Dict[str, Any]:
    with _conn() as c:
        row = c.execute("SELECT id, status, total, created_at FROM orders WHERE id=?", (order_id,)).fetchone()
    return _one_or_none(row) or {}

# =========================================================
# Analytics / Forecast
# =========================================================

def _range_strings(start: dt.datetime, end: dt.datetime) -> (str, str):
    # sqlite datetime strings like 'YYYY-MM-DD HH:MM:SS'
    return (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"))

def sales_week_over_week() -> Dict[str, Any]:
    now = dt.datetime.utcnow()
    # last 7 days vs previous 7 days (simple and timezone-neutral)
    curr_start = now - dt.timedelta(days=7)
    prev_start = now - dt.timedelta(days=14)
    prev_end = curr_start

    prev_s, prev_e = _range_strings(prev_start, prev_end)
    curr_s, curr_e = _range_strings(curr_start, now)

    with _conn() as c:
        prev = c.execute("""
            SELECT COUNT(*) AS count, IFNULL(SUM(total),0) AS total
            FROM orders WHERE created_at >= ? AND created_at < ?
        """, (prev_s, prev_e)).fetchone()

        curr = c.execute("""
            SELECT COUNT(*) AS count, IFNULL(SUM(total),0) AS total
            FROM orders WHERE created_at >= ? AND created_at <= ?
        """, (curr_s, curr_e)).fetchone()

    return {
        "prev_week": {"count": int(prev["count"]), "total": float(prev["total"])},
        "curr_week": {"count": int(curr["count"]), "total": float(curr["total"])},
    }

def forecast_sku(sku: str, horizon_days: int = 7) -> Dict[str, Any]:
    """
    Naive forecast:
      - compute total qty sold in last 30 days
      - daily_avg = total / 30  (min clamp 0)
      - current_qty from inventory
      - days_left = current_qty / max(daily_avg, 0.01)
      - risk if days_left < horizon_days
    """
    horizon_days = max(1, int(horizon_days))
    now = dt.datetime.utcnow()
    start_30 = now - dt.timedelta(days=30)
    s_30, s_now = _range_strings(start_30, now)

    with _conn() as c:
        sold_row = c.execute("""
            SELECT IFNULL(SUM(oi.qty),0) AS sold
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE oi.sku = ? AND o.created_at >= ? AND o.created_at <= ?
        """, (sku, s_30, s_now)).fetchone()
        sold_30 = int(sold_row["sold"] or 0)

        inv_row = c.execute("SELECT IFNULL(qty,0) AS qty FROM inventory WHERE sku=?", (sku,)).fetchone()
        cur_qty = int(inv_row["qty"] or 0)

        prod = c.execute("SELECT name, price, threshold FROM products WHERE sku=?", (sku,)).fetchone()

    daily_avg = sold_30 / 30.0 if sold_30 > 0 else 0.0
    denom = daily_avg if daily_avg > 0 else 0.01
    days_left = cur_qty / denom
    risk = "high" if days_left < horizon_days else "low"

    return {
        "sku": sku,
        "name": (prod["name"] if prod else None),
        "current_qty": cur_qty,
        "threshold": int(prod["threshold"]) if prod else 0,
        "avg_daily_sales_30d": round(daily_avg, 2),
        "days_left_est": round(days_left, 1),
        "horizon_days": horizon_days,
        "stockout_risk": risk,
    }
