const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${API}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error ${res.status}`);
  }

  return res.json();
}

/* =========================
   Recovery
========================= */

export interface CandidateAction {
  action_type: string;
  timing: string | null;
  predicted_probability: number;
  expected_recovery: number;
  friction_cost: number;
  action_cost: number;
  risk_penalty: number;
  net_expected_value: number;
  policy_valid: boolean;
  rejection_reasons: string[];
}

export interface Opportunity {
  id: number;
  payment_id: number;
  customer_id: number;
  merchant_id: number;
  risk_level: string;
  root_cause: string;
  recommended_action: string | null;
  expected_recovery: number | null;
  recovery_probability: number | null;
  recommended_timing?: string | null;
  confidence?: number | null;
  status: string;
  created_at: string;
}

export interface OpportunityDetail extends Opportunity {
  actions: CandidateAction[];
  outcome: {
    outcome: string;
    recovered_amount: number;
    execution_channel: string;
    external_reference: string | null;
    completed_at: string | null;
  } | null;
}

/* =========================
   Command Center
========================= */

export interface CommandCenter {
  revenue_at_risk: number;
  failed_payments: number;
  recoverable_revenue: number;
  recovered_revenue: number;
  recovery_rate: number;
  recovery_base: number;
  open_opportunities: number;

  by_failure_reason: {
    reason: string;
    count: number;
    amount: number;
  }[];

  payment_method_health: {
    method: string;
    failure_rate: number;
    transactions: number;
  }[];
}

/* =========================
   Evaluation
========================= */

export interface StrategyEvaluation {
  strategy: string;
  revenue_at_risk: number;
  revenue_recovered: number;
  recovery_rate: number;
  interventions: number;
  unnecessary_interventions: number;
  average_recovery_value: number;
  incremental_revenue: number | null;
}

export interface MLMetric {
  type?: string;
  constant?: number;
  roc_auc?: number | null;
  precision?: number | null;
  recall?: number | null;
  f1?: number | null;
  brier_calibration?: number | null;
  test_rows?: number;
  note?: string;
}

export interface MLEvaluationMetrics {
  models: Record<string, MLMetric>;
  feature_names: string[];
  model_version: string;
}

export interface EvaluationSummary {
  generated_at: string;
  transactions_evaluated: number;
  strategies: StrategyEvaluation[];

  revive_action_distribution?: Record<string, number>;

  ml_metrics?: MLEvaluationMetrics | null;
}

/* =========================
   Currency
========================= */

export const inr = (v: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(v);