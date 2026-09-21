import { useState, type FormEvent } from 'react';
import { Check } from 'lucide-react';
import type { Confirmation as ConfirmationData, Home, Locale, PlacementInputs } from '../contracts';
import { copy, date } from '../i18n';

export function Confirmation({
  confirmation,
  countries,
  locale,
  pending,
  onConfirm,
  onInputsChange,
}: {
  confirmation: ConfirmationData;
  countries: Home['countries'];
  locale: Locale;
  pending: boolean;
  onConfirm: () => void;
  onInputsChange: (inputs: PlacementInputs) => void;
}) {
  const t = copy(locale);
  const inputs = confirmation.inputs;
  const [invalid, setInvalid] = useState(false);
  const currencies = countries.find((country) => country.code === inputs.country)?.currencies ?? [
    inputs.currency,
  ];
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !Number.isFinite(Number(inputs.amount)) ||
      Number(inputs.amount) <= 0 ||
      Number(inputs.amount) > 1e12 ||
      !Number.isInteger(inputs.horizon_days) ||
      inputs.horizon_days < 1 ||
      inputs.horizon_days > 3650 ||
      (inputs.current_annual_rate_pct !== null &&
        !Number.isFinite(Number(inputs.current_annual_rate_pct)))
    ) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onConfirm();
  }
  return (
    <form className="confirmation" data-testid="confirmation" onSubmit={submit}>
      <h3>{t.confirmTitle}</h3>
      <p>{t.confirmHelp}</p>
      <div className="form-grid">
        <label>
          {t.amount}
          <input
            disabled={pending}
            id="confirmation-amount"
            name="amount"
            inputMode="decimal"
            type="number"
            min="0.01"
            max="1000000000000"
            step="any"
            required
            value={inputs.amount}
            onChange={(event) => onInputsChange({ ...inputs, amount: event.target.value })}
          />
        </label>
        <label>
          {t.horizon}
          <input
            disabled={pending}
            name="horizon_days"
            inputMode="numeric"
            type="number"
            min="1"
            max="3650"
            required
            value={inputs.horizon_days}
            onChange={(event) =>
              onInputsChange({ ...inputs, horizon_days: Number(event.target.value) })
            }
          />
        </label>
        <label>
          {t.country}
          <select
            disabled={pending}
            name="country"
            value={inputs.country}
            onChange={(event) => {
              const country = countries.find((item) => item.code === event.target.value);
              if (country)
                onInputsChange({
                  ...inputs,
                  country: country.code,
                  currency: country.currencies.includes(inputs.currency)
                    ? inputs.currency
                    : (country.currencies[0] ?? inputs.currency),
                });
            }}
          >
            {countries.map((country) => (
              <option key={country.code} value={country.code}>
                {country.names[locale]}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t.currency}
          <select
            disabled={pending}
            name="currency"
            value={inputs.currency}
            onChange={(event) => onInputsChange({ ...inputs, currency: event.target.value })}
          >
            {currencies.map((currency) => (
              <option key={currency}>{currency}</option>
            ))}
          </select>
        </label>
      </div>
      <label>
        {t.currentInput}
        <input
          disabled={pending}
          name="current_annual_rate_pct"
          type="number"
          step="any"
          inputMode="decimal"
          value={inputs.current_annual_rate_pct ?? ''}
          onChange={(event) =>
            onInputsChange({
              ...inputs,
              current_annual_rate_pct: event.target.value === '' ? null : event.target.value,
            })
          }
        />
      </label>
      <p className="small">{t.baselineHint}</p>
      <p className="small">
        {t.pendingInputs} · {date(confirmation.created_at, locale)} · {t.illustration}
      </p>
      {invalid && (
        <p role="alert" className="error">
          {t.inputError}
        </p>
      )}
      <button type="submit" className="primary" data-testid="confirm-comparison" disabled={pending}>
        <Check size={17} />
        {pending ? t.calculating : t.confirm}
      </button>
    </form>
  );
}
