import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';

const bundled = await build({ entryPoints: [new URL('./stream.ts', import.meta.url).pathname], bundle: true, write: false, platform: 'node', format: 'esm' });
const { turnCurrencyContext } = await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString('base64')}`);

test('free text and generic prepared reads carry a default hint without claiming an explicit denomination', () => {
  assert.deepEqual(turnCurrencyContext('DOP'), { default_currency: 'DOP' });
  assert.deepEqual(turnCurrencyContext('USD', { kind: 'read', action: 'net_worth', parameters: {} }), { default_currency: 'USD' });
  assert.deepEqual(turnCurrencyContext('EUR', { kind: 'calculation', tool_name: 'effective_rate', arguments: { nominal_rate_pct: 8 } }), { default_currency: 'EUR' });
});

test('typed action currency stays explicit while the view currency remains only a default', () => {
  assert.deepEqual(turnCurrencyContext('USD', { kind: 'proposal', command_name: 'goal.create', arguments: { currency: 'DOP', name: 'Sample' } }), { default_currency: 'USD', currency: 'DOP' });
  assert.deepEqual(turnCurrencyContext('DOP', { kind: 'records', resource: 'transactions', currency: 'USD' }), { default_currency: 'DOP', currency: 'USD' });
  assert.deepEqual(turnCurrencyContext('DOP', { kind: 'revise_proposal', proposal_id: 'p1', revision: 1, changes: { currency: 'EUR' } }), { default_currency: 'DOP', currency: 'EUR' });
});
