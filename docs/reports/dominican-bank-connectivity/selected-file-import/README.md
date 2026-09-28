# Selected-file import proof

This proof answers lane 4 of the [mobile baseline reconciliation contract](https://github.com/lagarcess/argus/blob/a1c294319a2c047623b9bbe5bedd36155d2e931d/docs/specs/lanes/mobile-baseline-reconciliation-contract.md) in pull request 727. It shows what a person can import by choosing a file, what happens to every other file, and what must exist before a production import lane starts. Everything in it is synthetic. No inbox, bank, real statement, credential, provider, or production system was touched.

It reuses two things and adds nothing to either:

- The [synthetic ingestion kit](../../../../tests/synthetic_ingestion/) from pull request 709, merged into `codex/private-alpha-next`. It supplies the fixtures and the parsers.
- The recording contract's reference model from [pull request 724](https://github.com/lagarcess/argus/pull/724), at head `8cdfc6a09e2fb1001b6a7c8694b67e3bd08fa491`. It supplies the draft, review, and confirm boundary. The proof writes only through the model's `create_account`, `draft`, `edit_draft`, `resolve`, `reject`, `preview`, and `confirm_batch`. It reads the model's stored drafts and records, and it computes totals and balance differences only through the model's `derive` module. It has no rules of its own about money, duplicates, or balance checks. It reports the issues the model raises.

The evidence behind the wider bank report is listed in the [evidence index](../evidence-index.md).

## Result

| Run | Recording model | Passed | Blocked | Failed |
| --- | --- | --- | --- | --- |
| With pull request 724 | `8cdfc6a09e2fb1001b6a7c8694b67e3bd08fa491` | 37 | 0 | 0 |
| Without pull request 724 | None | 15 | 22 | 0 |

Blocked means a case needs the recording model and could not run. It is not a pass.

- The committed [report with pull request 724](proof-report.json) and [report without it](proof-report-without-724.json) are the runs above. A second run of each writes the same bytes.
- The first report records the model's head as given to the runner, a digest of every Python file in that package (`f27de4c4...862f2`), and a digest of the ingestion kit (`48c40767...9925c`), so a reader can tell which versions it proves.
- Eleven deliberate breakages in [`mutation_check.py`](mutation_check.py) each made their target cases fail. They ignore encryption, refuse every encrypted PDF, keep duplicate rows, answer balance-check questions for the person, stop the model from asking them, cancel without discarding drafts, cancel without deleting the file, keep the file after a completed review, track open reviews only in memory, store a file under its original name, and hold a refused file.
- A case that raises an error is recorded as failed, with the error in the report, instead of stopping the run.

## Refresh against the revised recording model

This proof first ran against pull request 724 at `720aad3fd`. There, statement rows dated the day before a confirmed balance check confirmed without review. The [recording decision response](https://github.com/lagarcess/argus/blob/a1c294319a2c047623b9bbe5bedd36155d2e931d/docs/specs/lanes/financial-recording-decision-response.md) in pull request 727 settles question 3 the other way, and the [reconciliation handoff](https://github.com/lagarcess/argus/blob/a1c294319a2c047623b9bbe5bedd36155d2e931d/docs/specs/argus-account-balance-reconciliation-handoff.md) says document import must hand off to account review. The proof recorded this as an expected failure.

The lane named the revised model at `0df86aa8c`, which asks about activity dated on or before a confirmed check, unless the check contained it when confirmed or it came from the same document. The proof reproduced the scenario against it, and all four rows are asked about the check. The expected-failure case is now a regression assertion, `earlier_day_rows_behind_a_balance_check`. It passes only when each row names the check it waits on, nothing confirms the rows before the person answers, a direct confirmation of the unanswered rows is refused and writes nothing, and the answer reaches the check. After the answer, the check still shows its DOP 1,000.00 difference from confirmation time, and DOP 25.50 remains, which is 2,000.00 less 1,974.50. The case fails if the importer answers for the person or the model stops asking. Two of the breakages do exactly that.

Pull request 724 moved to `8cdfc6a09` during the refresh. That head refuses contradictory answers and restamps a check whose amount or date is corrected. The proof uses neither, and every case observed the same values on both heads. The committed report pins `8cdfc6a09`.

The refresh changed only the proof's integration boundary:

- Accounts are created with the model's new signature and carry the model's own space. The proof no longer keeps its own map of accounts to spaces. It reads membership through `derive.space_scope`.
- Balance-check questions are read from the model's `inclusion_unanswered` issue, which replaced `observation_order_unknown`.
- A check's result is read as the two differences the model now keeps apart, the one recorded at confirmation and the one remaining.
- The model digest covers every Python file in the package, because the model now spans more modules.

An automated review of the previous head, `54a359dea`, found two gaps in the proof's own importer, and both are fixed. Open reviews are now found from stored drafts, grouped by file digest, so a restarted app finds them with no session kept in memory. A stored file is now deleted once no row from it is left in review, not only when the person cancels.

## What Argus can claim

"Works with every bank" and "one tap" are not testable. This statement is, and each part of it maps to cases below.

> Choose a statement file with your device's file picker. Argus reads the formats listed as supported, shows you what it found, and records nothing until you confirm. Rows it is unsure about wait for your answer. Files it cannot read yet are named as such, and you can enter those amounts by hand.

| Part of the statement | Today | Cases |
| --- | --- | --- |
| Supported formats | The kit's synthetic CSV and text-PDF layouts only. No real bank's format is supported until a consented sample of that exact format passes a parser and this matrix. | `csv_accepted`, `statement_balance_reconciles` |
| Device file picker | The proof tests the import path from the moment a file's bytes arrive. It does not test any device's picker. | All intake cases |
| Share extension | Not built and not assigned. The proof labels a selection as coming from a share extension and shows that the label changes only the recorded entry point. The checks and duplicate protection are the same. | `pdf_accepted_from_share_extension`, `same_file_from_two_entry_points` |
| Records nothing until you confirm | Import creates drafts only. | `nothing_posts_without_confirmation` |
| Unsure rows wait | Each held row names its reason, including a balance check it may already be part of. | `uncertain_rows_stay_drafts`, `earlier_day_rows_behind_a_balance_check` |
| Files it cannot read | Photos, other PDF layouts, and other CSV headers reach review with no rows and an explicit error. Excel and OFX files are refused as unsupported. | The intake group |

"One tap" becomes three steps: choose a file, check what Argus found, confirm. A clean file with its accounts already chosen needs only the first and last.

Email stays outside this proof. Signing in with Apple or Google grants no mailbox access, as [option D](../options-comparison.md#the-seven-options) records with sources. A statement that arrives as an email attachment can be saved and then chosen with the file picker. An email that only links to the bank's sign-in page is not a statement. Which banks send attachments at all is unverified, as the [bank matrix](../bank-access-matrix.md#documented-statement-availability-versus-observed-file-formats) separates.

## How each file is handled

The proof decides by content, never by the file name.

| File | Outcome | What the person is told to do |
| --- | --- | --- |
| CSV with the kit's header | Rows proposed for review | Review and confirm |
| PDF in the kit's text layout | Rows and one closing balance proposed | Review, confirm the balance date, confirm |
| PDF that opens without a password but forbids copying | Read like any other PDF | Review and confirm |
| PDF that needs a password to open | Refused. Nothing stored or held. | Save an unlocked copy and choose that |
| PDF in another layout, or with no text layer | Accepted, no rows, explicit error | Enter amounts by hand |
| PNG, JPEG, or HEIC photo | Accepted, no rows, no OCR | Enter amounts by hand |
| CSV with another header | Accepted, no rows, explicit error | Enter amounts by hand |
| Excel workbook or OFX file | Refused as unsupported | Choose a CSV, PDF, or image |
| Email with only a sign-in link, or a saved sign-in page | Refused as not a statement | Download the statement file itself |
| Empty file | Refused | Choose another file |
| Larger than 10 MiB | Refused. Nothing stored or held. | Choose a smaller file |

The size limit and the unlocked-copy recovery are experimental assumptions, listed with the other unresolved questions [below](#experimental-assumptions-still-unresolved).

Saving an unlocked copy means opening the file with its password and exporting or printing it again as a PDF, which some people will not know how to do. A file password can itself be sensitive, for example if a bank derives it from an identity number. Whether any candidate bank protects its statements with a password is unverified.

## What comes from the recording model

The proof relies on these rules and does not restate them in code. Each is the model's behavior at `8cdfc6a09` and at `0df86aa8c`.

1. Import creates drafts. Only the person's confirmation writes records.
2. A row with a doubt stays a draft and names its reason, such as a possible duplicate, a missing account or counter-account, an unsupported currency, an invalid date or amount, a missing field, or an unanswered balance check. Clean rows confirm together. This follows lead recommendation 8 in the recording decision response.
3. A row seen before is flagged as already recorded. The importer drops that draft and counts the row as already imported. Seen before means the same file digest and row, or the same row reference on the same account, whether that row is recorded or still in review. Rows that merely look alike, such as two purchases of the same amount on the same day, are asked about and never dropped.
4. A row dated on or before a confirmed balance check waits until the person says whether the check already included it, unless the check contained it when confirmed or it came from the same document. A statement's own closing balance therefore asks nothing about the statement's own rows. The answer changes the check's remaining difference, and the difference recorded at confirmation stays as it was. This follows settled question 3 and question 4.
5. A dollar row pointed at a peso account is blocked until a dollar account is picked. No currency is converted.
6. A confirmation built on a stale preview writes nothing, and a fresh preview then confirms. Retrying a confirmation with the same key returns the same records. This matches lead recommendation 9.

## Experimental assumptions still unresolved

The proof's importer makes these choices so the cases can run. None is an approved production default, and each stays open. The report repeats them under `assumptions`.

| Question | The proof's assumption | Status |
| --- | --- | --- |
| Retention of source files | A stored file is deleted once no row from it is left in review, whether the review ends by confirming or by cancelling. Records keep the file's digest, its stored name, and the row. | Unresolved |
| Password entry | None. A file that needs a password is refused, and the person is asked for an unlocked copy. The alternative is to let a person type the password once so the server opens the file in memory and keeps nothing. | Unresolved |
| Upload limit | 10 MiB | Unresolved |
| Household visibility of source files | Not modeled. A record confirmed into a household account carries a reference to the file, never the file or its original name. Whether a household member may ever open the file is undecided. | Unresolved |

The importer's other choices are equally experimental. It sniffs content to classify files, stores a file under a digest-based name, leaves the account blank unless the file marks a row as personal, and asks the person for the closing balance date because the kit does not read the statement period.

## Acceptance matrix

Generated from the two committed reports, which also hold what each case observed.

| Case | Group | Claim | With 724 at `8cdfc6a09` | Without 724 |
| --- | --- | --- | --- | --- |
| `csv_accepted` | intake | A CSV selected with the file picker is accepted by content. | Passed | Passed |
| `pdf_accepted_from_share_extension` | intake | A PDF arriving from a future share extension takes the same intake path. | Passed | Passed |
| `empty_file` | intake | An empty file is refused with a recovery step. | Passed | Passed |
| `email_with_login_link` | intake | An email that only links to the bank's sign-in page is not an importable statement. | Passed | Passed |
| `html_named_as_pdf` | intake | A saved sign-in page named .pdf is judged by content, not by its name. | Passed | Passed |
| `excel_workbook` | intake | An Excel workbook is unsupported today and says so. | Passed | Passed |
| `ofx_file` | intake | An OFX file is unsupported today and says so. | Passed | Passed |
| `image_without_ocr` | intake | A photo is accepted, but no OCR runs, so it reaches review with no rows. | Passed | Passed |
| `heic_photo_without_ocr` | intake | An iPhone HEIC photo is recognized as an image and yields no rows. | Passed | Passed |
| `pdf_in_unknown_layout` | intake | A text PDF in an unknown layout yields no rows and an explicit error. | Passed | Passed |
| `pdf_without_text_layer` | intake | A PDF with no text layer yields no rows and an explicit error. | Passed | Passed |
| `csv_with_unknown_header` | intake | A CSV without the supported header yields no rows and an explicit error. | Passed | Passed |
| `too_large` | intake | A file over the size limit is refused, and nothing from it is stored or held. | Passed | Passed |
| `password_protected_pdf` | intake | A PDF that needs a password to open is refused with a recovery step, and nothing from it is stored or held. | Passed | Passed |
| `pdf_with_copy_restriction_only` | intake | An encrypted PDF that opens without a password but forbids copying is accepted and read. | Passed | Passed |
| `uncertain_rows_stay_drafts` | review | Clean rows confirm in one batch, and each uncertain row stays a draft with a named reason. | Passed | Blocked, needs 724 |
| `identical_rows_asked_once` | review | Two identical rows in one file are asked about once, then both confirm as distinct purchases. | Passed | Blocked, needs 724 |
| `statement_balance_reconciles` | review | A statement's closing balance becomes one observation, needs a person-confirmed date, and reconciles to zero against its rows when confirmed and afterwards. | Passed | Blocked, needs 724 |
| `scanned_image_with_stub` | review | A scanned image with an authored stub standing in for OCR proposes rows, and an unreadable amount stays blocked. | Passed | Blocked, needs 724 |
| `destination_space_chosen_before_confirming` | review | A household row waits for the person to pick an account, then counts only in that account's space. | Passed | Blocked, needs 724 |
| `currency_mismatch_destination` | review | A USD row pointed at a DOP account is blocked until the person picks a USD account. | Passed | Blocked, needs 724 |
| `source_file_visibility` | review | A Household account receives only the row confirmed into it, and records reference the source file without its contents or its original name. | Passed | Blocked, needs 724 |
| `completed_review_deletes_the_file` | review | Once no row from a file is left in review, the stored file is deleted, and the records still name it by digest. | Passed | Blocked, needs 724 |
| `same_file_from_two_entry_points` | duplicates | The same file selected again from the share extension creates nothing new. | Passed | Blocked, needs 724 |
| `overlapping_statement` | duplicates | An overlapping statement adds only its new row and its own closing balance. | Passed | Blocked, needs 724 |
| `manual_entry_then_import` | duplicates | A purchase already entered by hand links to the imported row instead of counting twice. | Passed | Blocked, needs 724 |
| `same_day_balance_check_hands_off` | review | Untimed rows on the same day as a confirmed balance check wait until the person says whether the check included them. | Passed | Blocked, needs 724 |
| `earlier_day_rows_behind_a_balance_check` | review | Rows dated the day before a confirmed balance check wait for the person's answer, nothing confirms them without it, and the answer reaches the check's remaining difference. | Passed | Blocked, needs 724 |
| `cancel_before_review` | cancellation | Cancelling after choosing a file and before review creates nothing and drops the file. | Passed | Blocked, needs 724 |
| `cancel_during_review` | cancellation | Cancelling during review records nothing, deletes the stored file, and lets the same file be imported afresh later. | Passed | Blocked, needs 724 |
| `cancel_after_partial_confirmation` | cancellation | Cancelling after a batch keeps the confirmed records, which still name the file by digest, and discards the unresolved rows and the file. | Passed | Blocked, needs 724 |
| `pause_and_resume` | cancellation | Leaving a review open keeps its drafts and its file. After the app restarts, the review is found again from the stored drafts alone, and the same file adds no second copy. | Passed | Blocked, needs 724 |
| `retry_with_same_key` | retry | Retrying a confirmation with the same key returns the same records and writes nothing new. | Passed | Blocked, needs 724 |
| `retry_after_stale_preview` | retry | A confirmation against a stale preview writes nothing, and a fresh preview then confirms. | Passed | Blocked, needs 724 |
| `unlocked_copy_after_refusal` | retry | After a password-protected file is refused, an unlocked copy imports cleanly with nothing left from the refusal. | Passed | Blocked, needs 724 |
| `reimport_after_partial_confirmation` | retry | Re-importing after a partial batch re-adds neither confirmed rows nor rows still in review. | Passed | Blocked, needs 724 |
| `nothing_posts_without_confirmation` | boundary | Import creates drafts only. Records change only when the person confirms. | Passed | Blocked, needs 724 |

The matrix covers each item the lane names:

- Unsupported and encrypted documents: the intake group and `unlocked_copy_after_refusal`.
- Uncertain rows: `uncertain_rows_stay_drafts`, `scanned_image_with_stub`, and the two balance-check cases.
- Duplicates: the duplicates group, `identical_rows_asked_once`, `pause_and_resume`, and `reimport_after_partial_confirmation`.
- Destination account and space: `destination_space_chosen_before_confirming` and `currency_mismatch_destination`.
- Source-file visibility: `source_file_visibility`, `completed_review_deletes_the_file`, and the cancellation group.
- Cancellation and retry: their groups.

## What this proof does not show

- **Any real bank's file.** No bank publishes its statement format, and no real statement was used. A real-format test needs separately supplied, authorized input, as the lane requires.
- **Stable row references.** The kit's rows carry stable references, which is what lets an overlapping statement skip its known rows. A real statement may carry no reference, or one that changes between exports. Without one, overlapping rows are asked about as possible duplicates instead of skipped. A bank's row reference should become an identity only after consented samples show that it stays the same across exports.
- **The statement period.** The kit does not read it, so the person confirms the closing balance date.
- **Every answer to a balance-check question.** The proof answers that the check included the rows. The model also accepts that it did not, which the proof does not exercise.
- **OCR.** No provider is selected. The scanned-image case uses an authored stub in place of OCR output.
- **Modern PDF encryption.** The fixtures use the oldest standard scheme, 40-bit RC4. The proof decides whether a password is needed by asking `pdftotext` to open the file without one. That test should hold for newer schemes, but it is proven here on this one only.
- **Who may see what.** No household permission contract exists. The proof shows what a record carries, not who may read it.
- **Production behavior.** Pull request 724's reference model proves examples, not database locking, row-level security, or retention, as the recording decision response says. The share extension is a label, not an extension.

## Dependencies

| Dependency | State on 2026-09-28 | What waits on it |
| --- | --- | --- |
| Ingestion kit, pull request 709 | Merged | Nothing. Fixtures and parsers are in place. |
| Recording contract, [pull request 724](https://github.com/lagarcess/argus/pull/724) | Open and out of draft at `8cdfc6a09` | The 22 recording cases, which report blocked without it |
| Recording decisions and reconciliation handoff, [pull request 727](https://github.com/lagarcess/argus/pull/727) | Open at `d7faac770`. The three documents this proof cites are unchanged since `a1c294319`. | Questions 3, 4, 7, 8, and 9, the balance-date rule, and the document-import handoff |
| Household permission contract | Absent | Who may see imported records and source files |
| Retention of source files | Unresolved | Whether a file outlives its review |
| Password entry | Unresolved | A recovery path easier than an unlocked copy |
| Upload limit | Unresolved | The 10 MiB assumption |
| OCR provider | Not selected | Photos and scanned PDFs |
| Per-bank parsers | Need consented samples | Any claim about a real bank |
| Native share extension | Not built or assigned | Importing from the share sheet |

Bank integration does not block manual account value. Everything above concerns files a person chooses to share.

## Proposal

When the recording contract is approved for production, the import lane should take this matrix as its acceptance gate and rerun it against the real API and database instead of the reference model. The balance-check regression belongs in that gate unchanged. Its first real-bank step is already in the [next assignment](../next-assignment.md). A consenting account holder exports one month in each format their bank offers, following the kit's consent and retention checklist. A format is listed as supported only after a parser for it passes these cases.

Until then, the proof stays documentation. Stop dependent work if another owner takes the lane, if the acceptance surface in pull request 727 changes, or if work would need hosted resources.

## Rerun

The proof needs `pdftotext` from Poppler, as the ingestion kit does. Without pull request 724, the intake cases run and the recording cases report blocked.

```bash
poetry run python docs/reports/dominican-bank-connectivity/selected-file-import/proof.py --report temp/selected-file-import-without-724.json
```

```bash
cmp temp/selected-file-import-without-724.json docs/reports/dominican-bank-connectivity/selected-file-import/proof-report-without-724.json
```

To run every case, fetch pull request 724 and extract the reference model at the head this proof records.

```bash
git fetch origin pull/724/head
```

```bash
mkdir -p temp/recording-724 && git archive 8cdfc6a09e2fb1001b6a7c8694b67e3bd08fa491 tests/financial_recording | tar -x -C temp/recording-724
```

```bash
PYTHONPATH=temp/recording-724 poetry run python docs/reports/dominican-bank-connectivity/selected-file-import/proof.py --report temp/selected-file-import-report.json --recording-ref "lagarcess/argus#724 at 8cdfc6a09e2fb1001b6a7c8694b67e3bd08fa491"
```

```bash
cmp temp/selected-file-import-report.json docs/reports/dominican-bank-connectivity/selected-file-import/proof-report.json
```

To confirm that the cases can fail, run the breakage check with the same path. It exits with an error if any breakage goes unnoticed or if the unbroken run fails.

```bash
PYTHONPATH=temp/recording-724 poetry run python docs/reports/dominican-bank-connectivity/selected-file-import/mutation_check.py
```
