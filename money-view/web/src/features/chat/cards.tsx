import { useEffect, useState, type FormEvent } from 'react';
import { Check, ChevronDown, ExternalLink, Pencil, X } from 'lucide-react';
import type { Locale, Page } from '../../platform/types';
import { EvidenceLine, Money } from '../../platform/ui';
import { commandFieldLabel, commandTitle, copy, dateLabel, enumValueLabel } from './copy';
import { canConfirmCanonicalProposal } from './proposal-state';
import { fieldLabel, toolFailureText, toolSourceText, toolStatusText, toolText } from './tool-copy';
import type {
  CalculationDeclaration,
  ChatCard,
  CommandDeclaration,
  CommandField,
  CommandReceipt,
  PreparedAction,
  Proposal,
  ReadFact,
  ToolFact,
  ToolInputFact,
  ToolResultCard,
} from './contracts';

type Navigate = (page: Page, query?: Record<string, string>) => void;
type JsonSchema = Record<string, unknown>;

function record(value: unknown): JsonSchema {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as JsonSchema : {};
}

function resolveRef(root: JsonSchema, schema: JsonSchema) {
  const reference = typeof schema.$ref === 'string' ? schema.$ref : '';
  if (!reference.startsWith('#/$defs/')) return schema;
  return record(record(root.$defs)[reference.slice('#/$defs/'.length)]);
}

function fieldSchema(root: JsonSchema, path: string) {
  let current = root;
  for (const segment of path.split('.')) {
    current = resolveRef(root, current);
    current = resolveRef(root, record(record(current.properties)[segment]));
  }
  return current;
}

function schemaVariants(schema: JsonSchema) {
  const values = Array.isArray(schema.anyOf) ? schema.anyOf.map(record) : [];
  return values.length ? values : [schema];
}

function schemaType(schema: JsonSchema) {
  return schemaVariants(schema).map((item) => item.type).find((value) => typeof value === 'string') as string | undefined;
}

function schemaEnum(schema: JsonSchema) {
  for (const item of schemaVariants(schema)) {
    if (Array.isArray(item.enum)) return item.enum.filter((value): value is string => typeof value === 'string');
  }
  return [];
}

function requiredPaths(root: JsonSchema, schema = root, prefix = ''): string[] {
  const resolved = resolveRef(root, schema);
  const properties = record(resolved.properties);
  const required = new Set(Array.isArray(resolved.required) ? resolved.required.filter((value): value is string => typeof value === 'string') : []);
  return Object.entries(properties).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    const nested = resolveRef(root, record(value));
    const nestedProperties = record(nested.properties);
    if (Object.keys(nestedProperties).length) return requiredPaths(root, nested, path);
    return required.has(key) ? [path] : [];
  });
}

function mappedTarget(page: string): { page: Page; query: Record<string, string> } | null {
  if (page === 'bills') return { page: 'budgets', query: { tab: 'bills' } };
  if (page === 'tax' || page === 'estate') return { page: 'tax-estate', query: { tab: page } };
  const pages: Page[] = ['accounts', 'transactions', 'spending', 'budgets', 'goals', 'scenarios', 'investments', 'credit', 'settings'];
  return pages.includes(page as Page) ? { page: page as Page, query: {} } : null;
}

function openTarget(target: { page: string; record_id?: string | null; query?: Record<string, string> }, onNavigate: Navigate) {
  const mapped = mappedTarget(target.page);
  if (!mapped) return;
  onNavigate(mapped.page, {
    ...mapped.query,
    ...(target.query ?? {}),
    ...(target.record_id ? { record_id: target.record_id } : {}),
  });
}

function FactValue({ fact, locale }: { fact: ReadFact; locale: Locale }) {
  if (fact.unit === 'money' && fact.currency) return <Money amount={fact.value} currency={fact.currency} locale={locale} />;
  if (fact.unit === 'percent') return <>{new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(Number(fact.value))}%</>;
  return <>{new Intl.NumberFormat(locale, { maximumFractionDigits: 8 }).format(Number(fact.value))}</>;
}

