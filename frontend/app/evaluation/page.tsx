"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  EvaluationSummary,
  MLMetric,
} from "@/lib/api";

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMetric(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }

  return value.toFixed(4);
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function strategyLabel(strategy: string) {
  if (strategy === "REVIVE") return "REVIVE (ours)";
  return strategy;
}

export default function EvaluationPage() {
  const [data, setData] = useState<EvaluationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadEvaluation() {
      try {
        setLoading(true);
        setError(null);

        const result = await api<EvaluationSummary>(
          "/evaluation/summary"
        );

        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load evaluation data"
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadEvaluation();

    return () => {
      cancelled = true;
    };
  }, []);

  const strategies = useMemo(() => data?.strategies ?? [], [data?.strategies]);

  const maxRevenue = useMemo(() => {
    if (!strategies.length) return 1;

    return Math.max(
      ...strategies.map((strategy) => strategy.revenue_recovered),
      1
    );
  }, [strategies]);

  const maxInterventions = useMemo(() => {
    if (!strategies.length) return 1;

    return Math.max(
      ...strategies.map((strategy) => strategy.interventions),
      1
    );
  }, [strategies]);

  /*
   * IMPORTANT:
   *
   * Backend response is:
   *
   * ml_metrics: {
   *   models: {
   *      DO_NOTHING: {...},
   *      RETRY_NOW: {...},
   *      ...
   *   },
   *   feature_names: [...],
   *   model_version: "1.0.0"
   * }
   *
   * Therefore we MUST use:
   *
   * Object.entries(data.ml_metrics.models)
   *
   * NOT:
   *
   * Object.entries(data.ml_metrics)
   */
  const mlModels = useMemo(() => {
    if (!data?.ml_metrics?.models) {
      return [];
    }

    return Object.entries(data.ml_metrics.models);
  }, [data]);

  if (loading) {
    return (
      <main className="min-h-screen bg-[#020617] px-10 py-12 text-white">
        <div className="mx-auto max-w-[1280px]">
          <h1 className="text-3xl font-semibold">Evaluation</h1>
          <p className="mt-2 text-slate-500">
            Loading evaluation results...
          </p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-[#020617] px-10 py-12 text-white">
        <div className="mx-auto max-w-[1280px]">
          <h1 className="text-3xl font-semibold">Evaluation</h1>

          <div className="mt-8 rounded-xl border border-red-900/50 bg-red-950/20 p-6">
            <p className="font-medium text-red-400">
              Failed to load evaluation
            </p>

            <p className="mt-2 text-sm text-red-300/70">
              {error}
            </p>
          </div>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-h-screen bg-[#020617] px-10 py-12 text-white">
        <div className="mx-auto max-w-[1280px]">
          <h1 className="text-3xl font-semibold">Evaluation</h1>
          <p className="mt-2 text-slate-500">
            No evaluation data available.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#020617] px-10 py-10 text-white">
      <div className="mx-auto max-w-[1280px]">

        {/* =========================================================
            HEADER
        ========================================================= */}

        <section>
          <h1 className="text-3xl font-semibold tracking-tight">
            Evaluation
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Measured on{" "}
            <span className="text-slate-400">
              {formatNumber(data.transactions_evaluated)}
            </span>{" "}
            held-out failed payments · generated{" "}
            <span className="text-slate-400">
              {new Date(data.generated_at).toLocaleString("en-IN")}
            </span>
          </p>
        </section>

        {/* =========================================================
            STRATEGY COMPARISON
        ========================================================= */}

        <section className="mt-8 overflow-hidden rounded-xl border border-slate-800 bg-[#080f21]">

          <div className="overflow-x-auto">
            <table className="w-full min-w-[950px] border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-4 font-medium">
                    Strategy
                  </th>

                  <th className="px-4 py-4 text-right font-medium">
                    Revenue Recovered
                  </th>

                  <th className="px-4 py-4 text-right font-medium">
                    Recovery Rate
                  </th>

                  <th className="px-4 py-4 text-right font-medium">
                    Interventions
                  </th>

                  <th className="px-4 py-4 text-right font-medium">
                    Avg Recovery / Intervention
                  </th>

                  <th className="px-4 py-4 text-right font-medium">
                    Incremental vs Do Nothing
                  </th>
                </tr>
              </thead>

              <tbody>
                {strategies.map((strategy) => {
                  const isRevive = strategy.strategy === "REVIVE";

                  return (
                    <tr
                      key={strategy.strategy}
                      className={`border-b border-slate-800/80 last:border-0 ${
                        isRevive
                          ? "bg-emerald-500/[0.06]"
                          : ""
                      }`}
                    >
                      <td className="px-4 py-4 text-sm font-medium">
                        <span
                          className={
                            isRevive
                              ? "text-emerald-400"
                              : "text-slate-200"
                          }
                        >
                          {strategyLabel(strategy.strategy)}
                        </span>
                      </td>

                      <td className="px-4 py-4 text-right text-sm text-slate-200">
                        {formatCurrency(
                          strategy.revenue_recovered
                        )}
                      </td>

                      <td className="px-4 py-4 text-right text-sm text-slate-200">
                        {formatPercent(
                          strategy.recovery_rate
                        )}
                      </td>

                      <td className="px-4 py-4 text-right text-sm text-slate-200">
                        {formatNumber(
                          strategy.interventions
                        )}
                      </td>

                      <td className="px-4 py-4 text-right text-sm text-slate-200">
                        {formatCurrency(
                          strategy.average_recovery_value
                        )}
                      </td>

                      <td className="px-4 py-4 text-right text-sm">
                        {strategy.incremental_revenue ===
                        null ? (
                          <span className="text-slate-500">
                            —
                          </span>
                        ) : (
                          <span className="text-slate-200">
                            +
                            {formatCurrency(
                              strategy.incremental_revenue
                            )}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* =========================================================
            CHARTS
        ========================================================= */}

        <section className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">

          {/* Revenue chart */}
          <div className="rounded-xl border border-slate-800 bg-[#080f21] p-6">
            <h2 className="text-base font-medium text-slate-200">
              Revenue Recovered
            </h2>

            <div className="mt-8 flex h-[260px] items-end justify-around gap-8 border-b border-slate-700 px-8">

              {strategies.map((strategy) => {
                const height =
                  strategy.revenue_recovered /
                  maxRevenue;

                return (
                  <div
                    key={strategy.strategy}
                    className="flex h-full flex-1 flex-col items-center justify-end"
                  >
                    <div className="mb-2 text-xs text-slate-500">
                      {formatCurrency(
                        strategy.revenue_recovered
                      )}
                    </div>

                    <div
                      className={`w-full max-w-[130px] rounded-t-md ${
                        strategy.strategy === "REVIVE"
                          ? "bg-emerald-400"
                          : "bg-emerald-400/90"
                      }`}
                      style={{
                        height: `${Math.max(
                          height * 85,
                          strategy.revenue_recovered > 0
                            ? 3
                            : 0
                        )}%`,
                      }}
                    />
                  </div>
                );
              })}
            </div>

            <div className="mt-3 flex justify-around gap-8 px-8">
              {strategies.map((strategy) => (
                <div
                  key={strategy.strategy}
                  className="flex-1 text-center text-xs text-slate-500"
                >
                  {strategy.strategy}
                </div>
              ))}
            </div>
          </div>

          {/* Intervention chart */}
          <div className="rounded-xl border border-slate-800 bg-[#080f21] p-6">
            <h2 className="text-base font-medium text-slate-200">
              Interventions (customer contacts)
            </h2>

            <div className="mt-8 flex h-[260px] items-end justify-around gap-8 border-b border-slate-700 px-8">

              {strategies.map((strategy) => {
                const height =
                  strategy.interventions /
                  maxInterventions;

                return (
                  <div
                    key={strategy.strategy}
                    className="flex h-full flex-1 flex-col items-center justify-end"
                  >
                    <div className="mb-2 text-xs text-slate-500">
                      {formatNumber(
                        strategy.interventions
                      )}
                    </div>

                    <div
                      className="w-full max-w-[130px] rounded-t-md bg-blue-400"
                      style={{
                        height: `${Math.max(
                          height * 85,
                          strategy.interventions > 0
                            ? 3
                            : 0
                        )}%`,
                      }}
                    />
                  </div>
                );
              })}
            </div>

            <div className="mt-3 flex justify-around gap-8 px-8">
              {strategies.map((strategy) => (
                <div
                  key={strategy.strategy}
                  className="flex-1 text-center text-xs text-slate-500"
                >
                  {strategy.strategy}
                </div>
              ))}
            </div>

            <div className="mt-5 flex items-center justify-center gap-2 text-sm text-blue-400">
              <span className="h-3 w-3 rounded-sm bg-blue-400" />
              Interventions
            </div>
          </div>
        </section>

        {/* =========================================================
            ACTION DISTRIBUTION
        ========================================================= */}

        <section className="mt-8 rounded-xl border border-slate-800 bg-[#080f21] p-6">

          <h2 className="text-base font-medium text-slate-200">
            REVIVE Action Distribution
          </h2>

          <p className="mt-2 text-xs text-slate-500">
            How often REVIVE chose each action — including
            choosing to do nothing.
          </p>

          <div className="mt-5 flex flex-wrap gap-3">
            {Object.entries(
              data.revive_action_distribution ?? {}
            ).map(([action, count]) => (
              <div
                key={action}
                className="rounded-lg border border-slate-700 bg-[#050b18] px-4 py-2 text-sm"
              >
                <span className="text-slate-200">
                  {action}
                </span>

                <span className="ml-2 font-semibold text-emerald-400">
                  {formatNumber(count)}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* =========================================================
            ML MODEL METRICS
        ========================================================= */}

        <section className="mt-8 rounded-xl border border-slate-800 bg-[#080f21] p-6">

          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-base font-medium text-slate-200">
                ML Model Metrics
                <span className="ml-2 text-slate-500">
                  (held-out test set)
                </span>
              </h2>

              <p className="mt-2 text-xs text-slate-500">
                Performance of each action-specific recovery
                model on unseen evaluation data.
              </p>
            </div>

            {data.ml_metrics?.model_version && (
              <div className="text-xs text-slate-500">
                Model version{" "}
                <span className="text-slate-300">
                  {data.ml_metrics.model_version}
                </span>
              </div>
            )}
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[850px] border-collapse">

              <thead>
                <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-3 py-3 font-medium">
                    Action Model
                  </th>

                  <th className="px-3 py-3 text-right font-medium">
                    ROC-AUC
                  </th>

                  <th className="px-3 py-3 text-right font-medium">
                    Precision
                  </th>

                  <th className="px-3 py-3 text-right font-medium">
                    Recall
                  </th>

                  <th className="px-3 py-3 text-right font-medium">
                    F1
                  </th>

                  <th className="px-3 py-3 text-right font-medium">
                    Brier (Calibration)
                  </th>

                  <th className="px-3 py-3 text-right font-medium">
                    Test Rows
                  </th>
                </tr>
              </thead>

              <tbody>

                {mlModels.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-3 py-8 text-center text-sm text-slate-500"
                    >
                      No ML model metrics available.
                    </td>
                  </tr>
                ) : (
                  mlModels.map(
                    ([action, metric]: [string, MLMetric]) => {

                      const isConstant =
                        metric.type === "constant";

                      return (
                        <tr
                          key={action}
                          className="border-b border-slate-800/80 last:border-0"
                        >
                          <td className="px-3 py-4">
                            <div className="font-medium text-slate-200">
                              {action}
                            </div>

                            {isConstant &&
                              metric.note && (
                                <div className="mt-1 text-xs text-slate-500">
                                  {metric.note}
                                </div>
                              )}

                            {!isConstant &&
                              metric.type && (
                                <div className="mt-1 text-xs text-slate-600">
                                  {metric.type}
                                </div>
                              )}
                          </td>

                          <td className="px-3 py-4 text-right text-sm text-slate-300">
                            {formatMetric(
                              metric.roc_auc
                            )}
                          </td>

                          <td className="px-3 py-4 text-right text-sm text-slate-300">
                            {formatMetric(
                              metric.precision
                            )}
                          </td>

                          <td className="px-3 py-4 text-right text-sm text-slate-300">
                            {formatMetric(
                              metric.recall
                            )}
                          </td>

                          <td className="px-3 py-4 text-right text-sm text-slate-300">
                            {formatMetric(metric.f1)}
                          </td>

                          <td className="px-3 py-4 text-right text-sm text-slate-300">
                            {formatMetric(
                              metric.brier_calibration
                            )}
                          </td>

                          <td className="px-3 py-4 text-right text-sm text-slate-300">
                            {metric.test_rows
                              ? formatNumber(
                                  metric.test_rows
                                )
                              : "—"}
                          </td>
                        </tr>
                      );
                    }
                  )
                )}

              </tbody>
            </table>
          </div>

          {/* Feature information */}
          {data.ml_metrics?.feature_names?.length ? (
            <div className="mt-6 border-t border-slate-800 pt-5">

              <div className="text-xs uppercase tracking-wide text-slate-500">
                Features used
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {data.ml_metrics.feature_names.map(
                  (feature) => (
                    <span
                      key={feature}
                      className="rounded-md border border-slate-800 bg-[#050b18] px-2.5 py-1 text-xs text-slate-500"
                    >
                      {feature}
                    </span>
                  )
                )}
              </div>

            </div>
          ) : null}

        </section>

        {/* =========================================================
            FOOTER
        ========================================================= */}

        <footer className="py-8 text-xs text-slate-600">
          Razorpay Buildathon prototype · Test Mode execution
          is real API calls; actions labelled &quot;Simulated&quot; use
          the synthetic outcome engine.
        </footer>

      </div>
    </main>
  );
}