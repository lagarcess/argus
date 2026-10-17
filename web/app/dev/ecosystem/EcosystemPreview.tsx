"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "react-i18next";
import { Bell, ChevronDown, CircleHelp, History, Plus, SlidersHorizontal, SquarePen, UserRound, X } from "lucide-react";
import ChatHeaderTitle from "@/components/chat/ChatHeaderTitle";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import { consumeOverlayEntriesForNavigation } from "@/lib/overlay-history";
import AccountPanels, { type AccountPanel } from "./AccountPanels";
import { AccountInspector } from "./AccountDetail";
import PreviewChat from "./PreviewChat";
import PreviewDialogs, { type SimpleDialog } from "./PreviewDialogs";
import PreviewNavigation from "./PreviewNavigation";
import { AccountsView, HomeView, PlanView, SearchView, SettingsView, UpdatesView, type SearchCategory, type ViewActions } from "./PreviewViews";
import { EmptyState } from "./PreviewPrimitives";
import { PREVIEW_STATES, PREVIEW_VIEWS, SAMPLE, previewCopy, previewHref, previewLocation, type PreviewView, type RecentId, type SampleAccount } from "./preview-content";
import styles from "./ecosystem-preview.module.css";

export default function EcosystemPreview() {
  const searchParams = useSearchParams();
  const location = previewLocation(searchParams);
  const { view, state, audience } = location;
  const { isBelowDesktop } = useResponsiveLayout();
  const selectedAccount = SAMPLE.accounts.find((account) => account.id === location.account) ?? null;
  const { i18n } = useTranslation();
  const copy = previewCopy(i18n.resolvedLanguage ?? i18n.language ?? "en");
  const [dialog, setDialog] = useState<SimpleDialog | null>(null);
  const [accountPanel, setAccountPanel] = useState<AccountPanel | null>(null);
  const [draft, setDraft] = useState("");
  const [recent, setRecent] = useState<RecentId | null>(null);
  const [notice, setNotice] = useState<"sendNotice" | "newChatNote" | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchCategory, setSearchCategory] = useState<SearchCategory>("all");
  const [accountFilter, setAccountFilter] = useState<SampleAccount | null>(null);
  const mainRef = useRef<HTMLElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const inspectorOpenerRef = useRef<HTMLElement | null>(null);
  const previousAccount = useRef(location.account);
  const previousView = useRef(view);
  const hadDialog = useRef(false);
  const hasDialog = dialog !== null || accountPanel !== null;

  useEffect(() => {
    if (previousView.current !== view) {
      mainRef.current?.focus({ preventScroll: true });
      mainRef.current?.scrollTo({ top: 0, behavior: "instant" });
    } else if (hadDialog.current && !hasDialog) {
      (openerRef.current?.isConnected ? openerRef.current : mainRef.current)?.focus({ preventScroll: true });
    } else if (previousAccount.current && !location.account && !hasDialog) {
      (inspectorOpenerRef.current?.isConnected ? inspectorOpenerRef.current : mainRef.current)?.focus();
    }
    if (location.account) {
      const row = mainRef.current?.querySelector<HTMLElement>(`[data-preview-account="${location.account}"]`);
      if (row) inspectorOpenerRef.current = row;
    }
    previousView.current = view;
    previousAccount.current = location.account;
    hadDialog.current = hasDialog;
  }, [view, hasDialog, location.account]);

  const href = (changes: Partial<typeof location> = {}) => previewHref({ ...location, account: undefined, ...changes });
  const updateLocation = (changes: Partial<typeof location>) => {
    const replacingOverlay = consumeOverlayEntriesForNavigation();
    setDialog(null);
    setAccountPanel(null);
    if (replacingOverlay) window.history.replaceState(null, "", href(changes));
    else window.history.pushState(null, "", href(changes));
  };
  const navigate = (next: PreviewView) => updateLocation({ view: next });
  const followLink = (event: MouseEvent<HTMLAnchorElement>, next: PreviewView) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(next);
  };
  const rememberOpener = () => {
    if (!hasDialog && document.activeElement instanceof HTMLElement) openerRef.current = document.activeElement;
  };
  const openDialog = (next: SimpleDialog) => { rememberOpener(); setDialog(next); };
  const closeDialog = () => { setDialog(null); setAccountPanel(null); };
  const withSample = (action: () => void) => { if (audience === "guest") openDialog("registration"); else action(); };
  const limited = () => withSample(() => openDialog("limited"));
  const openAccount = (account: SampleAccount) => withSample(() => {
    rememberOpener();
    if (!isBelowDesktop && (view === "accounts" || view === "search")) {
      if (document.activeElement instanceof HTMLElement) inspectorOpenerRef.current = document.activeElement;
      if (location.account !== account.id) updateLocation({ account: account.id });
    } else setAccountPanel({ mode: "detail", account });
  });
  const accountTask = (account: SampleAccount, mode: "edit" | "correction") => { rememberOpener(); setAccountPanel({ mode, account }); };
  const accountActivity = (account: SampleAccount) => { setAccountFilter(account); setSearchCategory("activity"); setSearchQuery(""); navigate("search"); };
  const createAccount = () => withSample(() => { rememberOpener(); setAccountPanel({ mode: "create" }); });
  const openRecent = (selection: RecentId) => {
    setRecent(selection);
    setNotice(null);
    if (view === "argus") setDialog(null);
    else navigate("argus");
  };
  const newChat = (searchDraft?: string) => {
    setRecent(null);
    if (searchDraft) setDraft(searchDraft);
    setNotice("newChatNote");
    openerRef.current = composerRef.current;
    setDialog(null);
    if (!hasDialog) composerRef.current?.focus();
  };
  const actions: ViewActions = { navigate, createAccount, openAccount, limited, preferences: () => openDialog("preferences"), openRecent };
  const viewProps = { copy, state, actions };
  const inspector = selectedAccount ? <AccountInspector account={selectedAccount} copy={copy} onClose={() => updateLocation({ account: undefined })} onEdit={() => accountTask(selectedAccount, "edit")} onCorrection={() => accountTask(selectedAccount, "correction")} onActivity={accountActivity} /> : null;
  const descriptions = { home: copy.recordedAsOf, accounts: copy.accountIntro, plan: copy.planIntro, search: copy.searchTitle, updates: copy.updateIntro, settings: copy.settingsIntro, argus: "" };

  return <div className={styles.preview} data-testid="ecosystem-preview" data-preview-view={view} data-preview-audience={audience}>
    <a className={styles.skipLink} href="#preview-main">{copy.skip}</a>
    <div className={styles.previewBar}>
      <p><span className={styles.previewDot} aria-hidden="true" /><strong>{copy.preview}</strong><span>{copy.previewNote}</span></p>
      <details className={styles.controls} data-testid="preview-controls"><summary aria-label={copy.previewControls}><SlidersHorizontal size={15} aria-hidden="true" /><span>{copy.previewControls}</span><ChevronDown size={13} aria-hidden="true" /></summary>
        <div className={styles.controlsPanel}><p>{copy.controlsNote}</p>
          <label>{copy.destination}<select data-testid="preview-view" value={view} onChange={(event) => updateLocation({ view: event.target.value as PreviewView })}>{PREVIEW_VIEWS.map((value) => <option key={value} value={value}>{copy[value]}</option>)}</select></label>
          <label>{copy.audience}<select data-testid="preview-audience" value={audience} onChange={(event) => updateLocation({ audience: event.target.value === "sample" ? "sample" : "guest" })}><option value="guest">{copy.guest}</option><option value="sample">{copy.sampleWorkspace}</option></select></label>
          <label>{copy.state}<select data-testid="preview-state" value={state} onChange={(event) => updateLocation({ state: PREVIEW_STATES.find((value) => value === event.target.value) ?? "sample" })}>{PREVIEW_STATES.map((value) => <option key={value} value={value}>{copy[value]}</option>)}</select></label>
          <small>{copy.stateApplies}</small>
        </div>
      </details>
    </div>
    <div className={styles.shell}>
      <PreviewNavigation copy={copy} view={view} audience={audience} href={(destination) => href({ view: destination })} onNavigate={followLink} />
      <div className={styles.workspace}>
        <header className={`${styles.header} ${view === "argus" && recent ? styles.headerWithTitle : ""}`}>
          {view === "argus" ? <div className={styles.chatHeaderLeft}><button className={styles.headerButton} aria-label={copy.recents} onClick={() => openDialog("recents")}><History size={20} /><span>{copy.recents}</span></button><button className={styles.iconButton} aria-label={copy.newChat} onClick={() => newChat()}><SquarePen size={20} /></button></div> : <button className={styles.contextButton} onClick={() => openDialog("context")}>{copy.personal}<ChevronDown size={14} /></button>}
          {view === "argus" && recent ? <h1 className={styles.chatHeaderTitle}><ChatHeaderTitle conversationId={`sample-${recent}`} title={copy[recent]} titleSource={null} /></h1> : null}
          <div className={styles.headerRight}>
            {view === "argus" ? <button className={styles.temporaryButton} onClick={() => openDialog("temporary")}>{copy.temporary}</button> : null}
            <a className={styles.iconButton} href={href({ view: "updates" })} onClick={(event) => followLink(event, "updates")} aria-label={copy.updates} aria-current={view === "updates" ? "page" : undefined}><Bell size={20} strokeWidth={1.6} /></a>
            <a className={styles.iconButton} href={href({ view: "settings" })} onClick={(event) => followLink(event, "settings")} aria-label={copy.settings} aria-current={view === "settings" ? "page" : undefined}><UserRound size={20} strokeWidth={1.6} /></a>
          </div>
        </header>
        <main id="preview-main" data-testid="preview-main" className={`${styles.main} ${view === "argus" ? styles.chatMain : ""}`} tabIndex={-1} ref={mainRef}>
          {view !== "argus" ? <div className={styles.pageHeading}><div><h1>{copy[view]}</h1><p>{descriptions[view]}</p></div>{view === "home" || view === "accounts" ? <button className={styles.headerAction} aria-label={view === "home" ? copy.record : copy.addAccount} onClick={view === "home" ? limited : createAccount}><Plus size={18} /><span>{view === "home" ? copy.record : copy.addAccount}</span></button> : null}</div> : null}
          {state === "loading" && view !== "settings" ? <section className={styles.stateCard} aria-busy="true"><h2>{copy.loadingTitle}</h2><p>{copy.loadingBody}</p><div className={styles.skeletons} aria-hidden="true"><span /><span /><span /></div></section>
            : state === "error" && view !== "settings" ? <EmptyState title={copy.errorTitle} body={copy.errorBody} action={copy.retry} onAction={() => updateLocation({ state: "sample" })}><CircleHelp size={30} strokeWidth={1.3} /></EmptyState>
              : <>
                {view === "home" ? <HomeView {...viewProps} /> : null}
                {view === "accounts" ? <AccountsView {...viewProps} inspector={inspector} selectedAccountId={location.account} /> : null}
                {view === "plan" ? <PlanView {...viewProps} /> : null}
                {view === "search" ? <SearchView {...viewProps} inspector={inspector} selectedAccountId={location.account} accountFilter={accountFilter} clearAccountFilter={() => setAccountFilter(null)} query={searchQuery} setQuery={setSearchQuery} category={searchCategory} setCategory={setSearchCategory} /> : null}
                {view === "updates" ? <UpdatesView {...viewProps} /> : null}
                {view === "settings" ? <SettingsView {...viewProps} /> : null}
                {view === "argus" ? <PreviewChat copy={copy} draft={draft} onDraft={setDraft} recent={recent} onNotice={() => setNotice("sendNotice")} onLimited={limited} inputRef={composerRef} /> : null}
              </>}
        </main>
      </div>
    </div>
    {notice ? <div className={styles.toast} data-testid="preview-notice"><p role="status">{copy[notice]}</p><button className={styles.iconButton} aria-label={copy.close} onClick={() => setNotice(null)}><X size={17} /></button></div> : null}
    {dialog ? <PreviewDialogs dialog={dialog} copy={copy} state={state} onClose={() => setDialog(null)} onDialog={setDialog} onRecent={openRecent} onNewChat={newChat} /> : null}
    {accountPanel ? <AccountPanels panel={accountPanel} copy={copy} onClose={closeDialog} onActivity={accountActivity} onLimited={limited} /> : null}
  </div>;
}