function ReadCard({ card, locale, onNavigate }: { card: Extract<ChatCard, { kind: 'read' }>; locale: Locale; onNavigate: Navigate }) {
  const t = copy(locale);
  if (!card.facts.length) return <section className="argus-inline-card argus-read-card"><p>{t.noFacts}</p></section>;
  return <section className="argus-inline-card argus-read-card">
    {card.facts.map((fact, index) => <article className="argus-fact" key={`${fact.key}-${fact.target.record_ids.join('-')}-${index}`}>
      <div className="argus-fact-main"><span>{fact.record_name ? `${fact.record_name} · ` : ''}{commandFieldLabel(fact.key, locale)}</span><strong><FactValue fact={fact} locale={locale} /></strong></div>
      {fact.notes.includes('partial_unpriced_holdings') ? <p className="argus-card-note">{t.partial}</p> : null}
      <EvidenceLine evidence={fact.source} locale={locale} />
      <button className="argus-card-link" type="button" onClick={() => {
        const page = mappedTarget(fact.target.page);
        if (page) onNavigate(page.page, { ...page.query, ...fact.target.query, ...(fact.target.record_ids[0] ? { record_id: fact.target.record_ids[0] } : {}) });
      }}>{t.openRecord}<ExternalLink size={14} /></button>
    </article>)}
  </section>;
}

function RecordsCard({ card, locale, busy, onNavigate, onPage }: {
  card: Extract<ChatCard, { kind: 'records' }>;
  locale: Locale;
  busy: boolean;
  onNavigate: Navigate;
  onPage: (action: PreparedAction) => void;
}) {
  const t = copy(locale);
  const first = card.total ? card.offset + 1 : 0;
  const last = Math.min(card.total, card.offset + card.rows.length);
  const label = card.resource === 'accounts' ? t.accountsRead : t.transactionsRead;
  return <section className="argus-inline-card argus-records-card" data-records-resource={card.resource}>
    <header><span>{label}</span><h3>{label}</h3></header>
    {card.rows.length ? <div className="argus-record-rows">{card.rows.map((row) => <article key={row.record_id} className="argus-record-row">
      <div className="argus-record-heading"><strong>{row.title}</strong><button className="argus-card-link" type="button" onClick={() => openTarget(row.target, onNavigate)}>{t.openRecord}<ExternalLink size={14} /></button></div>
      <dl className="argus-command-fields">{row.fields.map((field) => <div key={field.key}><dt>{commandFieldLabel(field.key, locale)}</dt><dd><CommandValue field={field} locale={locale} /></dd></div>)}</dl>
      {row.evidence.map((evidence) => <EvidenceLine evidence={evidence} locale={locale} key={evidence.id} />)}
    </article>)}</div> : <p>{t.noFacts}</p>}
    <footer className="argus-record-pagination"><span>{t.recordsRange}: {first}–{last} / {card.total}</span><div>
      <button type="button" className="p-button-ghost" disabled={busy || card.offset === 0} onClick={() => onPage({ ...card.query, offset: Math.max(0, card.offset - card.limit) })}>{t.previousRecords}</button>
      <button type="button" className="p-button-ghost" disabled={busy || last >= card.total} onClick={() => onPage({ ...card.query, offset: card.offset + card.limit })}>{t.nextRecords}</button>
    </div></footer>
  </section>;
}

function scalarText(value: ToolFact['value'], locale: Locale) {
  if (value === null) return locale === 'en' ? 'Unavailable' : 'No disponible';
  if (typeof value === 'number') return new Intl.NumberFormat(locale, { maximumFractionDigits: 8 }).format(value);
  if (typeof value === 'boolean') return value ? copy(locale).yes : copy(locale).no;
  return value;
}

function ToolFactView({ fact, locale, prominent = false }: { fact: ToolFact; locale: Locale; prominent?: boolean }) {
  const display = fact.value_text ? toolText(fact.value_text, locale) : scalarText(fact.value, locale);
  const unit = toolText(fact.unit, locale);
  const source = fact.source;
  return <div className={prominent ? 'argus-tool-answer' : 'argus-tool-row'}>
    <span>{toolText(fact.label, locale)}</span>
    <strong>{display}{unit ? ` ${unit}` : ''}</strong>
    {source ? <small>{toolSourceText(source.kind, locale, { title: source.title ?? '', date: source.date ?? '' })}</small> : null}
  </div>;
}

