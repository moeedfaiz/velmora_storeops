# app/ui_app.py
import os
import time
import requests
import pandas as pd
import streamlit as st

# -------------------- Config --------------------
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Velmora StoreOps", layout="wide")
st.title("🧭 Velmora StoreOps Dashboard")

# -------------------- HTTP helpers --------------------
def req_get(path: str, **kwargs):
    url = f"{API_BASE}{path}"
    try:
        r = requests.get(url, timeout=15, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"GET {url} failed: {e}")
        return None

def req_post(path: str, payload: dict):
    url = f"{API_BASE}{path}"
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code >= 400:
            st.error(f"POST {url} failed [{r.status_code}]: {r.text}")
            return None
        return r.json() if r.headers.get("content-type","").startswith("application/json") else {"ok": True}
    except Exception as e:
        st.error(f"POST {url} failed: {e}")
        return None

def req_put(path: str, payload: dict):
    url = f"{API_BASE}{path}"
    try:
        r = requests.put(url, json=payload, timeout=15)
        if r.status_code >= 400:
            st.error(f"PUT {url} failed [{r.status_code}]: {r.text}")
            return None
        return r.json() if r.headers.get("content-type","").startswith("application/json") else {"ok": True}
    except Exception as e:
        st.error(f"PUT {url} failed: {e}")
        return None

def req_delete(path: str):
    url = f"{API_BASE}{path}"
    try:
        r = requests.delete(url, timeout=15)
        if r.status_code >= 400:
            st.error(f"DELETE {url} failed [{r.status_code}]: {r.text}")
            return None
        return r.json() if r.headers.get("content-type","").startswith("application/json") else {"ok": True}
    except Exception as e:
        st.error(f"DELETE {url} failed: {e}")
        return None

# -------------------- Table helper --------------------
def table_from(url: str, cols=None, empty_msg="No data."):
    data = req_get(url) or []
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if not isinstance(data, list) or len(data) == 0:
        st.info(empty_msg)
        return
    df = pd.json_normalize(data)
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    st.dataframe(df, use_container_width=True)

# -------------------- Header / Health --------------------
colH1, colH2, colH3 = st.columns([1, 1, 2])
with colH1:
    h = req_get("/health")
    st.metric("API status", "OK" if h and h.get("status") == "ok" else "Down")

with colH2:
    info_hdr = req_get("/info") or {}
    st.metric("LLM ready", "True" if info_hdr.get("llm_ready") else "False")

with colH3:
    model_name = (info_hdr or {}).get("model") or "-"
    graph_ready = bool((info_hdr or {}).get("graph_ready", False))  # server should set this; defaults False
    st.metric("Graph ready", "Yes" if graph_ready else "No")
    st.caption(f"Model: `{model_name}` · API base: `{API_BASE}`")

# -------------------- Caches for selects --------------------
@st.cache_data(ttl=10)
def get_products():
    data = req_get("/products")
    return data if isinstance(data, list) else []

@st.cache_data(ttl=10)
def get_customers():
    data = req_get("/customers")
    return data if isinstance(data, list) else []

@st.cache_data(ttl=10)
def get_orders(limit=25):
    data = req_get(f"/orders?limit={limit}")
    return data if isinstance(data, list) else []

# -------------------- Tabs --------------------
tab_orders, tab_customers, tab_inventory, tab_analytics, tab_chat = st.tabs(
    ["📦 Orders", "👤 Customers", "📦 Inventory", "📈 Analytics", "💬 Chat"]
)

