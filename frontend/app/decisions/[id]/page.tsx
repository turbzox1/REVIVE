"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, inr, OpportunityDetail } from "@/lib/api";
import DecisionGraph from "@/components/DecisionGraph";

interface Detail extends OpportunityDetail {
  actions: ({ selected: boolean } & {
    action_type: string; timing: string | null; predicted_probability: number;
    expected_recovery: number; friction_cost: number; action_cost: number;
    risk_penalty: number; net_expected_value: number; policy_valid: boolean;
    rejection_reasons: string[];
  })[];
}

export default function DecisionPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [d, setD] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [execResult, setExecResult] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(() => {
    if (!id) return;
    api<Detail>(`/recovery/opportunities/${id}`)
      .then(setD)
      .catch((e) => setError(String(e)));
  }, [id]);

  useEffect(load, [load]);

  async function execute() {
    if (!id) return;
    setExecuting(true);
    setError(null);
    try {
      const r = await api<Record<string, unknown>>(`/recovery/${id}/execute`, { method: "POST" });
      setExecResult(r);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setExecuting(false);
    }
  }

  if (error && !d) return <p className="text-red-400">{error}</p>;
  if (!d) return <p className="text-slate-500">Loading…</p>;

  const selected = d.actions.find((a) => a.selected);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold">
          Opportunity #{d.id}{" "}
          <span className="text-sm font-normal text-slate-500">payment #{d.payment_id}</span>
        </h1>
        <span
          className={`rounded px-2.5 py-1 text-xs font-medium ${
            d.risk_level === "CRITICAL" || d.risk_level === "HIGH"
              ? "bg-rose-500/15 text-rose-300"
              : "bg-amber-500/15 text-amber-300"
          }`}
        >
          {d.risk_level} RISK · {d.root_cause}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Actions considered */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 lg:col-span-2">
          <h2 className="mb-4 font-medium">Actions Considered (counterfactual evaluation)</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="pb-2">Action</th>
                <th className="text-right">Prob.</th>
                <th className="text-right">Exp. Recovery</th>
                <th className="text-right">Friction</th>
                <th className="text-right">Risk</th>
                <th className="text-right">Net EV</th>
              </tr>
            </thead>
            <tbody>
              {[...d.actions]
                .sort((a, b) => b.net_expected_value - a.net_expected_value)
                .map((a) => (
                  <tr
                    key={a.action_type}
                    className={`border-t border-slate-800/60 ${
                      a.selected ? "bg-emerald-500/10" : !a.policy_valid ? "opacity-50" : ""
                    }`}
                  >
                    <td className="py-2">
                      {a.selected ? (
                        <span className="font-semibold text-emerald-300">✓ {a.action_type}</span>
                      ) : (
                        <>
                          {a.action_type}
                          {!a.policy_valid && (
                            <span
                              className="ml-2 cursor-help text-xs text-rose-400"
                              title={a.rejection_reasons.join("; ")}
                            >
                              policy-rejected
                            </span>
                          )}
                        </>
                      )}
                      {a.timing && <span className="ml-2 text-xs text-slate-500">@{a.timing}</span>}
                    </td>
                    <td className="text-right">{(a.predicted_probability * 100).toFixed(0)}%</td>
                    <td className="text-right">{inr(a.expected_recovery)}</td>
                    <td className="text-right text-slate-500">{inr(a.friction_cost + a.action_cost)}</td>
                    <td className="text-right text-slate-500">{inr(a.risk_penalty)}</td>
                    <td className={`text-right font-medium ${a.net_expected_value > 0 ? "text-emerald-300" : "text-rose-300"}`}>
                      {inr(a.net_expected_value)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <button
              onClick={execute}
              disabled={executing || d.outcome !== null || selected?.action_type === undefined}
              className="rounded-lg bg-emerald-500 px-5 py-2.5 font-medium text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {executing ? "Executing…" : d.outcome ? "Executed" : "Execute Recovery"}
            </button>
            {selected && selected.action_type === "DO_NOTHING" && (
              <span className="text-sm text-amber-300">
                REVIVE recommends restraint — no intervention is economically justified.
              </span>
            )}
          </div>

          {execResult && (
            <pre className="mt-4 overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-300">
              {JSON.stringify(execResult, null, 2)}
            </pre>
          )}
          {d.outcome && (
            <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950/70 p-4 text-sm">
              <p className="font-medium">
                Outcome:{" "}
                <span className={d.outcome.outcome === "RECOVERED" ? "text-emerald-300" : "text-slate-300"}>
                  {d.outcome.outcome}
                </span>{" "}
                {d.outcome.recovered_amount > 0 && `· ${inr(d.outcome.recovered_amount)}`}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Channel:{" "}
                {d.outcome.execution_channel === "RAZORPAY_TEST_MODE"
                  ? "Executed through Razorpay Test Mode"
                  : "Simulated recovery action"}
                {d.outcome.external_reference ? ` · ${d.outcome.external_reference}` : ""}
              </p>
            </div>
          )}
        </section>

        {/* Selected summary */}
        <section className="space-y-4">
          <div className="rounded-xl border border-emerald-800/50 bg-emerald-500/5 p-5">
            <p className="text-xs uppercase tracking-wide text-emerald-500">Selected</p>
            <p className="mt-1 text-lg font-bold">{selected?.action_type ?? "—"}</p>
            <dl className="mt-3 space-y-1.5 text-sm">
              <Row k="Expected recovery" v={inr(selected?.expected_recovery ?? 0)} />
              <Row k="Timing" v={selected?.timing ?? "—"} />
              <Row k="Probability" v={`${((selected?.predicted_probability ?? 0) * 100).toFixed(0)}%`} />
              <Row k="Confidence" v={`${((d.confidence ?? 0) * 100).toFixed(0)}%`} />
            </dl>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-sm leading-relaxed text-slate-300">
            <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Why</p>
            {d.recommended_action === "DO_NOTHING" ? (
              <p>
                Every intervention costs more than it is expected to recover. REVIVE chooses to
                spend nothing and contact nobody.
              </p>
            ) : (
              <p>
                <strong className="text-white">{selected?.action_type}</strong> maximizes net
                expected recovery after friction ({inr((selected?.friction_cost ?? 0) + (selected?.action_cost ?? 0))})
                and churn-risk penalty ({inr(selected?.risk_penalty ?? 0)}) while remaining inside
                the merchant&apos;s intervention policy.
              </p>
            )}
          </div>
        </section>
      </div>

      {/* Decision graph */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="mb-4 font-medium">Decision Graph</h2>
        <div className="h-[420px]">
          <DecisionGraph detail={d} />
        </div>
      </section>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-medium text-white">{v}</dd>
    </div>
  );
}

export const dynamic = "force-dynamic";
