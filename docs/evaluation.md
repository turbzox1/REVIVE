# Evaluation

All numbers below come from an actual run of `python scripts/run_evaluation.py --n 2000`
(seed 42) on this machine — 2,000 failed payments sampled from the 11,367 failures in the
synthetic dataset, scored against the ground-truth outcome oracle.

## Strategy comparison

| Strategy | Revenue Recovered | Recovery Rate | Interventions | Avg ₹/Intervention | Incremental |
|---|---|---|---|---|---|
| DO NOTHING | ₹140,685 | 2.1% | 0 | — | — |
| ALWAYS RETRY | ₹2,407,555 | 35.4% | 3,526 | ₹683 | +₹2,266,870 |
| **REVIVE** | **₹2,463,978** | **36.2%** | **1,784** | **₹1,381** | **+₹2,323,293** |

Reading:

- REVIVE recovers **+₹56k more than Always-Retry** while making **1,742 fewer customer
  contacts (−49%)**.
- Average value per intervention nearly doubles: REVIVE concentrates effort where models
  predict meaningful net recovery.
- REVIVE chose `DO_NOTHING` for 216 payments; Always-Retry burned two retries on each of
  those and every other payment regardless of context.

## REVIVE action distribution (same run)

CREATE_PAYMENT_LINK 1057 · ALTERNATE_PAYMENT_METHOD 392 · SEND_REMINDER 140 ·
RETRY_LATER 98 · RETRY_NOW 97 · **DO_NOTHING 216**

## ML metrics (held-out test set, from ml/models/metrics.json)

| Action model | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---|---|---|---|---|
| RETRY_NOW | 0.792 | 0.600 | 0.381 | 0.466 | 0.157 |
| ALTERNATE_PAYMENT_METHOD | 0.780 | 0.631 | 0.603 | 0.617 | 0.183 |
| CREATE_PAYMENT_LINK | 0.755 | 0.623 | 0.735 | 0.675 | 0.195 |
| RETRY_LATER | 0.744 | 0.531 | 0.346 | 0.419 | 0.182 |
| SEND_REMINDER | 0.685 | 0.500 | 0.018 | 0.035 | 0.175 |

Honest caveats: SEND_REMINDER has a low positive base rate, hence poor recall at a 0.5
threshold; the decision engine uses its probabilities rather than hard classifications.
Split is 70/15/15 train/val/test with no test leakage into training or decision logic.

## Methodology notes

- All three strategies run on the *same* payments with per-payment seeded RNG so runs are
  reproducible.
- The oracle is the documented simulator (`simulator/recovery_simulator.py`); results
  measure decision quality inside that synthetic world only.
- Re-run anytime: `python scripts/run_evaluation.py --n 2000` regenerates
  `data/processed/evaluation_summary.json`, which the Evaluation dashboard reads live.
