import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';

const bundled = await build({ entryPoints: [new URL('./composer-draft.ts', import.meta.url).pathname], bundle: true, write: false, platform: 'node', format: 'esm' });
const draft = await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString('base64')}`);

const account = { id: 'account-1', type: 'account', label: 'Checking', insert_text: '@Checking', description: 'USD checking' };

for (const [name, segments, delivered] of [
  ['trailing whitespace', [{ type: 'text', text: 'ask about spending  ' }], 'ask about spending'],
  ['multiline', [{ type: 'text', text: 'first line\nsecond line' }], 'first line\nsecond line'],
  ['account mention', [{ type: 'text', text: 'Review ' }, { type: 'token', token: account }], 'Review @Checking'],
]) {
  test(`accepted ${name} draft acknowledges the serialized submission`, () => {
    const current = draft.recordComposerDraft(draft.createComposerDraft(''), segments);
    assert.equal(current.snapshot.text, delivered);
    const acknowledged = draft.acknowledgeComposerDraft(current, current.snapshot);
    assert.equal(acknowledged?.snapshot.text, '');
  });
}

test('a later edit survives an older accepted retry even when its text normalizes identically', () => {
  const original = draft.recordComposerDraft(draft.createComposerDraft(''), [{ type: 'text', text: 'Review Checking' }]);
  const submitted = original.snapshot;
  const newer = draft.recordComposerDraft(original, [{ type: 'text', text: 'Review Checking  ' }]);
  assert.equal(newer.snapshot.text, submitted.text);
  assert.notEqual(newer.snapshot.editId, submitted.editId);
  assert.equal(draft.acknowledgeComposerDraft(newer, submitted), null);
});
