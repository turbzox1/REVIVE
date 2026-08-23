"use client";

import { useMemo } from "react";
import ReactFlow, { Background, Edge, Node, Position } from "react-flow-renderer";
import type { OpportunityDetail } from "@/lib/api";

export default function DecisionGraph({ detail }: { detail: OpportunityDetail }) {
  const { nodes, edges } = useMemo(() => {
    const selected = (detail.actions as unknown as { selected: boolean; action_type: string; net_expected_value: number }[]).find(
      (a) => a.selected
    );
    const top3 = [...(detail.actions as unknown as { action_type: string; net_expected_value: number; policy_valid: boolean; predicted_probability: number; selected?: boolean }[])]
      .sort((a, b) => b.net_expected_value - a.net_expected_value)
      .slice(0, 4);

    const nodes: Node[] = [
      {
        id: "payment", position: { x: 250, y: 0 }, sourcePosition: Position.Bottom, targetPosition: Position.Top,
        data: { label: `Payment #${detail.payment_id}` },
        style: nodeStyle("#334155"),
      },
      {
        id: "failure", position: { x: 250, y: 70 }, sourcePosition: Position.Bottom,
        data: { label: `FAILED · ${detail.root_cause}` },
        style: nodeStyle("#7f1d1d"),
      },
      {
        id: "risk", position: { x: 250, y: 140 }, sourcePosition: Position.Bottom,
        data: { label: `${detail.risk_level} risk` },
        style: nodeStyle("#78350f"),
      },
      ...top3.map((a, i) => ({
        id: `action-${a.action_type}`,
        position: { x: -80 + i * 220, y: 230 },
        sourcePosition: Position.Bottom,
        data: { label: `${a.action_type}\n${(a.predicted_probability * 100).toFixed(0)}% · ₹${Math.round(a.net_expected_value).toLocaleString("en-IN")}` },
        style: nodeStyle(a.selected ? "#065f46" : "#1e293b"),
      })),
      {
        id: "decision", position: { x: selectedActionX(top3), y: 330 }, sourcePosition: Position.Bottom,
        data: { label: `DECISION\n${selected?.action_type ?? "—"}` },
        style: nodeStyle("#065f46", true),
      },
      {
        id: "policy", position: { x: selectedActionX(top3), y: 410 }, sourcePosition: Position.Bottom,
        data: { label: "Policy Engine ✓" },
        style: nodeStyle("#1e3a8a"),
      },
      {
        id: "outcome",
        position: { x: selectedActionX(top3), y: 480 },
        data: {
          label: detail.outcome
            ? `Outcome: ${detail.outcome.outcome}${detail.outcome.recovered_amount > 0 ? ` (${detail.outcome.recovered_amount.toLocaleString("en-IN")}₹)` : ""}`
            : "Outcome: pending execution",
        },
        style: nodeStyle(detail.outcome?.outcome === "RECOVERED" ? "#065f46" : "#334155"),
      },
    ];

    const edges: Edge[] = [
      { id: "e1", source: "payment", target: "failure", animated: false, style: edgeStyle },
      { id: "e2", source: "failure", target: "risk", style: edgeStyle },
      ...top3.map((a) => ({
        id: `er-${a.action_type}`,
        source: "risk",
        target: `action-${a.action_type}`,
        style: a.selected ? { stroke: "#34d399" } : edgeStyle,
      })),
      ...(selected
        ? [{ id: "ed", source: `action-${selected.action_type}`, target: "decision", animated: true, style: { stroke: "#34d399" } }]
        : []),
      { id: "ep", source: "decision", target: "policy", style: edgeStyle },
      {
        id: "eo",
        source: "policy",
        target: "outcome",
        style: edgeStyle,
        label: detail.outcome?.execution_channel === "RAZORPAY_TEST_MODE" ? "Razorpay Test Mode" : undefined,
      },
    ];

    return { nodes, edges };
  }, [detail]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      nodesDraggable={false}
      nodesConnectable={false}
    >
      <Background color="#1e293b" gap={16} />
    </ReactFlow>
  );
}

const edgeStyle = { stroke: "#475569" };

function nodeStyle(bg: string, emphasis = false) {
  return {
    background: bg,
    border: emphasis ? "2px solid #34d399" : "1px solid #475569",
    borderRadius: 8,
    color: "#f1f5f9",
    fontSize: 11,
    padding: "8px 12px",
    width: 180,
    textAlign: "center" as const,
    whiteSpace: "pre-line" as const,
  };
}

function selectedActionX(top3: { action_type: string }[]) {
  const idx = top3.findIndex((a) => a.action_type);
  return -80 + Math.max(idx, 0) * 220 + 20;
}
