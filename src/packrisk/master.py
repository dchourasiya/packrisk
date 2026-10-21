"""Master data for the hypothetical battery-pack assembly site.

Every number here is a hypothetical placeholder. Nothing represents any real
company's suppliers, volumes, or costs.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DATA_DIR

VARIANTS = ["SR", "LR"]  # SR = LFP prismatic pack, LR = NMC cylindrical pack

# id, description, base lead weeks (normal mode), expedite mode, expedite cost share of unit cost
LANES = [
    ("L1", "Asia to US West Coast, ocean", 6, "air", 0.15),
    ("L2", "Mexico to site, truck", 1, "team driver", 0.03),
    ("L3", "US domestic, truck", 1, "none", 0.0),
    ("L4", "Europe to US, ocean", 5, "air", 0.15),
]

TIER2 = [
    ("T1", "Copper rod / foil"),
    ("T2", "Semiconductors"),
    ("T3", "Aluminum billet"),
    ("T4", "Resins and chemicals"),
    ("T5", "Mica and aerogel"),
    ("T6", "Cathode material"),
]

# id, supplies, region, lane, tier-2 (or None), lateness multiplier (supplier-specific reliability)
SUPPLIERS = [
    ("S01", "LFP prismatic cells", "Asia", "L1", "T6", 1.0),
    ("S02", "LFP prismatic cells (alternate)", "Asia", "L1", "T6", 1.1),
    ("S03", "NMC cylindrical cells", "Asia", "L1", "T6", 1.6),
    ("S04", "NMC cylindrical cells (alternate)", "US", "L3", "T6", 0.8),
    ("S05", "Busbars, current collectors", "Mexico", "L2", "T1", 1.0),
    ("S06", "HV cables, harnesses", "Mexico", "L2", "T1", 1.2),
    ("S07", "Electronics (CMB, BMS master)", "Asia", "L1", "T2", 1.0),
    ("S08", "Sensors, isolation monitor", "Europe", "L4", "T2", 0.9),
    ("S09", "Contactors, precharge parts", "Asia", "L1", None, 1.1),
    ("S10", "Pyro fuse, service disconnect", "Europe", "L4", None, 1.0),
    ("S11", "HV / LV connectors", "US", "L3", None, 0.7),
    ("S12", "TIM, adhesive, potting foam", "US", "L3", "T4", 0.9),
    ("S13", "Cooling plates and tubes", "Mexico", "L2", "T3", 1.3),
    ("S14", "Hoses, fittings", "US", "L3", None, 0.8),
    ("S15", "Mica, aerogel barriers", "Asia", "L1", "T5", 1.5),
    ("S16", "Enclosure trays, lids", "US", "L3", "T3", 0.9),
    ("S17", "Gaskets, vents, membranes", "US", "L3", "T4", 0.8),
    ("S18", "Fasteners", "Asia", "L1", None, 1.8),
    ("S19", "Cell frames, holders, plastics", "Mexico", "L2", "T4", 1.2),
    ("S20", "Labels, film, desiccant, misc.", "US", "L3", None, 0.7),
]

# id, name, category, qty SR, qty LR, primary, approved alternate (or None), unit cost ($), flags
COMPONENTS = [
    ("C01", "LFP prismatic cell", "Cells", 100, 0, "S01", "S02", 35.0, "QH"),
    ("C02", "NMC cylindrical cell", "Cells", 0, 4400, "S03", "S04", 2.5, "QH"),
    ("C03", "Prismatic cell frame", "Structure", 100, 0, "S19", None, 1.2, ""),
    ("C04", "Cylindrical cell holder", "Structure", 0, 8, "S19", None, 18.0, ""),
    ("C05", "Compression end plate", "Structure", 4, 0, "S16", None, 12.0, ""),
    ("C06", "Module side rail", "Structure", 8, 0, "S16", None, 9.0, ""),
    ("C07", "Copper module interconnect busbar", "Electrical", 12, 8, "S05", None, 6.0, ""),
    ("C08", "Aluminum cell busbar", "Electrical", 100, 0, "S05", None, 0.8, ""),
    ("C09", "Aluminum wire-bond wire (m)", "Electrical", 0, 50, "S05", None, 0.4, ""),
    ("C10", "Current collector plate", "Electrical", 0, 8, "S05", None, 14.0, ""),
    ("C11", "Cell monitoring board", "Electronics", 4, 4, "S07", None, 45.0, ""),
    ("C12", "BMS master controller", "Electronics", 1, 1, "S07", None, 160.0, ""),
    ("C13", "Main HV contactor", "Electrical", 2, 2, "S09", "S10", 55.0, ""),
    ("C14", "Precharge contactor", "Electrical", 1, 1, "S09", None, 22.0, ""),
    ("C15", "Precharge resistor", "Electrical", 1, 1, "S09", "S08", 6.0, ""),
    ("C16", "Pyrotechnic fuse", "Electrical", 1, 1, "S10", None, 40.0, ""),
    ("C17", "Current sensor (shunt)", "Electronics", 1, 1, "S08", None, 30.0, ""),
    ("C18", "HV service disconnect", "Electrical", 1, 1, "S10", None, 25.0, ""),
    ("C19", "HV output connector", "Electrical", 2, 2, "S11", None, 18.0, ""),
    ("C20", "LV signal connector", "Electrical", 2, 2, "S11", None, 4.0, ""),
    ("C21", "LV module harness", "Electrical", 1, 1, "S06", None, 35.0, ""),
    ("C22", "HV cable assembly", "Electrical", 2, 2, "S06", None, 28.0, ""),
    ("C23", "Thermistor assembly", "Electronics", 8, 16, "S08", None, 2.0, ""),
    ("C24", "Isolation monitoring board", "Electronics", 1, 1, "S08", None, 38.0, ""),
    ("C25", "Thermal interface material (kg)", "Thermal", 3.0, 3.5, "S12", "S17", 20.0, "SL;QH"),
    ("C26", "Cooling plate", "Thermal", 1, 0, "S13", None, 85.0, ""),
    ("C27", "Serpentine cooling tube", "Thermal", 0, 4, "S13", None, 30.0, ""),
    ("C28", "Coolant fittings", "Thermal", 2, 2, "S14", None, 5.0, ""),
    ("C29", "Coolant hose assembly", "Thermal", 2, 2, "S14", None, 9.0, ""),
    ("C30", "Thermal insulation pad", "Fire safety", 10, 6, "S15", None, 2.0, ""),
    ("C31", "Mica fire barrier sheet", "Fire safety", 4, 4, "S15", None, 6.0, ""),
    ("C32", "Aerogel cell spacer", "Fire safety", 50, 0, "S15", None, 3.0, ""),
    ("C33", "Pressure vent valve", "Enclosure", 2, 2, "S17", None, 8.0, ""),
    ("C34", "Enclosure tray, SR", "Enclosure", 1, 0, "S16", None, 260.0, ""),
    ("C35", "Enclosure tray, LR", "Enclosure", 0, 1, "S16", None, 310.0, ""),
    ("C36", "Enclosure lid", "Enclosure", 1, 1, "S16", None, 90.0, ""),
    ("C37", "Perimeter gasket", "Enclosure", 1, 1, "S17", None, 15.0, ""),
    ("C38", "Structural adhesive (kg)", "Chemicals", 1.2, 2.0, "S12", "S17", 18.0, "SL;QH"),
    ("C39", "Potting foam (kg)", "Chemicals", 0, 6.0, "S12", None, 12.0, "SL;QH"),
    ("C40", "Underbody shield", "Enclosure", 1, 1, "S16", None, 70.0, ""),
    ("C41", "Mounting bracket set", "Enclosure", 1, 1, "S16", None, 25.0, ""),
    ("C42", "M6 flange bolt", "Fasteners", 60, 60, "S18", "S20", 0.10, ""),
    ("C43", "M8 structural bolt", "Fasteners", 24, 24, "S18", "S20", 0.25, ""),
    ("C44", "Rivet nut", "Fasteners", 40, 40, "S18", "S20", 0.15, ""),
    ("C45", "Dielectric insulation film (m2)", "Misc", 2, 2, "S20", None, 3.0, ""),
    ("C46", "Edge grommet", "Misc", 10, 10, "S20", None, 0.30, ""),
    ("C47", "HV warning label set", "Misc", 1, 1, "S20", None, 1.5, ""),
    ("C48", "Desiccant pack", "Misc", 1, 1, "S20", None, 1.0, ""),
    ("C49", "Breather membrane", "Enclosure", 1, 1, "S17", None, 4.0, ""),
    ("C50", "Ground strap", "Electrical", 2, 2, "S06", None, 3.0, ""),
]


@dataclass
class Master:
    components: pd.DataFrame
    suppliers: pd.DataFrame
    lanes: pd.DataFrame
    tier2: pd.DataFrame
    q: np.ndarray            # (C, 2) quantity per pack by variant
    sup_of: np.ndarray       # (C,) primary supplier index
    alt_of: np.ndarray       # (C,) approved alternate supplier index, -1 if none
    lane_of_sup: np.ndarray  # (S,) lane index
    tier2_of_sup: np.ndarray  # (S,) tier-2 index, -1 if none
    lane_of: np.ndarray      # (C,) lane index of primary supplier
    unit_cost: np.ndarray    # (C,)
    qh: np.ndarray           # (C,) bool, elevated quality-hold risk
    req_base: np.ndarray     # (C,) weekly requirement under base plan
    cover_weeks: np.ndarray  # (C,) starting inventory, weeks of cover
    I0: np.ndarray           # (C,) starting inventory

    @property
    def C(self):
        return len(self.components)

    @property
    def S(self):
        return len(self.suppliers)


def build_master(params):
    lanes = pd.DataFrame(LANES, columns=["lane_id", "description", "base_lead_weeks",
                                         "expedite_mode", "expedite_cost_share"])
    tier2 = pd.DataFrame(TIER2, columns=["tier2_id", "shared_input"])
    sups = pd.DataFrame(SUPPLIERS, columns=["supplier_id", "supplies", "region", "lane_id",
                                            "tier2_id", "lateness_multiplier"])
    comps = pd.DataFrame(COMPONENTS, columns=["component_id", "name", "category", "qty_SR",
                                              "qty_LR", "primary_supplier_id",
                                              "alt_supplier_id", "unit_cost", "flags"])

    lane_idx = {l: i for i, l in enumerate(lanes.lane_id)}
    t2_idx = {t: i for i, t in enumerate(tier2.tier2_id)}
    sup_idx = {s: i for i, s in enumerate(sups.supplier_id)}

    q = comps[["qty_SR", "qty_LR"]].to_numpy(float)
    sup_of = comps.primary_supplier_id.map(sup_idx).to_numpy()
    alt_of = comps.alt_supplier_id.map(lambda s: sup_idx[s] if isinstance(s, str) else -1).to_numpy()
    lane_of_sup = sups.lane_id.map(lane_idx).to_numpy()
    tier2_of_sup = sups.tier2_id.map(lambda t: t2_idx[t] if isinstance(t, str) else -1).to_numpy()
    lane_of = lane_of_sup[sup_of]
    unit_cost = comps.unit_cost.to_numpy(float)
    qh = comps["flags"].str.contains("QH").to_numpy()

    plan = np.array([params["plan"]["SR"], params["plan"]["LR"]], float)
    req_base = q @ plan

    # Starting cover: cells 4 weeks (strategic stock), electronics boards 2 weeks
    # (lean, high value), everything else 2-4 weeks drawn once with a fixed seed.
    rng = np.random.default_rng(params["seed_master"])
    cover = rng.choice([2, 3, 4], size=len(comps)).astype(float)
    ids = comps.component_id.tolist()
    for cid in ("C01", "C02"):
        cover[ids.index(cid)] = 4
    for cid in ("C11", "C12"):
        cover[ids.index(cid)] = 2
    I0 = cover * req_base

    comps = comps.assign(
        lane_id=lanes.lane_id.to_numpy()[lane_of],
        tier2_id=sups.tier2_id.to_numpy()[sup_of],
        weekly_requirement=req_base,
        weekly_spend=req_base * unit_cost,
        starting_cover_weeks=cover,
        starting_inventory=I0,
        single_sourced=(alt_of < 0),
    )
    return Master(comps, sups, lanes, tier2, q, sup_of, alt_of, lane_of_sup, tier2_of_sup,
                  lane_of, unit_cost, qh, req_base, cover, I0)


def write_master_csvs(m):
    out = DATA_DIR / "master"
    out.mkdir(parents=True, exist_ok=True)
    m.components.to_csv(out / "components.csv", index=False)
    m.suppliers.to_csv(out / "suppliers.csv", index=False)
    m.lanes.to_csv(out / "lanes.csv", index=False)
    m.tier2.to_csv(out / "tier2.csv", index=False)
