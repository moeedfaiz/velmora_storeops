# StoreOps Copilot (Velmora)

Agentic AI assistant for retail operations using **LangChain + LangGraph + RAG + tool-calling + SQLite**.

## Features
- Ask natural-language questions like:
  - “Where’s order #1003? What items and status?”
  - “Predict stock-out risk for SKU VLM-TEE-001 in the next 7 days.”
  - “What’s our return policy on worn items?” (RAG over SOP docs)
- Tools: SQL (SQLite) execution, stock-out forecasting, email/SMS stubs, issue ticketing.
- All answers are auditable: SQL used + document citations logged.

## Quickstart

1) **Install deps**
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
```

2) **Set environment**
```bash
cp .env.example .env
# put your OPENAI_API_KEY in .env (or use an Azure/OpenRouter provider and edit app/config.py)
```

3) **Initialize SQLite with sample data**
```bash
python app/setup_db.py
```

4) **Ingest SOP/Policy docs into vector store**
```bash
# put .md/.txt/.pdf docs in data/sops first (some samples are already there)
python app/ingest.py
```

5) **Run the API**
```bash
uvicorn app.api.server:app --reload --port 8000
```

6) **Try it**
```bash
# Order status
curl -s -X POST "http://127.0.0.1:8000/ask" -H "Content-Type: application/json" -d '{"question":"where is order #1003"}' | jq

# Stock-out forecast (7 days)
curl -s -X POST "http://127.0.0.1:8000/ask" -H "Content-Type: application/json" -d '{"question":"predict stock-out for VLM-TEE-001 next 7 days"}' | jq

# Policy RAG
curl -s -X POST "http://127.0.0.1:8000/ask" -H "Content-Type: application/json" -d '{"question":"what is the return policy for worn items?"}' | jq
```

---

## Project layout
```
velmora_storeops/
  ├─ app/
  │  ├─ api/server.py              # FastAPI endpoints
  │  ├─ config.py                  # envs
  │  ├─ db.py                      # SQLite helpers
  │  ├─ setup_db.py                # init & seed
  │  ├─ ingest.py                  # build vector store from /data/sops
  │  ├─ tools/
  │  │   ├─ sql_tools.py           # SQL-backed tools (order status, inventory)
  │  │   ├─ comms_tools.py         # email/sms stubs
  │  │   └─ ticket_tools.py        # issue ticket tool (DB-backed)
  │  ├─ util/forecasting.py        # simple demand/stock-out forecast
  │  └─ graph/
  │      ├─ state.py               # Typed dict for graph state
  │      ├─ nodes.py               # classifier, SQL, RAG, compose nodes
  │      └─ build_graph.py         # assemble LangGraph
  ├─ data/sops/*                   # policy/SOP docs for RAG
  ├─ vectorstore/                  # Chroma persistence
  ├─ requirements.txt
  ├─ .env.example
  └─ README.md
```

# Velmora StoreOps

**AI-powered retail operations stack**: FastAPI API, Streamlit dashboard, LangGraph (Cohere) copilot with RAG over SOP docs, SQLite persistence, and Redis. Run locally or in prod with Docker Compose.

## ✨ Features

- **API (FastAPI)** for Customers, Products, Inventory, Orders, Analytics
- **Chat Copilot** (LangGraph + Cohere) with intents:
  - `order_status` — track an order by ID
  - `stock_forecast` — forecast stock-out risk for a SKU over N days
  - `inventory` — list in-stock/out-of-stock items
  - `policy_q` — answer questions from SOP docs (RAG)
- **RAG** over markdown/PDF SOPs (`/app/data/sops` → FAISS index at `/data/vectorstore`)
- **Streamlit UI**: Orders / Customers / Inventory / Analytics / Chat
- **Observability**: `/health`, `/info`, optional Prometheus metrics
- **Batteries included**: SQLite DB, Redis, Dockerized for parity

## 🧱 Stack

- **Backend**: FastAPI (Uvicorn), SQLite, Redis
- **AI**: LangGraph, LangChain, Cohere (chat + embeddings)
- **RAG**: FAISS (local), optional Chroma
- **UI**: Streamlit
- **Infra**: Docker, Docker Compose

## 🚀 Quick Start (Docker)

1) Copy `.env.example` → `.env` and fill your keys:
```env
# LLM
LLM_PROVIDER=cohere
MODEL_NAME=command-a-03-2025
EMBEDDINGS_BACKEND=cohere
EMBED_MODEL=embed-english-v3.0
COHERE_API_KEY=YOUR-KEY-HERE

# Paths (inside containers)
VECTOR_DIR=/data/vectorstore
SOPS_DIR=/app/data/sops
DB_PATH=/data/velmora.db

# API
API_HOST=0.0.0.0
API_PORT=8000
API_BASE=http://api:8000

# Redis
REDIS_URL=redis://redis:6379/0

# Observability (optional)
PROMETHEUS_ENABLE=1
SENTRY_DSN=
SENTRY_TRACES=0.05




Development (without Docker)
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-api.txt

# env
cp .env.example .env   # fill COHERE_API_KEY, paths, etc.

# run API
uvicorn app.api.server:app --host 0.0.0.0 --port 8000 --reload

# run UI
API_BASE=http://localhost:8000 python -m streamlit run app/ui_app.py

## Notes
- Uses Cohere models via `langchain-cohere`. Swap providers in `app/api/server.py` easily.
- For production: add auth to FastAPI, HTTPS, and move Chroma to a persistent volume.
- Extend tools to integrate with real email/sms/ticket platforms later.
