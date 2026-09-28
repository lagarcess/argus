from __future__ import annotations

import argparse
import contextlib
import importlib.util
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "proof", Path(__file__).with_name("proof.py")
)
proof = importlib.util.module_from_spec(spec)
sys.modules["proof"] = proof
spec.loader.exec_module(proof)


def run(case_ids: set[str]) -> dict[str, bool]:
    results = {}
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        proof.FIXTURES.clear()
        proof.FIXTURES.update(proof.build_fixtures(root / "fixtures"))
        for case_id, _, _, _, function in proof.CASES:
            if case_id in case_ids:
                workdir = root / case_id
                workdir.mkdir()
                results[case_id] = proof.run_case(function, workdir)[0]
    return results


@contextlib.contextmanager
def patched(changes):
    originals = [(target, name, getattr(target, name)) for target, name, _ in changes]
    for target, name, replacement in changes:
        setattr(target, name, replacement(getattr(target, name)))
    try:
        yield
    finally:
        for target, name, original in originals:
            setattr(target, name, original)


def ignore_encryption(original):
    def classify(data):
        if data.startswith(b"%PDF-"):
            return "accepted", "pdf", "pdf"
        return original(data)

    return classify


def refuse_every_encrypted_pdf(original):
    def classify(data):
        if data.startswith(b"%PDF-") and b"/Encrypt" in data:
            return "password_protected", "pdf", "pdf"
        return original(data)

    return classify


def keep_duplicates(original):
    def add(self, session, label, fields, reference):
        provenance = proof.derive.Provenance(
            "document", proof.CLOCK, {**reference, "entry": session.entry}
        )
        session.drafts.append(self.store.draft(fields, provenance).id)

    return add


def answer_for_the_person(original):
    def add(self, session, label, fields, reference):
        before = len(session.drafts)
        original(self, session, label, fields, reference)
        account = fields.get("account_id")
        if (
            len(session.drafts) > before
            and account
            and fields["kind"] != "balance_observation"
        ):
            anchors = proof.derive.anchors(self.store.book, account)
            self.store.resolve(
                session.drafts[-1], answers={record.id: "included" for record in anchors}
            )

    return add


def stop_asking(original):
    def review(state, draft, tz):
        body, found = original(state, draft, tz)
        return body, tuple(item for item in found if item.code != "inclusion_unanswered")

    return review


def cancel_without_reject(original):
    def cancel(self, session):
        self.selections.pop(session.id, None)
        self._release(session)
        session.status = "cancelled"

    return cancel


def cancel_keeps_file(original):
    def cancel(self, session):
        for item in self.pending(session.intake.digest):
            self.store.reject(item)
        self.selections.pop(session.id, None)
        session.status = "cancelled"

    return cancel


def completion_keeps_file(original):
    def confirm_ready(self, session, key):
        previews = [
            self.store.preview(item) for item in self.pending(session.intake.digest)
        ]
        ready = [item for item in previews if not proof.blocking(item)]
        return self.store.confirm_batch(ready, key) if ready else []

    return confirm_ready


def remember_reviews(original):
    def review(self, session, account_map, stub=None):
        self.__dict__.setdefault("seen", set()).add(session.intake.digest)
        return original(self, session, account_map, stub)

    return review


def only_remembered_reviews(original):
    def open_reviews(self):
        seen = self.__dict__.get("seen", set())
        return {digest: ids for digest, ids in original(self).items() if digest in seen}

    return open_reviews


def store_under_original_name(original):
    def extract(workdir, selection, intake, stub=None):
        path = workdir / selection.name
        path.write_bytes(selection.data)
        return path, proof.load_input(path, stub)

    return extract


def hold_refused(original):
    def select(self, selection):
        session = original(self, selection)
        self.selections[session.id] = selection
        return session

    return select


def mutations():
    balance_checks = {
        "same_day_balance_check_hands_off",
        "earlier_day_rows_behind_a_balance_check",
    }
    return (
        (
            "encryption ignored",
            [(proof, "_classify", ignore_encryption)],
            {"password_protected_pdf"},
        ),
        (
            "every encrypted PDF refused",
            [(proof, "_classify", refuse_every_encrypted_pdf)],
            {"pdf_with_copy_restriction_only"},
        ),
        (
            "duplicates kept",
            [(proof.Importer, "_add", keep_duplicates)],
            {
                "same_file_from_two_entry_points",
                "overlapping_statement",
                "pause_and_resume",
                "reimport_after_partial_confirmation",
            },
        ),
        (
            "importer answers balance-check questions for the person",
            [(proof.Importer, "_add", answer_for_the_person)],
            balance_checks,
        ),
        (
            "recording model stops asking about activity behind a check",
            [(proof.model, "review", stop_asking)],
            balance_checks,
        ),
        (
            "cancel keeps drafts",
            [(proof.Importer, "cancel", cancel_without_reject)],
            {"cancel_during_review", "cancel_after_partial_confirmation"},
        ),
        (
            "cancel keeps the stored file",
            [(proof.Importer, "cancel", cancel_keeps_file)],
            {"cancel_during_review", "cancel_after_partial_confirmation"},
        ),
        (
            "completed review keeps the stored file",
            [(proof.Importer, "confirm_ready", completion_keeps_file)],
            {"completed_review_deletes_the_file"},
        ),
        (
            "open reviews tracked only in memory",
            [
                (proof.Importer, "review", remember_reviews),
                (proof.Importer, "open_reviews", only_remembered_reviews),
            ],
            {"pause_and_resume"},
        ),
        (
            "file stored under its original name",
            [(proof, "extract", store_under_original_name)],
            {"source_file_visibility"},
        ),
        (
            "refused file held",
            [(proof.Importer, "select", hold_refused)],
            {"too_large", "password_protected_pdf", "unlocked_copy_after_refusal"},
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Break the selected-file import proof on purpose and confirm its cases fail."
    )
    parser.parse_args()
    if proof.model is None:
        parser.error("put pull request 724's tests/financial_recording on PYTHONPATH")
    ok = True
    for label, changes, case_ids in mutations():
        with patched(changes):
            results = run(case_ids)
        caught = not any(results.values())
        ok &= caught
        print(f"{'caught' if caught else 'MISSED'}: {label} {sorted(results)}")
    baseline = run({case_id for case_id, *_ in proof.CASES})
    clean = all(baseline.values())
    ok &= clean
    print(f"unbroken: {len(baseline)} cases, all pass {clean}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
