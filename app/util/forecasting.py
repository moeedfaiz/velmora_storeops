from typing import Dict, Any, List
from ..db import q, one

def daily_sales_last_n_days(sku: str, days: int = 14) -> List[Dict[str, Any]]:
    sql = '''
    SELECT date(created_at) as day, SUM(-delta) as sales
    FROM stock_moves
    WHERE sku = :sku AND delta < 0 AND date(created_at) >= date('now', :offset)
    GROUP BY date(created_at)
    ORDER BY day ASC
    '''
    rows = q(sql, sku=sku, offset=f"-{days} days")
    return rows

def simple_velocity(sku: str, lookback_days: int = 14) -> float:
    rows = daily_sales_last_n_days(sku, lookback_days)
    total = sum((r.get("sales") or 0) for r in rows)
    return total / max(1, lookback_days)

def stockout_risk(sku: str, horizon_days: int = 7, lookback_days: int = 14):
    inv = one("SELECT on_hand, reorder_point, reorder_qty FROM inventory WHERE sku=:sku", sku=sku)
    if not inv:
        return {"sku": sku, "error": "Unknown SKU"}
    on_hand = int(inv["on_hand"])
    v = simple_velocity(sku, lookback_days)
    days_of_cover = (on_hand / v) if v > 0 else float("inf")
    risk = days_of_cover < horizon_days
    return {
        "sku": sku,
        "on_hand": on_hand,
        "velocity_per_day": round(v, 3),
        "horizon_days": horizon_days,
        "days_of_cover": (round(days_of_cover, 2) if v > 0 else None),
        "risk": risk,
        "reorder_point": inv["reorder_point"],
        "reorder_qty": inv["reorder_qty"],
    }
