# Connect the approved Cuadrao interface

The founder rejected the separate Connected presentation on October 5. This lane
reuses Preview's approved rendering for the real account, movement, recurrence,
and payment-confirmation journey.

## Source and boundaries

The integration base is `875de09ac2115acec42e09060b92878aa5f18eff`.
The [baseline manifest](baseline/manifest.json) identifies the unchanged Preview
screens captured before implementation. Both installed phone apps are retained.
No phone build, merge, deployment, hosted migration, or provider call is part of
this acceptance record.

## Decisions

The experience-first principle keeps existing view bodies, typography and art.
The domain-model principle leaves live records and writes in existing owners.
Shared views accept display values and actions. They do not accept a mutable
Preview store containing real data.

The architecture comparison selected small shared views and explicit callbacks.
A whole-app snapshot would duplicate the financial model. A store protocol would
force durable review flows to imitate immediate fixture mutations. A third design
runner was unavailable because its model was at capacity.

The prove-it-works principle requires both matching fixture screenshots and a
real local API journey. A simulator result does not replace phone acceptance.

The live Home contract supplies current totals but no portfolio-history series.
Connected therefore uses the approved history-empty artwork beside the actual
balance. It does not infer history from current positions or future Plan points.
The expanded balance retains the supplied cash, asset and debt breakdown.

## Verification

Verification is in progress. The first connected recurring journey passed at
`a1f2aab31` against the local API and Postgres. It records an expense, prepares its
next expected payment, checks Home's independent 30-day window, confirms payment,
and verifies the result after relaunch. Preparing the expectation leaves the
recorded balance unchanged. Confirmation records one payment and removes the
expected occurrence once.

The Home detail/linked-account/back journey and account swipe/archive/restore
journey passed at the same app source. Further gesture, recovery, and release
checks are running. The final record will identify each result bundle.

The new account-read state test and six detail-presentation tests pass. They cover
unread/failed versus successful first use, identity reset, exact monetary
precision, fractional shares, signed legs, and unavailable amounts.

[The image comparison](preview-parity.json) records six byte-identical original
Preview captures. Plan light differs by only 31 pixels at one channel level; a
replay using the untouched original app binary matches the candidate byte for
byte. The original images remain intact. A later selector extraction requires a
fresh Home capture before visual acceptance.

The isolated local stack uses ports 59850 through 59855, synthetic accounts,
blank provider keys, and all 112 repository migrations. Its smoke check passed
login, profile, Accounts, and Plan reads for two synthetic users. Credentials stay
in ignored local files and are not part of this evidence.

Physical-phone acceptance is pending. Neither installed phone app was modified.
