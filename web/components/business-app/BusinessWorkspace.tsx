"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "react-i18next";
import {
  ChatWorkspaceProvider,
  type ChatShellBridge,
  type ChatShellView,
  type ChatWorkspace,
} from "@/components/chat/ChatWorkspace";
import type {
  BusinessOverview,
  BusinessWorkspaceInfo,
  ReceiptSummary,
} from "@/lib/business-api";
import type { BusinessDataSource } from "./business-data";
import { periodRange, type Period } from "./business-format";
import { useBusinessActions, type BusinessActions } from "./business-actions";
import BusinessSidebarNav from "./BusinessSidebarNav";
import BusinessCreateMenu from "./BusinessCreateMenu";
import BusinessPanel from "./BusinessPanel";
import BusinessHome from "./BusinessHome";
import ComposerAttachControl from "./ComposerAttachControl";
import ReceiptIntakeDialog, { type IntakeTarget } from "./ReceiptIntakeDialog";
import RecordExpenseDialog from "./RecordExpenseDialog";

export type BusinessPanelState =
  | { kind: "overview" }
  | { kind: "inbox" }
  | { kind: "expenses" }
  | { kind: "updates" }
  | { kind: "receipt"; receiptId: string };

type Records = {
  workspace: BusinessWorkspaceInfo | null;
  overview: BusinessOverview | null;
  inbox: ReceiptSummary[] | null;
  error: boolean;
};

export type BusinessContextValue = Readonly<{
  source: BusinessDataSource;
  records: Records;
  revision: number;
  reload: () => void;
  period: Period;
  setPeriod: (key: Period["key"]) => void;
  panel: BusinessPanelState;
  openPanel: (panel: BusinessPanelState) => void;
  actions: BusinessActions;
  bridge: ChatShellBridge | null;
  attachedReceipt: ReceiptSummary | null;
  clearAttachedReceipt: () => void;
}>;

const BusinessContext = createContext<BusinessContextValue | null>(null);

export function useBusiness(): BusinessContextValue {
  const value = useContext(BusinessContext);
  if (!value) throw new Error("useBusiness must be used inside BusinessWorkspaceProvider");
  return value;
}

const PANEL_KINDS = new Set(["overview", "inbox", "expenses", "updates"]);

function panelFromUrl(): BusinessPanelState {
  if (typeof window === "undefined") return { kind: "overview" };
  const params = new URL(window.location.href).searchParams;
  const receiptId = params.get("receipt");
  if (receiptId) return { kind: "receipt", receiptId };
  const view = params.get("view");
  if (view && PANEL_KINDS.has(view)) {
    return { kind: view as "overview" | "inbox" | "expenses" | "updates" };
  }
  return { kind: "overview" };
}

function initialShellView(): ChatShellView {
  if (typeof window === "undefined") return "workspace";
  const params = new URL(window.location.href).searchParams;
  return params.has("conversation") || params.get("view") === "chat" ? "chat" : "workspace";
}

function writePanelToUrl(view: ChatShellView, panel: BusinessPanelState) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete("view");
    url.searchParams.delete("receipt");
    if (view === "workspace") {
      if (panel.kind === "receipt") url.searchParams.set("receipt", panel.receiptId);
      else if (panel.kind !== "overview") url.searchParams.set("view", panel.kind);
    } else if (view === "chat" && !url.searchParams.has("conversation")) {
      url.searchParams.set("view", "chat");
    }
    const next = `${url.pathname}${url.search}`;
    if (next !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(window.history.state, "", next);
    }
  } catch {
    // The address bar is a convenience; the shell state is the truth.
  }
}

