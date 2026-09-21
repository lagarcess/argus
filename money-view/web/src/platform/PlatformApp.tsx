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
  ChevronDown,
  Landmark,
  Menu,
  Search,
  Sparkles,
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
  profileSchema,
  preferencesSchema,
  householdSchema,
} from "../features/settings/contracts";
const DepositsPage = lazy(() =>
  import("../features/deposits/DepositsPage").then((module) => ({
    default: module.DepositsPage,
  })),
);
const AssistantDrawer = lazy(() =>
  import("../features/assistant/AssistantDrawer").then((module) => ({
    default: module.AssistantDrawer,
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
import "./shell.css";

const sessionSchema = z.object({
  user: profileSchema,
  household: householdSchema,
  preferences: preferencesSchema,
  local_only: z.boolean(),
  supported_currencies: z.array(z.string()).min(1),
});
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
  const session = useResource(
    () => request("/session", sessionSchema),
    [authEpoch],
  );
  const [viewCurrencies, setViewCurrencies] = useState<Record<string, string>>(
    {},
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [householdOpen, setHouseholdOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [sessionError, setSessionError] = useState(false);
  const [switching, setSwitching] = useState(false);
  const data = expired || session.error ? null : session.data;
  const currencyOwner = data
    ? `${data.user.id}:${data.household.id}:${data.household.effective_currency}`
    : "";
  const explicitCurrency = viewCurrencies[currencyOwner];
  const currency = data?.supported_currencies.includes(explicitCurrency)
    ? explicitCurrency
    : (data?.household.effective_currency ?? "");
  const locale = data?.preferences.locale ?? guestLocale;
  const en = locale === "en";
  const change = useCallback(() => {
    setRevision((value) => value + 1);
    session.reload();
  }, [session.reload]);
  const go = useCallback(
    (destination: Page, params?: Record<string, string>) => {
      navigate(destination, params);
      setMobileOpen(false);
      setHouseholdOpen(false);
    },
    [navigate],
  );
  useEffect(() => {
    const expire = () => {
      setExpired(true);
      setAssistantOpen(false);
      setHouseholdOpen(false);
    };
    window.addEventListener("clara:session-expired", expire);
    return () => window.removeEventListener("clara:session-expired", expire);
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  useEffect(() => {
    setMobileOpen(false);
    const title = document.querySelector<HTMLElement>(".p-main h1");
    if (title) {
      title.tabIndex = -1;
      title.focus({ preventScroll: true });
    }
  }, [page]);
  const theme = data?.preferences.appearance ?? "light";
  const props: PlatformPageProps = {
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
      setAssistantOpen(false);
      setHouseholdOpen(false);
    } catch {
      setSessionError(true);
    }
  }
  if (!session.data && session.loading && !expired)
    return (
      <div className="platform-shell p-entry" data-theme="light">
        <span className="p-wordmark">
          Clara<span>·</span>
        </span>
        <p role="status">
          {en ? "Opening your workspace…" : "Abriendo tu espacio…"}
        </p>
      </div>
    );
  if (!data)
    return (
      <div className="platform-shell" data-theme="light">
        <Login
          locale={guestLocale}
          onLocale={setGuestLocale}
          onLogin={() => {
            setAuthEpoch((value) => value + 1);
            setExpired(false);
            setSessionError(false);
            setRevision((value) => value + 1);
          }}
        />
      </div>
    );
  function navItem(item: (typeof destinations)[number], compact = false) {
    const Icon = item.icon;
    return (
      <a
        key={item.id}
        href={`#${item.id}`}
        className="p-nav-item"
        aria-current={page === item.id ? "page" : undefined}
        title={compact ? (en ? item.en : item.es) : undefined}
        onClick={() => {
          setMobileOpen(false);
          setHouseholdOpen(false);
        }}
      >
        <Icon size={18} />
        <span>{en ? item.en : item.es}</span>
      </a>
    );
  }
  return (
    <div
      className="platform-shell"
      data-theme={theme}
      data-compact={data.preferences.sidebar_compact}
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
      <aside
        className="p-sidebar"
        aria-label={en ? "Main navigation" : "Navegación principal"}
      >
        <a className="p-wordmark" href="#overview">
          Clara<span>·</span>
        </a>
        <p className="p-nav-label">{en ? "MY MONEY" : "MI DINERO"}</p>
        <nav>
          {destinations
            .filter((item) => item.group === "money")
            .map((item) => navItem(item, data.preferences.sidebar_compact))}
        </nav>
        <p className="p-nav-label">{en ? "PLAN AHEAD" : "PLANIFICAR"}</p>
        <nav>
          {destinations
            .filter((item) => item.group === "plan")
            .map((item) => navItem(item, data.preferences.sidebar_compact))}
        </nav>
        <div className="p-sidebar-bottom">
          <nav>
            {destinations
              .filter((item) => item.group === "utility")
              .map((item) => navItem(item, data.preferences.sidebar_compact))}
          </nav>
          <div className="p-sidebar-note">
            <span className="p-status-dot" />
            {en ? "Local demonstration" : "Demostración local"}
          </div>
        </div>
      </aside>
      <div className="p-workspace">
        <header className="p-topbar">
          <button
            className="p-icon-button p-mobile-menu"
            aria-label={en ? "Open navigation" : "Abrir navegación"}
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={22} />
          </button>
          <button
            className="p-household-button"
            aria-label={`${data.household.name} · ${data.user.preferred_name ?? data.user.display_name}`}
            onClick={() => setHouseholdOpen(true)}
          >
            <span className="p-avatar">
              {data.user.display_name.slice(0, 1)}
            </span>
            <span className="p-household-name">
              {data.household.name}
              <small>{en ? "Demo mode" : "Modo demo"}</small>
            </span>
            <ChevronDown size={14} />
          </button>
          <span className="p-topbar-spacer" />
          <form
            className="p-global-search"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              go("transactions", { q: search });
            }}
          >
            <Search size={17} />
            <input
              aria-label={en ? "Search transactions" : "Buscar movimientos"}
              placeholder={en ? "Search transactions" : "Buscar movimientos"}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </form>
          <label className="p-currency">
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
              {data.supported_currencies.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <NoticeCenter
            key={`${data.user.id}:${data.household.id}`}
            locale={locale}
            currency={currency}
            revision={revision}
            routeKey={`${page}?${query.toString()}`}
            onNavigate={go}
          />
          <button
            className="p-assistant-trigger"
            aria-label={en ? "Ask Clara" : "Preguntar a Clara"}
            onClick={() => setAssistantOpen(true)}
          >
            <Sparkles size={17} />
            <span>{en ? "Ask Clara" : "Preguntar a Clara"}</span>
          </button>
        </header>
        <main id="platform-content" className="p-main" tabIndex={-1}>
          <Suspense
            fallback={
              <p className="p-loading" role="status">
                {en ? "Loading your view…" : "Cargando tu vista…"}
              </p>
            }
          >
            <ActivePage
              key={`${data.user.id}:${data.household.id}:${page}`}
              page={page}
              {...props}
            />
          </Suspense>
          <footer className="p-page-footer">
            <span className="p-status-dot" />
            {en
              ? "A local demonstration. Simulated data and workflows."
              : "Una demostración local. Datos y procesos simulados."}
          </footer>
        </main>
      </div>
      <nav
        className="p-mobile-tabs"
        aria-label={en ? "Quick navigation" : "Navegación rápida"}
      >
        {destinations
          .filter((item) =>
            ["overview", "accounts", "transactions"].includes(item.id),
          )
          .map((item) => navItem(item))}
        <button onClick={() => setMobileOpen(true)} className="p-nav-item">
          <Menu size={20} />
          <span>{en ? "More" : "Más"}</span>
        </button>
      </nav>
      {mobileOpen && (
        <Modal
          title={en ? "Your workspace" : "Tu espacio"}
          onClose={() => setMobileOpen(false)}
        >
          <nav className="p-mobile-full-nav">
            {destinations.map((item) => navItem(item))}
          </nav>
        </Modal>
      )}
      {householdOpen && (
        <Modal
          title={en ? "Your household" : "Tu hogar"}
          onClose={() => setHouseholdOpen(false)}
        >
          <div className="p-profile-summary">
            <span className="p-avatar">
              {(data.user.preferred_name ?? data.user.display_name).slice(0, 1)}
            </span>
            <div>
              <strong>
                {data.user.preferred_name ?? data.user.display_name}
              </strong>
              <p className="p-muted">{en ? "Local profile" : "Perfil local"}</p>
            </div>
          </div>
          <HouseholdMenu
            locale={locale}
            currentId={data.household.id}
            onSelect={async (id) => {
              setSwitching(true);
              setSessionError(false);
              try {
                await request("/households/switch", sessionSchema, {
                  method: "POST",
                  body: JSON.stringify({ household_id: id }),
                });
                setHouseholdOpen(false);
                setAssistantOpen(false);
                setAuthEpoch((value) => value + 1);
                setRevision((value) => value + 1);
                go("overview");
              } catch {
                setSessionError(true);
              } finally {
                setSwitching(false);
              }
            }}
            busy={switching}
          />
          <div className="p-stack p-menu-links">
            {destinations
              .filter((item) =>
                ["household", "membership", "employer", "settings"].includes(
                  item.id,
                ),
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
      {assistantOpen && (
        <Suspense
          fallback={
            <Modal title="Clara" onClose={() => setAssistantOpen(false)}>
              <p role="status">{en ? "Loading…" : "Cargando…"}</p>
            </Modal>
          }
        >
          <AssistantDrawer
            key={`${data.user.id}:${data.household.id}`}
            {...props}
            page={page}
            onClose={() => setAssistantOpen(false)}
          />
        </Suspense>
      )}
    </div>
  );
}

function Login({
  locale,
  onLocale,
  onLogin,
}: {
  locale: Locale;
  onLocale: (value: Locale) => void;
  onLogin: () => void;
}) {
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
    <div className="p-login">
      <header>
        <a href="#overview" className="p-wordmark">
          Clara<span>·</span>
        </a>
        <div className="p-actions">
          <button
            className="p-button-ghost"
            aria-pressed={!en}
            onClick={() => onLocale("es-419")}
          >
            ES
          </button>
          <button
            className="p-button-ghost"
            aria-pressed={en}
            onClick={() => onLocale("en")}
          >
            EN
          </button>
        </div>
      </header>
      <div className="p-login-body">
        <div className="p-login-intro">
          <span className="p-eyebrow">
            {en ? "A CLEARER VIEW" : "TODO, MÁS CLARO"}
          </span>
          <h1>
            {en
              ? "Your money.\nIn perspective."
              : "Tu dinero.\nEn perspectiva."}
          </h1>
          <p>
            {en
              ? "Accounts, plans, and the details that connect them. Explore a household with realistic, simulated records."
              : "Cuentas, planes y los detalles que los conectan. Explora un hogar con registros realistas y simulados."}
          </p>
          <div className="p-login-rule" />
          <p className="p-muted">
            {en
              ? "Local demo · No bank connection · No real transactions"
              : "Demo local · Sin conexión bancaria · Sin transacciones reales"}
          </p>
        </div>
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
                label={
                  en ? "Local account ID" : "Identificador de cuenta local"
                }
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
              <p role="status">
                {en ? "Loading profiles…" : "Cargando perfiles…"}
              </p>
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
                (mode === "demo" &&
                  (personas.loading || Boolean(personas.error)))
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
      </div>
    </div>
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
        title={en ? "Overview" : "Resumen"}
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
