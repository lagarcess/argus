import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowLeft, ArrowRight, Bookmark, ChevronRight, FileText, Loader2, Search, MessageCircle, Landmark, ArrowLeftRight, Target, Wallet, ChartNoAxesCombined } from 'lucide-react';
import { request } from '../../platform/client';
import { Modal, EvidenceLine } from '../../platform/ui';
import type { Locale, PlatformPageProps } from '../../platform/types';
import { copy } from './copy';
import { categoryLabel } from '../ledger/copy';
import { scenarioTemplateLabel } from '../planning/copy';
import { scenarioTemplateIdSchema } from '../planning/contracts';
import { kinds, searchSchema, selectionIndex, targetQuery, type SearchItem, type SearchKind, type SearchScope } from './contracts';
import { useResponsiveLayout } from '../../argus/useResponsiveLayout';
import './search.css';
const icons = { all: Search, conversation: MessageCircle, account: Landmark, transaction: ArrowLeftRight, budget: Wallet, goal: Target, scenario: ChartNoAxesCombined, holding: ChartNoAxesCombined, deposit: FileText };
export interface OmnisearchProps {
    locale: Locale;
    onClose: () => void;
    onNavigate: PlatformPageProps['onNavigate'];
    onAsk: (text: string) => void;
    revision: number;
}
function displayDate(value: string, locale: Locale) {
    const parsed = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
    return Number.isNaN(parsed.valueOf()) ? value : new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(parsed);
}
// Presentation adapted from Argus ChatCommandPalette, paletteLayout and its
// dossier sheet: a 56/44 split on wide screens and one active panel on mobile.
export function Omnisearch({ locale, onClose, onNavigate, onAsk, revision }: OmnisearchProps) {
    const t = copy[locale];
    function valueLabel(label: string, value: string) {
        if (['category','account_kind','status'].includes(label)) return categoryLabel(value,locale);
        if (label==='template') {
            const template=scenarioTemplateIdSchema.safeParse(value);
            if(template.success)return scenarioTemplateLabel(template.data,locale);
        }
        return value;
    }
    function titleLabel(item:SearchItem) {return item.kind==='budget'?categoryLabel(item.title,locale):item.title;}
    function previewLabel(item:SearchItem) {return item.kind==='scenario'?valueLabel('template',item.preview):item.preview;}

    const inputRef = useRef<HTMLInputElement>(null);
    const backRef = useRef<HTMLButtonElement>(null);
    const listId = useId();
    const requestId = useRef(0);
    const [query, setQuery] = useState('');
    const [kind, setKind] = useState<SearchKind>('all');
    const [scope, setScope] = useState<SearchScope>('all');
    const [items, setItems] = useState<SearchItem[]>([]);
    const [selected, setSelected] = useState(0);
    const [nextOffset, setNextOffset] = useState<number | null>(null);
    const [windowLimited, setWindowLimited] = useState(false);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [retry, setRetry] = useState(0);
    const [mobilePreview, setMobilePreview] = useState(false);
    const { isBelowDesktop: mobile, isBelowTablet: narrow } = useResponsiveLayout();
    const preview = items[selected];
    useEffect(() => {
        const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
        return () => window.clearTimeout(timer);
    }, []);
    useEffect(() => { if (mobilePreview)
        backRef.current?.focus(); }, [mobilePreview]);
    useEffect(() => { if (!mobile && mobilePreview) {
        setMobilePreview(false);
        inputRef.current?.focus();
    } }, [mobile, mobilePreview]);
    useEffect(() => { setOffset(0); setItems([]); setMobilePreview(false); }, [revision]);
    useEffect(() => {
        const sequence = ++requestId.current;
        const controller = new AbortController();
        setLoading(true);
        setError(false);
        if (offset === 0) {
            setItems([]);
            setNextOffset(null);
            setSelected(0);
        }
        const timer = window.setTimeout(() => {
            const params = new URLSearchParams({ q: query.trim(), kind, scope, limit: '20', offset: String(offset) });
            request(`/search?${params}`, searchSchema, { signal: controller.signal }).then(result => {
                if (sequence !== requestId.current)
                    return;
                setItems(previous => offset === 0 ? result.items : [...previous, ...result.items.filter(item => !previous.some(old => old.id === item.id))]);
                if (offset === 0 && result.items.length) {
                    const firstKind = kinds.find(value => result.items.some(item => item.kind === value));
                    setSelected(result.items.findIndex(item => item.kind === firstKind));
                }
                setNextOffset(result.next_offset);
                setWindowLimited(result.window_limited);
                setLoading(false);
            }).catch(() => { if (sequence === requestId.current && !controller.signal.aborted) {
                setError(true);
                setLoading(false);
            } });
        }, query ? 200 : 0);
        return () => { window.clearTimeout(timer); controller.abort(); };
    }, [query, kind, scope, offset, retry, revision]);
    useEffect(() => { document.getElementById(`${listId}-${selected}`)?.scrollIntoView({ block: 'nearest' }); }, [selected, listId]);
    function reset() { setOffset(0); setMobilePreview(false); setSelected(0); }
    function open(item: SearchItem) { onNavigate(item.target.page, targetQuery(item.target)); onClose(); }
    function activate(item: SearchItem, index: number) {
        setSelected(index);
        if (mobile)
            setMobilePreview(true);
        else
            open(item);
    }
    function back() { setMobilePreview(false); window.setTimeout(() => inputRef.current?.focus(), 0); }
    function keyDown(event: KeyboardEvent<HTMLDivElement>) {
        if (event.key === 'Escape' && mobilePreview) {
            event.preventDefault();
            event.stopPropagation();
            back();
            return;
        }
        if (event.target !== inputRef.current)
            return;
        if (event.key === 'Enter' && preview && !loading && !error) {
            event.preventDefault();
            activate(preview, selected);
        }
    }
    const grouped = kinds.filter(value => value !== 'all').map(value => ({ kind: value, items: items.map((item, index) => ({ item, index })).filter(row => row.item.kind === value) })).filter(group => group.items.length);
    // Keyboard order follows the same grouped order the person sees.
    const displayed = grouped.flatMap(group => group.items.map(row => row.item));
    const selectedId = preview?.id;
    function groupKeys(event: KeyboardEvent<HTMLInputElement>) {
        if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) || !displayed.length)
            return;
        if ((event.key === 'Home' || event.key === 'End') && !event.ctrlKey && !event.metaKey)
            return;
        event.preventDefault();
        event.stopPropagation();
        const current = displayed.findIndex(item => item.id === selectedId);
        const item = displayed[selectionIndex(current, event.key, displayed.length)];
        setSelected(items.findIndex(value => value.id === item.id));
    }
    return <Modal title={t.title} onClose={onClose} variant="search" footer={!narrow && <div className="omni-footer"><span><kbd>↑</kbd><kbd>↓</kbd> {t.move}</span><span><kbd>↵</kbd> {t.enter}</span><span><kbd>Esc</kbd> {t.escape}</span></div>}>
    <div className={`omni ${mobilePreview ? 'omni-preview-active' : ''}`} onKeyDown={keyDown}>
      <div className="omni-search-area">
        <div className="omni-input-row"><Search size={22}/><input ref={inputRef} value={query} maxLength={120} placeholder={t.placeholder} aria-label={t.title} role="combobox" aria-autocomplete="list" aria-expanded={!mobilePreview} aria-controls={listId} aria-activedescendant={preview && !mobilePreview ? `${listId}-${selected}` : undefined} onKeyDown={groupKeys} onChange={event => { reset(); setQuery(event.target.value); }}/>{loading && <Loader2 size={18} className="omni-spinner" aria-hidden/>}</div>
        <div className="omni-filters"><label><span>{t.filterType}</span><select aria-label={t.searchWithin} value={kind} onChange={event => { reset(); setKind(event.target.value as SearchKind); setScope('all'); }}>{kinds.map(value => <option key={value} value={value}>{value === 'deposit' ? t.depositFilter : t[value]}</option>)}</select></label><label><span>{t.scope}</span><select value={scope} onChange={event => { reset(); setScope(event.target.value as SearchScope); if (event.target.value !== 'all')
        setKind('conversation'); }}><option value="all">{t.scopeAll}</option><option value="recent">{t.scopeRecent}</option><option value="pinned">{t.scopePinned}</option></select></label></div>
      </div>
      <div className="omni-panes">
        <section className="omni-results" aria-label={t.results}>
          <div className="omni-status" role="status" aria-live="polite">{loading ? t.loading : !error && items.length ? `${items.length} ${t.results}` : ''}</div>
          {error && <div className="omni-state" role="alert"><h3>{t.error}</h3><p>{t.errorHint}</p><button className="p-button secondary" onClick={() => setRetry(value => value + 1)}>{t.retry}</button></div>}
          {!loading && !error && !items.length && <div className="omni-state"><Search size={28}/><h3>{windowLimited ? t.windowEmpty : query ? t.empty : t.noRecent}</h3><p>{windowLimited ? t.windowLimited : query ? t.emptyHint : t.noRecentHint}</p></div>}
          <div id={listId} role="listbox" aria-label={t.results} aria-busy={loading}>
            {grouped.map(group => <div role="group" aria-label={t[group.kind]} key={group.kind}><h3 className="omni-group-label">{t[group.kind]}</h3>{group.items.map(({ item, index }) => { const Icon = icons[item.kind]; return <div key={item.id} id={`${listId}-${index}`} role="option" aria-selected={selected === index} className={`omni-row ${selected === index ? 'is-selected' : ''}`} onMouseEnter={() => !mobile && setSelected(index)} onClick={() => activate(item, index)}><span className="omni-row-icon"><Icon size={19}/></span><span className="omni-row-text"><strong>{titleLabel(item)}</strong><span>{previewLabel(item) || t[item.kind]}</span></span><span className="omni-row-meta">{item.pinned && <Bookmark size={13} aria-label={t.pinnedLabel}/>}<small>{item.as_of ? displayDate(item.as_of, locale) : ''}</small><ChevronRight size={14}/></span></div>; })}</div>)}
          </div>
          {nextOffset !== null && !error && <button className="omni-more" disabled={loading} onClick={() => setOffset(nextOffset)}>{t.more}</button>}
          {!!query.trim() && <button className="omni-ask" onClick={() => { onAsk(query.trim()); onClose(); }}><MessageCircle size={20}/><span><strong>{t.ask}: “{query.trim()}”</strong><small>{t.askHint}</small></span><ArrowRight size={17}/></button>}
          {windowLimited && !!items.length && <p className="omni-window">{t.windowLimited}</p>}
          {(kind === 'deposit' || kind === 'all') && <p className="omni-window">{t.depositWindow}</p>}
        </section>
        <aside className="omni-dossier" aria-label={t.preview}>
          {mobilePreview && <button ref={backRef} className="omni-back" onClick={back}><ArrowLeft size={17}/>{t.back}</button>}
          {preview ? <><p className="omni-group-label">{t[preview.kind]}</p><h2>{titleLabel(preview)}</h2>{preview.preview && <p className="omni-preview-text">{previewLabel(preview)}</p>}<dl className="omni-details">{preview.fields.map(field => <div key={field.label}><dt>{t.fields[field.label as keyof typeof t.fields] ?? field.label}</dt><dd>{valueLabel(field.label,field.value)}</dd></div>)}{preview.as_of && <div><dt>{t.asOf}</dt><dd>{displayDate(preview.as_of, locale)}</dd></div>}{preview.recorded_at && <div><dt>{t.recorded}</dt><dd>{displayDate(preview.recorded_at, locale)}</dd></div>}</dl>{preview.evidence && <EvidenceLine evidence={preview.evidence} locale={locale}/>}<button className="p-button omni-open" onClick={() => open(preview)}>{t.open}<ArrowRight size={17}/></button></> : <div className="omni-state"><FileText size={28}/><h3>{t.select}</h3><p>{t.selectHint}</p></div>}
        </aside>
      </div>
    </div>
  </Modal>;
}
export default Omnisearch;
