# app/api/server.py
import os
from typing import List, Optional, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from prometheus_fastapi_instrumentator import Instrumentator
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.obs.logging_config import setup_logging
from ..config import get_cohere_key, MODEL_NAME, VECTOR_DIR, DB_PATH, ensure_dirs
from ..tools.sql_tools import (
    list_customers, create_customer, update_customer, delete_customer,
    list_products, create_product, update_product, delete_product,
    set_inventory_qty, list_inventory, list_out_of_stock,
    list_orders, get_order, create_order, update_order_status, delete_order,
    get_order_status, sales_week_over_week,
)

# Optional graph
try:
    from ..graph.build_graph import build_graph
    _HAS_GRAPH = True
except Exception:
    _HAS_GRAPH = False

# ----------------- Bootstrap -----------------
ensure_dirs()
app = FastAPI(title="Velmora StoreOps API")

# CORS so Streamlit can call it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Observability ----
setup_logging()
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FastApiIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES", "0.0")),
    )
if os.getenv("PROMETHEUS_ENABLE", "0") == "1":
    Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

# ----------------- Models -----------------
class AskIn(BaseModel):
    question: str
    use_rag: Optional[bool] = None
    top_k: Optional[int] = 3

class NewCustomer(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    address: str = ""

class UpdateCustomer(NewCustomer):
    pass

class ProductIn(BaseModel):
    sku: str = Field(..., min_length=1)
    name: str
    price: float = 0.0
    threshold: int = 0
    qty: int = 0

class ProductUpdate(BaseModel):
    name: str
    price: float
    threshold: int
    qty: int

class OrderItemIn(BaseModel):
    sku: str
    qty: int
    price: Optional[float] = None  # optional; fallback to product price

class OrderIn(BaseModel):
    customer_id: Optional[int] = None
    items: List[OrderItemIn]

class OrderStatusIn(BaseModel):
    status: str

class InventoryQty(BaseModel):
    qty: int

# ----------------- Misc -----------------
@app.get("/")
def root():
    return {"message": "Velmora StoreOps API", "try": ["/docs", "/health", "/info"]}

@app.get("/health")
def health():
    return {"status": "ok", "llm_ready": bool(get_cohere_key())}

@app.get("/info")
def info():
    return {
        "llm_ready": bool(get_cohere_key()),
        "model": MODEL_NAME,
        "vector_dir": VECTOR_DIR,
        "db_path": DB_PATH,
        "graph_ready": _HAS_GRAPH,
    }

# ----------------- Customers -----------------
@app.get("/customers")
def api_list_customers(q: Optional[str] = None):
    return list_customers(q)

@app.post("/customers")
def api_create_customer(body: NewCustomer):
    return create_customer(body.name, body.email, body.phone, body.address)

@app.put("/customers/{cid}")
def api_update_customer(cid: int, body: UpdateCustomer):
    return update_customer(cid, body.name, body.email, body.phone, body.address)

@app.delete("/customers/{cid}")
def api_delete_customer(cid: int):
    return delete_customer(cid)

# ----------------- Products & Inventory -----------------
@app.get("/products")
def api_list_products(q: Optional[str] = None):
    return list_products(q)

@app.post("/products")
def api_create_product(body: ProductIn):
    return create_product(body.sku, body.name, body.price, body.threshold, body.qty)

@app.put("/products/{sku}")
def api_update_product(sku: str, body: ProductUpdate):
    return update_product(sku, body.name, body.price, body.threshold, body.qty)

@app.delete("/products/{sku}")
def api_delete_product(sku: str):
    return delete_product(sku)

# NEW: list full inventory (UI & your tests call this)
@app.get("/inventory")
def api_list_inventory():
    return list_inventory()

# Match UI calls: PUT /inventory/stock/{sku} with JSON {"qty": <int>}
@app.put("/inventory/stock/{sku}")
def api_set_inventory_stock(sku: str, body: InventoryQty):
    return set_inventory_qty(sku, body.qty)

@app.get("/inventory/out_of_stock")
def api_out_of_stock():
    return list_out_of_stock()

# ----------------- Orders -----------------
@app.get("/orders")
def api_list_orders(limit: int = 25):
    return list_orders(limit)

@app.get("/orders/{order_id}")
def api_get_order(order_id: int):
    return get_order(order_id)

@app.post("/orders")
def api_create_order(body: OrderIn):
    items = [dict(sku=i.sku, qty=i.qty, price=i.price) for i in body.items]
    return create_order(body.customer_id, items)

@app.put("/orders/{order_id}/status")
def api_update_order_status(order_id: int, body: OrderStatusIn):
    return update_order_status(order_id, body.status)

@app.delete("/orders/{order_id}")
def api_delete_order(order_id: int):
    return delete_order(order_id)

@app.get("/orders/{order_id}/status")
def api_get_order_status(order_id: int):
    return get_order_status(order_id)

# ----------------- Analytics -----------------
@app.get("/analytics/sales/week_over_week")
def api_sales_wow():
    raw = sales_week_over_week()
    prev = raw.get("prev_week", {"count": 0, "total": 0.0})
    curr = raw.get("curr_week", {"count": 0, "total": 0.0})
    raw["series"] = [
        {"week": "prev", "orders": prev.get("count", 0), "revenue": float(prev.get("total", 0.0))},
        {"week": "curr", "orders": curr.get("count", 0), "revenue": float(curr.get("total", 0.0))},
    ]
    return raw

# ----------------- Ask -----------------
@app.post("/ask")
def ask(body: AskIn):
    if not _HAS_GRAPH:
        return {"answer": "RAG graph not available in this build.", "citations": []}
    graph = build_graph()
    state = {
        "question": body.question,
        "use_rag": body.use_rag,
        "top_k": body.top_k or 3,
    }
    out = graph.invoke(state)
    return {
        "intent": out.get("intent"),
        "order_id": out.get("order_id"),
        "sku": out.get("sku"),
        "horizon_days": out.get("horizon_days"),
        "answer": out.get("answer"),
        "sql_result": out.get("sql_result"),
        "citations": out.get("citations"),
        "error": out.get("error"),
    }
