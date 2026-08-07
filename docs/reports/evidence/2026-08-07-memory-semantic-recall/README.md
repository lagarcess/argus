# Semantic memory recall: exact-head evidence

Lane: Mem0 semantic recall behind `MemoryProvider` (recall-loop spec item 2).
Captured against the local Supabase QA stack with real Perplexity embeddings
and a real OpenRouter runtime. Sanitized: no keys, no tokens, no emails, no raw
auth ids.

## The claim under test

Recall today is a token intersection over the canonical store. This lane makes
it semantic. The proof has to show a query that token matching provably cannot
answer, answered correctly.

## A/B on the same stored memory

Stored memory (confirmed by the user through the real product path):

```text
AAPL Buy and Hold: Rejected
Rejected the higher drawdown Apple momentum variant and kept the steadier buy and hold.
```

| Query | Token overlap with the memory | Canonical token match | With the index |
| --- | --- | --- | --- |
| `which idea did I turn down for being too volatile?` | none | cannot answer | `provider_ranked`, score 0.3101 |
| `cual idea rechace por ser demasiado volatil?` | none | cannot answer | `provider_ranked`, score 0.3330 |

The canonical fallback ranks by `len(query_tokens & record_tokens)` over tokens
longer than two characters and returns nothing when that intersection is empty.
Both queries have an empty intersection, so the token matcher returns zero rows
by construction. `tests/memory/test_semantic_recall_degradation.py` pins that
baseline as an explicit test so the comparison cannot silently rot.

The Spanish query also crosses languages: the stored memory is English and the
query is es-419, which token matching could never bridge.

## Embedding quality and measured cost

Direct measurement against the live endpoint, `pplx-embed-v1-0.6b`, 1024
dimensions:

| Call | Latency | Tokens | Reported cost |
| --- | --- | --- | --- |
| embed memory 1 | 455 ms | 14 | $0.000000056 |
| embed memory 2 | 215 ms | 10 | $0.000000040 |

Cosine similarity for `which variant had the gentler decline`, a query sharing
no token with either memory:

- against the ETH drawdown memory: **0.4365**
- against the SPY benchmark memory: **0.0931**

The relevant memory scores 4.7x higher than the irrelevant one, so the ranking
signal is real rather than incidental. Recall quality and latency both clear
the spec's stop condition; no vendor change is needed.

At roughly 5e-8 USD per call, with one embedding per confirmation and one per
recall, embedding spend is not a meaningful cost line.

## Storage proof

After confirming one memory through the product surface:

```text
public.memory_records        -> 1 row (canonical truth)
public.argus_memory_vectors  -> 1 row, vector_dims = 1024
payload->>'argus_record_id'  -> fc9f6f91... (matches the canonical record id)
```

The derivative row carries the canonical record id, which is the only join
between index and truth. Nothing else about the memory is reachable from the
index.

## S10 re-verification

Mechanism, not just outcome. Recall annotations are written to assistant
message **metadata**. `load_runtime_thread_history` rebuilds every persisted
message as `ConversationMessage(role=..., content=...)`, a constructor that
takes two fields and drops the rest, so metadata cannot reach the interpreter's
input.

Live check against the QA database after both recall turns:

```text
role       | memory_recalls in metadata | content
assistant  | t                          | I don't have any record of rejected ideas...
user       | f                          | cual idea rechace por ser demasiado volatil?
assistant  | t                          | I don't have a record of any idea you turned...
user       | f                          | which idea did I turn down for being too volatile?
```

Memory is present in metadata and absent from content on every row.
`tests/memory/test_semantic_recall_s10.py` pins the constructor's behavior and
asserts the rebuilt history is byte-identical with and without stored memories
for the same turn.

## Flag-off byte identity

Cross-commit, flags off, two runs per side. The harness hashes the OpenAPI
document, the profile payload, conversation create and list, three chat turns
including every SSE event, message hydration, and history. Volatile ids,
timestamps, durations, and opaque pagination cursors are normalized by the
harness, which lives outside the code under test so both sides normalize
identically. Floats are hashed at full precision.

Measured twice, because integration moved mid-lane:

| Comparison | Combined digest | Result |
| --- | --- | --- |
| base `635d5ee8` vs lane code | `287720c2147be1d6a81467b5c3b1b97f7d32e4ddb56d4bb6684651b1ea0647f1` | identical |
| base `778f32c6` vs merged head | `14ee29def1bdc5a29ed2885159e553e3f0f1de22ab5f77f5ad32ed0839303c62` | identical |

