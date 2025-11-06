import sqlite3, pathlib, datetime, random
from .config import DB_PATH

SCHEMA = pathlib.Path(__file__).with_name("schema.sql")
SEED   = pathlib.Path(__file__).with_name("seed_data.sql")

def init_db():
    path = pathlib.Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.executescript(SEED.read_text(encoding="utf-8"))
        # synthetic stock_moves over 14 days
        skus = ["VLM-TEE-001","VLM-TEE-002","VLM-TEE-003","VLM-JNS-001"]
        today = datetime.date.today()
        for d in range(14, 0, -1):
            day = today - datetime.timedelta(days=d)
            for sku in skus:
                sales = random.randint(0, 4)
                for _ in range(sales):
                    conn.execute("INSERT INTO stock_moves(sku, delta, reason, created_at) VALUES (?,?,?,?)",
                                 (sku, -1, "sale", f"{day} 10:00:00"))
        conn.commit()
    finally:
        conn.close()
    print(f"Initialized DB at {path}")

if __name__ == "__main__":
    init_db()
