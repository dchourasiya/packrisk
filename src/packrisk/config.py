import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"


def load_params():
    params = json.loads((CONFIG_DIR / "params.json").read_text())
    delays = json.loads((CONFIG_DIR / "delay_params.json").read_text())
    params["lateness"] = delays["lanes"]
    params["lateness_source"] = delays.get("source", "")
    return params
