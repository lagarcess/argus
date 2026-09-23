import { useModalBackDismiss } from "../argus/useModalBackDismiss";
import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { X, ArrowRight, ExternalLink } from "lucide-react";
import type { Evidence, Locale } from "./types";

export function PageHeader({
  title,
  eyebrow,
  description,
  actions,
  children,
}: {
  title: string;
  eyebrow?: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="p-page-header">
      <div>
        {eyebrow && <p className="p-eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="p-description">{description}</p>}
        {children}
      </div>
      {actions && <div className="p-actions">{actions}</div>}
    </header>
  );
}
export function Panel({
  children,
  className = "",
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <section {...props} className={`p-panel ${className}`}>
      {children}
    </section>
  );
}
export function Field({
  label,
  children,
  help,
  error,
}: {
  label: string;
  children: ReactNode;
  help?: string;
  error?: string;
}) {
  const id = useId();
  const hint = help || error ? `${id}-description` : undefined;
  const input = isValidElement<HTMLAttributes<HTMLElement>>(children)
    ? cloneElement(children, {
        "aria-describedby":
          [children.props["aria-describedby"], hint]
            .filter(Boolean)
            .join(" ") || undefined,
        "aria-invalid": error ? true : undefined,
      })
    : children;
  return (
    <label className="p-field">
      <span>{label}</span>
      {input}
      {hint && (
        <small
          id={hint}
          className={error ? "p-error" : undefined}
          role={error ? "alert" : undefined}
        >
          {error ?? help}
        </small>
      )}
    </label>
  );
}
export function Money({
  amount,
  currency,
  locale,
}: {
  amount: string | number;
  currency: string;
  locale: Locale;
}) {
  const value = Number(amount);
  return (
    <span className="p-money">
      {Number.isFinite(value)
        ? new Intl.NumberFormat(locale, {
            style: "currency",
            currency,
            currencyDisplay: "code",
            maximumFractionDigits: undefined,
          }).format(value)
        : locale === "en"
          ? "Unavailable"
          : "No disponible"}
    </span>
  );
}
export function EvidenceLine({
  evidence,
  locale,
}: {
  evidence: Evidence;
  locale: Locale;
}) {
  const spanish = locale !== "en";
  const labels = spanish
    ? {
        synthetic: "Datos simulados",
        user: "Registro personal",
        calculated: "Cálculo",
        published: "Fuente publicada",
      }
    : {
        synthetic: "Simulated data",
        user: "Personal record",
        calculated: "Calculation",
        published: "Published source",
      };
  const dateValue = evidence.published_on ?? evidence.as_of;
  const parsed = new Date(
    dateValue.length === 10 ? `${dateValue}T12:00:00Z` : dateValue,
  );
  const date = Number.isNaN(parsed.valueOf())
    ? dateValue
    : new Intl.DateTimeFormat(locale, {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(parsed);
  const safeUrl =
    evidence.url && /^https?:\/\//.test(evidence.url) ? evidence.url : null;
  return (
    <div className="p-evidence">
      <span>
        {labels[evidence.kind]} ·{" "}
        {spanish
          ? evidence.published_on
            ? "Publicado"
            : "Al"
          : evidence.published_on
            ? "Published"
            : "As of"}{" "}
        {date}
      </span>
      <details>
        <summary>
          {spanish ? "Fuente y cálculo" : "Source and calculation"}
        </summary>
        <div className="p-evidence-detail">
          <strong>{evidence.title}</strong>
          {evidence.published_on &&
            evidence.as_of !== evidence.published_on && (
              <small>
                {spanish ? "Observación" : "Observed"}: {evidence.as_of}
              </small>
            )}
          {evidence.method && <p>{evidence.method}</p>}
          {evidence.inputs.length > 0 && (
            <p>
              {spanish ? "Registros utilizados" : "Records used"}:{" "}
              {evidence.inputs.length}
            </p>
          )}
          {safeUrl && (
            <a href={safeUrl} target="_blank" rel="noreferrer">
              {spanish ? "Abrir fuente" : "Open source"}{" "}
              <ExternalLink size={12} />
            </a>
          )}
          <small>
            {spanish ? "Registrado" : "Recorded"}: {evidence.recorded_at}
          </small>
        </div>
      </details>
    </div>
  );
}
export function EmptyState({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="p-empty">
      <ArrowRight size={24} />
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action}
      {children}
    </div>
  );
}

// Native modal dialogs give one topmost keyboard owner, including nested dialogs.
let openModals = 0;
let previousOverflow = "";
export function Modal({
  title,
  onClose,
  children,
  footer,
  destructive = false,
  variant = "default",
  dismissible = true,
  historyMode = "overlay",
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  destructive?: boolean;
  variant?: "default" | "search" | "drawer";
  dismissible?: boolean;
  historyMode?: "overlay" | "route";
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const locale = document.documentElement.lang;
  useModalBackDismiss({
    isOpen: historyMode === "overlay",
    overlayId: id,
    onDismiss: onClose,
    canDismiss: () => dismissible,
  });
  useEffect(() => {
    const dialog = ref.current;
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    if (!dialog) return;
    if (openModals++ === 0) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    dialog.showModal();
    (
      dialog.querySelector<HTMLButtonElement>("[data-modal-cancel]") ??
      dialog.querySelector<HTMLButtonElement>("[data-modal-close]")
    )?.focus();
    return () => {
      dialog.close();
      if (--openModals === 0) document.body.style.overflow = previousOverflow;
      if (opener?.isConnected) opener.focus();
      else document.querySelector<HTMLElement>(".p-main h1")?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="p-modal"
      data-variant={variant}
      role={destructive ? "alertdialog" : "dialog"}
      aria-labelledby={id}
      aria-modal="true"
      onCancel={(event) => {
        event.preventDefault();
        if (dismissible) closeRef.current();
      }}
      onClick={(event) => {
        if (dismissible && event.target === event.currentTarget) {
          const rect = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            closeRef.current();
        }
      }}
    >
      <div className="p-modal-header">
        <h2 id={id}>{title}</h2>
        <button
          type="button"
          className="p-icon-button"
          data-modal-close
          disabled={!dismissible}
          aria-label={locale === "en" ? "Close" : "Cerrar"}
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <div className="p-modal-body">{children}</div>
      {footer && <footer className="p-modal-footer">{footer}</footer>}
    </dialog>
  );
}
