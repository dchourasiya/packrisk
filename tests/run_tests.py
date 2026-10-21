"""Minimal test runner for environments without pytest."""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_invariants as t  # noqa: E402

failed = 0
for name in sorted(n for n in dir(t) if n.startswith("test_")):
    try:
        getattr(t, name)()
        print(f"PASS  {name}")
    except Exception:
        failed += 1
        print(f"FAIL  {name}")
        traceback.print_exc()
print(f"\n{failed} failed" if failed else "\nall tests passed")
sys.exit(1 if failed else 0)
