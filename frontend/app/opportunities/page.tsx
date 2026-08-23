"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, inr, Opportunity } from "@/lib/api";

export default function OpportunitiesPage() {
  const [rows, setRows] = useState<Opportunity[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Opportunity[]>("/recovery/opportunities?limit=100")
      .then(setRows)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Recovery Opportunities</h1>
        <button
          onClick={load}
          className="rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
        >
          Refresh
        </button>
      </div>

      {error && <p className="text-red-400">{error}</p>}

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
            <tr className="border-b border-slate-800">
              <th className="px-4 py-3">Opp #</th>
              <th>Risk</th>
              <th>Root Cause</th>
              <th>Prob.</th>
              <th>Best Action</th>
              <th className="text-right">Expected Recovery</th>
              <th>Timing</th>
              <th className="text-right">Confidence</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.id} className="border-b border-slate-800/50 transition hover:bg-slate-800/30">
                <td className="px-4 py-3">
                  <Link href={`/decisions/${o.id}`} className="font-medium text-emerald-400 hover:underline">
                    #{o.id}
                  </Link>
                </td>
                <td>
                  <RiskBadge level={o.risk_level} />
                </td>
                <td className="text-slate-400">{o.root_cause}</td>
                <td>{o.recovery_probability != null ? `${(o.recovery_probability * 100).toFixed(0)}%` : "—"}</td>
                <td className="font-medium">{o.recommended_action ?? "—"}</td>
                <td className="text-right text-emerald-300">
                  {o.expected_recovery != null ? inr(o.expected_recovery) : "—"}
                </td>
                <td className="text-slate-400">{o.recommended_timing ?? "—"}</td>
                <td className="text-right">{o.confidence != null ? `${(o.confidence * 100).toFixed(0)}%` : "—"}</td>
                <td><StatusBadge status={o.status} /></td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-slate-500">
                  No opportunities yet. Run <code className="text-emerald-400">python scripts/run_demo.py</code>{" "}
                  or POST to /recovery/decide.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    CRITICAL: "bg-rose-500/15 text-rose-400",
    HIGH: "bg-orange-500/15 text-orange-300",
    MEDIUM: "bg-amber-500/15 text-amber-300",
    LOW: "bg-emerald-500/15 text-emerald-300",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${map[level] ?? "bg-slate-700 text-slate-300"}`}>
      {level}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    RECOVERED: "bg-emerald-500/15 text-emerald-300",
    LOST: "bg-slate-600/30 text-slate-400",
    EXECUTING: "bg-sky-500/15 text-sky-300",
    DECIDED: "bg-violet-500/15 text-violet-300",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs ${map[status] ?? "bg-slate-700 text-slate-300"}`}>{status}</span>
  );
}

export const dynamic = "force-dynamic";
