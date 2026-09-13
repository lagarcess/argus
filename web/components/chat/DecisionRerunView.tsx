"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DecisionRerun } from "@/lib/decision-contract";
import { openDecision, rerunDecision } from "@/lib/decisions-api";
import { rerunCard, rerunErrorMessage, type RerunError } from "@/lib/computed-rerun";
import { decisionRerunTreatment } from "@/lib/tool-outcome-treatment";
import type { ToolResultCard, ToolScalar, ToolTranslator } from "@/lib/tool-result-card";
import { ComputedRerunPanels } from "./ComputedRerunPanel";

type Loaded = { reruns: DecisionRerun[]; latest: Array<ToolResultCard | null> };

/**
 * A reopened decision: the backend re-runs every stored calculation on open,
 * and a changed input re-runs again beside its own calculation. The decision
 * itself never changes.
 */
export default function DecisionRerunView({ decisionId }: { decisionId: string }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language ?? "en";
  const [state, setState] = useState<{ status: "loading" } | { status: "error" } | ({ status: "ready" } & Loaded)>({ status: "loading" });
  const [busy, setBusy] = useState(false);
  const [transportError, setTransportError] = useState<RerunError | null>(null);
  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    openDecision(decisionId)
      .then((opened) => { if (active) setState({ status: "ready", reruns: opened.reruns, latest: opened.reruns.map(() => null) }); })
      .catch(() => { if (active) setState({ status: "error" }); });
    return () => { active = false; };
  }, [decisionId]);
  const rerun = useCallback(async (calculation: number, changes: Record<string, ToolScalar>) => {
    setBusy(true);
    setTransportError(null);
    try {
      const response = await rerunDecision(decisionId, changes, calculation);
      const card = rerunCard(response.reruns[calculation]);
      setState((current) => current.status === "ready"
        ? { ...current, latest: current.latest.map((latest, index) => (index === calculation ? card : latest)) }
        : current);
    } catch {
      setTransportError({ calculation, message: t("tools.card.recompute_failed") });
    } finally {
      setBusy(false);
    }
  }, [decisionId, t]);
  if (state.status === "loading") return <p role="status" className="text-sm text-black/50 dark:text-white/50">{t("tools.decision.loading")}</p>;
  if (state.status === "error") return <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">{t("tools.decision.load_failed")}</p>;
  return <DecisionReruns decisionId={decisionId} reruns={state.reruns} latest={state.latest} busy={busy} transportError={transportError}
    onRerun={(calculation, changes) => { void rerun(calculation, changes); }} t={t} locale={locale} />;
}

/** The opened decision's calculations in marker order, each stored result beside its latest. */
export function DecisionReruns({ decisionId, reruns, latest, busy, transportError, onRerun, t, locale }: {
  decisionId: string;
  reruns: DecisionRerun[];
  latest: Array<ToolResultCard | null>;
  busy: boolean;
  transportError: RerunError | null;
  onRerun: (calculation: number, changes: Record<string, ToolScalar>) => void;
  t: ToolTranslator;
  locale: string;
}) {
  const calculations = reruns.map((opened, index) => {
    const unavailable = opened.status === "unavailable" && opened.reason_code ? decisionRerunTreatment(opened.reason_code, t) : null;
    return {
      stored: rerunCard(opened),
      latest: latest[index] ?? null,
      unavailable,
      transportError: rerunErrorMessage(transportError, index),
      labels: { stored: t("tools.decision.stored"), latest: t("tools.decision.today") },
      fallback: unavailable ? <ComputedRerunPanelFallback treatmentMessage={unavailable.message} /> : null,
    };
  });
  if (calculations.every((calculation) => !calculation.stored && !calculation.fallback)) return null;
  return <div data-testid="decision-rerun-view" data-decision-id={decisionId}>
    <ComputedRerunPanels calculations={calculations} busy={busy} onRerun={onRerun} t={t} locale={locale} />
  </div>;
}

function ComputedRerunPanelFallback({ treatmentMessage }: { treatmentMessage: string }) {
  return <p role="status" data-testid="computed-rerun-unavailable" className="text-sm text-black/60 dark:text-white/60">{treatmentMessage}</p>;
}
