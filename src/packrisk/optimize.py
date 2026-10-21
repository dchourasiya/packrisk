"""Planning and execution models (linear programs solved with HiGHS via SciPy).

Mitigation actions are decided at week 0 for the 8-week horizon:
  expedite  - move part of a scheduled lot to a fast mode (air / team driver);
              it then ignores lateness and lane disruptions, not supplier
              capacity cuts or quality holds
  extra     - order additional units from the primary supplier at normal lead
              time (exposed to the same disruptions as normal lots)
  alternate - buy from the approved alternate supplier after its ramp lag
              (exposed to the alternate's own capacity and tier-2 risks)

Planning objective: mitigation cost + penalty x lost packs (end of horizon)
+ backlog penalty x pack-weeks behind plan, with a hard budget.
  deterministic : one mean-value scenario
  stochastic    : sample average over prior scenarios
  cvar          : (1-lambda) * mean + lambda * CVaR_alpha of lost-pack cost
  oracle        : the realized scenario itself (same constraints, knows future)
"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

KINDS = ["expedite", "extra", "alternate"]


def build_actions(m, params):
    H = params["horizon_weeks"]
    lanes = m.lanes
    rows = []
    for c in range(m.C):
        L = lanes.iloc[m.lane_of[c]]
        uc, req = m.unit_cost[c], m.req_base[c]
        if L.expedite_cost_share > 0:
            for t in range(H):
                rows.append((0, c, t, req, L.expedite_cost_share * uc))
        for t in range(int(L.base_lead_weeks), H):
            rows.append((1, c, t, params["extra_capacity_share"] * req,
                         params["extra_holding_cost_share"] * uc))
        if m.alt_of[c] >= 0:
            alt_lane = lanes.iloc[m.lane_of_sup[m.alt_of[c]]]
            start = params["alt_ramp_weeks"] + params["alt_transit_weeks"]
            cost = (params["alt_premium_share"] + alt_lane.expedite_cost_share) * uc
            for t in range(start, H):
                rows.append((2, c, t, params["alt_capacity_share"] * req, cost))
    a = np.array(rows, float)
    return {"kind": a[:, 0].astype(int), "comp": a[:, 1].astype(int), "week": a[:, 2].astype(int),
            "cap": a[:, 3], "cost": a[:, 4]}


def _p_block(m, H):
    """Rows (c, t), cols (v, tau): q[c, v] if tau <= t (cumulative usage)."""
    C = m.C
    blk = np.zeros((C * H, 2 * H))
    tri = np.tril(np.ones((H, H)))
    for v in range(2):
        blk[:, v * H:(v + 1) * H] = np.kron(m.q[:, v][:, None], tri)
    return blk


def _action_arrivals(real, acts):
    """(n_actions, H) arrivals per unit of each action in one realization."""
    out = np.zeros((len(acts["kind"]), real["base_arr"].shape[1]))
    for k, name in enumerate(KINDS):
        idx = np.where(acts["kind"] == k)[0]
        out[idx] = real["G"][name][acts["comp"][idx], acts["week"][idx], :]
    return out


def solve_plan(reals, acts, m, params, budget, cvar=None):
    H, C = params["horizon_weeks"], m.C
    S, n1, nP = len(reals), len(acts["kind"]), 2 * H
    pen = params["penalty_per_lost_pack"]
    hb = params["backlog_penalty_per_pack_week"]
    pval = np.tile(pen + hb * (H - np.arange(H)), 2)  # value of one pack built in week tau
    lam = cvar[1] if cvar else 0.0
    alpha = cvar[0] if cvar else None
    nvar = n1 + S * nP + ((1 + S) if cvar else 0)
    eta = n1 + S * nP

    P = _p_block(m, H)
    P_r, P_c = np.nonzero(P)
    P_v = P[P_r, P_c]
    tri = np.tril(np.ones((H, H)))

    rows, cols, vals, b = [], [], [], []
    r0 = 0
    for s, real in enumerate(reals):
        pc0 = n1 + s * nP
        # inventory: usage(p) - arrivals(u) <= I0 + cumulative base arrivals
        rows.append(r0 + P_r); cols.append(pc0 + P_c); vals.append(P_v)
        cumA = np.cumsum(_action_arrivals(real, acts), axis=1)  # (n1, H)
        jj, tt = np.nonzero(cumA)
        rows.append(r0 + acts["comp"][jj] * H + tt); cols.append(jj); vals.append(-cumA[jj, tt])
        b.append((m.I0[:, None] + np.cumsum(real["base_arr"], axis=1)).ravel())
        r0 += C * H
        # cumulative production <= cumulative plan
        for v in range(2):
            tr, tc = np.nonzero(tri)
            rows.append(r0 + tr); cols.append(pc0 + v * H + tc); vals.append(np.ones(len(tr)))
            b.append(np.cumsum(real["plan"][v]))
            r0 += H
        # line capacity
        for v in range(2):
            rows.append(r0 + np.arange(H)); cols.append(pc0 + v * H + np.arange(H)); vals.append(np.ones(H))
        b.append(np.full(H, params["line_capacity"], float))
        r0 += H
        if cvar:
            # loss_s = pen*(plan - sum p) + hb*sum_t(cumplan - cump);  loss_s - eta - z_s <= 0
            const = pen * real["plan"].sum() + hb * np.cumsum(real["plan"], axis=1).sum()
            rows.append(np.full(nP + 2, r0))
            cols.append(np.r_[pc0 + np.arange(nP), eta, eta + 1 + s])
            vals.append(np.r_[-pval, -1.0, -1.0])
            b.append(np.array([-const]))
            r0 += 1
    # budget
    rows.append(np.full(n1, r0)); cols.append(np.arange(n1)); vals.append(acts["cost"])
    b.append(np.array([budget]))
    r0 += 1

    A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                   shape=(r0, nvar)).tocsr()
    b = np.concatenate(b)

    c = np.zeros(nvar)
    c[:n1] = acts["cost"]
    c[n1:n1 + S * nP] = -(1 - lam) * np.tile(pval, S) / S
    if cvar:
        c[eta] = lam
        c[eta + 1:] = lam / ((1 - alpha) * S)
    bounds = ([(0, cap) for cap in acts["cap"]] + [(0, None)] * (S * nP)
              + ([(None, None)] + [(0, None)] * S if cvar else []))
    res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(f"planning LP failed: {res.message}")
    u = res.x[:n1].copy()
    u[u < 1e-6] = 0.0
    return u


_EXEC_CACHE = {}


def execute(real, u, acts, m, params):
    """Schedule production optimally against the supply that actually arrives."""
    H, C = params["horizon_weeks"], m.C
    key = (id(m), H)
    if key not in _EXEC_CACHE:
        P = _p_block(m, H)
        tri = np.tril(np.ones((H, H)))
        cum = np.zeros((2 * H, 2 * H))
        cum[:H, :H] = tri
        cum[H:, H:] = tri
        capm = np.hstack([np.eye(H), np.eye(H)])
        _EXEC_CACHE[key] = np.vstack([P, cum, capm])
    A = _EXEC_CACHE[key]

    arr = real["base_arr"].copy()
    contrib = u[:, None] * _action_arrivals(real, acts)
    np.add.at(arr, acts["comp"], contrib)
    cumarr = np.cumsum(arr, axis=1)
    b = np.concatenate([(m.I0[:, None] + cumarr).ravel(),
                        np.cumsum(real["plan"][0]), np.cumsum(real["plan"][1]),
                        np.full(H, params["line_capacity"], float)])
    pen, hb = params["penalty_per_lost_pack"], params["backlog_penalty_per_pack_week"]
    w = np.tile(pen + hb * (H - np.arange(H)), 2)  # same production value as the planner
    res = linprog(-w, A_ub=A, b_ub=b, bounds=[(0, None)] * (2 * H), method="highs")
    if res.status != 0:
        raise RuntimeError(f"execution LP failed: {res.message}")
    p = res.x.reshape(2, H)
    cump = np.cumsum(p, axis=1)
    inv_end = m.I0[:, None] + cumarr - (m.q[:, 0][:, None] * cump[0] + m.q[:, 1][:, None] * cump[1])

    plan = real["plan"]
    cumplan = np.cumsum(plan, axis=1)
    built_prev = np.hstack([np.zeros((2, 1)), cump[:, :-1]])
    backlog = cumplan - built_prev
    gating = []
    short_weeks, first_short = 0, None
    for t in range(H):
        want = min(params["line_capacity"], backlog[:, t].sum())
        if p[:, t].sum() < want - 0.5:
            short_weeks += 1
            first_short = t if first_short is None else first_short
            for v in range(2):
                if p[v, t] < backlog[v, t] - 0.5:
                    used = np.where(m.q[:, v] > 0)[0]
                    ratio = inv_end[used, t] / m.q[used, v]
                    gating.append((t, v, int(used[np.argmin(ratio)])))
    lost = max(0.0, plan.sum() - p.sum())
    backlog_pw = float(np.clip(cumplan - cump, 0, None).sum())
    cost = float(u @ acts["cost"])
    return {"p": p, "inv_end": inv_end, "lost": float(lost), "built": float(p.sum()),
            "plan": float(plan.sum()), "cost": cost, "backlog_pack_weeks": backlog_pw,
            "objective": float(pen * lost + hb * backlog_pw + cost),
            "shortage_weeks": short_weeks, "first_shortage_week": first_short, "gating": gating}
