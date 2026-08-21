# Issue #461 Access Welcome Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send and durably record one bilingual transactional welcome email
when a requested private-alpha address becomes an active user.

**Architecture:** Replace the content inside the existing single-purpose SMTP
sender and keep the existing ops-only route as the sole application entry. A
private append-only delivery table plus one security-invoker Postgres function
atomically records the accepted send and promotes the allowlist row. A database
trigger rejects direct activation without the record, while the stable Resend
SMTP idempotency header protects the external-send retry window.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, stdlib `email` and `smtplib`,
Supabase Postgres and PostgREST RPC, pytest, Supabase CLI, Bash, Resend SMTP,
Gmail RAW verification, Playwright CLI.

## Global Constraints

- Start from `8025672924d1c74eb80cc926c72b5d8574b613d7` and target
  `codex/private-alpha-next`.
- Reuse `src/argus/domain/access_approval_email.py`; do not add a second sender,
  generic mailer, template engine, queue, campaign, broadcast, or second email.
- The only message is transactional access welcome. It has no opt-in,
  unsubscribe, topic, marketing preference, or follow-up sequence.
- Support English and `es-419`; no em dash may appear in either message.
- Use only existing Argus product language. Do not invent positioning.
- HTML CTA background is `#191c1f`; border radius is `9999px`.
- Derive the link from `ARGUS_APP_ORIGIN`; do not hardcode a live domain or edit
  the release integrity contract.
- Name `support@get-argus.com` in both alternatives.
- Never print, retrieve, copy, or inspect the Resend credential or SMTP
  password. Do not touch `.env` or `web/.env.local`.
- Do not use `git stash`, rebase after publication, merge, deploy, or apply a
  shared/hosted migration.
- Evidence belongs under `docs/reports/evidence/461/` and must cite the exact
  final head it supports.

---

### Task 1: Add the single-purpose delivery truth and guarded promotion

**Files:**

- Create via `supabase migration new add_access_welcome_deliveries`:
  `supabase/migrations/*_add_access_welcome_deliveries.sql`
- Create: `tests/test_access_welcome_delivery_migration.py`
- Modify: `tests/test_access_request_postgres.py`
- Modify: `docs/DATA_MODEL.md`

**Interfaces:**

- Produces table `public.private_alpha_access_welcome_deliveries` with primary
  key `recipient_email` and fields `language`, `content_version`, `subject`,
  `provider_receipt`, `sent_at`, and `created_at`.
- Produces RPC
  `public.complete_private_alpha_access_welcome(p_email text, p_language text,
  p_content_version text, p_subject text, p_provider_receipt text) returns
  boolean`.
- Produces trigger function
  `public.require_private_alpha_access_welcome_delivery() returns trigger`.
- Browser roles receive no table privileges, policies, or function execution.
  `service_role` receives table `select, insert` and RPC `execute` only.

- [ ] **Step 1: Discover and create the migration with the Supabase CLI**

Run:

```bash
supabase --version
supabase migration new --help
supabase migration new add_access_welcome_deliveries
```

Record the exact CLI-generated path in the implementation notes. Do not rename
or hand-create the migration.

- [ ] **Step 2: Write the failing migration contract test**

Create `tests/test_access_welcome_delivery_migration.py` so it finds exactly one
`*_add_access_welcome_deliveries.sql` migration and verifies these security and
integrity clauses:

```python
def test_access_welcome_delivery_migration_is_private_and_once_only() -> None:
    sql = _normalized_sql()
    assert "create table public.private_alpha_access_welcome_deliveries" in sql
    assert "recipient_email text primary key" in sql
    assert "content_version = 'private-alpha-access-welcome/v1'" in sql
    assert "enable row level security" in sql
    assert "from public, anon, authenticated, service_role" in sql
    assert "grant select, insert" in sql
    assert "create policy" not in sql


def test_access_welcome_delivery_migration_guards_direct_activation() -> None:
    sql = _normalized_sql()
    assert "complete_private_alpha_access_welcome" in sql
    assert "security invoker" in sql
    assert "require_private_alpha_access_welcome_delivery" in sql
    assert "new.role = 'user'" in sql
    assert "new.disabled_at is null" in sql
```

- [ ] **Step 3: Run the migration test red**

Run:

```bash
poetry run pytest tests/test_access_welcome_delivery_migration.py -q --no-cov
```

Expected: failure because the empty migration does not create the table or its
guarded completion boundary.

