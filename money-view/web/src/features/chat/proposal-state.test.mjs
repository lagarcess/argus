import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';

const bundled = await build({ entryPoints: [new URL('./proposal-state.ts', import.meta.url).pathname], bundle: true, write: false, platform: 'node', format: 'esm' });
const { canConfirmCanonicalProposal } = await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString('base64')}`);

test('confirmation is available only for the reviewed canonical proposal revision', () => {
  assert.equal(canConfirmCanonicalProposal(false, null, 0), true);
  assert.equal(canConfirmCanonicalProposal(true, null, 0), false, 'unsaved edits cannot confirm the prior revision');
  assert.equal(canConfirmCanonicalProposal(false, 4, 0), false, 'a saved edit must hydrate its revised canonical proposal first');
  assert.equal(canConfirmCanonicalProposal(false, null, 1), false, 'required fields remain a confirmation gate');
});
