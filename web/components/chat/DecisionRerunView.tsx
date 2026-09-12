"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DecisionOpenResponse } from "@/lib/decision-contract";
import { openDecision, rerunDecision } from "@/lib/decisions-api";
import { rerunCard } from "@/lib/computed-rerun";
import { decisionRerunTreatment } from "@/lib/tool-outcome-treatment";
import type { ToolResultCard, ToolScalar } from "@/lib/tool-result-card";
import ComputedRerunPanel from "./ComputedRerunPanel";

type Loaded = { opened: DecisionOpenResponse; latest: ToolResultCard | null };

/**
 * A reopened decision: the backend re-runs the stored inputs on open, and a
 * changed input re-runs again beside it. The decision itself never changes.
 */
export default function DecisionRerunView({ decisionId }: { decisionId: string }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language ?? "en";
  const [state, setState] = useState<{ status: "loading" } | { status: "error" } | ({ status: "ready" } & Loaded)>({ status: "loading" });
  const [busy, setBusy] = useState(false);
  const [transportError, setTransportError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    openDecision(decisionId)
      .then((opened) => { if (active) setState({ status: "ready", opened, latest: null }); })
      .catch(() => { if (active) setState({ status: "error" }); });
    return () => { active = false; };
  }, [decisionId]);
  const rerun = useCallback(async (changes: Record<string, ToolScalar>) => {
    setBusy(true);
    setTransportError(null);
    try {
      const response = await rerunDecision(decisionId, changes);
      setState((current) => current.status === "ready" ? { ...current, latest: rerunCard(response.rerun) } : current);
    } catch {
      setTransportError(t("tools.card.recompute_failed"));
    } finally {
      setBusy(false);
    }
  }, [decisionId, t]);
  if (state.status === "loading") return <p role="status" className="text-sm text-black/50 dark:text-white/50">{t("tools.decision.loading")}</p>;
  if (state.status === "error") return <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">{t("tools.decision.load_failed")}</p>;
  const { rerun: opened } = state.opened;
  const stored = rerunCard(opened);
  const unavailable = opened.status === "unavailable" && opened.reason_code ? decisionRerunTreatment(opened.reason_code, t) : null;
  if (!stored) {
    return unavailable
      ? <div data-testid="decision-rerun-view"><ComputedRerunPanelFallback treatmentMessage={unavailable.message} /></div>
      : null;
  }
  return <div data-testid="decision-rerun-view" data-decision-id={decisionId}>
    <ComputedRerunPanel stored={stored} latest={state.latest} busy={busy} unavailable={unavailable} transportError={transportError} onRerun={(changes) => { void rerun(changes); }} t={t} locale={locale}
      labels={{ stored: t("tools.decision.stored"), latest: t("tools.decision.today") }} />
  </div>;
}

function ComputedRerunPanelFallback({ treatmentMessage }: { treatmentMessage: string }) {
  return <p role="status" data-testid="computed-rerun-unavailable" className="text-sm text-black/60 dark:text-white/60">{treatmentMessage}</p>;
}
