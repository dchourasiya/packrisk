"""Run every policy on every scenario, then the stress tests. Writes outputs/."""
import json
import time

import numpy as np
import pandas as pd

from .analytics import run_analytics
from .config import OUT_DIR, load_params
from .history import generate_history
from .master import VARIANTS, build_master, write_master_csvs
from .optimize import KINDS, build_actions, execute, solve_plan
from .policies import lowest_cover_policy, worst_supplier_policy
from .world import SCENARIOS, expected_realization, sample_realization

POLICIES = [
    ("P1", "Do nothing", "Keep the current inventory policy; no mitigation spend."),
    ("P2", "Worst-supplier first", "Spend the budget on suppliers with the highest historical late rate."),
    ("P3", "Lowest-cover first", "Spend the budget on components with the fewest weeks of inventory."),
    ("P4", "Deterministic LP", "Optimize against one average scenario (mean delays)."),
    ("P5", "Stochastic LP", "Optimize the expected outcome across sampled scenarios."),
    ("P6", "Stochastic LP + CVaR", "Stochastic LP that also penalizes the worst 10% of scenarios."),
    ("P7", "Oracle (perfect foresight)", "Same constraints, but knows the realized scenario. Upper bound."),
]


def plan_policies(m, acts, params, scorecard, prior, ev, budget):
    cv = (params["cvar_alpha"], params["cvar_lambda"])
    return {
        "P1": np.zeros(len(acts["kind"])),
        "P2": worst_supplier_policy(m, acts, scorecard, budget),
        "P3": lowest_cover_policy(m, acts, budget),
        "P4": solve_plan([ev], acts, m, params, budget),
        "P5": solve_plan(prior, acts, m, params, budget),
        "P6": solve_plan(prior, acts, m, params, budget, cvar=cv),
    }


def sample_sets(scen_id, k, m, params, n_eval=None, corr_world=True, corr_prior=True):
    rp = np.random.default_rng([params["seed_planner"], k])
    prior = [sample_realization(rp, scen_id, m, params, "prior", corr_prior) for _ in range(params["n_prior_samples"])]
    ev = expected_realization([sample_realization(rp, scen_id, m, params, "prior", corr_prior)
                               for _ in range(params["n_ev_samples"])])
    rw = np.random.default_rng([params["seed_world"], k])
    n = n_eval or params["n_eval_realizations"]
    world = [sample_realization(rw, scen_id, m, params, "truth", corr_world) for _ in range(n)]
    return prior, ev, world


def actions_frame(u, acts, m, scen, pol):
    idx = np.where(u > 1e-6)[0]
    return pd.DataFrame({
        "scenario_id": scen, "policy_id": pol,
        "component_id": m.components.component_id.to_numpy()[acts["comp"][idx]],
        "action": [KINDS[k] for k in acts["kind"][idx]],
        "week": acts["week"][idx] + 1,
        "quantity": np.round(u[idx], 1),
        "cost": np.round(u[idx] * acts["cost"][idx], 0),
    })


