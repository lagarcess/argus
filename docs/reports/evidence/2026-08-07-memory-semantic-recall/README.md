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
| `cual idea rechace por ser demasiado volatil?` | none | cannot answer | `provider_ranked`, score 0.3044 |

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

Cross-commit, base `635d5ee8` versus lane head, flags off, two runs per side:

| Surface | Digest |
| --- | --- |
| openapi | `eda3956313dbec420294f1d07e053dba039274fba29149be78470089a6136bc0` |
| profile | `6497c3c43c7e192ff4d9ea5f94415cf41f67a804fffb3b8452520dd3c131f98e` |
| conversation_create | `e78cb2bad6443f771a9220d49aa19b1e9f77724500edd447a8e7422863a27187` |
| conversation_list | `bf475d4caf61de82d6cade3ad232c7fec021cc9d2f45ebf2d0ad74e3513c9693` |
| chat_turns | `d555df71677996de5fc95bcc510279ec58f3aa6a1063c28701c140de046d7acc` |
| hydration | `fc1fd90b0ba71cbb576b19c7aa8fee96b201f4d1555e1fabad9dba5e03e3694b` |
| history | `5c52971eb5bb38dccbb6121735420638074d1eb79ed117bf93297ae6e8c74e8f` |
| **combined** | **`287720c2147be1d6a81467b5c3b1b97f7d32e4ddb56d4bb6684651b1ea0647f1`** |

Identical on both sides and stable across repeated runs, so the match is a
result rather than a coincidence of timing.

## Screenshots

| File | What it shows |
| --- | --- |
| `en-01-signed-in.png` | Signed-in surface, English |
| `en-02-recall-note.png` | English recall note answering a zero-token-overlap query |
| `es-419-01-signed-in.png` | Signed-in surface, es-419 |
| `es-419-02-recall-note.png` | es-419 recall note answering the Spanish query |
| `en-page-text.txt`, `es-419-page-text.txt` | Captured page text for both locales |

## Two honest observations

The assistant prose still says it has no record while the correct memory renders
in the note directly below it. That is the exact PR #386 observation the
recall-loop spec cites, and it is spec item 1, history answering, which this
lane does not build. Recall is correct here; the conversational reading of it is
the next slice's job.

The assistant's prose rendered in English for the es-419 turn. That is
interpreter voicing, not this lane's surface. The recall note itself is
backend-provided, and stored memory content stays verbatim user content by spec
section 2.11, so the English memory text appearing under a Spanish question is
the specified behavior.
