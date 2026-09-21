import { useState } from "react";
import type { Locale } from "../../platform/types";
import { copy } from "./copy";
import { APIError } from "../../platform/client";

export function ledgerError(code: string, locale: Locale) {
  const messages: Record<string, [string, string]> = {
    read_only_household: [
      "Tu rol permite consultar. Pide a la persona propietaria que guarde este cambio.",
      "Your role allows viewing. Ask the owner to save this change.",
    ],
    permission_denied: [
      "No tienes permiso para cambiar este registro.",
      "You do not have permission to change this record.",
    ],
    forbidden: [
      "No tienes permiso para cambiar este registro.",
      "You do not have permission to change this record.",
    ],
    invalid_category: [
      "La categoría no corresponde al tipo de movimiento.",
      "The category does not match the transaction type.",
    ],
    split_total_mismatch: [
      "Las partes deben sumar el importe original y conservar su signo.",
      "Splits must total the original amount and keep its sign.",
    ],
    split_kind_unsupported: [
      "Solo se pueden dividir gastos y reembolsos.",
      "Only expenses and refunds can be split.",
    ],
    invalid_csv_headers: [
      "Usa las columnas del archivo de ejemplo, en el mismo orden.",
      "Use the sample file columns in the same order.",
    ],
    invalid_csv_row: [
      "Revisa fecha, importe, tipo y categoría de esta fila.",
      "Check the date, amount, type, and category in this row.",
    ],
    import_currency_mismatch: [
      "La moneda de la fila debe coincidir con la cuenta.",
      "The row currency must match the account.",
    ],
    import_too_large: [
      "El archivo supera el límite de 2,000 filas.",
      "The file exceeds the 2,000 row limit.",
    ],
    csv_transfer_unsupported: [
      "Registra las transferencias con el formulario de movimientos.",
      "Record transfers using the transaction form.",
    ],
    invalid_date_range: [
      "La fecha final debe ser igual o posterior a la inicial.",
      "The end date must be on or after the start date.",
    ],
    reversed_transaction_immutable: [
      "Este movimiento ya tiene una contrapartida y conserva su registro original.",
      "This transaction already has a reversal and retains its original record.",
    ],
    unsupported_currency: [
      "Esta moneda no está disponible. Elige una moneda del selector principal.",
      "This currency is unavailable. Choose a currency from the main selector.",
    ],
    invalid_money_precision: [
      "El importe tiene más decimales de los que admite esta moneda, o supera el límite.",
      "The amount has more decimal places than this currency supports, or exceeds the limit.",
    ],
    idempotency_conflict: [
      "Ya se guardó una versión anterior. Cierra y vuelve a abrir el formulario para otro cambio.",
      "An earlier version was already saved. Close and reopen the form for another change.",
    ],
  };
  return messages[code]?.[locale === "en" ? 1 : 0] ?? copy(locale).error;
}

export function ResourceState({
  loading,
  error,
  retry,
  locale,
}: {
  loading: boolean;
  error: Error | null;
  retry: () => void;
  locale: Locale;
}) {
  const t = copy(locale);
  return (
    <>
      {loading && (
        <p className="p-muted" role="status">
          {t.loading}
        </p>
      )}
      {error && (
        <div className="p-error" role="alert">
          {t.loadError}{" "}
          <button className="p-button-ghost" onClick={retry}>
            {t.retry}
          </button>
        </div>
      )}
    </>
  );
}
export function useLedgerMutation(locale: Locale) {
  const [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function run(action: () => Promise<unknown>, done?: () => void) {
    if (pending) return;
    setPending(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(copy(locale).saved);
      done?.();
    } catch (error) {
      setError(
        ledgerError(error instanceof APIError ? error.code : "unknown", locale),
      );
    } finally {
      setPending(false);
    }
  }
  return { pending, error, notice, run, setError, setNotice };
}
export const newKey = () => crypto.randomUUID();
