# Selected-file import proof

This proof answers lane 4 of the [mobile baseline reconciliation contract](https://github.com/lagarcess/argus/blob/a1c294319a2c047623b9bbe5bedd36155d2e931d/docs/specs/lanes/mobile-baseline-reconciliation-contract.md) in pull request 727. It shows what a person can import by choosing a file, what happens to every other file, and what must exist before a production import lane starts. Everything in it is synthetic. No inbox, bank, real statement, credential, or production system was touched.

It reuses two things and adds nothing to either:

- The [synthetic ingestion kit](../../../../tests/synthetic_ingestion/) from pull request 709, merged into `codex/private-alpha-next`. It supplies the fixtures and the parsers.
- The recording contract's reference model from [pull request 724](https://github.com/lagarcess/argus/pull/724), a draft pinned at `720aad3fdee1357e3dbe5c928176a6e458b01b0d`. It supplies the draft, review, and confirm boundary. The proof writes only through that model's `draft`, `edit_draft`, `resolve`, `reject`, `preview`, and `confirm_batch`, and reads totals only through its `derive` module. It keeps no ledger of its own.

The evidence behind the wider bank report is listed in the [evidence index](../evidence-index.md).

## Result

| Run | Passed | Known gap | Blocked | Failed |
| --- | --- | --- | --- | --- |
| With pull request 724 at `720aad3fd` | 35 | 1 | 0 | 0 |
| Without pull request 724 | 15 | 0 | 21 | 0 |

- The committed [proof report](proof-report.json) is the first run. A second run writes it byte for byte.
- The report records the digest of the recording model it ran against (`ca97f379...c6d3b`) and of the ingestion kit (`48c40767...9925c`), so a reader can tell which versions it proves.
- Without pull request 724, only the 15 intake cases can run. The other 21 report `blocked` instead of passing.
- Seven deliberate breakages in [`mutation_check.py`](mutation_check.py) each made their target cases fail: ignoring encryption, refusing every encrypted PDF, keeping duplicate rows, cancelling without discarding drafts, cancelling without deleting the file, storing a file under its original name, and holding a refused file.
- The known gap is explained [below](#known-gap). If pull request 724 closes it, the run reports an unexpected pass and exits with an error until this matrix is updated.

## What Argus can claim

"Works with every bank" and "one tap" are not testable. This statement is, and each part of it maps to cases below.

> Choose a statement file with your device's file picker. Argus reads the formats listed as supported, shows you what it found, and records nothing until you confirm. Rows it is unsure about wait for your answer. Files it cannot read yet are named as such, and you can enter those amounts by hand.

| Part of the statement | Today | Cases |
| --- | --- | --- |
| Supported formats | The kit's synthetic CSV and text-PDF layouts only. No real bank's format is supported until a consented sample of that exact format passes a parser and this matrix. | `csv_accepted`, `statement_balance_reconciles` |
| Device file picker | The proof tests the import path from the moment a file's bytes arrive. It does not test any device's picker. | All intake cases |
| Share extension | Not built and not assigned. The proof labels a selection as coming from a share extension and shows that the label changes only the recorded entry point. The checks and duplicate protection are the same. | `pdf_accepted_from_share_extension`, `same_file_from_two_entry_points` |
| Records nothing until you confirm | Import creates drafts only. | `nothing_posts_without_confirmation` |
| Unsure rows wait | Each held row names its reason. | `uncertain_rows_stay_drafts` |
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

The 10 MiB limit is an assumption made for the proof, not a decision.

Password recovery is honest but not free. Saving an unlocked copy means opening the file with its password and exporting or printing it again as a PDF, which some people will not know how to do. The alternative is to let a person type the file's password once so the server can open the file in memory without keeping the password. That is an open decision. A file password can itself be sensitive, for example if a bank derives it from an identity number. Whether any candidate bank protects its statements with a password is unverified.

## Rules the proof encodes

1. Import creates drafts. Only the person's confirmation writes records.
2. Clean rows confirm together. A row with a doubt stays a draft and names its reason, such as a possible duplicate, a missing account or counter-account, an unsupported currency, an invalid date or amount, or a missing field. This follows lead recommendation 8 in the [recording decision response](https://github.com/lagarcess/argus/blob/a1c294319a2c047623b9bbe5bedd36155d2e931d/docs/specs/lanes/financial-recording-decision-response.md).
3. A row seen before is skipped and counted as already imported. "Seen before" means the same file digest and row, or the same row reference on the same account, whether that row is recorded or still in review. Rows that merely look alike, such as two purchases of the same amount on the same day, are asked about and never dropped.
4. A statement's closing balance becomes one balance observation. The person confirms its date, because the kit does not read the statement period. The proof never uses the upload time or today's date as the balance date, as the [reconciliation handoff](https://github.com/lagarcess/argus/blob/a1c294319a2c047623b9bbe5bedd36155d2e931d/docs/specs/argus-account-balance-reconciliation-handoff.md) requires.
5. A row the file marks for the household waits for the person to pick the account. Once confirmed, it counts only in that account's space. A dollar row pointed at a peso account is blocked until a dollar account is picked. No currency is converted.
6. The source file is kept only while its review is open. Cancelling deletes it. Records keep a reference to the file (its digest, its stored name, and the row), never its contents or its original name.
7. Cancelling keeps what was already confirmed and discards the rest. Leaving a review open keeps its drafts, and after the app restarts, choosing the same file adds no second copy.
8. Retrying a confirmation with the same key returns the same records. A confirmation built on a stale preview writes nothing, and a fresh preview then confirms. This matches lead recommendation 9.

## Acceptance matrix

Generated from the committed [proof report](proof-report.json), which also holds what each case observed.

| Case | Group | Claim | Result |
| --- | --- | --- | --- |
| `csv_accepted` | intake | A CSV selected with the file picker is accepted by content. | Passed |
| `pdf_accepted_from_share_extension` | intake | A PDF arriving from a future share extension takes the same intake path. | Passed |
| `empty_file` | intake | An empty file is refused with a recovery step. | Passed |
| `email_with_login_link` | intake | An email that only links to the bank's sign-in page is not an importable statement. | Passed |
| `html_named_as_pdf` | intake | A saved sign-in page named .pdf is judged by content, not by its name. | Passed |
| `excel_workbook` | intake | An Excel workbook is unsupported today and says so. | Passed |
| `ofx_file` | intake | An OFX file is unsupported today and says so. | Passed |
| `image_without_ocr` | intake | A photo is accepted, but no OCR runs, so it reaches review with no rows. | Passed |
| `heic_photo_without_ocr` | intake | An iPhone HEIC photo is recognized as an image and yields no rows. | Passed |
| `pdf_in_unknown_layout` | intake | A text PDF in an unknown layout yields no rows and an explicit error. | Passed |
| `pdf_without_text_layer` | intake | A PDF with no text layer yields no rows and an explicit error. | Passed |
| `csv_with_unknown_header` | intake | A CSV without the supported header yields no rows and an explicit error. | Passed |
| `too_large` | intake | A file over the size limit is refused, and nothing from it is stored or held. | Passed |
| `password_protected_pdf` | intake | A PDF that needs a password to open is refused with a recovery step, and nothing from it is stored or held. | Passed |
| `pdf_with_copy_restriction_only` | intake | An encrypted PDF that opens without a password but forbids copying is accepted and read. | Passed |
| `uncertain_rows_stay_drafts` | review | Clean rows confirm in one batch, and each uncertain row stays a draft with a named reason. | Passed |
| `identical_rows_asked_once` | review | Two identical rows in one file are asked about once, then both confirm as distinct purchases. | Passed |
| `statement_balance_reconciles` | review | A statement's closing balance becomes one observation, needs a person-confirmed date, and reconciles to zero against its rows. | Passed |
| `scanned_image_with_stub` | review | A scanned image with an authored stub standing in for OCR proposes rows, and an unreadable amount stays blocked. | Passed |
| `destination_space_chosen_before_confirming` | review | A household row waits for the person to pick an account, then counts only in that account's space. | Passed |
| `currency_mismatch_destination` | review | A USD row pointed at a DOP account is blocked until the person picks a USD account. | Passed |
| `source_file_visibility` | review | A Household account receives only the row confirmed into it, and records reference the source file without its contents or its original name. | Passed |
| `same_file_from_two_entry_points` | duplicates | The same file selected again from the share extension creates nothing new. | Passed |
| `overlapping_statement` | duplicates | An overlapping statement adds only its new row and its own closing balance. | Passed |
| `manual_entry_then_import` | duplicates | A purchase already entered by hand links to the imported row instead of counting twice. | Passed |
| `same_day_balance_check_hands_off` | review | Untimed rows on the same day as a timed balance check go to account review. | Passed |
| `earlier_day_rows_behind_a_balance_check` | review | Rows dated the day before a confirmed balance check also go to account review. | Known gap |
| `cancel_before_review` | cancellation | Cancelling after choosing a file and before review creates nothing and drops the file. | Passed |
| `cancel_during_review` | cancellation | Cancelling during review records nothing, deletes the stored file, and lets the same file be imported afresh later. | Passed |
| `cancel_after_partial_confirmation` | cancellation | Cancelling after a batch keeps the confirmed records, which still name the file by digest, and discards the unresolved rows and the file. | Passed |
| `pause_and_resume` | cancellation | Leaving a review open keeps its drafts, and after the app restarts the same file adds no second copy. | Passed |
| `retry_with_same_key` | retry | Retrying a confirmation with the same key returns the same records and writes nothing new. | Passed |
| `retry_after_stale_preview` | retry | A confirmation against a stale preview writes nothing, and a fresh preview then confirms. | Passed |
| `unlocked_copy_after_refusal` | retry | After a password-protected file is refused, an unlocked copy imports cleanly with nothing left from the refusal. | Passed |
| `reimport_after_partial_confirmation` | retry | Re-importing after a partial batch re-adds neither confirmed rows nor rows still in review. | Passed |
| `nothing_posts_without_confirmation` | boundary | Import creates drafts only. Records change only when the person confirms. | Passed |

The matrix covers each item the lane names:

- Unsupported and encrypted documents: the intake group and `unlocked_copy_after_refusal`.
- Uncertain rows: `uncertain_rows_stay_drafts` and `scanned_image_with_stub`.
- Duplicates: the duplicates group, `identical_rows_asked_once`, `pause_and_resume`, and `reimport_after_partial_confirmation`.
- Destination account and space: `destination_space_chosen_before_confirming` and `currency_mismatch_destination`.
- Source-file visibility: `source_file_visibility` and the cancellation group.
- Cancellation and retry: their groups.

## Known gap

Pull request 724 at `720aad3fd` asks about untimed rows only when they fall on the same day as a timed balance check. Statement rows dated the day before a confirmed check confirm without review, which the proof observed directly. The recording decision response settles question 3 the other way. Argus asks whether an earlier or same-day purchase was included whenever inclusion is unresolved, and review is not restricted to same-day records. The reconciliation handoff adds that document import must hand off to account review in this case.

The proof records this as `earlier_day_rows_behind_a_balance_check`, expected to fail against the pinned model. It asserts only that each earlier-day row is held for a reason other than a possible duplicate, so it does not presume the issue code pull request 724 will choose.

## What this proof does not show

- **Any real bank's file.** No bank publishes its statement format, and no real statement was used. A real-format test needs separately supplied, authorized input, as the lane requires.
- **Stable row references.** The kit's rows carry stable references, which is what lets an overlapping statement skip its known rows. A real statement may carry no reference, or one that changes between exports. Without one, overlapping rows are asked about as possible duplicates instead of skipped. A bank's row reference should become an identity only after consented samples show that it stays the same across exports.
- **The statement period.** The kit does not read it, so the person confirms the closing balance date.
- **OCR.** No provider is selected. The scanned-image case uses an authored stub in place of OCR output.
- **Modern PDF encryption.** The fixtures use the oldest standard scheme, 40-bit RC4. The proof decides whether a password is needed by asking `pdftotext` to open the file without one. That test should hold for newer schemes, but it is proven here on this one only.
- **Who may see what.** No household permission contract exists. The proof shows what a record carries, not who may read it. Whether a household member may ever open a source file is undecided. The proof's default keeps no file once review ends.
- **Production behavior.** Pull request 724's reference model proves examples, not database locking, row-level security, or retention, as the recording decision response says. The share extension is a label, not an extension.

## Dependencies

| Dependency | State on 2026-09-28 | What waits on it |
| --- | --- | --- |
| Ingestion kit, pull request 709 | Merged | Nothing. Fixtures and parsers are in place. |
| Recording contract, [pull request 724](https://github.com/lagarcess/argus/pull/724) | Draft at `720aad3fd`, under reconciliation | The 21 recording cases, and the known gap |
| Recording decisions and reconciliation handoff, [pull request 727](https://github.com/lagarcess/argus/pull/727) | Open at `a1c294319` | Decisions 3, 7, 8, and 9, the balance-date rule, and the document-import handoff |
| Household permission contract | Absent | Who may see imported records and source files |
| Retention of source files | Undecided | Whether a file outlives its review |
| Transient password entry | Undecided | A recovery path easier than an unlocked copy |
| Upload size limit | Undecided | The 10 MiB assumption |
| OCR provider | Not selected | Photos and scanned PDFs |
| Per-bank parsers | Need consented samples | Any claim about a real bank |
| Native share extension | Not built or assigned | Importing from the share sheet |

Bank integration does not block manual account value. Everything above concerns files a person chooses to share.

## Proposal

When the recording contract is approved for production, the import lane should take this matrix as its acceptance gate and rerun it against the real API and database instead of the reference model. Its first real-bank step is already in the [next assignment](../next-assignment.md). A consenting account holder exports one month in each format their bank offers, following the kit's consent and retention checklist. A format is listed as supported only after a parser for it passes these cases.

Until then, the proof stays documentation. Stop dependent work if another owner takes the lane, if the acceptance surface in pull request 727 changes, or if work would need hosted resources.

## Rerun

The proof needs `pdftotext` from Poppler, as the ingestion kit does. The first command runs the intake cases and reports the recording cases as blocked.

```bash
poetry run python docs/reports/dominican-bank-connectivity/selected-file-import/proof.py --report temp/selected-file-import-report.json
```

To run every case, fetch pull request 724 and extract its pinned reference model.

```bash
git fetch origin pull/724/head
```

```bash
mkdir -p temp/recording-724 && git archive 720aad3fdee1357e3dbe5c928176a6e458b01b0d tests/financial_recording | tar -x -C temp/recording-724
```

```bash
PYTHONPATH=temp/recording-724 poetry run python docs/reports/dominican-bank-connectivity/selected-file-import/proof.py --report temp/selected-file-import-report.json --recording-ref "lagarcess/argus#724 at 720aad3fdee1357e3dbe5c928176a6e458b01b0d"
```

```bash
cmp temp/selected-file-import-report.json docs/reports/dominican-bank-connectivity/selected-file-import/proof-report.json
```

To confirm that the cases can fail, run the breakage check with the same path. It exits with an error if any breakage goes unnoticed.

```bash
PYTHONPATH=temp/recording-724 poetry run python docs/reports/dominican-bank-connectivity/selected-file-import/mutation_check.py
```
