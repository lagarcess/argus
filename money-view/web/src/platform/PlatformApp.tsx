import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useState,
  type FormEvent,
} from "react";
import { z } from "zod";
import {
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Landmark,
  Search,
  MessageCirclePlus,
  PanelLeftClose,
  ChevronRight,
  Wallet,
  ArrowUp,
  LogOut,
} from "lucide-react";
import { request, APIError } from "./client";
import { NoticeCenter } from "./NoticeCenter";
import { useResource } from "./hooks";
import { destinations, useNavigation } from "./navigation";
import {
  EvidenceLine,
  EmptyState,
  Field,
  Modal,
  Money,
  PageHeader,
  Panel,
} from "./ui";
import {
  evidenceSchema,
  type Locale,
  type Page,
  type PlatformPageProps,
} from "./types";
const AccountsPage = lazy(() =>
  import("../features/ledger").then((module) => ({
    default: module.AccountsPage,
  })),
);
const TransactionsPage = lazy(() =>
  import("../features/ledger").then((module) => ({
    default: module.TransactionsPage,
  })),
);
const SpendingPage = lazy(() =>
  import("../features/ledger").then((module) => ({
    default: module.SpendingPage,
  })),
);
import { accountSchema, cashflowSchema } from "../features/ledger/contracts";
const InvestmentsPage = lazy(() =>
  import("../features/investing").then((module) => ({
    default: module.InvestmentsPage,
  })),
);
const CreditPage = lazy(() =>
  import("../features/services").then((module) => ({
    default: module.CreditPage,
  })),
);
const TaxEstatePage = lazy(() =>
  import("../features/services").then((module) => ({
    default: module.TaxEstatePage,
  })),
);
const MembershipPage = lazy(() =>
  import("../features/services").then((module) => ({
    default: module.MembershipPage,
  })),
);
const HelpPage = lazy(() =>
  import("../features/services").then((module) => ({
    default: module.HelpPage,
  })),
);
const EmployerPage = lazy(() =>
  import("../features/services").then((module) => ({
    default: module.EmployerPage,
  })),
);
const SettingsPage = lazy(() =>
  import("../features/settings").then((module) => ({
    default: module.SettingsPage,
  })),
);
const HouseholdPage = lazy(() =>
  import("../features/settings").then((module) => ({
    default: module.HouseholdPage,
  })),
);
import {
  guestSchema,
  profileSchema,
  preferencesSchema,
  householdSchema,
} from "../features/settings/contracts";
const DepositsPage = lazy(() =>
  import("../features/deposits/DepositsPage").then((module) => ({
    default: module.DepositsPage,
  })),
);
const ConversationPage = lazy(() =>
  import("../features/chat/ConversationPage").then((module) => ({
    default: module.ConversationPage,
  })),
);
const RecentConversations = lazy(() =>
  import("../features/chat/RecentConversations").then((module) => ({
    default: module.RecentConversations,
  })),
);
const Omnisearch = lazy(() =>
  import("../features/search/Omnisearch").then((module) => ({
    default: module.Omnisearch,
  })),
);
const SavedAssistantPage = lazy(() =>
  import("../features/assistant/SavedAssistantPage").then((module) => ({
    default: module.SavedAssistantPage,
  })),
);
const BudgetsPage = lazy(() =>
  import("../features/planning").then((module) => ({
    default: module.BudgetsPage,
  })),
);
const GoalsPage = lazy(() =>
  import("../features/planning").then((module) => ({
    default: module.GoalsPage,
  })),
);
const ScenariosPage = lazy(() =>
  import("../features/planning").then((module) => ({
    default: module.ScenariosPage,
  })),
);
import { insightsSchema } from "../features/assistant/contracts";
import {
  copy as assistantCopy,
  label as assistantLabel,
} from "../features/assistant/catalog";
import { ArgusComposer } from "../argus/ArgusComposer";
import { stageChatDraft } from "../features/chat/drafts";
import { useResponsiveLayout } from "../argus/useResponsiveLayout";
import "./shell.css";

const sessionSchema = z.object({
  data_generation: z.number().int().nonnegative(),
  user: profileSchema,
  household: householdSchema,
  preferences: preferencesSchema,
  local_only: z.boolean(),
  supported_currencies: z.array(z.string()).min(1),
  guest: guestSchema,
  currency_context: z.object({
    currency: z.string().nullable(),
    source: z.enum([
      "explicit_override",
      "selected_account",
      "default_account",
      "household_default",
      "unknown",
    ]),
    account_id: z.string().nullable(),
  }),
});
function sessionWorkspaceKey(session: z.infer<typeof sessionSchema>) {
  return `${session.user.id}:${session.household.id}:${session.data_generation}`;
}
const personasSchema = z.object({
  items: z.array(
    z.object({
      user_id: z.string(),
      display_name: z.string(),
      households: z.array(
        z.object({ id: z.string(), name: z.string(), role: z.string() }),
      ),
    }),
  ),
  default_password: z.string(),
  local_only: z.boolean(),
});
const overviewSchema = z.object({
  as_of: z.string(),
  account_count: z.number(),
  accounts: z.array(accountSchema),
  net_worth: z.array(
    z.object({
      currency: z.string(),
      assets: z.string(),
      liabilities: z.string(),
      net_worth: z.string(),
      source: evidenceSchema,
    }),
  ),
  cashflow: z.array(cashflowSchema),
  source: evidenceSchema,
});

