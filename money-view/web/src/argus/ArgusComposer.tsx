import {
  useEffect,
  forwardRef,
  useImperativeHandle,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ArrowUp, AtSign, Paperclip } from "lucide-react";
import type { Locale } from "../platform/types";
import type { Mention } from "./types";
import {
  composerMentions,
  deleteTokenBeforeOffset,
  findMentionAtOffset,
  isComposerEmpty,
  rawComposerText,
  replaceRangeWithToken,
  serializeComposerSegments,
  type ComposerSegment,
} from "./composer-model";
import {
  clearComposerTokenFocus,
  getCaretTextOffset,
  readSegmentsFromEditor,
  setCaretTextOffset,
  syncComposerTokenFocus,
  writeSegmentsToEditor,
} from "./composer-dom";
import { acknowledgeComposerDraft, createComposerDraft, recordComposerDraft, type ComposerDraftSnapshot } from './composer-draft';
import "./composer.css";
export type { Mention } from "./types";
export type { ComposerDraftSnapshot } from './composer-draft';

export type ArgusComposerProps = {
  locale: Locale;
  onSend: (
    text: string,
    mentions?: Mention[],
    draft?: ComposerDraftSnapshot,
  ) => void | boolean | Promise<void | boolean>;
  onDraftChange?: (draft: ComposerDraftSnapshot) => void;
  disabled?: boolean;
  placeholder?: string;
  onAttach?: () => void;
  context?: ReactNode;
  onToast?: (message: string) => void;
  initialText?: string;
  discover?: (query: string, signal: AbortSignal) => Promise<Mention[]>;
};

export type ArgusComposerHandle = {
  snapshot: () => ComposerDraftSnapshot;
  acknowledge: (draft: ComposerDraftSnapshot) => boolean;
};

