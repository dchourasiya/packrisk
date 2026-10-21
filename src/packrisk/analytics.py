"""Run the SQL analytics layer (SQLite here; the same SQL ports to DuckDB / dbt)."""
import math
import sqlite3

import pandas as pd

from .config import SQL_DIR


def run_analytics(m, receipts):
    con = sqlite3.connect(":memory:")
    con.create_function("SQRT", 1, lambda x: math.sqrt(max(x, 0.0)) if x is not None else None)
    receipts.drop(columns=["scheduled_date", "received_date", "order_date"]).to_sql("receipts", con, index=False)
    comps = m.components.copy()
    comps["alt_supplier_id"] = comps.alt_supplier_id.where(comps.alt_supplier_id.notna(), None)
    comps["tier2_id"] = comps.tier2_id.where(comps.tier2_id.notna(), None)
    comps.to_sql("components", con, index=False)
    m.suppliers.to_sql("suppliers", con, index=False)
    scorecard = pd.read_sql((SQL_DIR / "01_supplier_scorecard.sql").read_text(), con)
    scorecard.to_sql("scorecard", con, index=False)
    exposure = pd.read_sql((SQL_DIR / "02_component_exposure.sql").read_text(), con)
    shared = pd.read_sql((SQL_DIR / "03_shared_dependency.sql").read_text(), con)
    con.close()
    return {"scorecard": scorecard, "exposure": exposure, "shared": shared}
