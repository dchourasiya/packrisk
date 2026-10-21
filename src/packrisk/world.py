"""Scenario catalog and Monte Carlo sampling of supply realizations.

A realization describes, for every component and every scheduled weekly lot,
when and how much of that lot actually arrives. It is stored as transfer
matrices G[c, t, tau] = fraction of a unit scheduled in week t that arrives
usable in week tau (arrivals after the horizon are dropped).

Two parameter sets exist for every disruption:
  * prior  - what the planner believes (used for planning samples)
  * truth  - how the simulated world actually behaves (used for evaluation)
For development scenarios they are identical; for held-out scenarios the truth
differs, which tests the planner under wrong assumptions.
"""
import numpy as np

EVENT_PRIOR = {
    "lane_delay": {"days_mean": 14.0, "days_sd": 5.0, "durations": [2, 3, 4], "dur_p": [0.3, 0.4, 0.3]},
    "capacity_cut": {"cut_lo": 0.4, "cut_hi": 0.8, "durations": [1, 2, 3], "dur_p": [0.3, 0.4, 0.3]},
    "tier2_cut": {"cut_lo": 0.2, "cut_hi": 0.6, "durations": [4, 6, 8], "dur_p": [0.3, 0.4, 0.3]},
    "quality_hold": {"hold_weeks": [1, 2, 3], "hold_p": [0.3, 0.4, 0.3], "scrap_lo": 0.1,
                     "scrap_hi": 0.4, "durations": [1, 2], "dur_p": [0.5, 0.5]},
}

SCENARIOS = {
    "D1": dict(name="Asia ocean-lane port congestion", split="development",
               desc="All L1 ocean shipments delayed; hits both cell suppliers, electronics, contactors, fire barriers, fasteners.",
               events=[dict(type="lane_delay", target="L1", start=0)]),
    "D2": dict(name="Semiconductor allocation", split="development",
               desc="Tier-2 semiconductor shortage cuts output at the electronics and sensor suppliers together.",
               events=[dict(type="tier2_cut", target="T2", start=0)]),
    "D3": dict(name="Enclosure plant outage", split="development",
               desc="Single-supplier capacity loss at the enclosure supplier.",
               events=[dict(type="capacity_cut", target="S16", start=1)]),
    "D4": dict(name="TIM quality hold", split="development",
               desc="Thermal interface material lots quarantined, part scrapped.",
               events=[dict(type="quality_hold", target=["C25"], start=0)]),
    "D5": dict(name="Demand mix shift", split="development",
               desc="Long Range plan +20%, Standard Range -10%; purchase orders still follow the old plan.",
               events=[dict(type="mix_shift", SR=0.9, LR=1.2)]),
    "D6": dict(name="Port congestion + TIM hold", split="development",
               desc="D1 and D4 at the same time.",
               events=[dict(type="lane_delay", target="L1", start=0),
                       dict(type="quality_hold", target=["C25"], start=0)]),
    "H1": dict(name="Europe ocean-lane disruption", split="held-out",
               desc="L4 delays longer and more severe than the planner's prior.",
               events=[dict(type="lane_delay", target="L4", start=0,
                            truth={"days_mean": 21.0, "days_sd": 6.0, "durations": [4], "dur_p": [1.0]})]),
    "H2": dict(name="Copper shortage", split="held-out",
               desc="Tier-2 copper cut hits busbar and harness suppliers together; shorter than prior expects.",
               events=[dict(type="tier2_cut", target="T1", start=0,
                            truth={"cut_lo": 0.5, "cut_hi": 0.5, "durations": [3], "dur_p": [1.0]})]),
    "H3": dict(name="Long adhesive quality hold", split="held-out",
               desc="4-week hold with 50% scrap on structural adhesive, outside the planner's prior.",
               events=[dict(type="quality_hold", target=["C38"], start=0,
                            truth={"hold_weeks": [4], "hold_p": [1.0], "scrap_lo": 0.5, "scrap_hi": 0.5,
                                   "durations": [2], "dur_p": [1.0]})]),
    "H4": dict(name="Port congestion, 30% worse", split="held-out",
               desc="D1, but event delays and background lateness are 30% worse than the planner assumes.",
               events=[dict(type="lane_delay", target="L1", start=0,
                            truth={"days_mean": 18.2, "days_sd": 6.5})],
               world_stress={"lateness_mult": 1.3}),
    "H5": dict(name="Multi-event combination", split="held-out",
               desc="Mexico truck-lane delay + connector supplier outage + potting foam hold, together.",
               events=[dict(type="lane_delay", target="L2", start=0),
                       dict(type="capacity_cut", target="S11", start=2),
                       dict(type="quality_hold", target=["C39"], start=1)]),
}


