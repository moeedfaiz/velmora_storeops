# app/graph/nodes.py
from typing import Dict, Any, List, Optional
import os
import re
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_cohere import ChatCohere, CohereEmbeddings

# Vector stores (fallback: FAISS if present; else Chroma)
_FAISS = None
_CHROMA = None
try:
    from langchain_community.vectorstores import FAISS as _FAISS
    _FAISS = _FAISS
except Exception:
    pass
try:
    from langchain_community.vectorstores import Chroma as _CHROMA
    _CHROMA = _CHROMA
except Exception:
    pass

from ..config import EMBED_MODEL, VECTOR_DIR
from ..tools.sql_tools import (
    get_order_status,
    forecast_sku,
    list_in_stock,
    list_out_of_stock,
)

# ---------- Intent & slot extraction ----------
class Extract(BaseModel):
    """
    intent: one of: order_status, stock_forecast, inventory, policy_q, unknown
    stock_query: for inventory intent, one of: in_stock, out_of_stock, all
    """
    intent: str = Field(description="order_status | stock_forecast | inventory | policy_q | unknown")
    order_id: Optional[int] = None
    sku: Optional[str] = None
    horizon_days: Optional[int] = 7
    stock_query: Optional[str] = None  # in_stock | out_of_stock | all

parser = JsonOutputParser(pydantic_object=Extract)

_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an intent classifier for a retail operations assistant.\n"
     "Classify the user's question into exactly ONE intent from:\n"
     "- order_status: queries about a specific order ID (#123 or id 123)\n"
     "- stock_forecast: predict stock-out risk for a SKU (e.g., VLM-TEE-001) with a timeframe\n"
     "- inventory: questions like 'which items are in stock/out of stock?'\n"
     "- policy_q: questions about policy or SOPs\n"
     "- unknown: anything else\n\n"
     "If intent is inventory, set 'stock_query' to one of: 'in_stock', 'out_of_stock', or 'all'.\n"
     "If an order ID is present (e.g., 'where is order #60'), extract it as integer 'order_id'.\n"
     "If a SKU is present (e.g., 'VLM-TEE-001'), put it under 'sku'.\n"
     "Set 'horizon_days' to a number if the user mentions a timeframe; default 7.\n\n"
     "Return ONLY a single JSON object that matches this schema.\n"
     "{format_instructions}"
     ),
    ("user", "{question}")
]).partial(format_instructions=parser.get_format_instructions())

def _post_fix_extraction(question: str, out: Dict[str, Any]) -> Dict[str, Any]:
    if not out.get("order_id"):
        m = re.search(r"(?:#|id\s*)(\d+)", question, flags=re.I)
        if m:
            out["order_id"] = int(m.group(1))
    qlow = question.lower()
    if out.get("intent") == "inventory" and not out.get("stock_query"):
        if "not in stock" in qlow or "out of stock" in qlow or "oos" in qlow:
            out["stock_query"] = "out_of_stock"
        elif "in stock" in qlow or "available now" in qlow:
            out["stock_query"] = "in_stock"
        else:
            out["stock_query"] = "all"
    return out

def _fallback_classify(question: str) -> Dict[str, Any]:
    q = question.lower()
    intent = "unknown"
    stock_query = None
    order_id = None
    sku = None
    horizon = 7

    if re.search(r"(?:order|tracking).*(?:#|\bid\b)\s*\d+", q):
        intent = "order_status"
        m = re.search(r"(?:#|id\s*)(\d+)", q)
        if m: order_id = int(m.group(1))
    elif any(k in q for k in ["stock-out", "stock out", "forecast", "run out", "days left"]):
        intent = "stock_forecast"
        m = re.search(r"\b[Vv][Ll][Mm]-[A-Za-z0-9-]+\b", question)
        if m: sku = m.group(0)
        m2 = re.search(r"(\d+)\s*(?:day|days|week|weeks)", q)
        if m2:
            horizon = 7 if "week" in q and m2.group(1) == "1" else int(m2.group(1))
    elif any(k in q for k in ["in stock", "out of stock", "not in stock", "available now", "which items are in stock", "which items are not in stock"]):
        intent = "inventory"
        if "out of stock" in q or "not in stock" in q:
            stock_query = "out_of_stock"
        elif "in stock" in q or "available now" in q:
            stock_query = "in_stock"
        else:
            stock_query = "all"
    elif any(k in q for k in ["policy", "refund", "exchange", "warranty", "shipping"]):
        intent = "policy_q"

    return {
        "intent": intent,
        "order_id": order_id,
        "sku": sku,
        "horizon_days": horizon,
        "stock_query": stock_query,
    }

