# app/graph/state.py
from typing import TypedDict, List, Optional, Any, Literal

class OpsState(TypedDict, total=False):
    question: str
    intent: Literal["order_status","stock_forecast","inventory","policy_q","unknown"]
    order_id: Optional[int]
    sku: Optional[str]
    horizon_days: int
    stock_query: Optional[str]   # in_stock | out_of_stock | all
    top_k: int                   # for RAG
    sql_result: Any
    docs: List[Any]
    answer: str
    citations: List[str]
    error: str