- [ ] **Step 4: Implement the minimum migration**

The migration must:

```sql
create table public.private_alpha_access_welcome_deliveries (
  recipient_email text primary key,
  language text not null check (language in ('en', 'es-419')),
  content_version text not null check (
    content_version = 'private-alpha-access-welcome/v1'
  ),
  subject text not null check (char_length(subject) between 1 and 200),
  provider_receipt text not null check (
    char_length(provider_receipt) between 1 and 256
  ),
  sent_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  check (recipient_email = lower(btrim(recipient_email)))
);
```

Enable RLS, revoke inherited privileges from `public`, `anon`,
`authenticated`, and `service_role`, then grant `select, insert` to
`service_role`. Add no policy.

The security-invoker completion function must lock the target allowlist row,
return `false` for missing, disabled, admin, developer, or other ineligible
states, accept an already-active `user` only when its delivery record exists,
insert the immutable record with `on conflict (recipient_email) do nothing`,
reject a conflicting language/version/subject, update `requested` to `user`,
and return `true`. Revoke execute from `public`, `anon`, and `authenticated`;
grant it only to `service_role`.

The before-update trigger must require a matching delivery record whenever a
row becomes an enabled `user` from a non-user or disabled state. It must not
change inserts, admin/developer roles, disabling, or existing active users.

- [ ] **Step 5: Make the migration contract green**

Run:

```bash
poetry run pytest tests/test_access_welcome_delivery_migration.py -q --no-cov
```

Expected: all tests pass.

- [ ] **Step 6: Add real Postgres behavior tests**

Replace the old direct-promotion assumptions in
`tests/test_access_request_postgres.py` with these named behavior tests:

- `test_direct_requested_user_activation_without_delivery_is_rejected`
- `test_completion_records_delivery_and_promotes_atomically`
- `test_completion_replay_returns_true_with_one_delivery_row`
- `test_concurrent_completion_has_one_delivery_and_one_active_row`
- `test_browser_roles_cannot_read_or_mutate_delivery_rows`

Use randomized incidental addresses, clean only those rows, and assert literal
record fields. Do not derive expectations with the RPC under test.

- [ ] **Step 7: Reset an isolated local Supabase stack and run Postgres proof**

Use the repository CI recipe on a lane-unique local stack:

```bash
supabase start -x vector,edge-runtime,imgproxy
supabase db reset
ARGUS_DISPOSABLE_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres" \
  poetry run pytest tests/test_access_request_postgres.py -q --no-cov
```

Before resetting, verify the local project and ports are this worktree's
disposable stack. Do not reset a shared QA stack.

- [ ] **Step 8: Update data-model truth and commit**

Document the table, immutability, service-role-only access, completion RPC, and
activation guard in `docs/DATA_MODEL.md`. Commit:

```bash
git add supabase/migrations tests/test_access_welcome_delivery_migration.py \
  tests/test_access_request_postgres.py docs/DATA_MODEL.md
git commit -m "feat(access): guard welcome delivery before promotion"
```

### Task 2: Replace the old approval copy with the bilingual welcome message

**Files:**

- Modify: `tests/test_access_approval_email.py`
- Modify: `src/argus/domain/access_approval_email.py`

**Interfaces:**

- Produces constant
  `ACCESS_WELCOME_CONTENT_VERSION = "private-alpha-access-welcome/v1"`.
- Produces frozen dataclass `AccessWelcomeEmailContent(subject: str,
  plain_text: str, html: str)`.
- Produces frozen dataclass `AccessWelcomeSendResult(subject: str,
  content_version: str, provider_receipt: str)`.
- Produces
  `build_access_welcome_email(*, language: Language, signup_url: str) ->
  AccessWelcomeEmailContent`.
- Replaces the route-owned sender with
  `send_access_welcome_email(*, recipient: str, language: Language,
  signup_url: str) -> AccessWelcomeSendResult`.

- [ ] **Step 1: Write failing bilingual content and transport tests**

Parametrize EN/es-419 literal expectations and prove each MIME message has:

```python
assert message.get_content_type() == "multipart/alternative"
assert set(payloads) == {"text/plain", "text/html"}
assert "support@get-argus.com" in payloads["text/plain"]
assert "support@get-argus.com" in payloads["text/html"]
assert "background-color: #191c1f" in payloads["text/html"]
assert "border-radius: 9999px" in payloads["text/html"]
assert "https://app.example/?auth=signup" in payloads["text/plain"]
assert "https://app.example/?auth=signup" in payloads["text/html"]
assert "\u2014" not in payloads["text/plain"] + payloads["text/html"]
```

