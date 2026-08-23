# Technical Decisions

## PostgreSQL canonical, no SQLite fallback
PostgreSQL 18 ran natively in the dev environment, so all development and tests run
against real Postgres (psycopg3 driver). `JSONB`, `make_interval` and server defaults are
used directly.

## Python 3.14 runtime with 3.12-compatible pins
The environment shipped only Python 3.14.4. Dependencies were pinned to ranges that
support both (e.g. scikit-learn ≥1.8 works on 3.12–3.14). Docker images use
`python:3.12-slim`.

## Action-conditioned ML models instead of one global model
Six HistGradientBoosting classifiers (one per candidate action) are easier to explain,
evaluate, and reason about than a single action-conditioned model, at no practical cost
at this data size. XGBoost was available but offered nothing extra here.

## Labels from a documented ground-truth simulator
With no production data, recovery labels come from `simulator/recovery_simulator.py`,
whose base rates encode plausible payments folklore (temporary bank failures recover well
on delayed retry; repeated failures barely recover). The models learn this world from
features only — evaluation scores them against the same oracle on held-out payments,
which measures decision quality within that world, not real-world performance.

## Friction economics tuned for visible restraint
Friction costs (₹35 notification / ₹45 retry) plus risk penalties make low-value
interventions net-negative, producing genuine `DO_NOTHING` decisions rather than
cosmetic ones. These are merchant-policy-configurable.

## LLM as explainer only
The LLM receives structured evidence and returns prose. It has no tools, cannot mutate
state, and its output never overrides the decision or policy engines. A rule-based
explanation generator guarantees the feature works with zero providers configured.

## Celery deferred
At hackathon scale, FastAPI request-scoped work covers everything; Redis/Celery would add
operational surface without benefit. Redis remains in compose for future async jobs.

## Webhook idempotency by external event ID
Razorpay delivers at-least-once and unordered. Events are stored raw (JSONB), keyed by a
unique external event ID; duplicates short-circuit; processing errors keep the payload
stored (`processed=false`) rather than losing it.