function CalculationVisual({ card, locale }: { card: ToolResultCard; locale: Locale }) {
  const visual = card.presentation.visual;
  if (!visual || visual.series.length < 2) return null;
  const values = visual.series.map((point) => point.value);
  const min = Math.min(...values), max = Math.max(...values), spread = max - min || 1;
  const points = visual.series.map((point, index) => `${(index / (visual.series.length - 1)) * 100},${48 - ((point.value - min) / spread) * 44}`).join(' ');
  const label = `${toolText(card.presentation.title, locale)}. ${dateLabel(visual.series[0].time, locale)} ${values[0]}. ${dateLabel(visual.series.at(-1)?.time ?? '', locale)} ${values.at(-1)}.`;
  return <details className="argus-tool-visual"><summary>{locale === 'en' ? 'Value path' : 'Trayectoria del valor'}</summary>
    <svg viewBox="0 0 100 52" role="img" aria-label={label} preserveAspectRatio="none"><polyline points={points} /></svg>
    <table><caption>{label}</caption><thead><tr><th>{locale === 'en' ? 'Date' : 'Fecha'}</th><th>{locale === 'en' ? 'Value' : 'Valor'}</th></tr></thead><tbody>{[visual.series[0], visual.series.at(-1)!].map((point) => <tr key={point.time}><td>{dateLabel(point.time, locale)}</td><td>{new Intl.NumberFormat(locale, { maximumFractionDigits: 8 }).format(point.value)}{visual.currency ? ` ${visual.currency}` : ''}</td></tr>)}</tbody></table>
  </details>;
}

function inputDraft(input: ToolInputFact) {
  if (input.value === null) return '';
  return String(input.value);
}

function CalculationCard({ card, evidence, declaration, locale, busy, onRecompute }: {
  card: ToolResultCard;
  evidence: Extract<ChatCard, { kind: 'calculation' }>['evidence'];
  declaration?: CalculationDeclaration;
  locale: Locale;
  busy: boolean;
  onRecompute: (action: PreparedAction) => void;
}) {
  const t = copy(locale);
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const visibleInputs = card.presentation.inputs.filter((input) => input.driving && !input.unknown);
  useEffect(() => setDrafts(Object.fromEntries(visibleInputs.map((input) => [input.name, inputDraft(input)]))), [card.artifact_id, card.input_revision]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const changes = Object.fromEntries(card.presentation.inputs.filter((input) => input.editable && drafts[input.name] !== inputDraft(input)).map((input) => {
      const schema = declaration ? fieldSchema(declaration.input_schema, input.name) : {};
      const type = schemaType(schema);
      const value = type === 'number' || type === 'integer' ? Number(drafts[input.name]) : type === 'boolean' ? drafts[input.name] === 'true' : drafts[input.name];
      return [input.name, value];
    }));
    if (Object.keys(changes).length) onRecompute({ kind: 'calculation', tool_name: card.tool_name, artifact_id: card.artifact_id, arguments: changes });
    setEditing(false);
  };
  const repair = card.outcome.failure?.repair;
  return <section className="argus-inline-card argus-tool-card">
    <header><span>{t.calculation}</span><h3>{toolText(card.presentation.title, locale)}</h3></header>
    {card.outcome.status === 'succeeded' ? <>
      {card.presentation.narrative ? <p>{card.presentation.narrative}</p> : null}
      {card.presentation.answer ? <ToolFactView fact={card.presentation.answer} locale={locale} prominent /> : null}
      {card.presentation.rows.filter((row) => !row.comparison_only).map((row) => <ToolFactView key={row.name} fact={row} locale={locale} />)}
      <CalculationVisual card={card} locale={locale} />
    </> : <div className="argus-card-error" role="status"><strong>{toolStatusText(card.outcome.status, locale)}</strong><p>{toolFailureText(card.outcome.failure?.code ?? '', card.outcome.failure?.fields ?? [], locale)}</p>{repair ? <button className="argus-next-move" disabled={busy} onClick={() => onRecompute({ kind: 'calculation', tool_name: card.tool_name, artifact_id: card.artifact_id, arguments: repair.changes })}><span aria-hidden="true">↳</span>{toolText(repair.label, locale)}</button> : null}</div>}
    {visibleInputs.length ? <details className="argus-card-details" open={editing}><summary><ChevronDown size={15} />{editing ? t.hideNumbers : t.showNumbers}</summary>
      {editing ? <form className="argus-card-form" onSubmit={submit}><p className="argus-card-note">{t.previousResult}</p>{visibleInputs.map((input) => <label key={input.name}><span>{toolText(input.label, locale)}</span><input disabled={busy || !input.editable} value={drafts[input.name] ?? ''} inputMode={typeof input.value === 'number' ? 'decimal' : undefined} onChange={(event) => setDrafts((current) => ({ ...current, [input.name]: event.target.value }))}/>{input.source ? <small>{toolSourceText(input.source.kind, locale, { title: input.source.title ?? '', date: input.source.date ?? '' })}</small> : null}</label>)}<div className="argus-card-actions"><button type="button" className="p-button-ghost" onClick={() => setEditing(false)}>{t.cancelEdit}</button><button className="p-button-secondary" disabled={busy}>{busy ? t.updating : t.updateResult}</button></div></form> : <><dl>{visibleInputs.map((input) => <div key={input.name}><dt>{toolText(input.label, locale)}</dt><dd>{scalarText(input.value, locale)}</dd></div>)}</dl>{visibleInputs.some((input) => input.editable) ? <button className="p-button-ghost" type="button" disabled={busy} onClick={() => setEditing(true)}><Pencil size={15}/>{t.edit}</button> : null}</>}
    </details> : null}
    {card.presentation.notes.map((note, index) => <p className="argus-card-note" key={`${note.locale_key}-${index}`}>{toolText(note, locale)}</p>)}
    {evidence.map((item) => <EvidenceLine evidence={item} locale={locale} key={item.id} />)}
  </section>;
}

