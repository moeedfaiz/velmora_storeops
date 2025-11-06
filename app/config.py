import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env once per process
load_dotenv()

# === Cohere keys ===
def get_cohere_key() -> str | None:
    return os.getenv("CO_API_KEY") or os.getenv("COHERE_API_KEY")

# === App paths & models ===
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "app" / "app.db"))
VECTOR_DIR = os.getenv("VECTOR_DIR", str(BASE_DIR / "vectorstore"))

# Cohere chat model: 'command-r' was removed in Sep 2025; default to a current one.
MODEL_NAME = os.getenv("MODEL_NAME", "command-r-plus")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embed-english-v3.0")

def ensure_dirs() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(VECTOR_DIR).mkdir(parents=True, exist_ok=True)
