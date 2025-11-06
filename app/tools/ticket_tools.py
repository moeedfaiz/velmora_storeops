from typing import Dict, Any
from ..db import exec_sql, one

def open_ticket(title: str, body: str) -> Dict[str, Any]:
    exec_sql("INSERT INTO tickets(title, body, status) VALUES (:t,:b,'open')", t=title, b=body)
    row = one("SELECT id, title, body, status, created_at FROM tickets ORDER BY id DESC LIMIT 1")
    return row or {"status": "error"}
