# REVIVE

> **Autonomous Revenue Recovery & Decision Engine**
> *Don't just detect lost revenue. Decide how to recover it.*

REVIVE is built for the **Razorpay Buildathon**. It goes beyond failed-payment detection:
it diagnoses why revenue is at risk, predicts recovery probability per intervention,
simulates counterfactual outcomes, chooses the action with the highest **expected net
recovery**, enforces merchant policy, executes through Razorpay Test Mode where possible,
and measures whether its decisions actually recovered more money.

```text
Expected Net Recovery =
    Expected Recovered Amount
  - Intervention Cost
  - Customer Friction Cost
  - Risk Penalty
```

REVIVE sometimes decides that the best action is **DO_NOTHING** — when every intervention
costs more than it can recover.

---

## Architecture

```text
Payment Events (PostgreSQL)
      ↓
Feature Engineering
      ↓
Risk / Root-Cause Analysis
      ↓
ML Recovery Predictions (per-action models)
      ↓
Counterfactual Action Simulation
      ↓
Decision Engine  (argmax net expected recovery + timing)
      ↓
Policy / Guardrail Engine   ← authoritative; nothing bypasses it
      ↓
Action Executor  (Razorpay Test Mode payment links / simulated actions)
      ↓
Webhooks → Outcome Tracking → Evaluation / Learning
```

The LLM layer is **explanation-only**: it receives structured evidence and produces
merchant-facing narratives. It cannot invent actions, probabilities, or bypass policy.

## Measured Results (real evaluation run — see docs/evaluation.md)

2,000 held-out failed payments scored against the ground-truth outcome simulator:

| Strategy | Revenue Recovered | Recovery Rate | Interventions | Incremental |
|---|---|---|---|---|
| DO NOTHING | ₹1.41L | 2.1% | 0 | — |
| ALWAYS RETRY | ₹24.08L | 35.4% | 3,526 | +₹22.67L |
| **REVIVE** | **₹24.64L** | **36.2%** | **1,784** | **+₹23.23L** |

**REVIVE recovers more revenue than Always-Retry while making ~49% fewer customer
contacts** — including choosing `DO_NOTHING` for 216 payments where intervention would
destroy value.

## Features

- Synthetic payment environment: 50k transactions with causal failure mechanisms and a
  payment-method degradation incident
- Action-conditioned recovery models (ROC-AUC 0.69–0.79 on held-out test data)
- Counterfactual decision engine over a controlled action space (8 actions, 6 timings)
- Policy/guardrail engine: retry budgets, notification budgets, minimum intervals,
  amount ceilings, merchant permissions
- Razorpay Test Mode Payment Link execution + HMAC-verified idempotent webhooks
- Provider-agnostic LLM explanation layer (rule-based fallback, always available)
- Next.js dashboard: Command Center, Opportunities, Decision Explanation, Decision Graph,
  Evaluation vs baselines

## Tech Stack

Python 3.12+ · FastAPI · SQLAlchemy 2 · PostgreSQL · scikit-learn (HistGradientBoosting) ·
Next.js 14 · TypeScript · Tailwind CSS · Recharts · React Flow · Docker Compose

## Setup

### Prerequisites
- Python 3.12+ (tested on 3.14), Node.js 18+
- PostgreSQL running locally (or Docker)

### 1. Backend + DB

```bash
# create database
createdb revive   # or: psql -c "CREATE DATABASE revive;"

python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r backend/requirements.txt

cp .env.example .env        # edit DATABASE_URL / Razorpay keys if you have them

python backend/app/db/init_db.py       # create tables in PostgreSQL
python scripts/generate_data.py --n 50000 --seed 42
python scripts/seed_database.py --reset
python ml/training/train.py            # trains per-action models into ml/models/
python scripts/run_evaluation.py --n 2000
```

### 2. Run

```bash
cd backend && uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev    # http://localhost:3000
```

### Demo

```bash
python scripts/run_demo.py     # three deterministic scenarios against live PostgreSQL
```

1. **High-value recoverable** — ₹15k temporary bank failure, 97%-success repeat customer
   → high-value intervention selected with full counterfactual breakdown.
2. **Restraint** — ₹100 repeated failure, churn-risk customer → `DO_NOTHING`; every
   alternative has negative net expected value and one is policy-rejected.
3. **Method degradation** — NETBANKING failure-rate spike (24.5%→36.5%) detected;
   highest-value failure routed off the failing rail.

### Docker

```bash
docker compose up --build
```

Starts PostgreSQL 16, Redis, and the FastAPI backend. (Compose files are provided but
were not executed in the original dev environment — Docker was unavailable there.)

## Environment Variables (.env)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL URL (`postgresql+psycopg://...`) |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Test Mode keys; enable real payment-link execution |
| `RAZORPAY_WEBHOOK_SECRET` | Enables HMAC signature verification on webhooks |
| `LLM_PROVIDER` | `none` (default) or `openai_compatible` |
| `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` | LLM explanation endpoint config |
| `RANDOM_SEED` | Deterministic synthetic data |

Never commit `.env`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| POST | `/api/v1/recovery/decide` | **The brain**: full counterfactual decision for a payment |
| POST | `/api/v1/recovery/{id}/execute` | Execute the selected action |
| GET | `/api/v1/recovery/opportunities` | Opportunity queue |
| GET | `/api/v1/recovery/{id}/actions` | Scored candidate actions |
| GET | `/api/v1/recovery/{id}/outcome` | Recorded outcome |
| POST | `/api/v1/webhooks/razorpay` | Idempotent webhook ingestion |
| GET | `/api/v1/stats/command-center` | Dashboard aggregates |
| GET | `/api/v1/evaluation/summary` · `/baseline` | Measured strategy comparison |

## Real vs Simulated — honesty rules

- `CREATE_PAYMENT_LINK` runs through **Razorpay Test Mode** when credentials are set;
  the UI shows *"Executed through Razorpay Test Mode"*.
- All other actions are clearly labelled *"Simulated recovery action"* and scored by the
  documented ground-truth simulator.
- Every number in the dashboard comes from live PostgreSQL queries or trained-model output.
  Nothing is hardcoded.

## Limitations (read before judging)

- Data is **synthetic**; "ground truth" recovery outcomes come from our own simulator.
  The ML models learn an approximation of that world, not real-world behaviour.
- Only Payment Links touch Razorpay; other rails are simulated by design.
- Timing intelligence uses the simulator's calibrated curve, not real-world A/B data.
- Docker Compose provided but untested in the original environment.

## License

MIT
