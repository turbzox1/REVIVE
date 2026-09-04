"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, CommandCenter, inr } from "@/lib/api";

const COLORS = [
  "#34d399",
  "#60a5fa",
  "#f472b6",
  "#fbbf24",
  "#a78bfa",
  "#f87171",
  "#2dd4bf",
  "#fb923c",
  "#94a3b8",
];

export default function CommandCenterPage() {
  const [data, setData] = useState<CommandCenter | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CommandCenter>("/stats/command-center")
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <p className="text-red-400">
        Backend unavailable: {error}
      </p>
    );
  }

  if (!data) {
    return <p className="text-slate-500">Loading...</p>;
  }

  const cards = [
    {
      label: "Revenue at Risk",
      value: inr(data.revenue_at_risk),
      sub: `${data.failed_payments} failed payment${
        data.failed_payments === 1 ? "" : "s"
      }`,
      accent: "text-rose-400",
    },
    {
      label: "Recoverable Revenue",
      value: inr(data.recoverable_revenue),
      sub: `${data.open_opportunities} open opportunit${
        data.open_opportunities === 1 ? "y" : "ies"
      }`,
      accent: "text-amber-300",
    },
    {
      label: "Recovered Revenue",
      value: inr(data.recovered_revenue),
      sub: "successful recovery outcomes",
      accent: "text-emerald-400",
    },
    {
      label: "Recovery Rate",
      value: `${(data.recovery_rate * 100).toFixed(1)}%`,
      sub: `of ${inr(data.recovery_base)} recovery base`,
      accent: "text-sky-400",
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">
          Command Center
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          Autonomous Revenue Recovery & Decision Engine
        </p>
      </div>

      {/* KPI CARDS */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
          >
            <p className="text-xs uppercase tracking-wide text-slate-500">
              {card.label}
            </p>

            <p
              className={`mt-2 text-2xl font-bold ${card.accent}`}
            >
              {card.value}
            </p>

            <p className="mt-1 text-xs text-slate-500">
              {card.sub}
            </p>
          </div>
        ))}
      </div>

      {/* CHARTS */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* FAILURE REASONS */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 lg:col-span-2">
          <div className="mb-4">
            <h2 className="font-medium">
              Revenue at Risk by Failure Reason
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Current failed payments grouped by root cause
            </p>
          </div>

          {data.by_failure_reason.length === 0 ? (
            <div className="flex h-[260px] items-center justify-center text-sm text-slate-500">
              No failed payments recorded.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.by_failure_reason}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#1e293b"
                />

                <XAxis
                  dataKey="reason"
                  tick={{
                    fill: "#64748b",
                    fontSize: 10,
                  }}
                  interval={0}
                  angle={-20}
                  textAnchor="end"
                />

                <YAxis
                  tick={{
                    fill: "#64748b",
                    fontSize: 11,
                  }}
                  tickFormatter={(value) =>
                    `₹${(value / 1000).toFixed(0)}K`
                  }
                />

                <Tooltip
                  contentStyle={{
                    background: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                  }}
                  labelStyle={{
                    color: "#e2e8f0",
                  }}
                  formatter={
                    ((value: unknown) =>
                      inr(Number(value))) as never
                  }
                />

                <Bar
                  dataKey="amount"
                  radius={[4, 4, 0, 0]}
                >
                  {data.by_failure_reason.map((_, index) => (
                    <Cell
                      key={index}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* PAYMENT METHOD HEALTH */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="mb-4">
            <h2 className="font-medium">
              Payment Method Health (7d)
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Failure rate by payment method
            </p>
          </div>

          {data.payment_method_health.length === 0 ? (
            <div className="flex h-[200px] items-center justify-center text-sm text-slate-500">
              No payment data available.
            </div>
          ) : (
            <ul className="space-y-4">
              {data.payment_method_health.map((method) => {
                const failurePercent =
                  method.failure_rate * 100;

                const barWidth = Math.min(
                  failurePercent / 40,
                  1
                );

                const barColor =
                  failurePercent > 25
                    ? "bg-rose-500"
                    : failurePercent > 15
                    ? "bg-amber-400"
                    : "bg-emerald-500";

                const textColor =
                  failurePercent > 25
                    ? "text-rose-400"
                    : failurePercent > 15
                    ? "text-amber-300"
                    : "text-emerald-400";

                return (
                  <li key={method.method}>
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">
                        {method.method}
                      </span>

                      <span className={textColor}>
                        {failurePercent.toFixed(1)}% fail
                      </span>
                    </div>

                    <div className="mt-2 h-1.5 w-full rounded bg-slate-800">
                      <div
                        className={`h-1.5 rounded ${barColor}`}
                        style={{
                          width: `${Math.max(
                            barWidth * 100,
                            4
                          )}%`,
                        }}
                      />
                    </div>

                    <p className="mt-1 text-xs text-slate-600">
                      {method.transactions} transaction
                      {method.transactions === 1 ? "" : "s"}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>

      {/* RECOVERY QUEUE */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="font-medium">
              High-Priority Recovery Queue
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Recovery opportunities requiring action
            </p>
          </div>

          <Link
            href="/opportunities"
            className="text-sm text-emerald-400 hover:underline"
          >
            View all →
          </Link>
        </div>

        <OpportunityMiniQueue />
      </section>
    </div>
  );
}

function OpportunityMiniQueue() {
  const [rows, setRows] = useState<
    {
      id: number;
      root_cause: string;
      expected_recovery: number | null;
      recovery_probability: number | null;
      recommended_action: string | null;
      risk_level: string;
      status?: string;
    }[]
  >([]);

  useEffect(() => {
    api<never[]>("/recovery/opportunities?limit=6")
      .then((data) => setRows(data as never))
      .catch(() => setRows([]));
  }, []);

  if (!rows.length) {
    return (
      <div className="rounded-lg border border-slate-800/60 bg-slate-950/30 p-6 text-center">
        <p className="text-sm text-slate-500">
          No recovery opportunities currently require attention.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-slate-500">
          <tr>
            <th className="pb-3">#</th>
            <th>Risk</th>
            <th>Root Cause</th>
            <th>Action</th>
            <th>Status</th>
            <th className="text-right">Prob.</th>
            <th className="text-right">Expected</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((opportunity) => (
            <tr
              key={opportunity.id}
              className="border-t border-slate-800/60 hover:bg-slate-800/30"
            >
              <td className="py-3">
                <Link
                  href={`/decisions/${opportunity.id}`}
                  className="text-emerald-400 hover:underline"
                >
                  {opportunity.id}
                </Link>
              </td>

              <td>
                <span
                  className={
                    opportunity.risk_level === "HIGH" ||
                    opportunity.risk_level === "CRITICAL"
                      ? "text-rose-400"
                      : opportunity.risk_level === "MEDIUM"
                      ? "text-amber-300"
                      : "text-emerald-400"
                  }
                >
                  {opportunity.risk_level}
                </span>
              </td>

              <td className="text-slate-400">
                {opportunity.root_cause}
              </td>

              <td>
                {opportunity.recommended_action ?? "—"}
              </td>

              <td>
                <span
                  className={
                    opportunity.status === "RECOVERED"
                      ? "text-emerald-400"
                      : opportunity.status === "EXPIRED"
                      ? "text-slate-500"
                      : "text-amber-300"
                  }
                >
                  {opportunity.status ?? "—"}
                </span>
              </td>

              <td className="text-right">
                {opportunity.recovery_probability != null
                  ? `${(
                      opportunity.recovery_probability * 100
                    ).toFixed(0)}%`
                  : "—"}
              </td>

              <td className="text-right">
                {opportunity.expected_recovery != null
                  ? inr(opportunity.expected_recovery)
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}