export function BusinessWorkspaceProvider({
  source,
  children,
}: {
  source: BusinessDataSource;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [panel, setPanel] = useState<BusinessPanelState>(panelFromUrl);
  const [initialView] = useState<ChatShellView>(initialShellView);
  const [periodKey, setPeriodKey] = useState<Period["key"]>("this_month");
  const period = useMemo(() => periodRange(periodKey), [periodKey]);
  const [records, setRecords] = useState<Records>({
    workspace: null,
    overview: null,
    inbox: null,
    error: false,
  });
  const [revision, setRevision] = useState(0);
  const [bridge, setBridge] = useState<ChatShellBridge | null>(null);
  const [intakeTarget, setIntakeTarget] = useState<IntakeTarget | null>(null);
  const [recordExpenseOpen, setRecordExpenseOpen] = useState(false);
  const [attachedReceipt, setAttachedReceipt] = useState<ReceiptSummary | null>(null);
  const drafts = useRef(new Map<string, string>());
  const [draftRevision, setDraftRevision] = useState(0);

  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      source.workspace(),
      source.overview(period.from, period.to),
      source.receipts("inbox"),
    ])
      .then(([workspace, overview, inbox]) => {
        if (!cancelled) setRecords({ workspace, overview, inbox, error: false });
      })
      .catch(() => {
        if (!cancelled) setRecords((current) => ({ ...current, error: true }));
      });
    return () => {
      cancelled = true;
    };
  }, [period.from, period.to, revision, source]);

  // The shell may replace the route while leaving a conversation; writing again
  // once that navigation lands keeps the panel in the address bar.
  const search = useSearchParams().toString();
  useEffect(() => {
    if (bridge) writePanelToUrl(bridge.currentView, panel);
  }, [bridge, panel, search]);

  const openPanel = useCallback(
    (next: BusinessPanelState) => {
      setPanel(next);
      bridge?.showWorkspace();
    },
    [bridge],
  );

  const actions = useBusinessActions({
    records,
    bridge,
    openIntake: setIntakeTarget,
    openRecordExpense: () => setRecordExpenseOpen(true),
    openPanel,
  });

  const value = useMemo<BusinessContextValue>(
    () => ({
      source,
      records,
      revision,
      reload,
      period,
      setPeriod: setPeriodKey,
      panel,
      openPanel,
      actions,
      bridge,
      attachedReceipt,
      clearAttachedReceipt: () => setAttachedReceipt(null),
    }),
    [actions, attachedReceipt, bridge, openPanel, panel, period, records, reload, revision, source],
  );

  const composerPlaceholder = records.workspace?.assistant_available
    ? t("business.composer.placeholder_ask", "Ask about your saved expenses")
    : t("business.composer.placeholder", "Write a message");
  const workspace = useMemo<ChatWorkspace>(() => {
    const draftKeyFor = (shell: ChatShellBridge) => shell.conversationId ?? "new";
    return {
      id: "business",
      initialView,
      profileInHeader: true,
      panelHasComposer: panel.kind === "overview",
      sidebarNav: (shell) => <BusinessSidebarNav shell={shell} />,
      sidebarFooter: (shell) => <BusinessCreateMenu shell={shell} />,
      headerActions: (shell) =>
        shell.isBelowTablet ? <BusinessCreateMenu shell={shell} compact /> : null,
      panel: () => <BusinessPanel />,
      starterEntries: () => actions.starterEntries,
      emptyChatLead: () => <BusinessHome variant="new_chat" />,
      composer: (shell) => {
        const key = draftKeyFor(shell);
        return {
          leadingControl: <ComposerAttachControl />,
          placeholder: composerPlaceholder,
          draftText: drafts.current.get(key) ?? null,
          draftKey: `business-composer-${key}-${draftRevision}`,
          onDraftChange: (text) => {
            drafts.current.set(key, text);
          },
          replaceDraft: (text) => {
            drafts.current.set(key, text);
            setDraftRevision((value) => value + 1);
          },
        };
      },
      onShellChange: (shell) => setBridge(shell),
    };
  }, [actions.starterEntries, composerPlaceholder, draftRevision, initialView, panel.kind]);

  return (
    <BusinessContext.Provider value={value}>
      <ChatWorkspaceProvider value={workspace}>
        {children}
        <ReceiptIntakeDialog
          target={intakeTarget}
          onClose={() => setIntakeTarget(null)}
          onCaptured={(captured, target) => {
            setIntakeTarget(null);
            reload();
            if (target === "composer") setAttachedReceipt(captured);
            else openPanel({ kind: "receipt", receiptId: captured.id });
          }}
        />
        <RecordExpenseDialog
          isOpen={recordExpenseOpen}
          onClose={() => setRecordExpenseOpen(false)}
          onRecorded={() => {
            setRecordExpenseOpen(false);
            reload();
            openPanel({ kind: "expenses" });
          }}
        />
      </ChatWorkspaceProvider>
    </BusinessContext.Provider>
  );
}
