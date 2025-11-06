from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from .config import DB_PATH

engine: Engine = create_engine(f"sqlite:///{DB_PATH}", future=True, echo=False)

def q(sql: str, **params):
    with engine.begin() as conn:
        res = conn.execute(text(sql), params)
        rows = [dict(r._mapping) for r in res.fetchall()]
    return rows

def exec_sql(sql: str, **params):
    with engine.begin() as conn:
        conn.execute(text(sql), params)

def one(sql: str, **params):
    rows = q(sql, **params)
    return rows[0] if rows else None