def _event_params(ev, mode):
    pr = dict(EVENT_PRIOR[ev["type"]])
    if mode == "truth":
        pr.update(ev.get("truth", {}))
    return pr


def sample_realization(rng, scen_id, m, params, mode="prior", corr=True):
    scen = SCENARIOS[scen_id]
    H, C, S = params["horizon_weeks"], m.C, m.S
    lanes = m.lanes.lane_id.tolist()
    tier2 = m.tier2.tier2_id.tolist()
    sup_ids = m.suppliers.supplier_id.tolist()
    comp_ids = m.components.component_id.tolist()
    lat_mult = scen.get("world_stress", {}).get("lateness_mult", 1.0) if mode == "truth" else 1.0

    plan = np.vstack([np.full(H, params["plan"]["SR"], float), np.full(H, params["plan"]["LR"], float)])
    cap_mult = np.ones((S, H))
    event_days = np.zeros((C, H))
    hold = np.zeros((C, H), int)
    scrap = np.zeros((C, H))
    meta = []

    for ev in scen["events"]:
        if ev["type"] == "mix_shift":
            plan[0] *= ev["SR"]
            plan[1] *= ev["LR"]
            meta.append({"type": "mix_shift"})
            continue
        pr = _event_params(ev, mode)
        dur = int(rng.choice(pr["durations"], p=pr["dur_p"]))
        wk = np.arange(ev["start"], min(ev["start"] + dur, H))
        if ev["type"] == "lane_delay":
            li = lanes.index(ev["target"])
            sups = np.where(m.lane_of_sup == li)[0]
            shared = max(0.0, rng.normal(pr["days_mean"], pr["days_sd"]))
            per_sup = {s: (shared if corr else max(0.0, rng.normal(pr["days_mean"], pr["days_sd"])))
                       for s in sups}
            for c in np.where(m.lane_of == li)[0]:
                event_days[c, wk] += per_sup[m.sup_of[c]]
            meta.append({"type": "lane_delay", "duration": dur, "days": shared})
        elif ev["type"] == "capacity_cut":
            si = sup_ids.index(ev["target"])
            cut = rng.uniform(pr["cut_lo"], pr["cut_hi"])
            cap_mult[si, wk] *= (1 - cut)
            meta.append({"type": "capacity_cut", "duration": dur, "cut": cut})
        elif ev["type"] == "tier2_cut":
            ti = tier2.index(ev["target"])
            shared = rng.uniform(pr["cut_lo"], pr["cut_hi"])
            for si in np.where(m.tier2_of_sup == ti)[0]:
                cut = shared if corr else rng.uniform(pr["cut_lo"], pr["cut_hi"])
                cap_mult[si, wk] *= (1 - cut)
            meta.append({"type": "tier2_cut", "duration": dur, "cut": shared})
        elif ev["type"] == "quality_hold":
            hw = int(rng.choice(pr["hold_weeks"], p=pr["hold_p"]))
            sc = rng.uniform(pr["scrap_lo"], pr["scrap_hi"])
            for cid in ev["target"]:
                c = comp_ids.index(cid)
                hold[c, wk] = np.maximum(hold[c, wk], hw)
                scrap[c, wk] = 1 - (1 - scrap[c, wk]) * (1 - sc)
            meta.append({"type": "quality_hold", "duration": dur, "hold_weeks": hw, "scrap": sc})

    # Background lateness (calibrated per lane, scaled by supplier reliability)
    lat = params["lateness"]
    p_late = np.array([lat[lanes[l]]["p_late"] for l in m.lane_of])
    mu = np.log([lat[lanes[l]]["median_days"] for l in m.lane_of])
    sig = np.array([lat[lanes[l]]["sigma"] for l in m.lane_of])
    sup_mult = m.suppliers.lateness_multiplier.to_numpy(float)[m.sup_of]
    p_late_c = np.minimum(0.95, p_late * sup_mult * lat_mult)
    late = rng.random((C, H)) < p_late_c[:, None]
    late_days = np.where(late, np.exp(rng.normal(mu[:, None], sig[:, None], (C, H))) * lat_mult, 0.0)

    # Background shocks: shared per lane-week (correlated) or per supplier-week (independent)
    p_sh, med, ssig = params["lane_shock_prob"], params["lane_shock_median_days"], params["lane_shock_sigma"]
    if corr:
        occ = rng.random((len(lanes), H)) < p_sh
        mag = np.exp(rng.normal(np.log(med), ssig, (len(lanes), H)))
        shock_c = (occ * mag)[m.lane_of]
    else:
        occ = rng.random((S, H)) < p_sh
        mag = np.exp(rng.normal(np.log(med), ssig, (S, H)))
        shock_c = (occ * mag)[m.sup_of]

    dow = rng.integers(0, 7, (C, H))
    delay_w = np.floor((dow + late_days + shock_c + event_days) / 7.0).astype(int)

    # Background quality holds on flagged components
    qh_bg = (rng.random((C, H)) < params["qh_prob"]) & m.qh[:, None]
    bg_hold = rng.integers(params["qh_hold_weeks"][0], params["qh_hold_weeks"][1] + 1, (C, H))
    bg_scrap = rng.uniform(params["qh_scrap"][0], params["qh_scrap"][1], (C, H))
    hold = np.maximum(hold, np.where(qh_bg, bg_hold, 0))
    scrap = 1 - (1 - scrap) * (1 - np.where(qh_bg, bg_scrap, 0.0))

    # Partial shipments: fraction f arrives on time-of-arrival, remainder one week later
    part = rng.random((C, H)) < params["partial_prob"]
    f = np.where(part, rng.uniform(*params["partial_fraction"], (C, H)), 1.0)

    y = cap_mult[m.sup_of] * (1 - scrap)  # usable yield of each lot
    cc, tt = np.meshgrid(np.arange(C), np.arange(H), indexing="ij")

    def transfer(arrival_week):
        G = np.zeros((C, H, H + 1))
        a1 = np.clip(arrival_week, 0, H)
        a2 = np.clip(arrival_week + 1, 0, H)
        np.add.at(G, (cc, tt, a1), f * y)
        np.add.at(G, (cc, tt, a2), (1 - f) * y)
        return G[:, :, :H]

    G_base = transfer(tt + delay_w + hold)   # normal shipping: lateness + lane events + holds
    G_exp = transfer(tt + hold)              # expedited: bypasses lateness and lane events, not holds

    ga = np.zeros((C, H, H))
    has_alt = np.where(m.alt_of >= 0)[0]
    for c in has_alt:
        ga[c, np.arange(H), np.arange(H)] = cap_mult[m.alt_of[c]]

    sched = np.repeat(m.req_base[:, None], H, axis=1)
    base_arr = np.einsum("ct,ctu->cu", sched, G_base)
    return {
        "scenario": scen_id, "plan": plan, "base_arr": base_arr,
        "G": {"expedite": G_exp - G_base, "extra": G_base, "alternate": ga},
        "meta": meta,
    }


def expected_realization(samples):
    """Mean-value scenario used by the deterministic planner."""
    out = {"scenario": samples[0]["scenario"], "plan": samples[0]["plan"],
           "base_arr": np.mean([s["base_arr"] for s in samples], axis=0),
           "G": {k: np.mean([s["G"][k] for s in samples], axis=0) for k in samples[0]["G"]},
           "meta": [{"type": "expected_value"}]}
    return out
