-- Route receipts admit every model tier the runtime declares in
-- OpenRouterModelTier (src/argus/llm/openrouter_tasks.py). The readout tier was
-- missing, so result_summary receipts and their cost-ledger rows failed to
-- persist (#605). No row is rewritten: every stored tier stays admitted.
-- DROP CONSTRAINT is classified destructive by the promotion gate. The founder
-- applies this migration at promotion.
-- Rollback: keep this check. The narrower one cannot return once readout
-- receipts exist.
alter table public.route_receipts
  drop constraint route_receipts_tier_check,
  add constraint route_receipts_tier_check
    check (tier in ('utility', 'chat', 'structured', 'context', 'readout'));