def run(verbose=True):
    t0 = time.time()
    params = load_params()
    m = build_master(params)
    write_master_csvs(m)
    acts = build_actions(m, params)
    receipts = generate_history(m, params)
    ana = run_analytics(m, receipts)
    comp_ids = m.components.component_id.to_numpy()
    H, B = params["horizon_weeks"], params["budget"]

    runs, gating_rows, gating_any, trace_rows, inv_rows, action_frames, summary = [], [], [], [], [], [], []
    for k, (sid, scen) in enumerate(SCENARIOS.items()):
        prior, ev, world = sample_sets(sid, k, m, params)
        pols = plan_policies(m, acts, params, ana["scorecard"], prior, ev, B)
        for pid, u in pols.items():
            action_frames.append(actions_frame(u, acts, m, sid, pid))
        res = {pid: [] for pid in [p[0] for p in POLICIES]}
        oracle_u = []
        for r_i, real in enumerate(world):
            u7 = solve_plan([real], acts, m, params, B)
            oracle_u.append(u7)
            for pid, u in list(pols.items()) + [("P7", u7)]:
                out = execute(real, u, acts, m, params)
                res[pid].append(out)
                runs.append({"scenario_id": sid, "policy_id": pid, "realization": r_i + 1,
                             "plan_packs": out["plan"], "built_packs": round(out["built"], 1),
                             "lost_packs": round(out["lost"], 1),
                             "attainment": out["built"] / out["plan"],
                             "backlog_pack_weeks": round(out["backlog_pack_weeks"], 1),
                             "mitigation_cost": round(out["cost"], 0),
                             "objective": round(out["objective"], 0),
                             "shortage_weeks": out["shortage_weeks"],
                             "first_shortage_week": None if out["first_shortage_week"] is None
                             else out["first_shortage_week"] + 1})
        # gating-part frequency
        n = len(world)
        for pid, outs in res.items():
            cnt = {}
            for out in outs:
                for (t, v, c) in out["gating"]:
                    cnt[(t, v, c)] = cnt.get((t, v, c), 0) + 1
            for (t, v, c), x in cnt.items():
                gating_rows.append({"scenario_id": sid, "policy_id": pid, "week": t + 1,
                                    "variant": VARIANTS[v], "component_id": comp_ids[c],
                                    "share_of_realizations": x / n})
            anyc = {}
            for out in outs:
                for c in {g[2] for g in out["gating"]}:
                    anyc[c] = anyc.get(c, 0) + 1
            for c, x in anyc.items():
                gating_any.append({"scenario_id": sid, "policy_id": pid, "component_id": comp_ids[c],
                                   "share_of_realizations_gated": x / n})
        # representative realizations: median and severe (90th percentile) do-nothing loss
        lost1 = np.array([o["lost"] for o in res["P1"]])
        reps = {"median": int(np.argmin(np.abs(lost1 - np.median(lost1)))),
                "severe (P90)": int(np.argmin(np.abs(lost1 - np.percentile(lost1, 90))))}
        action_frames.append(actions_frame(oracle_u[reps["median"]], acts, m, sid, "P7"))
        for rtype, rep in reps.items():
            for pid, outs in res.items():
                o = outs[rep]
                plan = world[rep]["plan"]
                gate = {(t, v): comp_ids[c] for (t, v, c) in o["gating"]}
                for v in range(2):
                    for t in range(H):
                        trace_rows.append({"scenario_id": sid, "policy_id": pid, "realization_type": rtype,
                                           "realization": rep + 1, "week": t + 1, "variant": VARIANTS[v],
                                           "plan_packs": plan[v, t], "built_packs": round(o["p"][v, t], 1),
                                           "cum_plan": plan[v, :t + 1].sum(),
                                           "cum_built": round(o["p"][v, :t + 1].sum(), 1),
                                           "gating_component_id": gate.get((t, v))})
                for c in range(m.C):
                    for t in range(H):
                        inv_rows.append({"scenario_id": sid, "policy_id": pid, "realization_type": rtype,
                                         "week": t + 1, "component_id": comp_ids[c],
                                         "inventory_end": round(max(o["inv_end"][c, t], 0.0), 1),
                                         "weeks_of_cover": round(max(o["inv_end"][c, t], 0.0) / m.req_base[c], 2)})
        # summary
        lost_oracle = np.mean([o["lost"] for o in res["P7"]])
        for pid, outs in res.items():
            lost = np.array([o["lost"] for o in outs])
            obj = np.array([o["objective"] for o in outs])
            cost = np.mean([o["cost"] for o in outs])
            denom = lost1.mean() - lost_oracle
            summary.append({
                "scenario_id": sid, "policy_id": pid,
                "mean_lost_packs": lost.mean(), "p90_lost_packs": np.percentile(lost, 90),
                "max_lost_packs": lost.max(),
                "plan_attainment": np.mean([o["built"] / o["plan"] for o in outs]),
                "mean_shortage_weeks": np.mean([o["shortage_weeks"] for o in outs]),
                "mean_backlog_pack_weeks": np.mean([o["backlog_pack_weeks"] for o in outs]),
                "mitigation_cost": cost, "budget_used_share": cost / B,
                "mean_objective": obj.mean(),
                "oracle_capture_share": (lost1.mean() - lost.mean()) / denom if denom > 1 else np.nan,
            })
        if verbose:
            s = {d["policy_id"]: round(d["mean_lost_packs"]) for d in summary if d["scenario_id"] == sid}
            print(f"{sid} done ({time.time() - t0:.0f}s): mean lost packs {s}", flush=True)

    summary = pd.DataFrame(summary)

    # ---- Budget sweep ----
    budget_rows = []
    for sid in params["budget_sweep_scenarios"]:
        k = list(SCENARIOS).index(sid)
        prior, ev, world = sample_sets(sid, k, m, params)
        base = np.mean([execute(r, np.zeros(len(acts["kind"])), acts, m, params)["lost"] for r in world])
        for b in params["budget_sweep"]:
            u = solve_plan(prior, acts, m, params, b)
            outs = [execute(r, u, acts, m, params) for r in world]
            orc = [execute(r, solve_plan([r], acts, m, params, b), acts, m, params)["lost"] for r in world]
            lost = np.array([o["lost"] for o in outs])
            budget_rows.append({"scenario_id": sid, "budget": b, "do_nothing_mean_lost": base,
                                "stochastic_mean_lost": lost.mean(), "stochastic_p90_lost": np.percentile(lost, 90),
                                "oracle_mean_lost": float(np.mean(orc)),
                                "mitigation_cost": float(u @ acts["cost"]),
                                "packs_protected": base - lost.mean()})
    if verbose:
        print(f"budget sweep done ({time.time() - t0:.0f}s)", flush=True)

    # ---- Correlation stress test ----
    stress_rows, corr_dist = [], []
    for sid in params["correlation_test_scenarios"]:
        k = list(SCENARIOS).index(sid)
        n = params["n_correlation_realizations"]
        _, _, w_corr = sample_sets(sid, k, m, params, n_eval=n, corr_world=True)
        _, _, w_ind = sample_sets(sid, k, m, params, n_eval=n, corr_world=False)
        zero = np.zeros(len(acts["kind"]))
        for label, w in [("correlated", w_corr), ("independent", w_ind)]:
            lost = np.array([execute(r, zero, acts, m, params)["lost"] for r in w])
            for x in lost:
                corr_dist.append({"scenario_id": sid, "world": label, "lost_packs": x})
            stress_rows += [
                {"test": "Correlation (do nothing)", "scenario_id": sid, "setting": label, "metric": "mean_lost_packs", "value": lost.mean()},
                {"test": "Correlation (do nothing)", "scenario_id": sid, "setting": label, "metric": "p90_lost_packs", "value": np.percentile(lost, 90)},
                {"test": "Correlation (do nothing)", "scenario_id": sid, "setting": label, "metric": "p95_lost_packs", "value": np.percentile(lost, 95)},
                {"test": "Correlation (do nothing)", "scenario_id": sid, "setting": label, "metric": "prob_any_loss", "value": float((lost > 0.5).mean())},
            ]
        # planner that wrongly assumes independence, evaluated in the correlated world
        prior_c, _, world_c = sample_sets(sid, k, m, params, corr_prior=True)
        prior_i, _, _ = sample_sets(sid, k, m, params, corr_prior=False)
        for label, pr in [("planner assumes correlation", prior_c), ("planner assumes independence", prior_i)]:
            u = solve_plan(pr, acts, m, params, B)
            lost = np.array([execute(r, u, acts, m, params)["lost"] for r in world_c])
            action_frames.append(actions_frame(u, acts, m, sid, "P5-indep" if "indep" in label else "P5-corr"))
            stress_rows += [
                {"test": "Planner correlation assumption", "scenario_id": sid, "setting": label, "metric": "mean_lost_packs", "value": lost.mean()},
                {"test": "Planner correlation assumption", "scenario_id": sid, "setting": label, "metric": "p90_lost_packs", "value": np.percentile(lost, 90)},
                {"test": "Planner correlation assumption", "scenario_id": sid, "setting": label, "metric": "mitigation_cost", "value": float(u @ acts["cost"])},
            ]
    if verbose:
        print(f"correlation tests done ({time.time() - t0:.0f}s)", flush=True)

    # ---- Write outputs ----
    pb = OUT_DIR / "powerbi"
    pb.mkdir(parents=True, exist_ok=True)
    m.components.to_csv(pb / "dim_component.csv", index=False)
    m.suppliers.merge(ana["scorecard"], on="supplier_id", how="left").to_csv(pb / "dim_supplier.csv", index=False)
    m.lanes.to_csv(pb / "dim_lane.csv", index=False)
    m.tier2.to_csv(pb / "dim_tier2.csv", index=False)
    pd.DataFrame([{"scenario_id": s, "name": v["name"], "split": v["split"], "description": v["desc"],
                   "sort": i + 1} for i, (s, v) in enumerate(SCENARIOS.items())]).to_csv(pb / "dim_scenario.csv", index=False)
    pd.DataFrame([{"policy_id": p, "name": n, "description": d, "sort": i + 1}
                  for i, (p, n, d) in enumerate(POLICIES)]).to_csv(pb / "dim_policy.csv", index=False)
    pd.DataFrame({"week": range(1, H + 1), "week_label": [f"W{i}" for i in range(1, H + 1)]}).to_csv(pb / "dim_week.csv", index=False)
    bom = m.components[["component_id", "qty_SR", "qty_LR"]].melt("component_id", var_name="variant", value_name="qty_per_pack")
    bom["variant"] = bom.variant.str.replace("qty_", "")
    bom[bom.qty_per_pack > 0].to_csv(pb / "fact_bom.csv", index=False)
    receipts.to_csv(pb / "fact_receipts.csv", index=False)
    ana["exposure"].to_csv(pb / "fact_component_exposure.csv", index=False)
    ana["shared"].to_csv(pb / "fact_shared_dependency.csv", index=False)
    summary.to_csv(pb / "fact_policy_evaluation.csv", index=False)
    pd.DataFrame(runs).to_csv(pb / "fact_realization_results.csv", index=False)
    pd.DataFrame(gating_rows).to_csv(pb / "fact_gating_frequency.csv", index=False)
    pd.DataFrame(gating_any).to_csv(pb / "fact_gating_component.csv", index=False)
    pd.DataFrame(trace_rows).to_csv(pb / "fact_weekly_trace.csv", index=False)
    pd.DataFrame(inv_rows).to_csv(pb / "fact_inventory_trace.csv", index=False)
    pd.concat(action_frames).to_csv(pb / "fact_actions.csv", index=False)
    pd.DataFrame(budget_rows).to_csv(pb / "fact_budget_curve.csv", index=False)
    pd.DataFrame(stress_rows).to_csv(pb / "fact_stress_tests.csv", index=False)
    pd.DataFrame(corr_dist).to_csv(OUT_DIR / "correlation_distribution.csv", index=False)
    (OUT_DIR / "run_info.json").write_text(json.dumps({
        "runtime_seconds": round(time.time() - t0, 1),
        "lateness_source": params["lateness_source"],
        "n_actions": int(len(acts["kind"])),
        "n_prior_samples": params["n_prior_samples"],
        "n_eval_realizations": params["n_eval_realizations"],
        "budget": B,
    }, indent=2))
    if verbose:
        print(f"all outputs written ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    run()