Expected subjects are `Welcome to Argus` and `Bienvenido a Argus`. Assert the
English repository-owned positioning sentence exactly and its faithful Spanish
localization. Assert one first-action paragraph only, no unsubscribe copy, and
no auth-template tagline.

Keep the existing SMTP host, port, TLS, username, sender, normalized recipient,
accepted response, 256-character receipt bound, and deterministic hashed
`Resend-Idempotency-Key` tests. Update the idempotency namespace to
`argus-access-welcome/v1`.

- [ ] **Step 2: Run email tests red**

Run:

```bash
poetry run pytest tests/test_access_approval_email.py -q --no-cov
```

Expected: the old approval subject/body lacks the product sentence, support
address, and Argus Dark pill CTA.

- [ ] **Step 3: Implement the minimum content builder and sender result**

Keep one module and one SMTP transaction. Escape the configured URL before HTML
insertion. Use a table-backed `<a>` button with inline email-safe styles. Do not
introduce CSS frameworks, remote fonts, images, tracking, or hidden pixels.

The plain and HTML bodies must express only:

1. Welcome/access granted.
2. Existing Argus product truth in one line.
3. The first action to try.
4. Signup CTA and raw URL fallback.
5. Human support address.

- [ ] **Step 4: Run email tests green and commit**

Run:

```bash
poetry run pytest tests/test_access_approval_email.py -q --no-cov
```

Commit:

```bash
git add tests/test_access_approval_email.py \
  src/argus/domain/access_approval_email.py
git commit -m "feat(email): welcome approved access users"
```

### Task 3: Make the protected approval route durably idempotent

**Files:**

- Modify: `tests/test_access_requests.py`
- Modify: `tests/test_access_approval_email.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `src/argus/api/routers/ops.py`
- Modify: `docs/API_CONTRACT.md`

**Interfaces:**

- Adds
  `SupabaseGateway.get_private_alpha_access_welcome_delivery(email: str) ->
  dict[str, Any] | None`.
- Replaces direct update with
  `SupabaseGateway.complete_private_alpha_access_welcome(*, email: str,
  language: Language, content_version: str, subject: str,
  provider_receipt: str) -> bool` calling the migration RPC.
- Preserves `AccessApprovalResponse` as `{"approved": true}` and keeps the
  route an exact internal OpenAPI exclusion.

- [ ] **Step 1: Write failing gateway boundary tests**

Prove the delivery lookup normalizes email and selects only the six documented
fields. Prove completion calls RPC with exact normalized values and returns the
database boolean. Remove the unit test that treats a raw table update as the
approved boundary.

- [ ] **Step 2: Write failing route replay tests**

Add a stateful fake gateway and fake sender so two real TestClient requests for
the same normalized address prove:

```python
assert first.status_code == second.status_code == 200
assert send_count == 1
assert fake_gateway.role == "user"
assert len(fake_gateway.deliveries) == 1
```

Also prove the first request orders `send` before `complete`, a recorded replay
never calls SMTP, a delivery record cannot approve a missing/disabled/privileged
row, missing origin and SMTP failure never call completion, and completion
failure remains a generic `409` or `503` without leaking provider details.

- [ ] **Step 3: Run route and gateway tests red**

Run:

```bash
poetry run pytest tests/test_access_requests.py \
  tests/test_access_approval_email.py -q --no-cov
```

Expected: missing delivery lookup/RPC methods and repeat requests do not yet
return idempotent success.

- [ ] **Step 4: Implement gateway methods and route orchestration**

The route algorithm is:

```python
existing = gateway.get_private_alpha_access_welcome_delivery(body.email)
if existing is not None:
    completed = gateway.complete_private_alpha_access_welcome(
        email=body.email,
        language=existing["language"],
        content_version=existing["content_version"],
        subject=existing["subject"],
        provider_receipt=existing["provider_receipt"],
    )
    if completed:
        return AccessApprovalResponse()
    raise HTTPException(status_code=409, detail=INELIGIBLE_DETAIL)

requested = gateway.get_requested_private_alpha_access(body.email)
if requested is None:
    raise HTTPException(status_code=409, detail=INELIGIBLE_DETAIL)