function CommandValue({ field, locale }: { field: CommandField; locale: Locale }) {
  if (field.kind === 'money' && field.currency && !Array.isArray(field.value) && typeof field.value !== 'boolean') return <Money amount={field.value} currency={field.currency} locale={locale} />;
  if (Array.isArray(field.value)) return <ul>{field.value.map((value, index) => <li key={`${value}-${index}`}>{enumValueLabel(value, locale)}</li>)}</ul>;
  if (typeof field.value === 'boolean') return <>{field.value ? copy(locale).yes : copy(locale).no}</>;
  if (typeof field.value === 'number') return <>{new Intl.NumberFormat(locale, { maximumFractionDigits: 8 }).format(field.value)}{field.currency ? ` ${field.currency}` : ''}</>;
  if (field.kind === 'date' && typeof field.value === 'string') return <>{dateLabel(field.value, locale)}</>;
  return <>{enumValueLabel(String(field.value), locale)}{field.currency ? ` ${field.currency}` : ''}</>;
}

function CurrencyLines({ proposal, locale }: { proposal: Proposal; locale: Locale }) {
  const t = copy(locale);
  return <div className="argus-currency-lines">{proposal.currency.map((item, index) => <p key={`${item.kind}-${item.code}-${index}`}><strong>{t.currencySource}:</strong> {item.code} · {item.kind === 'account' ? t.currencyAccount : item.kind === 'record' ? t.currencyRecord : item.kind === 'ui_default' ? t.currencyDefault : t.currencyExplicit}{item.record_id ? ` · ${item.record_id}` : ''}</p>)}</div>;
}

function FieldEditor({ field, rootSchema, locale, value, onChange, missing = false }: {
  field: CommandField;
  rootSchema: JsonSchema;
  locale: Locale;
  value: string | boolean;
  onChange: (value: string | boolean) => void;
  missing?: boolean;
}) {
  const t = copy(locale);
  if (!field.editable) return <div className="argus-proposal-field argus-proposal-readonly"><span>{commandFieldLabel(field.key, locale)}{field.currency ? ` · ${field.currency}` : ''}</span><strong><CommandValue field={field} locale={locale}/></strong></div>;
  const schema = fieldSchema(rootSchema, field.key);
  const options = schemaEnum(schema);
  const boolean = typeof field.value === 'boolean' || schemaType(schema) === 'boolean';
  return <label className="argus-proposal-field"><span>{commandFieldLabel(field.key, locale)}{field.currency ? ` · ${field.currency}` : ''}</span>
    {boolean ? <select value={String(value)} onChange={(event) => onChange(event.target.value === 'true')}><option value="true">{t.yes}</option><option value="false">{t.no}</option></select>
      : options.length ? <select value={String(value)} onChange={(event) => onChange(event.target.value)}><option value="" disabled>{missing ? t.fieldMissing : ''}</option>{options.map((option) => <option value={option} key={option}>{enumValueLabel(option, locale)}</option>)}</select>
      : field.kind === 'list' ? <><textarea rows={3} value={String(value)} onChange={(event) => onChange(event.target.value)} /><small>{t.fieldListHelp}</small></>
      : <input type={field.kind === 'date' ? 'date' : 'text'} inputMode={field.kind === 'number' || field.kind === 'money' ? 'decimal' : undefined} value={String(value)} onChange={(event) => onChange(event.target.value)} />}
    {missing ? <small className="p-error">{t.fieldMissing}</small> : null}
  </label>;
}

