"""Baseline heuristic policies. Both spend the same budget as the optimizers."""
import numpy as np


def _spend(order_comps, acts, budget, max_week=3):
    u = np.zeros(len(acts["kind"]))
    left = budget
    for c in order_comps:
        idx = np.where(acts["comp"] == c)[0]
        exp = [j for j in idx if acts["kind"][j] == 0 and acts["week"][j] <= max_week]
        other = [j for j in idx if acts["kind"][j] != 0]
        other.sort(key=lambda j: (acts["kind"][j] != 2, acts["week"][j]))  # alternates first, earliest first
        for j in (exp if exp else other):
            if left <= 1e-9:
                return u
            qty = min(acts["cap"][j], left / acts["cost"][j]) if acts["cost"][j] > 0 else acts["cap"][j]
            u[j] = qty
            left -= qty * acts["cost"][j]
    return u


def worst_supplier_policy(m, acts, scorecard, budget):
    """Prioritize suppliers with the highest historical late rate."""
    rate = scorecard.set_index("supplier_id").late_rate
    sup_ids = m.suppliers.supplier_id.to_numpy()
    order = []
    for sid in rate.sort_values(ascending=False).index:
        s = list(sup_ids).index(sid)
        comps = np.where(m.sup_of == s)[0]
        order += sorted(comps, key=lambda c: -m.req_base[c] * m.unit_cost[c])
    return _spend(order, acts, budget)


def lowest_cover_policy(m, acts, budget):
    """Prioritize components with the fewest weeks of inventory cover."""
    order = np.lexsort((-m.req_base * m.unit_cost, m.cover_weeks))
    return _spend(list(order), acts, budget)
