import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';

const bundled = await build({ entryPoints: [new URL('./drafts.ts', import.meta.url).pathname], bundle: true, write: false, platform: 'node', format: 'esm' });
const drafts = await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString('base64')}`);

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
    clear: () => values.clear(),
  };
}

globalThis.sessionStorage = storage();

test.beforeEach(() => sessionStorage.clear());

test('opaque drafts are isolated by user, household, and data generation scope', () => {
  const firstScope = 'user-a:household-a:7';
  const id = drafts.stageChatDraft(firstScope, 'private question');

  assert.match(id, /^[0-9a-f-]{36}$/);
  assert.equal(drafts.readChatDraft(firstScope, id)?.text, 'private question');
  assert.equal(drafts.readChatDraft('user-b:household-a:7', id), null);
  assert.equal(drafts.readChatDraft('user-a:household-b:7', id), null);
  assert.equal(drafts.readChatDraft('user-a:household-a:8', id), null);
});

test('rejected delivery preserves one submitted turn and accepted delivery clears it', () => {
  const scope = 'user-a:household-a:7';
  const id = drafts.stageChatDraft(scope, 'review my records');
  const submitted = drafts.markChatDraftSubmitted(scope, id);

  assert.equal(submitted?.status, 'submitted');
  assert.ok(submitted?.turn_id);
  assert.deepEqual(drafts.readChatDraft(scope, id), submitted);
  assert.equal(drafts.markChatDraftSubmitted(scope, id), null, 'a remount cannot submit the handoff twice');

  drafts.clearChatDraft(scope, id);
  assert.equal(drafts.readChatDraft(scope, id), null);
});

test('retry replays the original turn only for unchanged user text', () => {
  const scope = 'user-a:household-a:7';
  const id = drafts.stageChatDraft(scope, 'same request');
  const submitted = drafts.markChatDraftSubmitted(scope, id);

  assert.equal(drafts.stagedChatTurnId(scope, id, 'same request'), submitted?.turn_id);
  assert.equal(drafts.stagedChatTurnId(scope, id, 'edited request'), null);
  assert.equal(drafts.stagedChatTurnId('user-a:household-a:8', id, 'same request'), null);
});

test('an edit before delivery survives reload and an edit after delivery cannot reuse the old turn', () => {
  const scope = 'user-a:household-a:7';
  const id = drafts.stageChatDraft(scope, 'original');
  drafts.updateChatDraftText(scope, id, 'original amended');
  assert.equal(drafts.readChatDraft(scope, id)?.text, 'original amended');

  const submitted = drafts.markChatDraftSubmitted(scope, id);
  assert.ok(submitted?.turn_id);
  drafts.updateChatDraftText(scope, id, 'different request');
  assert.equal(drafts.readChatDraft(scope, id)?.text, 'different request');
  assert.equal(drafts.stagedChatTurnId(scope, id, 'different request'), null);
});