The digest differs between the two rows because the integration branch itself
changed underneath, which is the point: each row compares a base against a head
built on that base. Both sides were run twice and were stable, so the match is
a result rather than a coincidence of timing.

## Screenshots

Captured at the merged lane head against the local Supabase stack, real
OpenRouter runtime, real Perplexity embeddings.

| File | What it shows |
| --- | --- |
| `en-01-signed-in.png` | Signed-in surface, English |
| `en-02-backtest-result.png` | The real backtest the decision is saved from |
| `en-03-memory-proposal.png` | The proposal asking before anything is stored |
| `en-04-recall-note.png` | English recall answering a zero-token-overlap query |
| `drawer-en-01-collapsed.png` | The collapsed drawer, English |
| `drawer-en-02-expanded.png` | The same drawer open, feedback row intact |
| `drawer-es-419-01-collapsed.png` | The collapsed drawer, es-419 |
| `drawer-es-419-02-expanded.png` | The same drawer open, es-419 |
| `*-page-text.txt` | Captured page text per locale |

The es-419 evidence is the `drawer-es-419-*` pair. An earlier `es-419-01` and
`es-419-02` pair was removed: it came from the run whose profile language never
switched, so it showed an English interface under an es-419 name. The
signed-in shot was byte-identical to its English counterpart.

The English run is the whole journey: backtest, save decision, confirm the
memory proposal, then ask. The es-419 run asks only, against the memory the
English run confirmed, which is what makes it a cross-language recall.

## The recall drawer

The recall block was a permanently open banner: informative, but it occupied
the space directly under every answer whether or not the user cared. It is now
a persistent one-line disclosure that opens on click, matching the avatar-theme
drawer in the profile menu.

| State | Measured height | `aria-expanded` |
| --- | --- | --- |
| collapsed (default) | 28 px | `false` |
| expanded | 111 px | `true` |

The label stays visible in both states, so the fact that Argus recalled
something is never hidden; only the memory text is behind the click.

Interaction with the feedback row, which is the risk in putting a
height-changing control above hover-gated controls:

- The trigger lives outside the hover-gated footer, so it stays reachable
  whether or not the pointer is over the message.
- Expanding grows the message inside the same hover group, so the thumbs and
  three-dot row moves with the layout instead of falling out from under the
  pointer. Verified: the feedback row was still visible after expanding while
  hovered (`feedbackRowStillVisible: true`).
- Keyboard: the trigger is focusable and Enter toggles it
  (`aria-expanded` went `true` to `false` on Enter).
- The panel carries `inert` and `aria-hidden` while closed, so it is out of tab
  order and out of the accessibility tree rather than merely invisible.
- Motion honors `prefers-reduced-motion`.

Both locales, taken from the real UI:

| Locale | Collapsed | Expanded |
| --- | --- | --- |
| en | `FROM YOUR MEMORY Show` | `FROM YOUR MEMORY Hide` |
| es-419 | `DE TU MEMORIA Mostrar` | `DE TU MEMORIA Ocultar` |

## Two honest observations

The assistant prose still says it has no record while the correct memory renders
in the drawer directly below it. That is the exact PR #386 observation the
recall-loop spec cites, and it is spec item 1, history answering, which this
lane does not build. Recall is correct here; the conversational reading of it is
the next slice's job. Worth noting for sequencing: semantic recall makes this
contradiction *more* visible, because recall now succeeds on questions token
matching used to miss entirely.

Correction to an earlier draft of this document: it claimed the assistant's
prose rendered in English for the es-419 turn and attributed that to interpreter
voicing. That was wrong, and the artifacts were wrong with it. The first es-419
capture never switched the profile language, so the whole UI was English; the
signed-in screenshot was byte-identical to the English one. Those three files
have been removed rather than left to mislead a reviewer.

The cause is worth recording for the next lane: `i18n` follows the **profile
language**, not the browser locale, so a Playwright `newContext({locale})` does
nothing on its own. Set `public.profiles.language` before sign-in.

With the profile language actually set to es-419, the interface, the assistant
prose, and the drawer all render in Spanish. Only the stored memory text stays
English, which is correct: stored memory content is verbatim user content by
spec section 2.11 and is not localized.