// ChatInput's segment model, DOM/caret handling and send acceptance are retained.
// Session, discovery and financial meaning belong to the caller.
export const ArgusComposer = forwardRef<ArgusComposerHandle, ArgusComposerProps>(function ArgusComposer({
  locale,
  onSend,
  disabled = false,
  placeholder,
  onAttach,
  context,
  onToast,
  initialText = "",
  discover,
  onDraftChange,
}, ref) {
  const en = locale === "en";
  const label =
    placeholder ??
    (en
      ? "Ask about your money"
      : "Pregunta sobre tu dinero");
  const [segments, setSegments] = useState<ComposerSegment[]>([
    { type: "text", text: initialText },
  ]);
  const [hasContent, setHasContent] = useState(Boolean(initialText.trim()));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState<string | null>(null);
  const [items, setItems] = useState<Mention[]>([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const editor = useRef<HTMLDivElement>(null);
  const caret = useRef<number | null>(null);
  const sending = useRef(false);
  const mounted = useRef(true);
  const draft = useRef(createComposerDraft(initialText));
  const onDraftChangeRef = useRef(onDraftChange);
  onDraftChangeRef.current = onDraftChange;
  const publish = (current: ComposerSegment[]) => {
    const next = recordComposerDraft(draft.current, current);
    if (next !== draft.current) {
      draft.current = next;
      onDraftChangeRef.current?.(next.snapshot);
    }
    return draft.current.snapshot;
  };
  const acknowledge = (submitted: ComposerDraftSnapshot) => {
    const next = acknowledgeComposerDraft(draft.current, submitted);
    if (!next) return false;
    draft.current = next;
    setSegments(next.segments);
    setHasContent(false);
    setQuery(null);
    onDraftChangeRef.current?.(next.snapshot);
    return true;
  };
  useImperativeHandle(ref, () => ({ snapshot: () => draft.current.snapshot, acknowledge }));
  const listId = useId();
  const locked = disabled || pending;
  useEffect(() => {
    mounted.current = true;
    onDraftChangeRef.current?.(draft.current.snapshot);
    return () => {
      mounted.current = false;
    };
  }, []);
  useLayoutEffect(() => {
    writeSegmentsToEditor(editor.current, segments);
    setHasContent(!isComposerEmpty(segments));
    if (caret.current !== null) {
      setCaretTextOffset(editor.current, caret.current);
      caret.current = null;
    }
    syncComposerTokenFocus(editor.current, segments);
  }, [segments]);
  useEffect(() => {
    if (query === null || !discover) return;
    const controller = new AbortController();
    setItems([]);
    setLoading(true);
    setActive(0);
    const timer = setTimeout(() => {
      discover(query.trim(), controller.signal)
        .then((result) => {
          if (!controller.signal.aborted) setItems(result);
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setError(
              en
                ? "References could not be loaded."
                : "No se pudieron cargar las referencias.",
            );
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 180);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query, discover, en]);
  const sync = () => {
    const current = readSegmentsFromEditor(editor.current);
    publish(current);
    setHasContent(!isComposerEmpty(current));
    if (discover)
      setQuery(
        findMentionAtOffset(
          current,
          getCaretTextOffset(editor.current) ?? rawComposerText(current).length,
        )?.query ?? null,
      );
    syncComposerTokenFocus(editor.current, current);
  };
  const submit = async () => {
    if (locked || sending.current) return;
    const current = readSegmentsFromEditor(editor.current);
    const text = serializeComposerSegments(current);
    if (!text) return;
    const submitted = publish(current);
    sending.current = true;
    setPending(true);
    setError("");
    try {
      const accepted = await onSend(text, composerMentions(current, text), submitted);
      if (mounted.current && accepted !== false) {
        acknowledge(submitted);
      }
    } catch {
      if (mounted.current)
        setError(
          en
            ? "Your message was not sent. Try again."
            : "Tu mensaje no se envió. Inténtalo de nuevo.",
        );
    } finally {
      sending.current = false;
      if (mounted.current) setPending(false);
    }
  };
  const insert = (item: Mention) => {
    const current = readSegmentsFromEditor(editor.current);
    const offset =
      getCaretTextOffset(editor.current) ?? rawComposerText(current).length;
    const range = findMentionAtOffset(current, offset) ?? {
      start: offset,
      end: offset,
    };
    const next = replaceRangeWithToken(current, range, item);
    publish(next);
    caret.current = range.start + item.insert_text.length + 1;
    setSegments(next);
    setQuery(null);
  };
  const transfer = (data: DataTransfer) => {
    const text = data.getData("text/plain") || data.getData("text/uri-list");
    if (data.files.length || (!text && data.types.length)) {
      const message = en
        ? "Use the attachment button to import a statement."
        : "Usa el botón de adjuntar para importar un estado de cuenta.";
      setError(message);
      onToast?.(message);
    }
    if (text && !locked) {
      editor.current?.focus();
      document.execCommand("insertText", false, text);
      sync();
    }
  };
  return (
    <div className="argus-composer-wrap">
      {context && <div className="argus-composer-context">{context}</div>}
      <form
        className="argus-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
        onClick={() => editor.current?.focus()}
      >
        {query !== null && discover && (
          <div
            className="argus-discovery"
            id={listId}
            role="listbox"
            aria-label={en ? "References" : "Referencias"}
            aria-busy={loading}
          >
            <div className="argus-discovery-heading">
              {en ? "Your records" : "Tus registros"}
            </div>
            {loading ? (
              <p role="status">{en ? "Searching…" : "Buscando…"}</p>
            ) : items.length ? (
              items.map((item, index) => (
                <button
                  type="button"
                  role="option"
                  id={`${listId}-${index}`}
                  aria-selected={index === active}
                  key={`${item.type}:${item.id}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActive(index)}
                  onClick={(event) => {
                    event.stopPropagation();
                    insert(item);
                  }}
                >
                  <span>
                    {item.label}
                    <small>{item.description}</small>
                  </span>
                </button>
              ))
            ) : (
              <p>
                {en ? "No matching records" : "No hay registros coincidentes"}
              </p>
            )}
          </div>
        )}
        {onAttach && (
          <button
            className="argus-composer-attach"
            type="button"
            disabled={locked}
            aria-label={
              en ? "Import a statement" : "Importar un estado de cuenta"
            }
            onClick={(event) => {
              event.stopPropagation();
              onAttach();
            }}
          >
            <Paperclip size={19} />
          </button>
        )}
        {discover && (
          <button
            className="argus-composer-attach"
            type="button"
            disabled={locked}
            aria-label={en ? "Mention a record" : "Mencionar un registro"}
            onMouseDown={(event) => event.preventDefault()}
            onClick={(event) => {
              event.stopPropagation();
              editor.current?.focus();
              document.execCommand("insertText", false, "@");
              sync();
            }}
          >
            <AtSign size={19} />
          </button>
        )}
        <div
          className="argus-composer-editor"
          ref={editor}
          data-testid="chat-input"
          role={discover ? "combobox" : "textbox"}
          aria-multiline="true"
          aria-label={label}
          aria-disabled={locked}
          aria-expanded={discover ? query !== null : undefined}
          aria-controls={query !== null ? listId : undefined}
          aria-activedescendant={
            query !== null && items[active] ? `${listId}-${active}` : undefined
          }
          data-placeholder={label}
          data-empty={!hasContent}
          contentEditable={!locked}
          suppressContentEditableWarning
          onInput={sync}
          onSelect={sync}
          onFocus={sync}
          onBlur={() => clearComposerTokenFocus(editor.current)}
          onPaste={(event) => {
            event.preventDefault();
            transfer(event.clipboardData);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            transfer(event.dataTransfer);
          }}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing || event.keyCode === 229) return;
            if (query !== null) {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                setQuery(null);
                return;
              }
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                setActive((index) =>
                  items.length
                    ? (index +
                        (event.key === "ArrowDown" ? 1 : -1) +
                        items.length) %
                      items.length
                    : 0,
                );
                return;
              }
              if (event.key === "Enter" && !event.shiftKey && items[active]) {
                event.preventDefault();
                insert(items[active]);
                return;
              }
            }
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            } else if (
              event.key === "Backspace" &&
              window.getSelection()?.isCollapsed
            ) {
              const current = readSegmentsFromEditor(editor.current);
              const offset = getCaretTextOffset(editor.current);
              if (offset !== null) {
                const next = deleteTokenBeforeOffset(current, offset);
                if (next.segments !== current) {
                  event.preventDefault();
                  caret.current = next.offset;
                  publish(next.segments);
                  setSegments(next.segments);
                }
              }
            }
          }}
        />
        <button
          className="argus-composer-send"
          data-testid="chat-send"
          type="submit"
          disabled={locked || !hasContent}
          aria-label={en ? "Send message" : "Enviar mensaje"}
          title={
            !hasContent
              ? en
                ? "Write a message first"
                : "Escribe un mensaje primero"
              : undefined
          }
          onClick={(event) => event.stopPropagation()}
        >
          <ArrowUp size={21} strokeWidth={2.5} />
        </button>
      </form>
      {error && (
        <p className="argus-composer-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
});