# =========================================================
# Orders Tab
# =========================================================
with tab_orders:
    st.subheader("Create / Manage Orders")
    c1, c2 = st.columns([1, 2])

    # ---- Add Order Form ----
    with c1:
        st.markdown("### ➕ Add Order")

        custs = get_customers()
        cust_map = {f"{c.get('id')} — {c.get('name')}": c.get("id") for c in custs}
        cust_label = st.selectbox(
            "Customer",
            list(cust_map.keys()) if cust_map else ["No customers — add in Customers tab"],
            key="ord_select_customer",
        )
        customer_id = cust_map.get(cust_label) if cust_map else None

        if "order_items_rows" not in st.session_state:
            st.session_state.order_items_rows = 1  # start with one row

        prod_list = get_products()
        sku_options = [p.get("sku") for p in prod_list]
        price_lookup = {p.get("sku"): float(p.get("price") or 0.0) for p in prod_list}

        with st.form("form_add_order", clear_on_submit=False):
            items_payload = []
            est_total = 0.0

            for idx in range(st.session_state.order_items_rows):
                st.markdown(f"**Item #{idx + 1}**")
                cc = st.columns([2, 1, 1])
                with cc[0]:
                    sku = st.selectbox(
                        "SKU",
                        sku_options if sku_options else ["No products"],
                        key=f"ord_item_sku_{idx}",
                    )
                with cc[1]:
                    qty = st.number_input(
                        "Qty", min_value=1, step=1, value=1, key=f"ord_item_qty_{idx}"
                    )
                with cc[2]:
                    default_price = price_lookup.get(sku, 0.0)
                    price = st.number_input(
                        "Unit Price",
                        min_value=0.0,
                        step=1.0,
                        value=float(default_price),
                        key=f"ord_item_price_{idx}",
                    )

                est_total += float(qty) * float(price)
                items_payload.append({"sku": sku, "qty": int(qty), "price": float(price)})

            st.caption(f"**Estimated total:** {est_total:,.2f}")

            add_more = st.form_submit_button("➕ Add another item row", type="secondary")
            if add_more:
                st.session_state.order_items_rows += 1
                st.rerun()

            submitted = st.form_submit_button("Create Order")
            if submitted:
                if not customer_id:
                    st.error("Please select a customer.")
                elif not items_payload:
                    st.error("Please add at least one item.")
                else:
                    payload = {"customer_id": int(customer_id), "items": items_payload}
                    with st.spinner("Creating order..."):
                        res = req_post("/orders", payload)
                    if res is not None:
                        st.success("Order created.")
                        st.session_state.order_items_rows = 1
                        get_orders.clear()
                        time.sleep(0.5)
                        st.rerun()

    # ---- Orders Table + Status Update ----
    with c2:
        st.markdown("### 📋 Recent Orders")
        table_from(
            "/orders?limit=50",
            ["id", "customer_id", "status", "total", "created_at"],
            empty_msg="No orders yet.",
        )

        st.markdown("### ✏️ Update Order Status")
        orders = get_orders(limit=50)
        if orders:
            order_ids = [str(o.get("id")) for o in orders if o.get("id") is not None]
            sel_order = st.selectbox("Order ID", order_ids, key="ord_status_select")
            new_status = st.selectbox(
                "New Status",
                ["pending", "confirmed", "packed", "shipped", "delivered", "cancelled"],
                key="ord_status_new",
            )
            if st.button("Update Status", key="ord_status_btn"):
                with st.spinner("Updating..."):
                    res = req_put(f"/orders/{sel_order}/status", {"status": new_status})
                if res is not None:
                    st.success(f"Order {sel_order} → {new_status}")
                    get_orders.clear()
                    time.sleep(0.4)
                    st.rerun()
        else:
            st.info("No orders yet.")

# =========================================================
# Customers Tab
# =========================================================
with tab_customers:
    st.subheader("Customers")

    cc = st.columns([1, 2])
    with cc[0]:
        st.markdown("### ➕ Add Customer")
        with st.form("form_add_customer"):
            cname = st.text_input("Name", key="cust_name")
            cemail = st.text_input("Email", key="cust_email")
            cphone = st.text_input("Phone", key="cust_phone")
            caddr = st.text_input("Address", key="cust_address")
            sub = st.form_submit_button("Create Customer")
            if sub:
                if not cname.strip():
                    st.error("Name is required.")
                else:
                    payload = {
                        "name": cname,
                        "email": cemail,
                        "phone": cphone,
                        "address": caddr,
                    }
                    with st.spinner("Creating customer..."):
                        res = req_post("/customers", payload)
                    if res is not None:
                        st.success("Customer created.")
                        get_customers.clear()
                        time.sleep(0.3)
                        st.rerun()

    with cc[1]:
        st.markdown("### 📋 Customer List")
        table_from(
            "/customers",
            ["id", "name", "email", "phone", "address", "created_at"],
            empty_msg="No customers.",
        )

# =========================================================
# Inventory Tab
# =========================================================
with tab_inventory:
    st.subheader("Inventory & Products")

    invC = st.columns([1, 1, 1])

    # ---- Add/Update Product ----
    with invC[0]:
        st.markdown("### ➕ Add Product")
        with st.form("form_add_product"):
            psku = st.text_input("SKU", key="prod_sku")
            pname = st.text_input("Name", key="prod_name")
            pprice = st.number_input("Price", min_value=0.0, step=1.0, value=0.0, key="prod_price")
            pth = st.number_input(
                "Reorder threshold", min_value=0, step=1, value=5, key="prod_threshold"
            )
            sub = st.form_submit_button("Save Product")
            if sub:
                if not psku.strip():
                    st.error("SKU is required.")
                else:
                    payload = {
                        "sku": psku,
                        "name": pname,
                        "price": float(pprice),
                        "threshold": int(pth),
                    }
                    with st.spinner("Saving product..."):
                        res = req_post("/products", payload)
                    if res is not None:
                        st.success("Product saved.")
                        get_products.clear()
                        time.sleep(0.3)
                        st.rerun()

    # ---- Set Stock (absolute) ----
    with invC[1]:
        st.markdown("### 🧮 Set Stock (absolute)")
        prods = get_products()
        sku_list = [p.get("sku") for p in prods]
        selected_sku = st.selectbox(
            "SKU", sku_list if sku_list else ["No products"], key="stk_set_sku"
        )
        new_qty = st.number_input("New qty", min_value=0, step=1, value=0, key="stk_set_qty")
        if st.button("Set Qty", key="stk_set_btn"):
            if selected_sku in (None, "No products"):
                st.error("No SKU selected.")
            else:
                with st.spinner("Updating stock..."):
                    res = req_put(f"/inventory/stock/{selected_sku}", {"qty": int(new_qty)})
                if res is not None:
                    st.success(f"Stock for {selected_sku} set to {new_qty}")

    # ---- Adjust Stock (delta) ----
    with invC[2]:
        st.markdown("### 🔁 Adjust Stock (delta)")
        selected_sku2 = st.selectbox(
            "SKU ", sku_list if sku_list else ["No products"], key="stk_adj_sku"
        )
        delta = st.number_input("Delta (+/-)", step=1, value=0, key="stk_adj_delta")
        if st.button("Apply Delta", key="stk_adj_btn"):
            if selected_sku2 in (None, "No products"):
                st.error("No SKU selected.")
            else:
                inv_rows = req_get("/inventory") or []
                cur_qty = 0
                for row in inv_rows:
                    if str(row.get("sku")) == str(selected_sku2):
                        cur_qty = int(row.get("qty") or 0)
                        break
                newq = max(0, cur_qty + int(delta))
                with st.spinner("Updating stock..."):
                    res = req_put(f"/inventory/stock/{selected_sku2}", {"qty": int(newq)})
                if res is not None:
                    st.success(f"Stock for {selected_sku2} now {newq}")

    st.markdown("### 📋 Products")
    table_from("/products", ["sku", "name", "price", "threshold"], empty_msg="No products.")

    st.markdown("### 🚨 Out-of-stock / Below Threshold")
    table_from(
        "/inventory/out_of_stock",
        ["sku", "name", "qty", "threshold"],
        empty_msg="Nothing out of stock.",
    )

