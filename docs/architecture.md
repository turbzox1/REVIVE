# Architecture

## System flow

```text
┌─────────────┐   ┌──────────────────┐   ┌─────────────────┐
│ Simulator / │ → │ PostgreSQL       │ → │ Feature Builder │
│ Webhooks    │   │ (canonical)      │   │ (context_builder│
└─────────────┘   └──────────────────┘   └────────┬────────┘
                                                  ↓
                                       ┌─────────────────────┐
                                       │ ModelRegistry       │
                                       │ per-action GBMs     │
                                       └────────┬────────────┘
                                                ↓
                                    ┌───────────────────────┐
                                    │ Decision Engine       │
                                    │ p×amount − friction − │
                                    │ cost − risk, ×timing  │
                                    └────────┬──────────────┘
                                             ↓
                                   ┌───────────────────┐
                                   │ Policy Engine     │  ← authoritative
                                   └────────┬──────────┘
                                             ↓
                              ┌──────────────────────────────┐
                              │ Executor                     │
                              │ Razorpay Test Mode | Simulated│
                              └────────┬─────────────────────┘
                                       ↓
                          Webhooks → Outcomes → Evaluation API
```

## Components

| Module | Responsibility |
|---|---|
| `backend/app/models/` | 11 ORM entities, JSONB payloads, FKs, indexes |
| `simulator/payment_simulator.py` | Synthetic transactions with causal failure mechanisms |
| `simulator/recovery_simulator.py` | Ground-truth counterfactual outcome oracle |
| `ml/training/` | Features, action-conditioned labels, model training + metrics |
| `app/ml/predictor.py` | Model registry; loads artifacts at first use |
| `app/services/context_builder.py` | Reconstructs training features from live DB state |
| `app/services/decision_engine.py` | Counterfactual scoring, timing selection, confidence |
| `app/policies/engine.py` | Guardrails: budgets, permissions, ceilings |
| `app/integrations/razorpay.py` | Test Mode payment links, webhook signature verification |
| `app/services/llm/client.py` | Provider-agnostic explanation-only LLM client |
| `frontend/` | Next.js dashboard (5 views) |

## Key invariants

1. **PostgreSQL is canonical.** All state lives there; no SQLite fallback exists.
2. **The policy engine is authoritative.** The decision engine proposes; policy disposes.
   The LLM can neither execute actions nor override policy.
3. **The action space is closed** (`RecoveryActionType`). No component — including any AI
   layer — can introduce new actions.
4. **Determinism**: identical inputs (payment row + models + policy) produce an identical
   decision.
5. **Honest labelling**: every execution records its channel
   (`RAZORPAY_TEST_MODE` vs `SIMULATED`) and the UI surfaces it.
