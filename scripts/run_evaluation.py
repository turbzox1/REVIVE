"""Run business evaluation and persist results for the dashboard/API."""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.evaluation.business_metrics import run_evaluation  # noqa: E402

OUT = Path("data/processed/evaluation_summary.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=2000)
    args = parser.parse_args()
    result = run_evaluation(n_samples=args.n)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"wrote {OUT}")
    for s in result["strategies"]:
        print(f"  {s['strategy']:<13} recovered=₹{s['revenue_recovered']:,.0f} "
              f"rate={s['recovery_rate']:.1%} interventions={s['interventions']}")


if __name__ == "__main__":
    main()
