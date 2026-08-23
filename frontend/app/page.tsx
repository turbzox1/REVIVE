"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, CommandCenter, inr } from "@/lib/api";

const COLORS = ["#34d399", "#60a5fa", "#f472b6", "#fbbf24", "#a78bfa", "#f87171", "#2dd4bf", "#fb923c", "#94a3b8"];

export default function CommandCenterPage() {
  const [data, setData] = useState<CommandCenter | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CommandCenter>("/stats/command-center").then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="text-red-400">Backend unavailable: {error}</p>;
  if (!data) return <p className="text-slate-500">Loading…</p>;

  const cards = [
    { label: "Revenue at Risk", value: inr(data.revenue_at_risk), sub: `${data.failed_payments} failed payments`, accent: "text-rose-400" },
    { label: "Recoverable Revenue", value: inr(data.recoverable_revenue), sub: `${data.open_opportunities} open opportunities`, accent: "text-amber-300" },
    { label: "Recovered Revenue", value: inr(data.recovered_revenue), sub: "recorded outcomes", accent: "text-emerald-400" },
    { label: "Recovery Rate", value: `${(data.recovery_rate * 100).toFixed(1)}%`, sub: "of revenue at risk", accent: "text-sky-400" },
  ];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Command Center</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <p className="text-xs uppercase tracking-wide text-slate-500">{c.label}</p>
            <p className={`mt-2 text-2xl font-bold ${c.accent}`}>{c.value}</p>
            <p className="mt-1 text-xs text-slate-500">{c.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 lg:col-span-2">
          <h2 className="mb-4 font-medium">Revenue at Risk by Failure Reason</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.by_failure_reason}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="reason" tick={{ fill: "#64748b", fontSize: 10 }} interval={0} angle={-20} textAnchor="end" />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1e5).toFixed(0)}L`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
                formatter={((v: unknown) => inr(Number(v))) as never}
              />
              <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
                {data.by_failure_reason.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <h2 className="mb-4 font-medium">Payment Method Health (7d)</h2>
          <ul className="space-y-3">
            {data.payment_method_health.map((m) => {
              const pct = Math.min(m.failure_rate * 100 / 40, 1);
              const color = m.failure_rate > 0.25 ? "bg-rose-500" : m.failure_rate > 0.15 ? "bg-amber-400" : "bg-emerald-500";
              return (
                <li key={m.method}>
                  <div className="flex justify-between text-sm">
                    <span>{m.method}</span>
                    <span className={m.failure_rate > 0.25 ? "text-rose-400" : "text-slate-300"}>
                      {(m.failure_rate * 100).toFixed(1)}% fail
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full rounded bg-slate-800">
                    <div className={`h-1.5 rounded ${color}`} style={{ width: `${Math.max(pct * 100, 4)}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-medium">High-Priority Recovery Queue</h2>
          <Link href="/opportunities" className="text-sm text-emerald-400 hover:underline">
            View all →
          </Link>
        </div>
        <OpportunityMiniQueue />
      </section>
    </div>
  );
}

function OpportunityMiniQueue() {
  const [rows, setRows] = useState<{ id: number; root_cause: string; expected_recovery: number | null; recovery_probability: number | null; recommended_action: string | null; risk_level: string }[]>([]);

  useEffect(() => {
    api<never[]>("/recovery/opportunities?limit=6")
      .then((d) => setRows(d as never))
      .catch(() => setRows([]));
  }, []);

  if (!rows.length) return <p className="text-sm text-slate-500">No decisions yet — run the demo script or open Opportunities to generate decisions.</p>;

  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs uppercase text-slate-500">
        <tr><th className="pb-2">#</th><th>Risk</th><th>Root Cause</th><th>Action</th><th className="text-right">Prob.</th><th className="text-right">Expected</th></tr>
      </thead>
      <tbody>
        {rows.map((o) => (
          <tr key={o.id} className="border-t border-slate-800/60 hover:bg-slate-800/30">
            <td className="py-2">
              <Link href={`/decisions/${o.id}`} className="text-emerald-400 hover:underline">{o.id}</Link>
            </td>
            <td>{o.risk_level}</td>
            <td className="text-slate-400">{o.root_cause}</td>
            <td>{o.recommended_action}</td>
            <td className="text-right">{o.recovery_probability != null ? `${(o.recovery_probability * 100).toFixed(0)}%` : "—"}</td>
            <td className="text-right">{o.expected_recovery != null ? inr(o.expected_recovery) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
