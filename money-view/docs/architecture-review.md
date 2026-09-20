# Architecture review

Two independent design candidates were reviewed by a third agent. Candidate A
was selected for immutable source and comparison receipts, guarded confirmation,
country-neutral types and idempotent publication/checks. Candidate B contributed
the single home projection and deriving notices from check records. Its fixed
country enum and `offer` terminology were rejected.

The captain chose simple annual ACT/365 deposit arithmetic, so fixture rates
never imply reinvestment. Equivalent annual return is an explicitly computed
comparison measure, not a quoted product yield. Annual inflation is held constant
as an index scenario, with its compounding formula shown separately; inflation
index growth is not deposit reinvestment.

The three designs agreed that no-key arbitrary-language interpretation must not
be faked with a parser. Explicit prepared-example replay makes the demo testable;
a separate model adapter handles genuine open text only when configured.

Every synthetic receipt has a dated fixture document and is labeled synthetic.
Its publication date belongs to that simulated document, never to an actual SB
publication. Real observations with unknown publication dates or rate conventions
cannot become calculable records. User inputs carry their confirmation timestamp
and are not represented as published regulator facts.

SQLite was selected over hosted Supabase to keep the entire demo isolated and
persistent without applying any Supabase migrations. This is a single-user local
application, not a production identity or authorization implementation.
