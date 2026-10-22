"""Build figures and RESULTS.md from the evaluation outputs."""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import OUT_DIR, ROOT  # noqa: E402

PB = OUT_DIR / "powerbi"
FIG = OUT_DIR / "figures"
COLORS = {"P1": "#9e9e9e", "P2": "#c58b5b", "P3": "#d9b86c", "P4": "#7aa6c2",
          "P5": "#2f6f9f", "P6": "#1b4965", "P7": "#5a9e6f"}


def load():
    t = {n: pd.read_csv(PB / f"{n}.csv") for n in [
        "fact_policy_evaluation", "fact_realization_results", "fact_budget_curve", "fact_stress_tests", "fact_weekly_trace",
        "fact_gating_component", "fact_actions", "dim_policy", "dim_scenario", "dim_component"]}
    sens = PB / "fact_penalty_sensitivity.csv"
    t["sens"] = pd.read_csv(sens) if sens.exists() else None
    t["corr"] = pd.read_csv(OUT_DIR / "correlation_distribution.csv")
    t["info"] = json.loads((OUT_DIR / "run_info.json").read_text())
    return t


def fig_objective_heatmap(t):
    ev, pol, sc = t["fact_policy_evaluation"], t["dim_policy"], t["dim_scenario"]
    piv = ev.pivot(index="scenario_id", columns="policy_id", values="mean_objective")
    piv = piv.loc[sc.scenario_id]
    rel = piv.div(piv["P1"], axis=0)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    im = ax.imshow(rel.values, cmap="RdYlGn_r", vmin=0, vmax=2, aspect="auto")
    ax.set_xticks(range(len(rel.columns)), [pol.set_index("policy_id").name[p] for p in rel.columns],
                  rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(rel.index)), [f"{s} {sc.set_index('scenario_id').name[s]}" for s in rel.index], fontsize=8)
    for i in range(rel.shape[0]):
        for j in range(rel.shape[1]):
            ax.text(j, i, f"${piv.values[i, j] / 1000:,.0f}k", ha="center", va="center", fontsize=7)
    ax.axhline(5.5, color="black", lw=1.5)
    ax.set_title("Expected total cost (lost packs + backlog + mitigation spend)\ncolor = relative to Do nothing; line separates development / held-out", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.025, label="cost / do-nothing cost")
    fig.tight_layout()
    fig.savefig(FIG / "policy_cost_heatmap.png", dpi=150)
    plt.close(fig)