result = send_access_welcome_email(
    recipient=body.email,
    language=language,
    signup_url=signup_url,
)
completed = gateway.complete_private_alpha_access_welcome(
    email=body.email,
    language=language,
    content_version=result.content_version,
    subject=result.subject,
    provider_receipt=result.provider_receipt,
)
```

Catch database/provider errors at the route boundary and keep the existing
generic `Approval is unavailable.` response. Do not log the address or receipt.

- [ ] **Step 5: Run route and gateway tests green**

Run:

```bash
poetry run pytest tests/test_access_requests.py \
  tests/test_access_approval_email.py -q --no-cov
```

- [ ] **Step 6: Update API semantics and commit**

Document durable replay, the record-before-activation rule, and the sole
promotion boundary in `docs/API_CONTRACT.md`. Keep the route and response shape
unchanged. Commit:

```bash
git add tests/test_access_requests.py tests/test_access_approval_email.py \
  src/argus/domain/supabase_gateway.py src/argus/api/routers/ops.py \
  docs/API_CONTRACT.md
git commit -m "feat(access): make welcome promotion idempotent"
```

### Task 4: Route operational promotion through the one approved path

**Files:**

- Modify: `tests/test_render_canary_script.py`
- Modify: `.github/canary-render.sh`
- Modify: `docs/PRIVATE_LAUNCH_RUNBOOK.md`

**Interfaces:**

- `promote_requested_signup_allowlist()` calls
  `${API_URL}/internal/access-requests/approve` with the existing ops token and
  validates `{"approved": true}`.
- Direct service-role `PATCH` of `role=user` is removed from the canary and the
  human promotion instructions.

- [ ] **Step 1: Write the failing canary behavior test**

Update the existing canary test so it requires the protected route URL,
credential-safe curl config, request body normalization, response validation,
and no direct role PATCH in `promote_requested_signup_allowlist()`.

- [ ] **Step 2: Run canary tests red**

Run:

```bash
poetry run pytest tests/test_render_canary_script.py -q --no-cov
```

Expected: the script still patches the allowlist through PostgREST.

- [ ] **Step 3: Implement the narrow canary change**

Load `ARGUS_OPS_TOKEN` through the existing root-env loader, write only its
Authorization header to a `0600` temporary curl config, and remove that file in
the existing cleanup trap. Never echo the token. Preserve all signup, Auth-user,
and allowlist cleanup behavior.

- [ ] **Step 4: Update the runbook**

Document the ops route as the only requested-user promotion command, the
delivery-table fields support may read, generic failure behavior, and the
transactional-only consent boundary. Keep all secrets as variable references.

- [ ] **Step 5: Run shell and canary verification, then commit**

Run:

```bash
bash -n .github/canary-render.sh
poetry run pytest tests/test_render_canary_script.py \
  tests/test_environment_scripts.py \
  tests/test_private_alpha_release_docs.py -q --no-cov
```

Commit:

```bash
git add tests/test_render_canary_script.py .github/canary-render.sh \
  docs/PRIVATE_LAUNCH_RUNBOOK.md
git commit -m "fix(canary): use recorded access welcome promotion"
```

### Task 5: Verify the complete lane and capture exact-head evidence

**Files:**

- Create: `docs/reports/evidence/461/README.md`
- Create: `docs/reports/evidence/461/welcome-email-en.png`
- Create: `docs/reports/evidence/461/welcome-email-es-419.png`
- Create: `docs/reports/evidence/461/raw-header-proof.txt`
- Create: `docs/reports/evidence/461/idempotency-proof.txt`
- Modify only if generated drift exists: `docs/api/openapi.yaml`

**Interfaces:**

- Evidence contains no full recipient address, token, SMTP credential, or raw
  message body. Header proof keeps only Authentication-Results, Content-Type,
  From, Subject, Date, and redacted Message-ID lines.

- [ ] **Step 1: Run focused and contract verification**

Run fresh on the candidate tree:

```bash
poetry run python -V
poetry run pytest tests/test_access_welcome_delivery_migration.py \
  tests/test_access_request_postgres.py tests/test_access_requests.py \
  tests/test_access_approval_email.py tests/test_render_canary_script.py \
  tests/test_openapi_compatibility.py tests/test_alpha_artifacts.py \
  tests/test_environment_scripts.py tests/test_private_alpha_release_docs.py \
  -q --no-cov
