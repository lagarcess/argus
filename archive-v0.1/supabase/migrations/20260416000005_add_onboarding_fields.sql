alter table if exists profiles
  add column if not exists onboarding_completed boolean not null default false,
  add column if not exists onboarding_step text not null default 'profile',
  add column if not exists onboarding_intent text;