# =========================================================
# Analytics Tab
# =========================================================
with tab_analytics:
    st.subheader("Sales Analytics")
    wow = req_get("/analytics/sales/week_over_week") or {}
    curr = (wow or {}).get("curr_week", {}) or {}
    prev = (wow or {}).get("prev_week", {}) or {}

    curr_cnt = int(curr.get("count") or 0)
    prev_cnt = int(prev.get("count") or 0)
    curr_tot = float(curr.get("total") or 0.0)
    prev_tot = float(prev.get("total") or 0.0)

    if prev_tot == 0:
        delta_str = "∞ (new)" if curr_tot > 0 else "0.0%"
    else:
        delta_val = (curr_tot - prev_tot) * 100.0 / prev_tot
        delta_str = f"{delta_val:.1f}%"

    if (curr_cnt + prev_cnt) > 0:
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("This week – orders", curr_cnt)
        m2.metric("This week – revenue", f"{curr_tot:,.0f}")
        m3.metric("WoW %", delta_str)
        m4.metric("Last week – orders", prev_cnt)
        m5.metric("Last week – revenue", f"{prev_tot:,.0f}")
        m6.metric("Total (2w)", f"{(curr_tot + prev_tot):,.0f}")

        st.write("")
        df_rev = pd.DataFrame({"Week": ["Last week", "This week"], "Revenue": [prev_tot, curr_tot]}).set_index("Week")
        st.bar_chart(df_rev, height=180)

        df_ord = pd.DataFrame({"Week": ["Last week", "This week"], "Orders": [prev_cnt, curr_cnt]}).set_index("Week")
        st.bar_chart(df_ord, height=180)
    else:
        st.info("No WoW data.")

# =========================================================
# Chat Tab (now supports RAG toggle)
# =========================================================
with tab_chat:
    st.subheader("Ask the Copilot")

    # Fetch graph readiness so we can enable/disable the toggle
    info_chat = req_get("/info") or {}
    graph_ready_chat = bool(info_chat.get("graph_ready", False))

    q = st.text_input("Ask a question", key="chat_question")

    colC1, colC2 = st.columns([1,1])
    with colC1:
        use_rag = st.checkbox(
            "Use RAG (requires graph build)",
            value=graph_ready_chat,
            disabled=not graph_ready_chat,
            help="When enabled, the server will try the knowledge graph; otherwise, plain LLM."
        )
    with colC2:
        top_k = st.number_input(
            "Top-K chunks",
            min_value=1, max_value=10, value=3, step=1,
            disabled=not use_rag
        )

    if st.button("Ask", key="chat_ask_btn"):
        if not q.strip():
            st.error("Please enter a question.")
        else:
            payload = {"question": q}
            if use_rag:
                payload.update({"use_rag": True, "top_k": int(top_k)})
            with st.spinner("Thinking..."):
                res = req_post("/ask", payload) or {}

            st.markdown("**Answer**")
            st.write(
                res.get("answer")
                or res.get("message")
                or "RAG graph not available in this build."
            )

            err = res.get("error")
            if err:
                st.warning(err)

            st.markdown("**Citations**")
            cites = res.get("citations") or []
            if isinstance(cites, list) and cites:
                try:
                    dfc = pd.json_normalize(cites)
                    st.dataframe(dfc, use_container_width=True)
                except Exception:
                    st.write(cites)
            else:
                st.caption("No citations.")

            st.markdown("**SQL Result**")
            st.write(res.get("sql_result"))
