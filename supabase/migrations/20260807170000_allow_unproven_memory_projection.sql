-- Let a projection record that no reconciliation claim ever proved it.
--
-- Attaching a provider ref out of band says nothing about what the index
-- actually holds. Retrieval decides whether an empty index answer is
-- authoritative from the projection's generation, so an unproven attachment
-- needs a generation it can never satisfy that comparison with. Every real
-- reconciliation generation starts at 1, so 0 is that value.
--
-- Widening a check only; no rows change and no existing generation is valid
-- under the old rule but invalid under the new one.

alter table public.memory_provider_projections
  drop constraint if exists memory_provider_projections_generation_check;

alter table public.memory_provider_projections
  add constraint memory_provider_projections_generation_check
  check (generation >= 0);