poetry run ruff check src/argus/domain/access_approval_email.py \
  src/argus/api/routers/ops.py src/argus/domain/supabase_gateway.py \
  tests/test_access_approval_email.py tests/test_access_requests.py \
  tests/test_access_request_postgres.py \
  tests/test_access_welcome_delivery_migration.py
poetry run mypy src/argus/domain/access_approval_email.py \
  src/argus/api/routers/ops.py
python scripts/check_modularity_budget.py
```

Run `scripts/generate_openapi_artifact.py` only if the compatibility test finds
generated drift. Do not change the internal-route exclusion.

- [ ] **Step 2: Render exact code-owned HTML in both languages**

Use `build_access_welcome_email` to write two temporary HTML documents with a
non-production example origin, then use the Playwright CLI at a fixed mobile-
friendly viewport to capture the full rendered message. Inspect both images
before copying them into `docs/reports/evidence/461/`.

- [ ] **Step 3: Prove double promotion yields one send**

Against the isolated local Supabase stack, insert one fresh requested row, run
the local protected operation twice with a sender test double that records the
MIME acceptance boundary, and query both tables. Capture a secret-free report
showing two HTTP 200 responses, one send, one delivery row, and final role
`user`.

- [ ] **Step 4: Send one real credential-safe message and read RAW Gmail**

Generate the exact EN body from the final code and send it from
`Argus <noreply@get-argus.com>` to the connected real Gmail inbox using the
credential-owning Resend connector. Do not retrieve or expose the provider key.
Read that exact Gmail message in RAW format and retain only proof that:

```text
spf=pass
dkim=pass
dmarc=pass
Content-Type: multipart/alternative
```

Also inspect the inbox rendering and confirm it is in Inbox, not Spam. This
external provider proof supplements, but does not replace, the deterministic
SMTP transport and route tests.

- [ ] **Step 5: Write the evidence index at the exact head**

Record base SHA, current candidate SHA, commands, pass/skip counts, local
database isolation, content version, screenshots, double-promotion result, RAW
header fields, inbox placement, and any unproven release surface. State that no
hosted migration or production deploy occurred.

- [ ] **Step 6: Run full proportional verification and commit evidence**

Run the repository backend suite, then any changed shell/docs gates. If a broad
failure appears, reproduce it against untouched base `80256729` before changing
code.

Commit:

```bash
git add docs/reports/evidence/461 docs/api/openapi.yaml
git commit -m "test(email): record access welcome evidence"
```

Omit `docs/api/openapi.yaml` from staging when it has no diff.

### Task 6: Publish, review, and stop at the founder gate

**Files:**

- No new product files unless a validated review finding requires the smallest
  safe fix.

- [ ] **Step 1: Reconcile the integration branch if it advanced**

Fetch `origin/codex/private-alpha-next`, record original base and current
integration SHA, compare semantic overlap across API, allowlist, migrations,
environment, canary, and tests. If advanced, merge integration one way into the
worker branch. Do not rebase.

- [ ] **Step 2: Re-run exact-head gates and modularity on the merged result**

Re-run every invalidated gate, including screenshots and real-send evidence if
the relevant email content, transport, origin, or persistence boundary changed.
Do not repeat paid or external proof when reconciliation is demonstrably
unrelated.

- [ ] **Step 3: Push and open a Draft PR**

Target `codex/private-alpha-next`, link issue #461, apply existing labels
`enhancement` and `med-priority` plus applicable repository labels, and use the
required structured PR body. The PR body must explicitly say:

```text
This welcome message is transactional because the recipient requested access
and Argus granted that request. It has no opt-in or unsubscribe requirement.
Product updates, tips, re-engagement, campaigns, and every second email remain
marketing scope with a separate legal and founder approval boundary.
```

- [ ] **Step 4: Run the review loop to terminal state**

Wait for CI. Enumerate every unresolved inline and general comment, validate it
against the lane spec and code, apply only confirmed proportional fixes, reply
to every finding, push, and re-run invalidated evidence. Once required CI is
green and unresolved threads are zero, post one latest-head `@codex review`
request. Stop only after the latest-delta review is clean.

- [ ] **Step 5: Report and stop**

Report issue, PR URL, branch, original base, current integration SHA,
reconciliation SHA if any, semantic-overlap disposition, final exact head,
commits, CI, review verdict, unresolved-thread count, deterministic proof,
database proof, bilingual screenshots, RAW authentication results, inbox
placement, and any remaining founder action. Do not merge or deploy.
