"""Generate synthetic dataset CSVs into data/synthetic/."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from simulator.payment_simulator import generate_dataset  # noqa: E402

OUT_DIR = Path("data/synthetic")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = generate_dataset(n_payments=args.n, seed=args.seed)

    failed = (data["payments"]["status"] == "FAILED").sum()
    for name, df in data.items():
        path = OUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"wrote {path} rows={len(df)}")

    print(f"failure_rate={failed / len(data['payments']):.4f} failed={failed}")
    print("\nfailure reason distribution:")
    print(data["payments"].loc[data['payments']['status'] == 'FAILED', 'failure_reason'].value_counts())


if __name__ == "__main__":
    main()