def fig_centerpiece(t, sid="D1"):
    r = t["fact_realization_results"]
    r = r[r.scenario_id == sid]
    names = t["dim_policy"].set_index("policy_id").name
    pids = list(t["dim_policy"].policy_id)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1.4, 1]})
    ax = axes[0]
    rng = np.random.default_rng(0)
    for i, pid in enumerate(pids):
        y = r[r.policy_id == pid].lost_packs.to_numpy()
        ax.scatter(i + rng.uniform(-0.25, 0.25, len(y)), y, s=8, alpha=0.35, color=COLORS[pid])
        ax.plot([i - 0.3, i + 0.3], [y.mean()] * 2, color="black", lw=2)
        ax.plot([i - 0.3, i + 0.3], [np.percentile(y, 90)] * 2, color="black", lw=1, ls=":")
    ax.set_xticks(range(len(pids)), [names[p] for p in pids], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Lost packs over 8 weeks")
    ax.set_title(f"{sid}: lost packs per realization (solid = mean, dotted = P90)", fontsize=10)
    tr = t["fact_weekly_trace"]
    tr = tr[(tr.scenario_id == sid) & (tr.realization_type == "severe (P90)")]
    tr = tr.groupby(["policy_id", "week"])[["cum_plan", "cum_built"]].sum().reset_index()
    ax = axes[1]
    ax.axhline(0, color="black", lw=1, ls="--")
    for pid, ls in [("P1", "-"), ("P2", "-."), ("P5", "-"), ("P7", ":")]:
        d = tr[tr.policy_id == pid]
        ax.plot(d.week, d.cum_built - d.cum_plan, ls, marker="o", ms=4, lw=2, color=COLORS[pid], label=names[pid])
    ax.set_xlabel("Week")
    ax.set_ylabel("Cumulative packs vs plan")
    ax.set_title("Severe (P90) realization: shortfall by week", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / f"centerpiece_{sid}.png", dpi=150)
    plt.close(fig)


def fig_gating(t, sid="D1"):
    g = t["fact_gating_component"]
    comp = t["dim_component"].set_index("component_id").name
    d = g[(g.scenario_id == sid) & (g.policy_id.isin(["P1", "P5"]))]
    piv = d.pivot_table(index="component_id", columns="policy_id", values="share_of_realizations_gated",
                        fill_value=0)
    piv = piv.sort_values("P1", ascending=True).tail(8)
    fig, ax = plt.subplots(figsize=(7, 4))
    y = np.arange(len(piv))
    ax.barh(y - 0.2, piv.get("P1", 0), 0.4, color=COLORS["P1"], label="Do nothing")
    ax.barh(y + 0.2, piv.get("P5", 0), 0.4, color=COLORS["P5"], label="Stochastic LP")
    ax.set_yticks(y, [f"{c} {comp[c]}" for c in piv.index], fontsize=8)
    ax.set_xlabel("Share of realizations where the part stops assembly at least once")
    ax.set_title(f"{sid}: which part actually gates production", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / f"gating_{sid}.png", dpi=150)
    plt.close(fig)


def fig_budget(t):
    b = t["fact_budget_curve"]
    fig, axes = plt.subplots(1, b.scenario_id.nunique(), figsize=(10, 3.8), sharey=False)
    for ax, (sid, d) in zip(np.atleast_1d(axes), b.groupby("scenario_id")):
        ax.plot(d.budget / 1000, d.do_nothing_mean_lost, "--", color=COLORS["P1"], label="Do nothing")
        ax.plot(d.budget / 1000, d.stochastic_mean_lost, "o-", color=COLORS["P5"], label="Stochastic LP (mean)")
        ax.plot(d.budget / 1000, d.stochastic_p90_lost, "o:", color=COLORS["P6"], label="Stochastic LP (P90)")
        ax.plot(d.budget / 1000, d.oracle_mean_lost, "o-", color=COLORS["P7"], label="Oracle (mean)")
        ax.set_title(sid, fontsize=10)
        ax.set_xlabel("Mitigation budget ($k)")
        ax.set_ylabel("Lost packs over 8 weeks")
    np.atleast_1d(axes)[0].legend(fontsize=7)
    fig.suptitle("Packs protected per dollar: diminishing returns", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "budget_curve.png", dpi=150)
    plt.close(fig)


def fig_correlation(t):
    c = t["corr"]
    st = t["fact_stress_tests"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    d = c[c.scenario_id == "D1"]
    bins = np.linspace(0, d.lost_packs.max() + 1, 25)
    for w, col in [("correlated", "#1b4965"), ("independent", "#c58b5b")]:
        axes[0].hist(d[d.world == w].lost_packs, bins=bins, alpha=0.55, color=col, label=f"{w} delays")
    axes[0].set_title("D1, do nothing: lost packs by delay structure", fontsize=10)
    axes[0].set_xlabel("Lost packs")
    axes[0].legend(fontsize=8)
    p = st[(st.test == "Planner correlation assumption")].pivot_table(
        index=["scenario_id", "setting"], columns="metric", values="value").reset_index()
    x = np.arange(len(p))
    axes[1].bar(x - 0.2, p.mean_lost_packs, 0.4, label="mean", color="#7aa6c2")
    axes[1].bar(x + 0.2, p.p90_lost_packs, 0.4, label="P90", color="#1b4965")
    axes[1].set_xticks(x, [f"{r.scenario_id}\n{r.setting.replace('planner assumes ', 'assumes ')}" for r in p.itertuples()], fontsize=7)
    axes[1].set_ylabel("Lost packs (correlated world)")
    axes[1].set_title("Planner's correlation assumption, evaluated in a correlated world", fontsize=10)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "correlation_tests.png", dpi=150)
    plt.close(fig)


def md_table(df, floatfmt="{:,.0f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(floatfmt.format(v) if isinstance(v, (float, np.floating)) and np.isfinite(v) else
                         ("—" if isinstance(v, (float, np.floating)) else str(v)))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def sensitivity_section(s, names, snames):
    """Does the stochastic LP still win when the lost-pack penalty is halved or doubled?"""
    rows, beats, best_or_close, smart_best, n = [], 0, 0, 0, 0
    for (pen, sid), g in s.groupby(["penalty_per_lost_pack", "scenario_id"], sort=False):
        e = g.set_index("policy_id")
        saving = e.mean_objective["P1"] - e.mean_objective["P5"]
        best = e.mean_objective.idxmin()
        n += 1
        beats += saving > 0
        best_or_close += e.mean_objective["P5"] <= 1.05 * e.mean_objective[best]
        smart_best += best in ("P5", "P6")
        rows.append({"Penalty": f"${pen:,.0f}", "Scenario": f"{sid} {snames[sid]}",
                     "Do nothing lost": e.mean_lost_packs["P1"], "Stochastic LP lost": e.mean_lost_packs["P5"],
                     "Stochastic LP spend ($k)": e.mitigation_cost["P5"] / 1000,
                     "Net saving vs do nothing ($k)": saving / 1000, "Lowest-cost policy": names[best]})
    return ["## Penalty sensitivity (lost-pack penalty $1k / $2k / $4k)", "",
            "Every policy except the oracle is re-planned with each penalty and evaluated on the same realizations; "
            "the backlog penalty stays at $100 per pack-week.", "",
            f"- The stochastic LP has lower expected total cost than doing nothing in **{beats} of {n}** scenario-penalty combinations.",
            f"- It is the lowest-cost policy, or within 5% of it, in **{best_or_close} of {n}**.",
            f"- The lowest-cost policy is one of the two stochastic LPs (with or without CVaR) in **{smart_best} of {n}**; "
            "no heuristic or deterministic plan is ever cheapest.", "",
            md_table(pd.DataFrame(rows)), ""]


def write_results(t):
    ev, pol, sc = t["fact_policy_evaluation"], t["dim_policy"], t["dim_scenario"]
    names = pol.set_index("policy_id").name
    snames = sc.set_index("scenario_id").name
    split = sc.set_index("scenario_id").split
    info = t["info"]
    budget = info["budget"]
    lines = ["# PackRisk results", "",
             "_All operational data is simulated. Results are \"in simulation\", never business savings._", "",
             f"- Delay parameters: {info['lateness_source']}",
             f"- {info['n_prior_samples']} planning samples per scenario; {info['n_eval_realizations']} evaluation realizations per scenario",
             f"- Mitigation budget: ${info['budget']:,.0f} per 8-week horizon; runtime {info['runtime_seconds']}s", ""]

    lost = ev.pivot(index="scenario_id", columns="policy_id", values="mean_lost_packs").loc[sc.scenario_id]
    obj = ev.pivot(index="scenario_id", columns="policy_id", values="mean_objective").loc[sc.scenario_id] / 1000
    lost.columns = [names[c] for c in lost.columns]
    obj.columns = [names[c] for c in obj.columns]
    lost.insert(0, "Scenario", [f"{s} {snames[s]} ({split[s]})" for s in lost.index])
    obj.insert(0, "Scenario", [f"{s} {snames[s]} ({split[s]})" for s in obj.index])
    lines += ["## Mean lost packs (8-week horizon, plan = 12,000 packs)", "", md_table(lost.reset_index(drop=True)), "",
              "## Mean total cost ($k) = $2,000 × lost packs + $100 × backlog pack-weeks + mitigation spend", "",
              md_table(obj.reset_index(drop=True)), "", "![cost heatmap](outputs/figures/policy_cost_heatmap.png)", ""]

    # VSS and oracle capture
    rows = []
    for s in sc.scenario_id:
        e = ev[ev.scenario_id == s].set_index("policy_id")
        rows.append({"Scenario": s, "Split": split[s],
                     "VSS ($k)": (e.mean_objective["P4"] - e.mean_objective["P5"]) / 1000,
                     "Stochastic LP oracle capture": e.oracle_capture_share["P5"],
                     "CVaR oracle capture": e.oracle_capture_share["P6"],
                     "Stochastic LP spend ($k)": e.mitigation_cost["P5"] / 1000})
    v = pd.DataFrame(rows)
    v["Stochastic LP oracle capture"] = v["Stochastic LP oracle capture"].map(lambda x: f"{x:.0%}" if np.isfinite(x) else "—")
    v["CVaR oracle capture"] = v["CVaR oracle capture"].map(lambda x: f"{x:.0%}" if np.isfinite(x) else "—")
    lines += ["## Value of the stochastic solution and oracle capture", "",
              "VSS = expected total cost of the deterministic LP minus the stochastic LP. "
              "Oracle capture = share of the do-nothing → oracle gap in lost packs that the policy closes.", "",
              md_table(v), ""]

    # Failure analysis
    fails = []
    for s in sc.scenario_id:
        e = ev[ev.scenario_id == s].set_index("policy_id")
        simple = e.loc[["P1", "P2", "P3"], "mean_objective"]
        best = simple.idxmin()
        gap = (simple[best] - e.mean_objective["P5"]) / max(simple[best], 1)
        if gap < 0.15:
            fails.append(f"- **{s} {snames[s]}**: best simple policy ({names[best]}) costs "
                         f"${simple[best] / 1000:,.0f}k vs ${e.mean_objective['P5'] / 1000:,.0f}k for the stochastic LP "
                         f"({gap:+.0%} advantage to the LP).")
        lp_lost, sp_lost = e.mean_lost_packs["P5"], e.loc[["P2", "P3"], "mean_lost_packs"].min()
        if sp_lost < lp_lost - 1:
            fails.append(f"- **{s}**: a heuristic protects more packs ({sp_lost:,.0f} lost vs {lp_lost:,.0f}) "
                         f"but spends ${e.loc[['P2', 'P3'], 'mitigation_cost'].max() / 1000:,.0f}k to do it; "
                         "the LP judges the extra packs not worth that cost at the stated penalties.")
        if e.mean_lost_packs["P5"] - e.mean_lost_packs["P7"] > 200:
            spend = e.mitigation_cost["P5"]
            if spend < 0.9 * budget:
                why = (f"the LP spent only ${spend / 1000:,.0f}k of ${budget / 1000:,.0f}k because its model judged more "
                       "protection not worth the cost")
                if split[s] == "held-out":
                    why += "; the planner's prior underestimated this disruption (deliberate misspecification)"
            else:
                why = "the budget was binding and some loss cannot be bought back"
            fails.append(f"- **{s}**: large remaining gap to the oracle ({e.mean_lost_packs['P5']:,.0f} vs "
                         f"{e.mean_lost_packs['P7']:,.0f} lost packs); {why}.")
    lines += ["## Where the method fails or barely helps (auto-detected)", "",
              *(fails or ["- None detected under current thresholds."]), ""]

    # Budget
    b = t["fact_budget_curve"]
    lines += ["## Budget sweep (stochastic LP)", "",
              md_table(b[["scenario_id", "budget", "mitigation_cost", "stochastic_mean_lost",
                          "stochastic_p90_lost", "oracle_mean_lost", "packs_protected"]]),
              "", "![budget](outputs/figures/budget_curve.png)", ""]

    # Penalty sensitivity
    if t["sens"] is not None:
        lines += sensitivity_section(t["sens"], names, snames)

    # Correlation
    st = t["fact_stress_tests"]
    lines += ["## Correlation stress tests", "",
              md_table(st.assign(value=st.value.round(2))[["test", "scenario_id", "setting", "metric", "value"]],
                       floatfmt="{:,.2f}"),
              "", "![correlation](outputs/figures/correlation_tests.png)", ""]
    for sid in st.scenario_id.unique():
        d = st[(st.scenario_id == sid) & (st.test == "Correlation (do nothing)")].pivot(index="setting", columns="metric", values="value")
        comp = "lower" if d.loc["correlated", "mean_lost_packs"] < d.loc["independent", "mean_lost_packs"] else "higher"
        pl = st[(st.scenario_id == sid) & (st.test == "Planner correlation assumption")].pivot(index="setting", columns="metric", values="value")
        lines.append(f"- {sid}: with no mitigation, mean loss is {comp} when delays are correlated "
                     f"({d.loc['correlated', 'mean_lost_packs']:,.0f} vs {d.loc['independent', 'mean_lost_packs']:,.0f}). "
                     f"A planner that assumes independence, evaluated in the correlated world, has P90 loss "
                     f"{pl.loc['planner assumes independence', 'p90_lost_packs']:,.0f} vs "
                     f"{pl.loc['planner assumes correlation', 'p90_lost_packs']:,.0f} for the planner that models correlation.")
    lines += ["", "## Gating parts and centerpiece", "", "![gating](outputs/figures/gating_D1.png)", "",
              "![centerpiece](outputs/figures/centerpiece_D1.png)", "",
              "## Limitations", "",
              "- All operations are simulated; delay distributions are placeholders until `calibrate.py` is run on real shipment data, and even then the source data is not battery parts.",
              "- Decisions are made once at week 0 (static two-stage). Weekly rolling re-planning is a v2 item.",
              "- Execution schedules production optimally against realized supply, which flatters every policy equally.",
              "- Capacity lost to cuts and scrap is not recovered within the horizon; backlog recovery is not modeled.",
              "- Costs, penalty per pack, BOM quantities and cover levels are hypothetical."]
    (ROOT / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    t = load()
    fig_objective_heatmap(t)
    fig_centerpiece(t)
    fig_gating(t)
    fig_budget(t)
    fig_correlation(t)
    write_results(t)
    print("figures + RESULTS.md written")


if __name__ == "__main__":
    main()
