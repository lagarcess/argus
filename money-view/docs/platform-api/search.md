# Omnisearch API

`GET /api/platform/search?q=&kind=all&limit=20&offset=0&scope=all`

- q: trimmed literal prefix, max 120 characters. `%`, `_`, quotes are literal text. Empty q browses recent records. Text matching is case-insensitive for ASCII, SQLite NOCASE semantics; no fuzzy/semantic claims. Searches only declared human-facing fields, not internal IDs, private metadata, or arbitrary JSON.
- kind: all | conversation | account | transaction | budget | goal | scenario | holding | deposit.
- scope: all | recent | pinned. recent/pinned restrict to conversations. Pinned recall uses the new chat owner's actual `pinned` field. Legacy assistant `saved` is not relabeled as a pin; those conversations remain in all/recent recall.
- limit: 1–40; offset: 0–1000. Each indexed source field returns at most offset+limit+1 visible candidates. Transaction fields first read at most 1042 indexed IDs, then check canonical active-account visibility on the first 1041. This fixed per-field window is identical at every offset; no full household ledger scan or duplicate text index.
- response: `{items:[{id,kind,title,preview,recorded_at,as_of,pinned,target:{page,record_id,conversation_id:null,account_id:null,decision:null},fields:[{label,value}],evidence:null|Evidence}],has_more,next_offset:null|number,match_mode:"field_prefix",query,kind,scope,deposit_window:500,window_limited:false}`.
- fields labels are stable localization keys. Amounts remain exact decimal strings with separate currency fields. Preview/title strings are bounded. Navigation only contains owned record identifiers and a whitelisted page, never arbitrary URLs.
- Auth/session/household from shared context. Deleted/trashed records are excluded; records from another household never contribute IDs, counts or previews.

Navigation pages: accounts, transactions, budgets, goals, scenarios, investments, deposits, saved, chat. Existing assistant opens saved/conversation_id; new chat opens chat/conversation_id. Record_id is supplied to destination pages. Accounts and transactions also receive account_id; deposit saved records receive decision. All matching happens in local SQLite and never invokes a model. Explicit Ask passes query text to the chat owner.

Prefix matches sort by their matched field (ASCII case-insensitive), then stable record ID. Empty-query results sort by recording/update date descending, then stable ID. Categories group the frontend display and keyboard order. `window_limited:true` means the transaction candidate window or offset ceiling was reached. It is independent of `has_more`: `has_more` and `next_offset` describe only visible results inside the same candidate window. An empty limited window returns `items:[]`, `has_more:false`, `next_offset:null`, `window_limited:true`; it does not claim there are no matches beyond the window. Refine the query or choose another field prefix. Hidden child IDs and fields never reach the response.
