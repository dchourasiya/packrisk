"""Invariant tests. Run with `pytest -q` or `python tests/run_tests.py` (no pytest needed)."""
import numpy as np

from packrisk.config import load_params
from packrisk.master import build_master
from packrisk.optimize import build_actions, execute, solve_plan
from packrisk.world import SCENARIOS, sample_realization

PARAMS = load_params()
PARAMS["n_prior_samples"] = 20
M = build_master(PARAMS)
ACTS = build_actions(M, PARAMS)


def _world(scen="D1", n=5, seed=123, corr=True):
    rng = np.random.default_rng(seed)
    return [sample_realization(rng, scen, M, PARAMS, "truth", corr) for _ in range(n)]


def _prior(scen="D1", n=20, seed=42):
    rng = np.random.default_rng(seed)
    return [sample_realization(rng, scen, M, PARAMS, "prior") for _ in range(n)]


def test_master_data_integrity():
    assert M.C == 50 and M.S == 20
    assert (M.sup_of >= 0).all()
    assert set(M.components.primary_supplier_id) <= set(M.suppliers.supplier_id)
    assert (M.q.sum(axis=1) > 0).all(), "every component is used by at least one variant"


def test_alternates_only_where_approved():
    alt_comps = set(np.where(M.alt_of >= 0)[0])
    assert set(ACTS["comp"][ACTS["kind"] == 2]) <= alt_comps


def test_realization_conserves_or_loses_material():
    for r in _world(n=10):
        for name in ("extra",):
            # a lot can arrive late, partially, or not at all, but never more than ordered
            assert (r["G"][name].sum(axis=2) <= 1 + 1e-9).all()
        assert (r["base_arr"] >= -1e-9).all()


def test_planning_respects_budget_and_caps():
    u = solve_plan(_prior(), ACTS, M, PARAMS, PARAMS["budget"])
    assert u @ ACTS["cost"] <= PARAMS["budget"] + 1e-3
    assert (u <= ACTS["cap"] + 1e-6).all() and (u >= 0).all()


def test_execution_physical_constraints():
    u = solve_plan(_prior(), ACTS, M, PARAMS, PARAMS["budget"])
    for r in _world():
        out = execute(r, u, ACTS, M, PARAMS)
        assert (out["inv_end"] >= -1e-6).all(), "inventory never negative"
        assert (out["p"].sum(axis=0) <= PARAMS["line_capacity"] + 1e-6).all(), "line capacity"
        assert (np.cumsum(out["p"], axis=1) <= np.cumsum(r["plan"], axis=1) + 1e-6).all(), "never build ahead of plan"


def test_oracle_is_an_upper_bound():
    u5 = solve_plan(_prior(), ACTS, M, PARAMS, PARAMS["budget"])
    for r in _world(n=5):
        u7 = solve_plan([r], ACTS, M, PARAMS, PARAMS["budget"])
        o7 = execute(r, u7, ACTS, M, PARAMS)["objective"]
        for u in (np.zeros(len(ACTS["kind"])), u5):
            assert o7 <= execute(r, u, ACTS, M, PARAMS)["objective"] + 1.0


def test_no_leakage_plans_do_not_depend_on_evaluation_world():
    # The stochastic plan must be identical no matter which held-out world is evaluated later.
    u_a = solve_plan(_prior(seed=42), ACTS, M, PARAMS, PARAMS["budget"])
    _ = _world(seed=1)
    u_b = solve_plan(_prior(seed=42), ACTS, M, PARAMS, PARAMS["budget"])
    assert np.allclose(u_a, u_b)


def test_reproducible_with_seed():
    a, b = _world(seed=7, n=2), _world(seed=7, n=2)
    for x, y in zip(a, b):
        assert np.array_equal(x["base_arr"], y["base_arr"])


def test_zero_budget_means_zero_spend():
    u = solve_plan(_prior(), ACTS, M, PARAMS, 0.0)
    assert u @ ACTS["cost"] <= 1e-6


def test_all_scenarios_sample():
    rng = np.random.default_rng(0)
    for sid in SCENARIOS:
        for mode in ("prior", "truth"):
            r = sample_realization(rng, sid, M, PARAMS, mode)
            assert r["base_arr"].shape == (M.C, PARAMS["horizon_weeks"])