function missingField(path: string, rootSchema: JsonSchema): CommandField {
  const schema = fieldSchema(rootSchema, path);
  const type = schemaType(schema);
  return { key: path, value: type === 'boolean' ? false : type === 'array' ? [] : '', kind: type === 'array' ? 'list' : type === 'number' || type === 'integer' ? 'number' : typeof schema.format === 'string' && schema.format === 'date' ? 'date' : 'text', currency: null, editable: true };
}

function ProposalCard({ proposal, declaration, locale, busy, onPatch, onConfirm, onCancel, onNavigate }: {
  proposal: Proposal;
  declaration?: CommandDeclaration;
  locale: Locale;
  busy: boolean;
  onPatch: (proposal: Proposal, changes: Record<string, string | number | boolean | string[]>) => Promise<boolean>;
  onConfirm: (proposal: Proposal) => void;
  onCancel: (proposal: Proposal) => void;
  onNavigate: Navigate;
}) {
  const t = copy(locale);
  const rootSchema = declaration?.input_schema ?? {};
  const required = declaration ? requiredPaths(rootSchema) : [];
  const missing = required.filter((path) => !proposal.fields.some((field) => field.key === path));
  const fields = [...proposal.fields, ...missing.map((path) => missingField(path, rootSchema))];
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string | boolean>>({});
  const [awaitingRevision, setAwaitingRevision] = useState<number | null>(null);
  useEffect(() => {
    setDrafts(Object.fromEntries(fields.map((field) => [field.key, typeof field.value === 'boolean' ? field.value : Array.isArray(field.value) ? field.value.join('\n') : String(field.value)])));
    setAwaitingRevision(null);
  }, [proposal.proposal_id, proposal.revision]);
  const expired = Date.parse(proposal.expires_at) <= Date.now();
  const active = proposal.status === 'pending' && !expired;
  const paperOnly = proposal.fields.some((field) => field.key === 'execution.scope' && field.value === 'scheduled_paper');
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const changes = Object.fromEntries(fields.flatMap((field) => {
      if (!field.editable) return [];
      const before = Array.isArray(field.value) ? field.value.join('\n') : field.value;
      const next = drafts[field.key];
      if (next === before && !missing.includes(field.key)) return [];
      const schema = fieldSchema(rootSchema, field.key);
      const value = field.kind === 'list' ? String(next).split('\n').map((item) => item.trim()).filter(Boolean) : ['integer', 'number'].includes(schemaType(schema) ?? '') ? Number(next) : next;
      return [[field.key, value]];
    }));
    if (!Object.keys(changes).length) {
      setEditing(false);
      return;
    }
    setAwaitingRevision(proposal.revision);
    if (await onPatch(proposal, changes)) setEditing(false);
    else setAwaitingRevision(null);
  };
  const confirmReady = canConfirmCanonicalProposal(editing, awaitingRevision, missing.length);
  return <section className="argus-inline-card argus-proposal-card" data-proposal-id={proposal.proposal_id} data-proposal-status={proposal.status}>
    <header><span>{t.proposal}</span><h3>{commandTitle(proposal.title_key, locale)}</h3><p>{t.proposedOnly}</p></header>
    {editing ? <form className="argus-card-form" onSubmit={submit}>{fields.map((field) => <FieldEditor field={field} rootSchema={rootSchema} locale={locale} value={drafts[field.key] ?? ''} missing={missing.includes(field.key)} onChange={(value) => setDrafts((current) => ({ ...current, [field.key]: value }))} key={field.key} />)}<div className="argus-card-actions"><button type="button" className="p-button-ghost" disabled={busy} onClick={() => setEditing(false)}>{t.cancelEdit}</button><button className="p-button-secondary" disabled={busy}>{busy ? t.updating : t.saveEdits}</button></div></form> : <dl className="argus-command-fields">{proposal.fields.map((field) => <div key={field.key}><dt>{commandFieldLabel(field.key, locale)}</dt><dd><CommandValue field={field} locale={locale} /></dd></div>)}</dl>}
    {missing.length && !editing ? <div className="argus-card-error" role="status"><p>{missing.map((field) => commandFieldLabel(field, locale)).join(', ')}: {t.fieldMissing}</p></div> : null}
    {paperOnly ? <p className="argus-simulation-notice">{t.paperOnly}</p> : null}
    <CurrencyLines proposal={proposal} locale={locale} />
    {proposal.evidence.map((evidence) => <EvidenceLine evidence={evidence} locale={locale} key={evidence.id} />)}
    <p className="argus-card-note">{expired ? t.expired : `${locale === 'en' ? 'Expires' : 'Vence'}: ${dateLabel(proposal.expires_at, locale, true)}`}</p>
    {active && !editing ? <div className="argus-card-actions"><button className="p-button-ghost" type="button" disabled={busy || awaitingRevision !== null} onClick={() => onCancel(proposal)}><X size={16} />{busy ? t.cancelling : t.cancelProposal}</button><button className="p-button-secondary" type="button" disabled={busy || awaitingRevision !== null} onClick={() => setEditing(true)}><Pencil size={16} />{t.edit}</button>{awaitingRevision === null ? <button className="p-button" type="button" disabled={busy || !confirmReady} onClick={() => onConfirm(proposal)}><Check size={16} />{busy ? t.confirming : t.confirm}</button> : <span className="p-badge" role="status">{t.updating}</span>}</div> : !active ? <span className="p-badge">{proposal.status === 'consumed' ? t.receipt : proposal.status === 'cancelled' ? t.cancelProposal : proposal.status}</span> : null}
    {proposal.target.record_id ? <button className="argus-card-link" type="button" onClick={() => openTarget(proposal.target, onNavigate)}>{t.openRecord}<ExternalLink size={14} /></button> : null}
  </section>;
}

