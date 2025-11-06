from __future__ import annotations
from typing import Any, Dict

# ---------- Safe imports ----------
_DEPS_OK = True
_ERR: Exception | None = None
try:
    from langgraph.graph import StateGraph, END
    from langchain_cohere import ChatCohere
    from ..config import MODEL_NAME, get_cohere_key
    from .state import OpsState
    from .nodes import (
        classifier_node,
        order_status_node,
        stock_forecast_node,
        inventory_node,
        rag_node,
        compose_node,
    )
except Exception as e:
    _DEPS_OK = False
    _ERR = e

# ---------- Stub ----------
class _DummyGraph:
    def __init__(self, err: Exception | None = None):
        self.err = err
    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        q = (state or {}).get("question", "")
        top_k = int((state or {}).get("top_k", 3))
        msg = "(Graph stub) "
        if self.err:
            msg += f"[missing deps: {type(self.err).__name__}] "
        msg += f"I don't have indexed docs yet, but I received your question: '{q}'. top_k={top_k}"
        return {
            "intent": "generic_question",
            "order_id": None,
            "sku": None,
            "horizon_days": None,
            "answer": msg,
            "sql_result": None,
            "citations": [{"source": "vectorstore", "note": "Stub graph; plug in real retriever later."}],
            "error": None if not self.err else str(self.err),
        }

# ---------- Real builder ----------
def _build_real_graph():
    llm = ChatCohere(
        model=MODEL_NAME,
        temperature=0,
        cohere_api_key=get_cohere_key(),
    )

    g = StateGraph(OpsState)

    def _classify(state: Dict[str, Any]): return classifier_node(state, llm)
    def _compose(state: Dict[str, Any]):   return compose_node(state, llm)

    g.add_node("classify", _classify)
    g.add_node("order_status", order_status_node)
    g.add_node("stock_forecast", stock_forecast_node)
    g.add_node("inventory", inventory_node)
    g.add_node("rag", rag_node)
    g.add_node("compose", _compose)

    g.set_entry_point("classify")

    def _route(state: Dict[str, Any]) -> str:
        intent = (state or {}).get("intent", "unknown")
        if intent == "order_status":   return "order_status"
        if intent == "stock_forecast": return "stock_forecast"
        if intent == "inventory":      return "inventory"
        return "rag"

    g.add_conditional_edges("classify", _route, {
        "order_status": "order_status",
        "stock_forecast": "stock_forecast",
        "inventory": "inventory",
        "rag": "rag",
    })

    g.add_edge("order_status", "compose")
    g.add_edge("stock_forecast", "compose")
    g.add_edge("inventory", "compose")
    g.add_edge("rag", "compose")
    g.add_edge("compose", END)

    compiled = g.compile()

    class _Wrapper:
        def __init__(self, cg): self.cg = cg
        def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
            try:
                out = self.cg.invoke(state or {})
                if hasattr(out, "dict"): out = out.dict()
                elif not isinstance(out, dict):
                    try: out = dict(out)
                    except Exception: out = {"answer": str(out)}
                return {
                    "intent": out.get("intent"),
                    "order_id": out.get("order_id"),
                    "sku": out.get("sku"),
                    "horizon_days": out.get("horizon_days"),
                    "answer": out.get("answer"),
                    "sql_result": out.get("sql_result"),
                    "citations": out.get("citations", []),
                    "error": out.get("error"),
                }
            except Exception as e:
                return {
                    "intent": None, "order_id": None, "sku": None, "horizon_days": None,
                    "answer": None, "sql_result": None, "citations": [], "error": f"graph.invoke failed: {e}",
                }

    return _Wrapper(compiled)

def build_graph():
    if not _DEPS_OK:
        return _DummyGraph(err=_ERR)
    try:
        return _build_real_graph()
    except Exception as e:
        return _DummyGraph(err=e)
