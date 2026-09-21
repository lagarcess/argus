import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from './api';
import type {
  ComparisonResult,
  Confirmation,
  Example,
  Home,
  Locale,
  Notice,
  PlacementInputs,
  SavedDecision,
  Scenario,
} from './contracts';
export type Conversation =
  | { stage: 'start' }
  | { stage: 'confirmation'; message: string; confirmation: Confirmation }
  | { stage: 'result'; message: string; result: ComparisonResult };
export type SavedView = { decision: SavedDecision; notice: Notice | null };

export function useMoneyView(locale: Locale) {
  const [home, setHome] = useState<Home | null>(null);
  const [homeError, setHomeError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conversation, setConversation] = useState<Conversation>({ stage: 'start' });
  const [pending, setPending] = useState<
    'interpret' | 'compute' | 'save' | 'open' | 'simulate' | null
  >(null);
  const [savedView, setSavedView] = useState<SavedView | null>(null);
  const [pendingLoad, setPendingLoad] = useState<{load_id: string; job_id: string} | null>(null);
  const [page, setPage] = useState<'money' | 'saved'>('money');
  const [draft, setDraft] = useState('');
  const [exampleId, setExampleId] = useState<string | undefined>();
  const code = (failure: unknown) =>
    failure instanceof ApiError ? failure.code : 'request_failed';
  const refresh = useCallback(async () => {
    try {
      const data = await api.home();
      setHome(data);
      setHomeError(null);
      return data;
    } catch (failure) {
      setHomeError(code(failure));
      return null;
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    if (!pendingLoad && home?.source_status.state !== 'loading') return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (pendingLoad) {
        try {
          const job = await api.job(pendingLoad.job_id);
          if (disposed) return;
          if (job.status === 'failed') {
            setPendingLoad(null);
            setError(job.error_code ?? 'request_failed');
            await refresh();
            return;
          }
          if (job.status === 'queued' || job.status === 'running') {
            timer = setTimeout(() => {void poll();}, 800);
            return;
          }
        } catch (failure) {
          if (disposed) return;
          setPendingLoad(null);
          setError(code(failure));
          return;
        }
      }
      const next = await refresh();
      if (disposed) return;
      if (next && next.source_status.state !== 'loading') {
        setPendingLoad(null);
        if (savedView) {
          try {
            const decision = await api.decision(savedView.decision.id);
            if (!disposed)
              setSavedView((current) =>
                current?.decision.id === decision.id ? { ...current, decision } : current,
              );
          } catch (failure) {
            if (!disposed) setError(code(failure));
          }
        }
      } else
        timer = setTimeout(() => {
          void poll();
        }, 800);
    };
    timer = setTimeout(() => {
      void poll();
    }, 500);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [pendingLoad, home?.source_status.state, refresh, savedView?.decision.id]);
  useEffect(() => {
    if (!exampleId) return;
    const selected = home?.examples.find((example) => example.id === exampleId);
    if (selected) setDraft(selected.messages[locale]);
  }, [locale, exampleId, home?.examples]);
  function chooseExample(example: Example) {
    setDraft(example.messages[locale]);
    setExampleId(example.id);
    setError(null);
    setPage('money');
  }
  function editDraft(value: string) {
    setDraft(value);
    setExampleId(undefined);
  }
  async function send() {
    if (!draft.trim() || pending) return;
    setPending('interpret');
    setError(null);
    try {
      const response = await api.interpret(draft, locale, exampleId);
      if (response.status === 'confirmation') {
        setConversation({
          stage: 'confirmation',
          message: draft,
          confirmation: response.confirmation,
        });
        setDraft('');
        setExampleId(undefined);
        setPage('money');
      } else
        setError(
          response.status === 'needs_input'
            ? 'missing_inputs'
            : response.status === 'unsupported'
              ? 'unsupported'
              : (response.code ?? 'model_unavailable'),
        );
    } catch (failure) {
      setError(code(failure));
    } finally {
      setPending(null);
    }
  }
  async function prepare(inputs: PlacementInputs) {
    if (pending) return;
    setPending('interpret');
    setError(null);
    try {
      const confirmation = await api.prepare(inputs);
      setConversation({ stage: 'confirmation', message: '', confirmation });
      setPage('money');
    } catch (failure) {
      setError(code(failure));
    } finally {
      setPending(null);
    }
  }
  function editConfirmation(inputs: PlacementInputs) {
    if (pending) return;
    setConversation((current) =>
      current.stage === 'confirmation'
        ? { ...current, confirmation: { ...current.confirmation, inputs } }
        : current,
    );
  }
  async function compute() {
    if (conversation.stage !== 'confirmation' || pending) return;
    setPending('compute');
    setError(null);
    try {
      const result = await api.compute(
        conversation.confirmation.id,
        conversation.confirmation.inputs,
      );
      setConversation({ stage: 'result', result, message: conversation.message });
    } catch (failure) {
      setError(code(failure));
    } finally {
      setPending(null);
    }
  }
  async function save() {
    if (conversation.stage !== 'result' || pending) return;
    setPending('save');
    setError(null);
    try {
      await api.save(conversation.result.id);
      await refresh();
    } catch (failure) {
      setError(code(failure));
    } finally {
      setPending(null);
    }
  }
  async function openDecision(id: string, notice: Notice | null = null) {
    if (pending) return;
    setPending('open');
    setError(null);
    try {
      const decision = await api.decision(id);
      setSavedView({ decision, notice });
      setPage('saved');
      if (notice) {
        await api.readNotice(notice.id);
        await refresh();
      }
    } catch (failure) {
      setError(code(failure));
    } finally {
      setPending(null);
    }
  }
  async function simulate(scenario: Scenario) {
    if (pending || pendingLoad) return;
    setPending('simulate');
    setError(null);
    try {
      const response = await api.simulate(scenario);
      setPendingLoad(response);
    } catch (failure) {
      setError(code(failure));
    } finally {
      setPending(null);
    }
  }
  return {
    home,
    homeError,
    error,
    conversation,
    pending,
    page,
    setPage,
    draft,
    chooseExample,
    editDraft,
    send,
    prepare,
    restart: () => { setConversation({ stage: 'start' }); setError(null); },
    compute,
    editConfirmation,
    save,
    savedView,
    setSavedView,
    openDecision,
    simulate,
    refresh,
    loadingSources: pendingLoad !== null || home?.source_status.state === 'loading',
  };
}