function ReceiptCard({ receipt, locale, onNavigate }: { receipt: CommandReceipt; locale: Locale; onNavigate: Navigate }) {
  const t = copy(locale);
  const paperOnly = receipt.fields.some((field) => field.key === 'execution.scope' && field.value === 'scheduled_paper');
  return <section className="argus-inline-card argus-receipt-card" data-receipt-id={receipt.receipt_id}>
    <header><span><Check size={15} />{t.receipt}</span><h3>{commandTitle(receipt.title_key, locale)}</h3><p>{t.receiptDetail}</p></header>
    <dl className="argus-command-fields">{receipt.fields.map((field) => <div key={field.key}><dt>{commandFieldLabel(field.key, locale)}</dt><dd><CommandValue field={field} locale={locale} /></dd></div>)}</dl>
    {paperOnly ? <p className="argus-simulation-notice">{t.paperOnly}</p> : null}
    {receipt.evidence.map((evidence) => <EvidenceLine evidence={evidence} locale={locale} key={evidence.id} />)}
    <p className="argus-card-note">{t.savedAt}: {dateLabel(receipt.created_at, locale, true)}</p>
    <button className="argus-card-link" type="button" onClick={() => openTarget({ ...receipt.target, record_id: receipt.record_id }, onNavigate)}>{t.openArtifact}<ExternalLink size={14} /></button>
  </section>;
}

export function ChatCardView({ card, locale, commands, calculations, busy, onPatch, onConfirm, onCancel, onRecompute, onNavigate }: {
  card: ChatCard;
  locale: Locale;
  commands: CommandDeclaration[];
  calculations: CalculationDeclaration[];
  busy: boolean;
  onPatch: (proposal: Proposal, changes: Record<string, string | number | boolean | string[]>) => Promise<boolean>;
  onConfirm: (proposal: Proposal) => void;
  onCancel: (proposal: Proposal) => void;
  onRecompute: (action: PreparedAction) => void;
  onNavigate: Navigate;
}) {
  if (card.kind === 'read') return <ReadCard card={card} locale={locale} onNavigate={onNavigate} />;
  if (card.kind === 'records') return <RecordsCard card={card} locale={locale} busy={busy} onNavigate={onNavigate} onPage={onRecompute} />;
  if (card.kind === 'calculation') return <CalculationCard card={card.card} evidence={card.evidence} declaration={calculations.find((item) => item.name === card.card.tool_name)} locale={locale} busy={busy} onRecompute={onRecompute} />;
  if (card.kind === 'proposal') return <ProposalCard proposal={card.proposal} declaration={commands.find((item) => item.name === card.proposal.command_name)} locale={locale} busy={busy} onPatch={onPatch} onConfirm={onConfirm} onCancel={onCancel} onNavigate={onNavigate} />;
  return <ReceiptCard receipt={card.receipt} locale={locale} onNavigate={onNavigate} />;
}
