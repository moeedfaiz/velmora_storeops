# app/routes_copilot.py
import os
from typing import List, Optional

import cohere
from fastapi import APIRouter
from pydantic import BaseModel

# Optional RAG via FAISS
from langchain_cohere import CohereEmbeddings
from langchain_community.vectorstores import FAISS

MODEL_NAME   = os.getenv("MODEL_NAME", "command-a-03-2025")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "embed-english-v3.0")
VECTOR_DIR   = os.getenv("VECTOR_DIR", "/data/vectorstore")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

co = cohere.Client(COHERE_API_KEY)

_emb = None
_vs = None
def _lazy_vs():
    """Load FAISS only if/when RAG is requested."""
    global _emb, _vs
    if _vs is None:
        _emb = CohereEmbeddings(cohere_api_key=COHERE_API_KEY, model=EMBED_MODEL)
        # FAISS stores pickled metadata; allow_dangerous_deserialization is required to load it.
        _vs = FAISS.load_local(VECTOR_DIR, _emb, allow_dangerous_deserialization=True)
    return _vs

class AskReq(BaseModel):
    question: str
    use_rag: bool = False
    top_k: int = 4

class AskResp(BaseModel):
    answer: str
    citations: List[dict] = []
    sql_result: Optional[dict] = None

router = APIRouter()

@router.post("/ask", response_model=AskResp)
def ask(req: AskReq):
    ctx = ""
    citations: List[dict] = []
    if req.use_rag:
        try:
            docs = _lazy_vs().similarity_search(req.question, k=req.top_k)
            ctx = "\n\n".join(d.page_content for d in docs)
            citations = [{"source": d.metadata.get("source", "")} for d in docs]
        except Exception:
            # If RAG fails for any reason, fall back to LLM-only.
            ctx = ""
            citations = []

    prompt = f"""You are Velmora StoreOps Copilot. Be concise and helpful.
If 'Context' is provided, ground your answer in it.

Question: {req.question}

Context:
{ctx}
"""
    resp = co.chat(model=MODEL_NAME, message=prompt)
    text = getattr(resp, "text", "") or str(resp)
    return AskResp(answer=text, citations=citations, sql_result=None)