def classify(llm: ChatCohere, question: str) -> Dict[str, Any]:
    chain = _prompt | llm | parser
    try:
        out = chain.invoke({"question": question})
        return _post_fix_extraction(question, out)
    except OutputParserException:
        return _post_fix_extraction(question, _fallback_classify(question))
    except Exception:
        return _post_fix_extraction(question, _fallback_classify(question))

# ---------- Retrieval (RAG) ----------
def _has_faiss(dir_: str) -> bool:
    return os.path.exists(os.path.join(dir_, "index.faiss")) and os.path.exists(os.path.join(dir_, "index.pkl"))

def _has_chroma(dir_: str) -> bool:
    # Chroma writes a set of files; simplest: non-empty dir check
    try:
        return any(os.scandir(dir_))
    except Exception:
        return False

def get_retriever(top_k: int = 3):
    embeddings = CohereEmbeddings(model=EMBED_MODEL)
    # Prefer FAISS if present (matches your current /data/vectorstore layout)
    if _FAISS and _has_faiss(VECTOR_DIR):
        vs = _FAISS.load_local(VECTOR_DIR, embeddings, allow_dangerous_deserialization=True)
        return vs.as_retriever(search_kwargs={"k": max(1, int(top_k))})
    # Fallback to Chroma if available
    if _CHROMA and _has_chroma(VECTOR_DIR):
        vs = _CHROMA(collection_name="velmora_sops", persist_directory=VECTOR_DIR, embedding_function=embeddings)
        return vs.as_retriever(search_kwargs={"k": max(1, int(top_k))})
    return None

def retrieve_docs(query: str, top_k: int = 3):
    r = get_retriever(top_k=top_k)
    if not r:
        return []
    return r.get_relevant_documents(query)

# ---------- Node functions ----------
def classifier_node(state: Dict[str, Any], llm: ChatCohere):
    ext = classify(llm, state["question"])
    state.update({
        "intent": ext.get("intent", "unknown"),
        "order_id": ext.get("order_id"),
        "sku": ext.get("sku"),
        "horizon_days": ext.get("horizon_days") or 7,
        "stock_query": ext.get("stock_query"),
    })
    return state

def order_status_node(state: Dict[str, Any]):
    if not state.get("order_id"):
        state["error"] = "Missing order id"
        return state
    res = get_order_status(int(state["order_id"]))
    state["sql_result"] = res
    return state

def stock_forecast_node(state: Dict[str, Any]):
    sku = state.get("sku")
    horizon = int(state.get("horizon_days") or 7)
    if not sku:
        state["error"] = "Missing SKU"
        return state
    res = forecast_sku(sku, horizon_days=horizon)
    state["sql_result"] = res
    return state

def inventory_node(state: Dict[str, Any]):
    q = (state.get("stock_query") or "all").lower()
    if q == "in_stock":
        res = list_in_stock()
    elif q == "out_of_stock":
        res = list_out_of_stock()
    else:
        res = list_in_stock() + list_out_of_stock()
    state["sql_result"] = res
    return state

def rag_node(state: Dict[str, Any]):
    k = int(state.get("top_k") or 3)
    docs = retrieve_docs(state["question"], top_k=k)
    state["docs"] = [{"snippet": d.page_content[:300], "metadata": getattr(d, "metadata", {})} for d in docs]
    return state

def compose_node(state: Dict[str, Any], llm: ChatCohere):
    sys = (
        "You are Velmora StoreOps assistant. Answer briefly with any SQL-backed facts and cite policy snippets when used. "
        "If policy docs were retrieved, include 1 short quote with section/source if available. "
        "If SQL result is a list of items (inventory), summarise the items."
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys),
        ("user", "Question: {q}\nSQL result: {sql}\nDocs: {docs}")
    ])
    chain = prompt | llm
    ans = chain.invoke({"q": state["question"], "sql": state.get("sql_result"), "docs": state.get("docs")})
    state["answer"] = ans.content if hasattr(ans, "content") else str(ans)
    cites = []
    for d in state.get("docs", []):
        meta = d.get("metadata", {})
        src = meta.get("source") or meta.get("file") or "policy"
        cites.append(src)
    state["citations"] = cites[:3]
    return state
