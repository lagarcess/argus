-- Generated from OpenRouterModelTier for document extraction receipts.
alter table public.route_receipts
  drop constraint route_receipts_tier_check,
  add constraint route_receipts_tier_check
    check (tier in ('utility', 'chat', 'structured', 'context', 'readout', 'vision'));
