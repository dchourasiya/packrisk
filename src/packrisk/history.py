"""26 weeks of simulated purchase-order receipts (background noise only, no major events)."""
import numpy as np
import pandas as pd


def generate_history(m, params):
    rng = np.random.default_rng(params["seed_history"])
    W = params["history_weeks"]
    lanes = m.lanes
    lat = params["lateness"]
    sup_ids = m.suppliers.supplier_id.to_numpy()
    comp_ids = m.components.component_id.to_numpy()
    shock = {}
    for li in range(len(lanes)):
        for w in range(W):
            if rng.random() < params["lane_shock_prob"]:
                shock[(li, w)] = float(np.exp(rng.normal(np.log(params["lane_shock_median_days"]),
                                                         params["lane_shock_sigma"])))
    rows, po = [], 0
    for w in range(W):
        for c in range(m.C):
            po += 1
            li = m.lane_of[c]
            L = lanes.iloc[li]
            lp = lat[L.lane_id]
            s = m.sup_of[c]
            mult = m.suppliers.lateness_multiplier.iloc[s]
            sched = w * 7 + int(rng.integers(0, 7))
            order_day = sched - int(L.base_lead_weeks) * 7 - 7
            late = rng.random() < min(0.95, lp["p_late"] * mult)
            days = float(np.exp(rng.normal(np.log(lp["median_days"]), lp["sigma"]))) if late else 0.0
            days += shock.get((li, w), 0.0)
            held = bool(m.qh[c] and rng.random() < params["qh_prob"])
            if held:
                days += 7 * int(rng.integers(params["qh_hold_weeks"][0], params["qh_hold_weeks"][1] + 1))
            recv = sched + int(round(days))
            qty = float(m.req_base[c])
            partial = rng.random() < params["partial_prob"]
            f = rng.uniform(*params["partial_fraction"]) if partial else 1.0
            base = dict(po_id=f"PO{po:05d}", supplier_id=sup_ids[s], component_id=comp_ids[c],
                        lane_id=L.lane_id, order_day=order_day, scheduled_day=sched,
                        qty_ordered=qty, unit_cost=float(m.unit_cost[c]), quality_hold=int(held))
            rows.append({**base, "receipt_seq": 1, "received_day": recv, "qty_received": qty * f})
            if partial:
                rows.append({**base, "receipt_seq": 2, "received_day": recv + 7, "qty_received": qty * (1 - f)})
    df = pd.DataFrame(rows)
    start = pd.Timestamp("2026-04-06")
    df["scheduled_date"] = start + pd.to_timedelta(df.scheduled_day, unit="D")
    df["received_date"] = start + pd.to_timedelta(df.received_day, unit="D")
    df["order_date"] = start + pd.to_timedelta(df.order_day, unit="D")
    df["days_late"] = (df.received_day - df.scheduled_day).clip(lower=0)
    return df
