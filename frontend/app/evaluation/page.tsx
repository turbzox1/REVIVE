"use client";

import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, EvaluationSummary, inr } from "@/lib/api";

export default function EvaluationPage() {
  const [data, setData] = useState<EvaluationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<EvaluationSummary>("/evaluation/summary").then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="text-red-400">Backend unavailable: {error}</p>;
  if (!data) return <p className="text-slate-500">Loading…</p>;

  const hasData = data.strategies.length > 0;
  const chartData = data.strategies.map((s) => ({
    name: s.strategy,
    "Revenue Recovered": s.revenue_recovered,
    Interventions: s.interventions,
  }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Evaluation</h1>
        <p className="mt-1 text-sm text-slate-500">
          Measured on {data.transactions_evaluated.toLocaleString("en-IN")} held-out failed payments ·
          generated {new Date(data.generated_at).toLocaleString()}
        </p>
      </div>

      {!hasData ? (
        <p className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-slate-400">
          No evaluation results yet. Run <code className="text-emerald-400">python scripts/run_evaluation.py</code>.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="px-4 py-3">Strategy</th>
                  <th className="text-right">Revenue Recovered</th>
                  <th className="text-right">Recovery Rate</th>
                  <th className="text-right">Interventions</th>
                  <th className="text-right">Avg Recovery / Intervention</th>
                  <th className="text-right">Incremental vs Do Nothing</th>
                </tr>
              </thead>
              <tbody>
                {data.strategies.map((s) => (
                  <tr
                    key={s.strategy}
                    className={`border-b border-slate-800/50 ${s.strategy === "REVIVE" ? "bg-emerald-500/5" : ""}`}
                  >
                    <td className={`px-4 py-3 font-medium ${s.strategy === "REVIVE" ? "text-emerald-300" : ""}`}>
                      {s.strategy}{s.strategy === "REVIVE" && " (ours)"}
                    </td>
                    <td className="text-right">{inr(s.revenue_recovered)}</td>
                    <td className="text-right">{(s.recovery_rate * 100).toFixed(1)}%</td>
                    <td className="text-right">{s.interventions.toLocaleString("en-IN")}</td>
                    <td className="text-right">{inr(s.average_recovery_value)}</td>
                    <td className="text-right">{s.incremental_revenue != null ? `+${inr(s.incremental_revenue)}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h2 className="mb-4 font-medium">Revenue Recovered</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1e5).toFixed(0)}L`} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} formatter={((v: unknown) => inr(Number(v))) as never} />
                  <Bar dataKey="Revenue Recovered" fill="#34d399" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h2 className="mb-4 font-medium">Interventions (customer contacts)</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} cursor={{ fill: "#1e293b55" }} />
                  <Legend />
                  <Bar dataKey="Interventions" fill="#60a5fa" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {data.revive_action_distribution && (
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h2 className="mb-2 font-medium">REVIVE Action Distribution</h2>
              <p className="mb-4 text-xs text-slate-500">
                How often REVIVE chose each action — including choosing to do nothing.
              </p>
              <div className="flex flex-wrap gap-3">
                {Object.entries(data.revive_action_distribution).map(([k, v]) => (
                  <span key={k} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm">
                    {k} <strong className={k === "DO_NOTHING" ? "text-amber-300" : "text-emerald-300"}>{v}</strong>
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {data.ml_metrics && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <h2 className="mb-4 font-medium">ML Model Metrics (held-out test set)</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr><th className="pb-2">Action Model</th><th>ROC-AUC</th><th>Precision</th><th>Recall</th><th>F1</th><th>Brier (calibration)</th></tr>
            </thead>
            <tbody>
              {Object.entries(data.ml_metrics).map(([action, m]) => (
                <tr key={action} className="border-t border-slate-800/60">
                  <td className="py-2">{action}</td>
                  <td>{fmt(m.roc_auc)}</td>
                  <td>{fmt(m.precision)}</td>
                  <td>{fmt(m.recall)}</td>
                  <td>{fmt(m.f1)}</td>
                  <td>{fmt(m.brier_calibration)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

const fmt = (v: unknown) => (typeof v === "number" ? v.toFixed(3) : "—");

export const dynamic = "force-dynamic";