export default function PlatformApp() {
  const { page, query, navigate } = useNavigation();
  const [revision, setRevision] = useState(0);
  const [expired, setExpired] = useState(false);
  const [authEpoch, setAuthEpoch] = useState(0);
  const [guestLocale, setGuestLocale] = useState<Locale>("es-419");
  const selectedAccount = query.get("account_id");
  const session = useResource(async () => {
    try {
      return await request(
        `/session${selectedAccount ? `?account_id=${encodeURIComponent(selectedAccount)}` : ""}`,
        sessionSchema,
      );
    } catch (error) {
      // An unavailable record must not masquerade as an expired identity.
      if (
        selectedAccount &&
        error instanceof APIError &&
        error.code === "account_not_found"
      )
        return request("/session", sessionSchema);
      throw error;
    }
  }, [authEpoch, selectedAccount]);
  const [viewCurrencies, setViewCurrencies] = useState<Record<string, string>>(
    {},
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [householdOpen, setHouseholdOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [claimOpen, setClaimOpen] = useState(false);
  const [sessionError, setSessionError] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const layout = useResponsiveLayout();
  const data = expired || session.error ? null : session.data;
  const workspaceKey = data ? sessionWorkspaceKey(data) : "";
  const canonicalCurrency = data?.currency_context.currency;
  const currencyOwner = data ? `${workspaceKey}:${canonicalCurrency}` : "";
  const explicitCurrency = viewCurrencies[currencyOwner];
  const currency = data?.supported_currencies.includes(explicitCurrency)
    ? explicitCurrency
    : (canonicalCurrency ?? "");
  const locale = data?.preferences.locale ?? guestLocale;
  const en = locale === "en";
  const change = useCallback(() => {
    setRevision((value) => value + 1);
    session.reload();
  }, [session.reload]);
  const go = useCallback(
    (
      destination: Page,
      params?: Record<string, string>,
      options?: { replace?: boolean },
    ) => {
      navigate(destination, params, options);
      setMobileOpen(false);
      setHouseholdOpen(false);
      setSearchOpen(false);
    },
    [navigate],
  );
  const ask = (text: string) => {
    go("chat", { draft: stageChatDraft(workspaceKey, text) });
    return true;
  };
  const newChat = () => go("chat", { new: crypto.randomUUID() });
  useEffect(() => {
    const expire = () => {
      setExpired(true);
      setHouseholdOpen(false);
      setSearchOpen(false);
      setMobileOpen(false);
      setClaimOpen(false);
    };
    window.addEventListener("clara:session-expired", expire);
    return () => window.removeEventListener("clara:session-expired", expire);
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = en
      ? "Argus | Your money, in perspective"
      : "Argus | Tu dinero, en perspectiva";
  }, [locale, en]);
  useEffect(() => {
    if (!layout.isBelowTablet && !searchOpen && !householdOpen && !claimOpen)
      setMobileOpen(false);
  }, [layout.isBelowTablet, searchOpen, householdOpen, claimOpen]);
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "k" &&
        data
      ) {
        event.preventDefault();
        setSearchOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [data]);
  const props: PlatformPageProps = {
    workspaceKey,
    locale,
    currency,
    query,
    revision,
    onNavigate: go,
    onChanged: change,
  };
  async function logout() {
    try {
      await request("/session/logout", z.object({ logged_out: z.boolean() }), {
        method: "POST",
      });
      setExpired(true);
      setHouseholdOpen(false);
      setSearchOpen(false);
      setClaimOpen(false);
    } catch {
      setSessionError(true);
    }
  }
  const loggedIn = () => {
    setExpired(false);
    setAuthEpoch((value) => value + 1);
    setSessionError(false);
    setRevision((value) => value + 1);
  };
  if (!session.data && session.loading && !expired)
    return (
      <div className="platform-shell p-entry" data-theme="light">
        <span className="p-wordmark">Argus</span>
        <p role="status">
          {en ? "Opening your workspace…" : "Abriendo tu espacio…"}
        </p>
      </div>
    );
  if (!data)
    return (
      <div className="platform-shell" data-theme="light">
        <GuestLanding
          locale={guestLocale}
          onLocale={setGuestLocale}
          onLogin={loggedIn}
          onNavigate={go}
        />
      </div>
    );
  const owner = workspaceKey;
  const compact =
    !layout.isBelowTablet && (collapsed || data.preferences.sidebar_compact);
  const current = destinations.find((item) => item.id === page);
  const navItem = (item: (typeof destinations)[number]) => {
    const Icon = item.icon;
    return (
      <a
        key={item.id}
        href={`#${item.id}`}
        className="p-nav-item"
        aria-current={page === item.id ? "page" : undefined}
        title={compact ? (en ? item.en : item.es) : undefined}
        onClick={(event) => {
          event.preventDefault();
          go(item.id);
        }}
      >
        <Icon size={18} />
        <span>{en ? item.en : item.es}</span>
      </a>
    );
  };
  const sidebar = (
    <>
      <div className="argus-sidebar-heading">
        <a
          className="p-wordmark"
          href="#chat"
          onClick={(event) => {
            event.preventDefault();
            newChat();
          }}
        >
          Argus
        </a>
        <button
          className="p-icon-button"
          aria-label={
            compact
              ? en
                ? "Expand navigation"
                : "Expandir navegación"
              : en
                ? "Collapse navigation"
                : "Contraer navegación"
          }
          onClick={() =>
            layout.isBelowTablet
              ? setMobileOpen(false)
              : setCollapsed((value) => !value)
          }
        >
          <PanelLeftClose size={18} />
        </button>
      </div>
      <nav
        className="argus-primary-nav"
        aria-label={en ? "Workspace" : "Espacio"}
      >
        <button
          className="p-nav-item"
          onClick={newChat}
          title={en ? "New chat" : "Nueva conversación"}
        >
          <MessageCirclePlus size={19} />
          <span>{en ? "New chat" : "Nueva conversación"}</span>
        </button>
        <button
          className="p-nav-item"
          onClick={() => {
            setSearchOpen(true);
          }}
          title={en ? "Search" : "Buscar"}
        >
          <Search size={19} />
          <span>{en ? "Search" : "Buscar"}</span>
          <kbd>⌘ K</kbd>
        </button>
        {navItem(destinations.find((item) => item.id === "overview")!)}
      </nav>
      <div className="argus-sidebar-scroll">
        <details
          className="argus-nav-section"
          open={
            page !== "overview" &&
            (current?.group === "money" || current?.group === "plan")
          }
        >
          <summary
            aria-label={en ? "Finance destinations" : "Vistas de finanzas"}
          >
            <ChevronRight size={14} />
            <span>{en ? "Your finances" : "Tus finanzas"}</span>
          </summary>
          <nav>
            {destinations
              .filter(
                (item) =>
                  ["money", "plan"].includes(item.group) &&
                  item.id !== "overview",
              )
              .map(navItem)}
          </nav>
        </details>
        <details className="argus-nav-section">
          <summary
            aria-label={en ? "Household destinations" : "Vistas del hogar"}
          >
            <ChevronRight size={14} />
            <span>{en ? "Household & more" : "Hogar y más"}</span>
          </summary>
          <nav>
            {destinations
              .filter(
                (item) => item.group === "household" || item.id === "help",
              )
              .map(navItem)}
          </nav>
        </details>
        {!compact && (
          <section className="argus-recents">
            <h2>{en ? "Recent conversations" : "Conversaciones recientes"}</h2>
            <Suspense
              fallback={
                <p className="p-muted">{en ? "Loading…" : "Cargando…"}</p>
              }
            >
              <RecentConversations
                key={owner}
                locale={locale}
                revision={revision}
                onNavigate={go}
              />
            </Suspense>
          </section>
        )}
      </div>
      <div className="argus-sidebar-profile">
        <button
          className="p-nav-item"
          onClick={() => setHouseholdOpen(true)}
          title={en ? "Profile and settings" : "Perfil y ajustes"}
        >
          <span className="p-avatar">
            {data.guest.is_guest ? "A" : data.user.display_name.slice(0, 1)}
          </span>
          <span>
            {data.guest.is_guest
              ? en
                ? "Guest workspace"
                : "Espacio de invitado"
              : (data.user.preferred_name ?? data.user.display_name)}
            <small>{en ? "Profile & settings" : "Perfil y ajustes"}</small>
          </span>
        </button>
      </div>
    </>
  );
  return (
    <div
      className="platform-shell argus-workspace"
      data-theme={data.preferences.appearance}
      data-compact={compact}
      data-page={page}
    >
      <a
        className="p-skip"
        href="#platform-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("platform-content")?.focus();
        }}
      >
        {en ? "Skip to content" : "Ir al contenido"}
      </a>
      {!layout.isBelowTablet && (
        <aside
          className="p-sidebar"
          aria-label={en ? "Main navigation" : "Navegación principal"}
        >
          {sidebar}
        </aside>
      )}
      <div className="p-workspace">
        <header className="p-topbar">
          {layout.isBelowTablet && (
            <button
              className="p-icon-button p-mobile-menu"
              aria-label={en ? "Open navigation" : "Abrir navegación"}
              onClick={() => setMobileOpen(true)}
            >
              <PanelLeftClose size={20} />
            </button>
          )}
          <div className="argus-location">
            <span>
              {page === "chat" ? "Argus" : en ? current?.en : current?.es}
            </span>
            <small>
              {data.guest.is_guest
                ? en
                  ? "Local guest"
                  : "Invitado local"
                : en
                  ? "Local workspace"
                  : "Espacio local"}
              {data.guest.mode === "demo"
                ? ` · ${en ? "Demo data" : "Datos demo"}`
                : ""}
            </small>
          </div>
          <span className="p-topbar-spacer" />
          <label
            className="p-currency"
            title={
              en
                ? "This view does not convert balances"
                : "Esta vista no convierte saldos"
            }
          >
            <small>
              {explicitCurrency ||
              data.currency_context.source === "explicit_override"
                ? en
                  ? "View"
                  : "Vista"
                : data.currency_context.account_id
                  ? en
                    ? "Account"
                    : "Cuenta"
                  : en
                    ? "Currency"
                    : "Moneda"}
            </small>
            <span className="sr-only">
              {en
                ? "Display currency, no conversion"
                : "Moneda, sin conversión"}
            </span>
            <select
              value={currency}
              onChange={(event) =>
                setViewCurrencies((previous) => ({
                  ...previous,
                  [currencyOwner]: event.target.value,
                }))
              }
            >
              {!currency && (
                <option value="">{en ? "Currency" : "Moneda"}</option>
              )}
              {data.supported_currencies.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <button
            className="p-icon-button argus-search-trigger"
            aria-label={en ? "Search workspace" : "Buscar en el espacio"}
            onClick={() => setSearchOpen(true)}
          >
            <Search size={19} />
          </button>
          {currency && (
            <NoticeCenter
              key={owner}
              locale={locale}
              currency={currency}
              revision={revision}
              routeKey={`${page}?${query.toString()}`}
              onNavigate={go}
            />
          )}
          {data.guest.can_claim && (
            <button
              className="p-button-secondary argus-save-workspace"
              aria-label={en ? "Keep workspace" : "Conservar espacio"}
              onClick={() => setClaimOpen(true)}
            >
              {layout.isBelowTablet
                ? en
                  ? "Keep"
                  : "Conservar"
                : en
                  ? "Keep workspace"
                  : "Conservar espacio"}
            </button>
          )}
        </header>
        <main id="platform-content" className="p-main" tabIndex={-1}>
          <Suspense
            fallback={
              <p className="p-loading" role="status">
                {en ? "Loading your view…" : "Cargando tu vista…"}
              </p>
            }
          >
            {!currency && page === "overview" ? (
              <EmptyMoney {...props} />
            ) : (
              <ActivePage key={`${owner}:${page}`} page={page} {...props} />
            )}
          </Suspense>
          {page === "overview" && !currency && (
            <section className="argus-money-composer">
              <ArgusComposer
                locale={locale}
                onSend={ask}
                onAttach={() => go("transactions", { import: "1" })}
              />
              <p>
                {en
                  ? "Ask about these records, or explore a plan."
                  : "Pregunta sobre estos registros o explora un plan."}
              </p>
            </section>
          )}
          {page !== "chat" && (
            <footer className="p-page-footer">
              {data.guest.mode === "demo"
                ? en
                  ? "Local demo · Simulated records"
                  : "Demo local · Registros simulados"
                : en
                  ? "Local workspace · No bank connection"
                  : "Espacio local · Sin conexión bancaria"}
            </footer>
          )}
        </main>
      </div>
      {mobileOpen && (
        <Modal
          title="Argus"
          variant="drawer"
          onClose={() => setMobileOpen(false)}
        >
          <div className="argus-mobile-sidebar">{sidebar}</div>
        </Modal>
      )}
      {searchOpen && (
        <Suspense
          fallback={
            <p className="argus-overlay-loading" role="status">
              {en ? "Loading search…" : "Cargando búsqueda…"}
            </p>
          }
        >
          <Omnisearch
            key={owner}
            locale={locale}
            onClose={() => setSearchOpen(false)}
            onNavigate={go}
            onAsk={ask}
            revision={revision}
          />
        </Suspense>
      )}
      {claimOpen && (
        <ClaimWorkspace
          locale={locale}
          onClose={() => setClaimOpen(false)}
          onClaimed={() => {
            setClaimOpen(false);
            change();
          }}
        />
      )}
      {householdOpen && (
        <Modal
          title={en ? "Your workspace" : "Tu espacio"}
          onClose={() => setHouseholdOpen(false)}
        >
          <div className="p-profile-summary">
            <span className="p-avatar">
              {data.user.display_name.slice(0, 1)}
            </span>
            <div>
              <strong>
                {data.guest.is_guest
                  ? en
                    ? "Guest workspace"
                    : "Espacio de invitado"
                  : (data.user.preferred_name ?? data.user.display_name)}
              </strong>
              <p className="p-muted">{data.household.name}</p>
            </div>
          </div>
          {data.guest.expires_at && (
            <p className="p-muted">
              {en ? "Available until" : "Disponible hasta"}{" "}
              {new Date(data.guest.expires_at).toLocaleString(locale)}
            </p>
          )}
          <HouseholdMenu
            locale={locale}
            currentId={data.household.id}
            busy={switching}
            onSelect={async (id) => {
              setSwitching(true);
              setSessionError(false);
              try {
                await request("/households/switch", sessionSchema, {
                  method: "POST",
                  body: JSON.stringify({ household_id: id }),
                });
                setHouseholdOpen(false);
                setSearchOpen(false);
                setAuthEpoch((value) => value + 1);
                setRevision((value) => value + 1);
                go("overview");
              } catch {
                setSessionError(true);
              } finally {
                setSwitching(false);
              }
            }}
          />
          <div className="p-stack p-menu-links">
            {destinations
              .filter((item) =>
                [
                  "household",
                  "membership",
                  "employer",
                  "settings",
                  "help",
                ].includes(item.id),
              )
              .map((item) => (
                <button
                  key={item.id}
                  className="p-button-ghost"
                  onClick={() => go(item.id)}
                >
                  {en ? item.en : item.es}
                  <ArrowRight size={16} />
                </button>
              ))}
            {data.guest.can_claim && (
              <button
                className="p-button-secondary"
                onClick={() => {
                  setClaimOpen(true);
                }}
              >
                {en ? "Keep this workspace" : "Conservar este espacio"}
              </button>
            )}
            <button className="p-button-ghost" onClick={() => void logout()}>
              <LogOut size={16} />
              {en ? "Sign out" : "Cerrar sesión"}
            </button>
            {sessionError && (
              <p className="p-error" role="alert">
                {en
                  ? "The session change failed. Try again."
                  : "No se pudo cambiar la sesión. Inténtalo de nuevo."}
              </p>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

function GuestLanding({
  locale,
  onLocale,
  onLogin,
  onNavigate,
}: {
  locale: Locale;
  onLocale: (locale: Locale) => void;
  onLogin: () => void;
  onNavigate: PlatformPageProps["onNavigate"];
}) {
  const en = locale === "en";
  const [loginOpen, setLoginOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const enter = async (mode: "demo" | "empty", text?: string) => {
    setBusy(true);
    setError("");
    try {
      const guest = await request("/session/guest", sessionSchema, {
        method: "POST",
        body: JSON.stringify({ mode, locale }),
      });
      onLogin();
      onNavigate(
        text ? "chat" : "overview",
        text
          ? { draft: stageChatDraft(sessionWorkspaceKey(guest), text) }
          : undefined,
      );
      return true;
    } catch {
      setError(
        en
          ? "Your workspace could not be opened. Try again."
          : "No se pudo abrir tu espacio. Inténtalo de nuevo.",
      );
      return false;
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="argus-guest">
      <header>
        <a className="p-wordmark" href="#chat">
          Argus
        </a>
        <div className="p-actions">
          <button
            className="p-button-ghost"
            onClick={() => onLocale(en ? "es-419" : "en")}
          >
            {en ? "Español" : "English"}
          </button>
          <button
            className="p-button-secondary"
            onClick={() => setLoginOpen(true)}
          >
            {en ? "Sign in" : "Iniciar sesión"}
          </button>
        </div>
      </header>
      <main className="argus-guest-main">
        <section className="argus-guest-question">
          <span className="argus-overline">
            {en ? "A little more perspective" : "Un poco más de perspectiva"}
          </span>
          <h1>
            {en
              ? "Your money. Your next question."
              : "Tu dinero. Tu próxima pregunta."}
          </h1>
          <p>
            {en
              ? "Make sense of your accounts, explore a plan, or start with what is on your mind."
              : "Entiende tus cuentas, explora un plan o empieza con lo que tienes en mente."}
          </p>
          <ArgusComposer
            locale={locale}
            disabled={busy}
            onSend={(text) => enter("empty", text)}
          />
          <div className="argus-starters">
            <button
              disabled={busy}
              onClick={() =>
                void enter(
                  "demo",
                  en
                    ? "What does my money look like today?"
                    : "¿Cómo está mi dinero hoy?",
                )
              }
            >
              {en ? "Understand my money" : "Entender mi dinero"}
            </button>
            <button
              disabled={busy}
              onClick={() =>
                void enter(
                  "demo",
                  en
                    ? "How much room is there in my budget?"
                    : "¿Cuánto espacio hay en mi presupuesto?",
                )
              }
            >
              {en ? "Review my budget" : "Revisar mi presupuesto"}
            </button>
            <button disabled={busy} onClick={() => void enter("empty")}>
              {en ? "Start with my own records" : "Empezar con mis registros"}
            </button>
          </div>
          {error && (
            <p role="alert" className="p-error">
              {error}
            </p>
          )}
          <p className="argus-guest-note">
            {en
              ? "A private local workspace. No bank connection or real transactions."
              : "Un espacio local privado. Sin conexión bancaria ni transacciones reales."}
          </p>
        </section>
        <section className="argus-demo-preview">
          <div className="argus-demo-copy">
            <span className="argus-overline">
              {en
                ? "A place for the whole picture"
                : "Un lugar para ver el panorama"}
            </span>
            <h2>{en ? "Meet your money view" : "Conoce tu vista de dinero"}</h2>
            <p>
              {en
                ? "Accounts, spending and plans stay connected to your questions. Explore the prepared household to see how it works."
                : "Tus cuentas, gastos y planes acompañan tus preguntas. Explora el hogar preparado para ver cómo funciona."}
            </p>
            <button
              className="p-button-ghost"
              disabled={busy}
              onClick={() => void enter("demo")}
            >
              {en ? "Explore the demo" : "Explorar la demo"}
              <ArrowRight size={17} />
            </button>
          </div>
          <div
            className="argus-demo-ledger"
            aria-label={en ? "Money view preview" : "Vista previa de dinero"}
          >
            <div>
              <Wallet size={20} />
              <strong>
                {en ? "Your money, together" : "Tu dinero, en un lugar"}
              </strong>
              <small>{en ? "Demo preview" : "Vista previa demo"}</small>
            </div>
            {[
              {
                icon: Landmark,
                en: "Accounts & balances",
                es: "Cuentas y saldos",
                detail: en ? "One clear view" : "Una vista clara",
              },
              {
                icon: ArrowUp,
                en: "Spending & cash flow",
                es: "Gastos y flujo de caja",
                detail: en ? "Follow the details" : "Sigue los detalles",
              },
              {
                icon: ChevronRight,
                en: "Plans & goals",
                es: "Planes y metas",
                detail: en ? "Explore what comes next" : "Explora lo que sigue",
              },
            ].map((item) => (
              <div key={item.en}>
                <item.icon size={18} />
                <span>{en ? item.en : item.es}</span>
                <small>{item.detail}</small>
              </div>
            ))}
          </div>
        </section>
      </main>
      {loginOpen && (
        <Modal
          title={en ? "Sign in to Argus" : "Entrar a Argus"}
          onClose={() => setLoginOpen(false)}
        >
          <Login locale={locale} onLogin={onLogin} />
        </Modal>
      )}
    </div>
  );
}
function ClaimWorkspace({
  locale,
  onClose,
  onClaimed,
}: {
  locale: Locale;
  onClose: () => void;
  onClaimed: () => void;
}) {
  const en = locale === "en";
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [loginId, setLoginId] = useState("");
  return (
    <Modal
      title={en ? "Keep your workspace" : "Conservar tu espacio"}
      onClose={loginId ? onClaimed : onClose}
      dismissible={!busy}
    >
      {loginId ? (
        <div className="p-stack">
          <p>
            {en
              ? "Your records are saved. Use this local account ID and your password to return."
              : "Tus registros están guardados. Usa este identificador local y tu contraseña para volver."}
          </p>
          <Field label={en ? "Local account ID" : "Identificador local"}>
            <input readOnly value={loginId} />
          </Field>
          <button
            className="p-button-secondary"
            onClick={() =>
              navigator.clipboard.writeText(loginId).catch(() => setError(true))
            }
          >
            {en ? "Copy login ID" : "Copiar identificador"}
          </button>
          {error && (
            <p className="p-error" role="alert">
              {en
                ? "Select the ID above and copy it."
                : "Selecciona el identificador de arriba y cópialo."}
            </p>
          )}
          <button className="p-button" onClick={onClaimed}>
            {en ? "Continue" : "Continuar"}
          </button>
        </div>
      ) : (
        <form
          className="p-stack"
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setError(false);
            try {
              const data = await request("/session/claim", sessionSchema, {
                method: "POST",
                body: JSON.stringify({ display_name: name.trim(), password }),
              });
              setLoginId(data.user.id);
            } catch {
              setError(true);
            } finally {
              setBusy(false);
            }
          }}
        >
          <p className="p-muted">
            {en
              ? "Save your conversations and records in this local app."
              : "Conserva tus conversaciones y registros en esta aplicación local."}
          </p>
          <Field label={en ? "Your name" : "Tu nombre"}>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              maxLength={80}
              disabled={busy}
            />
          </Field>
          <Field
            label={en ? "Password" : "Contraseña"}
            help={
              en
                ? "At least 10 characters. This password is only for this local app."
                : "Al menos 10 caracteres. Esta contraseña es solo para esta aplicación local."
            }
          >
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={10}
              maxLength={128}
              autoComplete="new-password"
              disabled={busy}
            />
          </Field>
          {error && (
            <p role="alert" className="p-error">
              {en
                ? "Your workspace could not be saved. Try again."
                : "No se pudo guardar tu espacio. Inténtalo de nuevo."}
            </p>
          )}
          <button className="p-button" disabled={busy || !name.trim()}>
            {busy
              ? en
                ? "Saving…"
                : "Guardando…"
              : en
                ? "Keep workspace"
                : "Conservar espacio"}
          </button>
        </form>
      )}
    </Modal>
  );
}
function EmptyMoney(props: PlatformPageProps) {
  const en = props.locale === "en";
  return (
    <div className="argus-empty-money">
      <span className="argus-overline">{en ? "Your money" : "Tu dinero"}</span>
      <h1>{en ? "A clear place to begin" : "Un lugar claro para empezar"}</h1>
      <p>
        {en
          ? "Add an account to see your balances and give your next question some context."
          : "Agrega una cuenta para ver tus saldos y darle contexto a tu próxima pregunta."}
      </p>
      <button
        className="p-button-secondary"
        onClick={() => props.onNavigate("accounts")}
      >
        {en ? "Add an account" : "Agregar una cuenta"}
        <ArrowRight size={16} />
      </button>
    </div>
  );
}

function Login({ locale, onLogin }: { locale: Locale; onLogin: () => void }) {
  const en = locale === "en";
  const personas = useResource(
    () => request("/demo/personas", personasSchema),
    [],
  );
  const [mode, setMode] = useState<"demo" | "local">("demo");
  const [demoUser, setDemoUser] = useState<string | null>(null);
  const [demoPassword, setDemoPassword] = useState<string | null>(null);
  const [localUser, setLocalUser] = useState("");
  const [localPassword, setLocalPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const user =
    mode === "local"
      ? localUser.trim()
      : (demoUser ?? personas.data?.items[0]?.user_id ?? "");
  const password =
    mode === "local"
      ? localPassword
      : (demoPassword ?? personas.data?.default_password ?? "");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await request("/session/login", sessionSchema, {
        method: "POST",
        body: JSON.stringify({ user_id: user, password }),
      });
      onLogin();
    } catch (error) {
      setError(error instanceof APIError ? error.code : "network_error");
    } finally {
      setPending(false);
    }
  }
  return (
    <Panel className="p-login-form">
      <h2>{en ? "Enter the demo" : "Entrar a la demo"}</h2>
      <p className="p-muted">
        {en
          ? "Choose a prepared profile or use the ID of a local account created in your household."
          : "Elige un perfil preparado o usa el identificador de una cuenta local creada en tu hogar."}
      </p>
      <div
        className="p-login-methods"
        role="group"
        aria-label={en ? "Sign-in method" : "Forma de acceso"}
      >
        <button
          type="button"
          className="p-button-secondary"
          aria-pressed={mode === "demo"}
          disabled={pending}
          onClick={() => setMode("demo")}
        >
          {en ? "Demo profiles" : "Perfiles demo"}
        </button>
        <button
          type="button"
          className="p-button-secondary"
          aria-pressed={mode === "local"}
          disabled={pending}
          onClick={() => setMode("local")}
        >
          {en ? "Use a local account ID" : "Usar un identificador local"}
        </button>
      </div>
      <form onSubmit={submit} className="p-stack">
        {mode === "local" ? (
          <Field
            label={en ? "Local account ID" : "Identificador de cuenta local"}
            help={
              en
                ? "Use the exact ID shown when the household member was created. It is not an email address."
                : "Usa el identificador que se mostró al crear la persona en el hogar. No es un correo electrónico."
            }
          >
            <input
              value={localUser}
              onChange={(event) => setLocalUser(event.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={100}
              disabled={pending}
              required
            />
          </Field>
        ) : personas.error ? (
          <EmptyState
            title={
              en
                ? "Demo profiles are unavailable"
                : "Los perfiles demo no están disponibles"
            }
            action={
              <button
                type="button"
                className="p-button-secondary"
                onClick={personas.reload}
              >
                {en ? "Try again" : "Reintentar"}
              </button>
            }
          />
        ) : personas.loading ? (
          <p role="status">{en ? "Loading profiles…" : "Cargando perfiles…"}</p>
        ) : (
          <Field label={en ? "Local profile" : "Perfil local"}>
            <select
              value={user}
              onChange={(event) => setDemoUser(event.target.value)}
              disabled={pending}
              required
            >
              {personas.data?.items.map((item) => (
                <option key={item.user_id} value={item.user_id}>
                  {item.display_name} ·{" "}
                  {roleLabel(item.households[0]?.role ?? "", locale)}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field
          label={
            mode === "local"
              ? en
                ? "Local password"
                : "Contraseña local"
              : en
                ? "Demo password"
                : "Contraseña de demo"
          }
          help={
            mode === "local"
              ? en
                ? "Enter the local password chosen when this member was created. No invitation or password email is sent."
                : "Escribe la contraseña local elegida al crear esta persona. No se envían invitaciones ni contraseñas por correo."
              : en
                ? "This password belongs only to the local fixture."
                : "Esta contraseña pertenece solo al perfil local."
          }
        >
          <input
            type="password"
            value={password}
            onChange={(event) =>
              mode === "local"
                ? setLocalPassword(event.target.value)
                : setDemoPassword(event.target.value)
            }
            autoComplete="current-password"
            disabled={pending}
            required
          />
        </Field>
        {error && (
          <p className="p-error" role="alert">
            {error === "invalid_credentials"
              ? en
                ? "The account ID or password is incorrect."
                : "El identificador o la contraseña no coincide."
              : en
                ? "Could not sign in. Try again."
                : "No se pudo entrar. Inténtalo de nuevo."}
          </p>
        )}
        <button
          className="p-button"
          disabled={
            pending ||
            !user ||
            (mode === "demo" && (personas.loading || Boolean(personas.error)))
          }
          type="submit"
        >
          {pending
            ? en
              ? "Opening…"
              : "Abriendo…"
            : en
              ? "Open workspace"
              : "Abrir espacio"}
          <ArrowRight size={18} />
        </button>
      </form>
    </Panel>
  );
}

function roleLabel(role: string, locale: Locale) {
  return locale === "en"
    ? ({ owner: "Owner", editor: "Editor", viewer: "Viewer" }[role] ?? role)
    : ({ owner: "Propietario", editor: "Editor", viewer: "Solo lectura" }[
        role
      ] ?? role);
}
function HouseholdMenu({
  locale,
  currentId,
  onSelect,
  busy,
}: {
  locale: Locale;
  currentId: string;
  onSelect: (id: string) => void;
  busy: boolean;
}) {
  const resource = useResource(
    () => request("/households", z.object({ items: z.array(householdSchema) })),
    [],
  );
  return (
    <div className="p-stack">
      {resource.loading && (
        <p role="status">{locale === "en" ? "Loading…" : "Cargando…"}</p>
      )}
      {resource.error && (
        <button className="p-button-secondary" onClick={resource.reload}>
          {locale === "en" ? "Retry" : "Reintentar"}
        </button>
      )}
      {resource.data?.items.map((item) => (
        <button
          key={item.id}
          disabled={busy}
          className="p-button-secondary p-household-choice"
          aria-pressed={item.id === currentId}
          onClick={() => onSelect(item.id)}
        >
          <span>
            {item.name}
            <small>
              {roleLabel(item.role, locale)} · {item.effective_currency}
            </small>
          </span>
          {item.id === currentId && <span>✓</span>}
        </button>
      ))}
    </div>
  );
}

function OverviewPage(props: PlatformPageProps) {
  const { locale, currency, revision, onNavigate } = props;
  const en = locale === "en";
  const resource = useResource(
    () =>
      request(
        `/overview?currency=${encodeURIComponent(currency)}`,
        overviewSchema,
      ),
    [currency, revision],
  );
  const review = useResource(
    () =>
      request(
        `/insights?currency=${encodeURIComponent(currency)}`,
        insightsSchema,
      ),
    [currency, revision],
  );
  const notices =
    review.data?.notices
      .filter((item) => item.state !== "dismissed")
      .slice(0, 3) ?? [];
  const data = resource.data;
  const net = data?.net_worth.find((item) => item.currency === currency);
  const cash = data?.cashflow.find((item) => item.currency === currency);
  return (
    <>
      <PageHeader
        eyebrow={en ? "YOUR HOUSEHOLD" : "TU HOGAR"}
        title={en ? "My money" : "Mi dinero"}
        description={
          en
            ? "The whole picture, down to the details."
            : "El panorama completo, hasta el último detalle."
        }
        actions={
          <button
            className="p-button-secondary"
            onClick={() => onNavigate("accounts")}
          >
            {en ? "Manage accounts" : "Gestionar cuentas"}
            <ArrowRight size={16} />
          </button>
        }
      />
      {resource.error && (
        <div className="p-inline-error" role="alert">
          <p>
            {en
              ? "Your balances could not be refreshed."
              : "No se pudieron actualizar tus saldos."}
          </p>
          <button className="p-button-secondary" onClick={resource.reload}>
            {en ? "Retry" : "Reintentar"}
          </button>
        </div>
      )}
      {!data && resource.loading ? (
        <div
          className="p-overview-skeleton"
          role="status"
          aria-label={en ? "Loading account balances" : "Cargando saldos"}
        >
          <div />
          <div />
          <div />
          <div />
        </div>
      ) : (
        data && (
          <>
            <section className="p-networth-band">
              <div className="p-networth-main">
                <span className="p-metric-label">
                  {en ? "Net worth" : "Patrimonio neto"}
                  <span className="p-badge">{currency}</span>
                </span>
                {net ? (
                  <Money
                    amount={net.net_worth}
                    currency={currency}
                    locale={locale}
                  />
                ) : (
                  <p className="p-muted">
                    {en
                      ? "No accounts in this currency"
                      : "No hay cuentas en esta moneda"}
                  </p>
                )}
                <p className="p-muted p-currency-note">
                  {en
                    ? "Balances in this currency only. No exchange conversion."
                    : "Solo saldos en esta moneda. Sin conversión de divisas."}
                </p>
              </div>
              {net && (
                <div className="p-networth-details">
                  <div>
                    <span className="p-metric-label">
                      {en ? "Assets" : "Activos"}
                    </span>
                    <Money
                      amount={net.assets}
                      currency={currency}
                      locale={locale}
                    />
                  </div>
                  <div>
                    <span className="p-metric-label">
                      {en ? "Liabilities" : "Deudas"}
                    </span>
                    <Money
                      amount={net.liabilities}
                      currency={currency}
                      locale={locale}
                    />
                  </div>
                </div>
              )}
              <div className="p-networth-evidence">
                <EvidenceLine
                  evidence={net?.source ?? data.source}
                  locale={locale}
                />
                {resource.loading && (
                  <span role="status" className="p-muted">
                    {en ? "Refreshing…" : "Actualizando…"}
                  </span>
                )}
              </div>
            </section>
            <section className="argus-money-composer">
              <ArgusComposer
                locale={locale}
                placeholder={en ? "Ask Argus" : "Pregunta a Argus"}
                onSend={(text) => {
                  onNavigate("chat", {
                    draft: stageChatDraft(props.workspaceKey, text),
                  });
                  return true;
                }}
                onAttach={() => onNavigate("transactions", { import: "1" })}
              />
              <p>
                {en
                  ? "Ask about these records, or explore a plan."
                  : "Pregunta sobre estos registros o explora un plan."}
              </p>
            </section>
            <section className="p-overview-accounts">
              <div className="p-section-heading">
                <h2>{en ? "Your accounts" : "Tus cuentas"}</h2>
                <button
                  className="p-button-ghost"
                  onClick={() => onNavigate("accounts")}
                >
                  {en ? "View all" : "Ver todas"}
                  <ArrowRight size={16} />
                </button>
              </div>
              {data.accounts.length ? (
                <div className="p-ledger">
                  {data.accounts.slice(0, 5).map((account) => (
                    <div
                      className="p-ledger-row p-overview-account"
                      key={account.id}
                    >
                      <span
                        className={`p-account-icon p-account-${account.kind}`}
                      >
                        <Landmark size={20} />
                      </span>
                      <div className="p-row-main">
                        <button
                          className="p-text-button"
                          onClick={() =>
                            onNavigate("transactions", {
                              account_id: account.id,
                            })
                          }
                        >
                          {account.name}
                        </button>
                        <span className="p-muted">
                          {account.institution} · {account.currency}
                        </span>
                      </div>
                      <div className="p-row-value">
                        <Money
                          amount={account.balance}
                          currency={account.currency}
                          locale={locale}
                        />
                        <EvidenceLine
                          evidence={account.source}
                          locale={locale}
                        />
                      </div>
                      <button
                        className="p-icon-button p-account-arrow"
                        aria-label={`${en ? "View transactions for" : "Ver movimientos de"} ${account.name}`}
                        onClick={() =>
                          onNavigate("transactions", { account_id: account.id })
                        }
                      >
                        <ArrowRight size={17} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title={
                    en ? "Start with an account" : "Empieza con una cuenta"
                  }
                  description={
                    en
                      ? "Add a local account to see its balance here."
                      : "Agrega una cuenta local para ver su saldo aquí."
                  }
                  action={
                    <button
                      className="p-button-secondary"
                      onClick={() => onNavigate("accounts")}
                    >
                      {en ? "Add account" : "Agregar cuenta"}
                    </button>
                  }
                />
              )}
            </section>
            <div className="p-overview-bottom">
              <section>
                <div className="p-section-heading">
                  <h2>{en ? "This month" : "Este mes"}</h2>
                  <button
                    className="p-button-ghost"
                    onClick={() => onNavigate("spending")}
                  >
                    {en ? "View spending" : "Ver gastos"}
                    <ArrowRight size={16} />
                  </button>
                </div>
                {cash ? (
                  <>
                    <div className="p-cashflow-row">
                      <span className="p-cashflow-label">
                        <ArrowDownLeft size={18} />
                        {en ? "Money in" : "Entradas"}
                      </span>
                      <Money
                        amount={cash.income}
                        currency={currency}
                        locale={locale}
                      />
                    </div>
                    <div className="p-cashflow-row">
                      <span className="p-cashflow-label">
                        <ArrowUpRight size={18} />
                        {en ? "Money out" : "Salidas"}
                      </span>
                      <Money
                        amount={cash.spending}
                        currency={currency}
                        locale={locale}
                      />
                    </div>
                    <div className="p-cashflow-row p-cashflow-net">
                      <span>{en ? "Net cash flow" : "Flujo neto"}</span>
                      <Money
                        amount={cash.net}
                        currency={currency}
                        locale={locale}
                      />
                    </div>
                    <EvidenceLine evidence={cash.source} locale={locale} />
                  </>
                ) : (
                  <p className="p-muted">
                    {en
                      ? "No activity in this currency."
                      : "Sin actividad en esta moneda."}
                  </p>
                )}
              </section>
              {notices.length > 0 && (
                <section className="p-review-section">
                  <h2>{en ? "For your review" : "Para revisar"}</h2>
                  {notices.map((notice) => (
                    <article key={notice.id} className="p-review-row">
                      <button
                        className="p-text-button"
                        onClick={() =>
                          onNavigate(
                            notice.fact.target.page,
                            notice.fact.target.query,
                          )
                        }
                      >
                        {assistantLabel(
                          assistantCopy(locale).notices,
                          notice.code,
                        )}
                        <ArrowRight size={16} />
                      </button>
                      <EvidenceLine
                        evidence={notice.fact.source}
                        locale={locale}
                      />
                    </article>
                  ))}
                </section>
              )}
            </div>
          </>
        )
      )}
    </>
  );
}

function ActivePage({ page, ...props }: PlatformPageProps & { page: Page }) {
  switch (page) {
    case "chat":
      return <ConversationPage {...props} />;
    case "accounts":
      return <AccountsPage {...props} />;
    case "budgets":
      return <BudgetsPage {...props} />;
    case "goals":
      return <GoalsPage {...props} />;
    case "scenarios":
      return <ScenariosPage {...props} />;
    case "transactions":
      return <TransactionsPage {...props} />;
    case "spending":
      return <SpendingPage {...props} />;
    case "investments":
      return <InvestmentsPage {...props} />;
    case "deposits":
      return <DepositsPage {...props} />;
    case "credit":
      return <CreditPage {...props} />;
    case "tax-estate":
      return <TaxEstatePage {...props} />;
    case "membership":
      return <MembershipPage {...props} />;
    case "help":
      return <HelpPage {...props} />;
    case "employer":
      return <EmployerPage {...props} />;
    case "settings":
      return <SettingsPage {...props} />;
    case "household":
      return <HouseholdPage {...props} />;
    case "saved":
      return <SavedAssistantPage {...props} />;
    default:
      return <OverviewPage {...props} />;
  }
}
