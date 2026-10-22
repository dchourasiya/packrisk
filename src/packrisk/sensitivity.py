"""Penalty sensitivity: does the ranking of policies survive a different lost-pack penalty?

For each penalty in params["penalty_sensitivity"], every policy is re-planned with that penalty and
evaluated on the same realizations as the main run (same seeds), so only the penalty changes.
The oracle is skipped (it would need one LP per realization per penalty). Writes
outputs/powerbi/fact_penalty_sensitivity.csv.
"""
import copy
import time

import numpy as np
import pandas as pd

from .analytics import run_analytics
from .config import OUT_DIR, load_params
from .evaluate import plan_policies, sample_sets
from .history import generate_history
from .master import build_master
from .optimize import build_actions, execute
from .world import SCENARIOS


def run(verbose=True):
    t0 = time.time()
    base = load_params()
    m = build_master(base)
    acts = build_actions(m, base)
    ana = run_analytics(m, generate_history(m, base))
    B = base["budget"]

    rows = []
    for pen in base["penalty_sensitivity"]:
        params = copy.deepcopy(base)
        params["penalty_per_lost_pack"] = pen
        for k, sid in enumerate(SCENARIOS):
            prior, ev, world = sample_sets(sid, k, m, params)
            pols = plan_policies(m, acts, params, ana["scorecard"], prior, ev, B)
            for pid, u in pols.items():
                outs = [execute(r, u, acts, m, params) for r in world]
                lost = np.array([o["lost"] for o in outs])
                rows.append({"penalty_per_lost_pack": pen, "scenario_id": sid, "policy_id": pid,
                             "mean_lost_packs": lost.mean(), "p90_lost_packs": np.percentile(lost, 90),
                             "mitigation_cost": float(np.mean([o["cost"] for o in outs])),
                             "mean_objective": float(np.mean([o["objective"] for o in outs]))})
        if verbose:
            print(f"penalty ${pen:,} done ({time.time() - t0:.0f}s)", flush=True)

    pb = OUT_DIR / "powerbi"
    pb.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(pb / "fact_penalty_sensitivity.csv", index=False)
    if verbose:
        print(f"penalty sensitivity written ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    run()
