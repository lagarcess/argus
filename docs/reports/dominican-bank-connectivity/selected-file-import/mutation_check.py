from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
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
        for case_id, _, _, _, _, function in proof.CASES:
            if case_id in case_ids:
                workdir = root / case_id
                workdir.mkdir()
                results[case_id] = bool(function(proof.FIXTURES, workdir)[0])
    return results


@contextlib.contextmanager
def patched(target, name: str, replacement):
    original = getattr(target, name)
    setattr(target, name, replacement(original))
    try:
        yield
    finally:
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


def cancel_without_reject(original):
    def cancel(self, session):
        self.selections.pop(session.id, None)
        if session.source:
            session.source.unlink(missing_ok=True)
            session.source = None
        session.status = "cancelled"

    return cancel


def cancel_keeps_file(original):
    def cancel(self, session):
        for item in self.pending(session):
            self.store.reject(item)
        self.selections.pop(session.id, None)
        session.status = "cancelled"

    return cancel


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


def close_known_gap(original):
    def rows(env, as_of):
        return {
            label: sorted(set(codes) | {"observation_order_unknown"})
            for label, codes in original(env, as_of).items()
        }

    return rows


MUTATIONS = (
    (
        "encryption ignored",
        proof,
        "_classify",
        ignore_encryption,
        {"password_protected_pdf"},
    ),
    (
        "every encrypted PDF refused",
        proof,
        "_classify",
        refuse_every_encrypted_pdf,
        {"pdf_with_copy_restriction_only"},
    ),
    (
        "duplicates kept",
        proof.Importer,
        "_add",
        keep_duplicates,
        {
            "same_file_from_two_entry_points",
            "overlapping_statement",
            "pause_and_resume",
            "reimport_after_partial_confirmation",
        },
    ),
    (
        "cancel keeps drafts",
        proof.Importer,
        "cancel",
        cancel_without_reject,
        {"cancel_during_review", "cancel_after_partial_confirmation"},
    ),
    (
        "cancel keeps the stored file",
        proof.Importer,
        "cancel",
        cancel_keeps_file,
        {"cancel_during_review", "cancel_after_partial_confirmation"},
    ),
    (
        "file stored under its original name",
        proof,
        "extract",
        store_under_original_name,
        {"source_file_visibility"},
    ),
    (
        "refused file held",
        proof.Importer,
        "select",
        hold_refused,
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
    for label, target, name, replacement, case_ids in MUTATIONS:
        with patched(target, name, replacement):
            results = run(case_ids)
        caught = not any(results.values())
        ok &= caught
        print(f"{'caught' if caught else 'MISSED'}: {label} {sorted(results)}")
    gaps = {case_id for case_id, *_, known_gap, _ in proof.CASES if known_gap}
    baseline = run({case_id for case_id, *_ in proof.CASES})
    clean = all(passed for case_id, passed in baseline.items() if case_id not in gaps)
    gaps_open = not any(baseline[case_id] for case_id in gaps)
    ok &= clean and gaps_open
    print(
        f"unbroken: {len(baseline)} cases, others pass {clean}, known gaps fail {gaps_open}"
    )
    with (
        tempfile.TemporaryDirectory() as folder,
        patched(proof, "_rows_behind_balance_check", close_known_gap),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        sys.argv = ["proof.py", "--report", str(Path(folder) / "report.json")]
        closed_exit = proof.main()
    ok &= closed_exit == 1
    print(f"a closed known gap makes the proof exit {closed_exit}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
