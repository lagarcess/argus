---
description: Critical data integrity and safety constraints (Model Decision - Trigger on any task involving data preservation, Firestore, or notifications)
---

# Data Integrity Rules

When working on persistence or notification logic, you act as the **Data Reliability Engineer**. The consequences of a bug here are financial loss or corrupted states.

## 1. Two-Phase Commit Pattern (Persistence Before Notification)
- **CRITICAL**: You must **never** send a Discord notification or external alert *before* the state is successfully persisted to Firestore.
- **The Flow**:
  1. Execute Trade / Generate Signal.
  2. Write to Firestore.
  3. Wait for Firestore Promise/Await to resolve successfully.
  4. Send Discord Notification.
- **Why**: If the process crashes between step 2 and 4, we miss a notification (annoying). If it crashes between 4 and 2, we have notified users of a trade that our database doesn't know about (catastrophic zombie state).

## 2. Environment Isolation
- **Rule**: Never hardcode or override `ENVIRONMENT="PROD"` in local testing or automated scripts.
- **Defensive Default**: Always default to `ENVIRONMENT="DEV"` if the variable is missing.

## 3. Idempotency
- **Rule**: All updates to critical tables (like Signals or Positions) should be idempotent where possible. Avoid blind increments (`+= 1`); prefer setting explicit derived states.
