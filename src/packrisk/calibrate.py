"""Fit lane lateness parameters from real public shipment data.

Usage (after downloading the files into data/raw/):
    python -m packrisk.calibrate --usaid data/raw/usaid_scms.csv
    python -m packrisk.calibrate --usaid data/raw/usaid_scms.csv --dataco data/raw/DataCoSupplyChainDataset.csv

Column names below are the defaults expected for each dataset. VERIFY them against
the file you downloaded and pass --*-col overrides if they differ.

Mapping (documented in ASSUMPTIONS.md): ocean shipments -> lanes L1 and L4,
truck shipments -> lanes L2 and L3. This is a proxy: the source data is not
battery parts, which is a stated limitation.
"""
import argparse
import json

import numpy as np
import pandas as pd

from .config import CONFIG_DIR, OUT_DIR

MODE_TO_LANES = {"ocean": ["L1", "L4"], "truck": ["L2", "L3"]}


def fit(lateness_days):
    x = np.asarray(lateness_days, float)
    x = x[np.isfinite(x)]
    late = x[x > 0]
    if len(late) < 30:
        raise ValueError(f"only {len(late)} late shipments; too few to fit")
    logs = np.log(late)
    return {"p_late": round(float((x > 0).mean()), 4), "median_days": round(float(np.exp(np.median(logs))), 2),
            "sigma": round(float(np.std(logs)), 3), "n_shipments": int(len(x)), "n_late": int(len(late))}


def calibrate_usaid(path, sched_col, deliv_col, mode_col):
    df = pd.read_csv(path, low_memory=False)
    missing = [c for c in (sched_col, deliv_col, mode_col) if c not in df.columns]
    if missing:
        raise SystemExit(f"Columns not found: {missing}. Available: {list(df.columns)}")
    sched = pd.to_datetime(df[sched_col], errors="coerce", format="mixed")
    deliv = pd.to_datetime(df[deliv_col], errors="coerce", format="mixed")
    ok = sched.notna() & deliv.notna()
    print(f"USAID rows: {len(df)}, usable date pairs: {ok.sum()} (dropped {len(df) - ok.sum()})")
    d = pd.DataFrame({"lateness": (deliv - sched).dt.days, "mode": df[mode_col].astype(str).str.lower()})[ok]
    fits = {}
    for mode in MODE_TO_LANES:
        sub = d[d["mode"].str.contains(mode)]
        print(f"  mode '{mode}': {len(sub)} shipments")
        fits[mode] = fit(sub.lateness)
    return fits, d


def check_dataco(path, real_col, sched_col, mode_col):
    df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    missing = [c for c in (real_col, sched_col, mode_col) if c not in df.columns]
    if missing:
        raise SystemExit(f"Columns not found: {missing}. Available: {list(df.columns)}")
    lat = df[real_col] - df[sched_col]
    out = {}
    for mode, sub in lat.groupby(df[mode_col]):
        out[str(mode)] = {"p_late": round(float((sub > 0).mean()), 4),
                          "mean_days_late_when_late": round(float(sub[sub > 0].mean()), 2) if (sub > 0).any() else 0.0,
                          "n": int(len(sub))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usaid", required=True)
    ap.add_argument("--usaid-scheduled-col", default="Scheduled Delivery Date")
    ap.add_argument("--usaid-delivered-col", default="Delivered to Client Date")
    ap.add_argument("--usaid-mode-col", default="Shipment Mode")
    ap.add_argument("--dataco")
    ap.add_argument("--dataco-real-col", default="Days for shipping (real)")
    ap.add_argument("--dataco-scheduled-col", default="Days for shipment (scheduled)")
    ap.add_argument("--dataco-mode-col", default="Shipping Mode")
    a = ap.parse_args()

    fits, d = calibrate_usaid(a.usaid, a.usaid_scheduled_col, a.usaid_delivered_col, a.usaid_mode_col)
    lanes = {}
    for mode, lane_ids in MODE_TO_LANES.items():
        for lid in lane_ids:
            lanes[lid] = {k: fits[mode][k] for k in ("p_late", "median_days", "sigma")}
    payload = {"source": f"Calibrated from USAID SCMS shipment data ({a.usaid}); ocean->L1/L4, truck->L2/L3",
               "lanes": lanes, "fit_details": fits}
    if a.dataco:
        payload["dataco_cross_check"] = check_dataco(a.dataco, a.dataco_real_col, a.dataco_scheduled_col, a.dataco_mode_col)
    (CONFIG_DIR / "delay_params.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    for ax, mode in zip(axes, MODE_TO_LANES):
        late = d[d["mode"].str.contains(mode) & (d.lateness > 0)].lateness
        ax.hist(late.clip(upper=late.quantile(0.98)), bins=40, density=True, alpha=0.6)
        f = fits[mode]
        xs = np.linspace(0.5, late.quantile(0.98), 200)
        mu, s = np.log(f["median_days"]), f["sigma"]
        ax.plot(xs, np.exp(-(np.log(xs) - mu) ** 2 / (2 * s * s)) / (xs * s * np.sqrt(2 * np.pi)))
        ax.set_title(f"{mode}: p_late={f['p_late']:.2f}, median={f['median_days']}d")
        ax.set_xlabel("days late (late shipments only)")
    fig.tight_layout()
    (OUT_DIR / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "figures" / "calibration_fit.png", dpi=150)
    print("Saved outputs/figures/calibration_fit.png. Now rerun: make all")


if __name__ == "__main__":
    main()
