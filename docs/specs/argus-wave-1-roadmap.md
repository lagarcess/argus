# Argus Wave 1 roadmap

> Draft, not approved by Lucas. Lucas said the roadmap is not ready until he
> says so. This document is not a locked decision. Nobody builds from it.

Drafted from Iris's consolidated brief and executive summary in the Product
Strategy room, 2026-09-25 2:54 PM CT, plus Head of Engineering costing.

## Goal and one number (Draft, not approved by Lucas)

The goal number is the share of signed-in pilot users who return between day 8
and day 30. The early signal is the share who save a card or create a goal in
their first week.

Head of Engineering costing: the wave total is 5 to 6 weeks, with web push
included. Email-only would have been 4 to 5 weeks.

## Steps 0 to 3 (Draft, not approved by Lucas)

### Step 0 (Draft, not approved by Lucas)

Step 0 is foundations and cleanup. It includes #681, #691, #692, and #693; the
sharing privacy trace; removing the feedback attachment picker (#675); checking
the USD setting; clean analytics that exclude eval and dev accounts; an
invite-link cohort tag; a "before taxes" line on receipts; the eval run; and
the docs accuracy batch (#672).

### Step 1 (Draft, not approved by Lucas)

Step 1 adds a bottom navigation bar with Home, Tools, AI, Search, and Profile.
AI is the landing page. Tools opens the same cards as chat. The step also adds
a card payoff calculator for a peso balance plus a dollar balance. The pilot
moves to the new build after step 1.

### Step 2 (Draft, not approved by Lucas)

Step 2 adds Search and Home. Home shows saved cards, goals, and rechecks. It
also adds savings goals with a progress bar, and it covers setup checklist
items 1 and 2.

### Step 3 (Draft, not approved by Lucas)

Step 3 adds one daily job plus a channel-agnostic notifications table, monthly
goal check-ins, and maturity reminders. Email reminders ship first. Email is
opt-in. Consent is recorded. The email carries no amounts, at most one message
per goal per month, and a one-click unsubscribe. Web push plus the home-screen
install guide ship last, on the same notifications table. If push slips, the
monthly check-ins and the day 8 to 30 return measurement still start on time.
The step covers setup checklist item 3. Rate rechecks wait until the eval
passes.

## Setup checklist (Draft, not approved by Lucas)

This three-step setup checklist is locked by Lucas. It is the only locked part
of this document.

1. Get a first answer.
2. Save a card or create a goal. Sign-in happens here.
3. Turn on reminders.

## Running alongside (Draft, not approved by Lucas)

Work that runs alongside wave 1 is the Bridge half-day test, about 20 DR user
interviews, and the counsel (legal) question.

## Out of scope (Draft, not approved by Lucas)

Wave 1 does not include net worth and Accounts, Connectors, Discover, statement
upload, budgets, debt goals, Pro+ and Rewards, or WhatsApp.

## Mobile (Draft, not approved by Lucas)

The native mobile wrapper is not in wave 1. It is revisited at the end of the
wave together with the company and entity decision. Both app stores depend on
the entity.

## Still open (Draft, not approved by Lucas)

Still open are eval approval, the Render scheduled job, the Resend sending
domain, the entity decision, and Lucas's final approval of this roadmap.
