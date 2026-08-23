# Demo Script (~5 minutes)

## Setup (before audience arrives)

```bash
uvicorn app.main:app --port 8000        # backend (from backend/)
npm run dev                             # frontend (from frontend/)
```

Data, models, and evaluation results are already in PostgreSQL / ml/models /
data/processed from the seed commands in the README.

## Part 1 — Problem (30s)

> A failed payment isn't lost revenue yet. The real question is whether to intervene,
> how, and when — and every intervention costs money and customer goodwill.

Open the **Command Center**: revenue at risk by failure reason, method health,
opportunity queue — all live PostgreSQL queries.

## Part 2–3 — Reasoning on one payment (90s)

Run `python scripts/run_demo.py` — Scenario 1 picks a high-value failure from a reliable
repeat customer. Open the opportunity in the dashboard:

- Root cause: TEMPORARY_BANK_FAILURE
- Customer history surfaced as evidence
- All candidate actions scored: probability × amount − friction − cost − risk
- Winner selected on net expected recovery, timing included
- Policy checks shown

## Part 4 — Execute (60s)

Click **Execute Recovery**. With Razorpay Test Mode keys configured, a real Test Mode
Payment Link is created (labelled *"Executed through Razorpay Test Mode"*); otherwise the
action runs through the simulator and says so. The decision graph animates Payment →
Failure → Actions → Decision → Policy → Outcome.

## Part 5 — Restraint (60s)

Scenario 2 from the demo script: a ₹100 repeated-failure payment from a churn-risk
customer. Every intervention has negative net expected value; one is policy-rejected.

> REVIVE's answer: DO_NOTHING. It doesn't maximize retries; it maximizes net recovered
> value.

## Part 6 — Scale (60s)

Evaluation view: DO NOTHING vs ALWAYS RETRY vs REVIVE on 2,000 held-out failures —
REVIVE recovers more than always-retrying with half the interventions. ML metrics table
included underneath.

## Closing

> Don't just detect lost revenue. Decide how to recover it.

## Notes

- Scenario selection is deterministic given the same database seed.
- If asked "is the data real?": no — fully synthetic, honestly disclosed; see Limitations
  in the README.
