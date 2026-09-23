import { serializeComposerSegments, type ComposerSegment } from './composer-model';

export type ComposerDraftSnapshot = { text: string; editId: number };
export type ComposerDraftState = { segments: ComposerSegment[]; snapshot: ComposerDraftSnapshot };

export function createComposerDraft(text: string): ComposerDraftState {
  const segments: ComposerSegment[] = [{ type: 'text', text }];
  return { segments, snapshot: { text: serializeComposerSegments(segments), editId: 0 } };
}

export function recordComposerDraft(state: ComposerDraftState, segments: ComposerSegment[]): ComposerDraftState {
  if (JSON.stringify(state.segments) === JSON.stringify(segments)) return state;
  return { segments, snapshot: { text: serializeComposerSegments(segments), editId: state.snapshot.editId + 1 } };
}

export function acknowledgeComposerDraft(state: ComposerDraftState, submitted: ComposerDraftSnapshot): ComposerDraftState | null {
  if (state.snapshot.editId !== submitted.editId || state.snapshot.text !== submitted.text) return null;
  return recordComposerDraft(state, [{ type: 'text', text: '' }]);
}
