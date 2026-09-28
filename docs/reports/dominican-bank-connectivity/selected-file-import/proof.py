from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tests.synthetic_ingestion.extract import load_input
from tests.synthetic_ingestion.generate import generate

try:
    from tests.financial_recording import derive, model
except ImportError:
    derive = model = None

SIZE_LIMIT = 10 * 1024 * 1024
AST = timezone(timedelta(hours=-4))
CLOCK = datetime(2026, 9, 28, 12, 0, tzinfo=AST)
FIXTURE_PASSWORD = "synthetic-only"
PDF_PAD = bytes.fromhex(
    "28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A"
)
RECOVERY = {
    "empty": "choose_another_file",
    "too_large": "choose_smaller_file",
    "password_protected": "save_unlocked_copy",
    "not_a_statement": "download_statement_file",
    "unsupported_type": "choose_csv_pdf_or_image",
}
SUFFIX = {"pdf": ".pdf", "csv": ".csv", "png": ".png", "jpeg": ".jpg", "heic": ".heic"}
REFERENCE_KEYS = {"digest", "file", "row", "page", "external_id", "entry", "stub_digest"}


@dataclass(frozen=True)
class Selection:
    entry: str
    name: str
    data: bytes


@dataclass(frozen=True)
class Intake:
    status: str
    kind: str | None
    subtype: str | None
    digest: str
    recovery: str | None


def check(selection: Selection) -> Intake:
    status, kind, subtype = _classify(selection.data)
    digest = hashlib.sha256(selection.data).hexdigest()
    return Intake(status, kind, subtype, digest, RECOVERY.get(status))


def _classify(data: bytes) -> tuple[str, str | None, str | None]:
    if not data:
        return "empty", None, None
    if len(data) > SIZE_LIMIT:
        return "too_large", None, None
    if data.startswith(b"%PDF-"):
        locked = b"/Encrypt" in data and pdf_text(data) is None
        return ("password_protected" if locked else "accepted"), "pdf", "pdf"
    image = _image_subtype(data)
    if image:
        return "accepted", "image", image
    if data.startswith(b"PK\x03\x04"):
        return "unsupported_type", None, "zip"
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "unsupported_type", None, None
    head = text.lstrip()[:200].lower()
    if head.startswith(("<!doctype html", "<html")) or _is_email(text):
        return "not_a_statement", None, None
    if head.startswith(("ofxheader", "<ofx")):
        return "unsupported_type", None, "ofx"
    return "accepted", "csv", "csv"


def _image_subtype(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1"):
        return "heic"
    return None


def _is_email(text: str) -> bool:
    header = text.replace("\r\n", "\n").split("\n\n", 1)[0].lower()
    names = {line.split(":", 1)[0] for line in header.splitlines() if ":" in line}
    return {"from", "subject"} <= names or "mime-version" in names


def pdf_text(data: bytes, password: str | None = None) -> str | None:
    command = ["pdftotext", *(["-upw", password] if password else []), "-", "-"]
    result = subprocess.run(command, input=data, capture_output=True, timeout=20)
    return result.stdout.decode("utf-8", "replace") if result.returncode == 0 else None


def extract(
    workdir: Path, selection: Selection, intake: Intake, stub: Path | None = None
):
    path = workdir / f"{intake.digest[:16]}{SUFFIX[intake.subtype]}"
    path.write_bytes(selection.data)
    return path, load_input(path, stub)


@dataclass
class Session:
    id: str
    entry: str
    intake: Intake
    status: str = "checked"
    mode: str | None = None
    errors: list[str] = field(default_factory=list)
    drafts: list[str] = field(default_factory=list)
    already_imported: list[str] = field(default_factory=list)
    balances: dict | None = None
    source: Path | None = None


def blocking(preview) -> list[str]:
    return sorted({item.code for item in preview.issues if item.severity == "blocking"})


class Importer:
    def __init__(self, store, workdir: Path) -> None:
        self.store = store
        self.sources = workdir / "sources"
        self.selections: dict[str, Selection] = {}
        self._ids = itertools.count(1)

    def select(self, selection: Selection) -> Session:
        intake = check(selection)
        session = Session(f"import-{next(self._ids)}", selection.entry, intake)
        if intake.status == "accepted":
            self.selections[session.id] = selection
        else:
            session.status = "refused"
        return session

    def held(self) -> dict[str, list[str]]:
        return {
            "in_memory": sorted(self.selections),
            "on_disk": sorted(path.name for path in self.sources.glob("*")),
        }

    def review(
        self, session: Session, account_map: dict[str, str], stub: Path | None = None
    ) -> Session:
        self.sources.mkdir(exist_ok=True)
        path, loaded = extract(
            self.sources, self.selections.pop(session.id), session.intake, stub
        )
        session.mode, session.errors, session.source = (
            loaded["mode"],
            list(loaded["errors"]),
            path,
        )
        rows = loaded["proposals"]
        for proposal in rows:
            row = proposal["fields"]
            account = (
                account_map.get(row["account"], "")
                if row["destination"] == "personal"
                else ""
            )
            self._add(
                session,
                row["source_id"],
                {
                    "kind": row["kind"],
                    "account_id": account,
                    "amount": row["amount"],
                    "currency": row["currency"],
                    "occurred_on": row["date"],
                },
                {**proposal["source_ref"], "external_id": row["source_id"]},
            )
        if loaded.get("balances") and rows:
            session.balances = dict(loaded["balances"])
            self._add(
                session,
                "closing-balance",
                {
                    "kind": "balance_observation",
                    "account_id": account_map.get(rows[0]["fields"]["account"], ""),
                    "amount": loaded["balances"]["closing"],
                    "as_of": "",
                    "basis": "statement",
                },
                {"digest": session.intake.digest, "file": path.name, "row": "closing"},
            )
        session.status = "in_review"
        return session

    def _add(self, session: Session, label: str, fields: dict, reference: dict) -> None:
        provenance = derive.Provenance(
            "document", CLOCK, {**reference, "entry": session.entry}
        )
        draft = self.store.draft(fields, provenance)
        if "already_recorded" in blocking(self.store.preview(draft.id)):
            self.store.reject(draft.id)
            session.already_imported.append(label)
        else:
            session.drafts.append(draft.id)

    def pending(self, session: Session) -> list[str]:
        drafts = self.store.state.drafts
        return [item for item in session.drafts if drafts[item].status == "proposed"]

    def confirm_ready(self, session: Session, key: str) -> list:
        previews = [self.store.preview(item) for item in self.pending(session)]
        ready = [item for item in previews if not blocking(item)]
        return self.store.confirm_batch(ready, key) if ready else []

    def cancel(self, session: Session) -> None:
        for item in self.pending(session):
            self.store.reject(item)
        self.selections.pop(session.id, None)
        if session.source:
            session.source.unlink(missing_ok=True)
            session.source = None
        session.status = "cancelled"

    def summary(self, session: Session) -> dict[str, int]:
        states = [self.store.state.drafts[item].status for item in session.drafts]
        return {
            "added": states.count("confirmed"),
            "already_imported": len(session.already_imported),
            "unresolved": states.count("proposed"),
            "discarded": states.count("rejected"),
        }


@dataclass
class Env:
    store: object
    importer: Importer
    ids: dict[str, str]
    spaces: dict[str, str]

    def label(self, draft_id: str) -> str:
        reference = self.store.state.drafts[draft_id].provenance.source_ref or {}
        return reference.get("external_id") or str(reference.get("row"))

    def by_label(self, session: Session) -> dict[str, str]:
        return {self.label(item): item for item in session.drafts}

    def scope(self, space: str) -> list[str]:
        return [account for account, owner in self.spaces.items() if owner == space]


def make_env(workdir: Path) -> Env:
    store = model.Store(clock=lambda: CLOCK, ids=itertools.count(1))
    opened = datetime(2026, 9, 1, tzinfo=AST)
    ids, spaces = {}, {}
    for nickname, kind, currency, opening, space in (
        ("Cuenta corriente", "checking", "DOP", "1000.00", "Personal"),
        ("Efectivo", "cash", "DOP", None, "Personal"),
        ("Dolares", "savings", "USD", None, "Personal"),
        ("Cuenta de la casa", "checking", "DOP", None, "Household"),
    ):
        account = store.create_account(
            nickname,
            kind,
            currency,
            opening,
            idempotency_key=f"create:{nickname}",
            as_of=opened if opening else None,
        )
        ids[nickname] = account.id
        spaces[account.id] = space
    return Env(store, Importer(store, workdir), ids, spaces)


def _rc4(key: bytes, data: bytes) -> bytes:
    box = list(range(256))
    j = 0
    for i in range(256):
        j = (j + box[i] + key[i % len(key)]) % 256
        box[i], box[j] = box[j], box[i]
    out = bytearray()
    i = j = 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + box[i]) % 256
        box[i], box[j] = box[j], box[i]
        out.append(byte ^ box[(box[i] + box[j]) % 256])
    return bytes(out)


def encrypt_pdf(
    plain: bytes, user: str, owner: str | None = None, permissions: int = -44
) -> bytes:
    def pad(password: str) -> bytes:
        return (password.encode("latin-1") + PDF_PAD)[:32]

    owner_entry = _rc4(hashlib.md5(pad(owner or user)).digest()[:5], pad(user))
    file_id = hashlib.md5(b"synthetic-encrypted-statement").digest()
    key = hashlib.md5(
        pad(user) + owner_entry + struct.pack("<i", permissions) + file_id
    ).digest()[:5]
    user_entry = _rc4(key, PDF_PAD)
    start = plain.index(b"stream\n", plain.index(b"5 0 obj")) + len(b"stream\n")
    end = plain.index(b"\nendstream", start)
    object_key = hashlib.md5(key + (5).to_bytes(3, "little") + bytes(2)).digest()[:10]
    body = plain[:start] + _rc4(object_key, plain[start:end]) + plain[end:]
    encrypt = (
        f"/Root 1 0 R /Encrypt << /Filter /Standard /V 1 /R 2 /O <{owner_entry.hex()}> "
        f"/U <{user_entry.hex()}> /P {permissions} >> "
        f"/ID [<{file_id.hex()}> <{file_id.hex()}>] >>"
    )
    return body.replace(b"/Root 1 0 R >>", encrypt.encode(), 1)


def simple_pdf(content: bytes) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(b"%d 0 obj\n%s\nendobj\n" % (number, obj))
    start = len(output)
    output.extend(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    output.extend(b"".join(b"%010d 00000 n \n" % offset for offset in offsets))
    output.extend(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, start)
    )
    return bytes(output)


def build_fixtures(directory: Path) -> dict[str, bytes]:
    kit = directory / "kit"
    generate(kit, seed=71)
    files = {path.name: path.read_bytes() for path in sorted(kit.iterdir())}
    workbook = io.BytesIO()
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    files.update(
        {
            "encrypted-statement.pdf": encrypt_pdf(
                files["statement.pdf"], FIXTURE_PASSWORD
            ),
            "copy-restricted.pdf": encrypt_pdf(
                files["statement.pdf"], "", owner=FIXTURE_PASSWORD, permissions=-60
            ),
            "unknown-layout.pdf": simple_pdf(
                b"BT /F1 9 Tf 40 740 Td 14 TL (ESTADO DE CUENTA FICTICIO) Tj T* "
                b"(10/09/2026 SUPERMERCADO FICTICIO 1,234.56) Tj ET"
            ),
            "image-only.pdf": simple_pdf(b"0.8 g 60 560 480 200 re f"),
            "wrong-header.csv": b"fecha,descripcion,monto\n10/09/2026,COMPRA FICTICIA,125.50\n",
            "statement-link.eml": (
                b"From: avisos@banco-ficticio.example\r\nTo: persona@correo.example\r\n"
                b"Subject: Su estado de cuenta esta disponible\r\nMIME-Version: 1.0\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
                b"Inicie sesion para verlo: https://banco-ficticio.example/iniciar\r\n"
            ),
            "login-page.pdf": (
                b"<!DOCTYPE html><html><body><form action='/iniciar'>"
                b"<input name='usuario'></form></body></html>"
            ),
            "movements.xlsx": workbook.getvalue(),
            "movements.ofx": b"OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n\n<OFX></OFX>\n",
            "photo.heic": b"\x00\x00\x00\x18ftypheic" + bytes(24),
            "empty.csv": b"",
        }
    )
    return files


CASES: list[tuple[str, str, bool, str, str | None, object]] = []


def case(
    case_id: str,
    group: str,
    claim: str,
    recording: bool = True,
    known_gap: str | None = None,
):
    def register(function):
        CASES.append((case_id, group, recording, claim, known_gap, function))
        return function

    return register


def intake_case(name: str, entry: str, status: str, kind: str | None = None):
    def run(fx: dict, workdir: Path):
        result = check(Selection(entry, name, fx[name]))
        observed = {
            "status": result.status,
            "kind": result.kind,
            "recovery": result.recovery,
        }
        return result.status == status and result.kind == kind, observed

    return run


def zero_rows_case(name: str, subtype: str):
    def run(fx: dict, workdir: Path):
        selection = Selection("file_picker", name, fx[name])
        result = check(selection)
        if result.status != "accepted" or result.subtype != subtype:
            return False, {"status": result.status, "subtype": result.subtype}
        _, loaded = extract(workdir, selection, result)
        observed = {
            "status": result.status,
            "subtype": result.subtype,
            "mode": loaded["mode"],
            "rows": len(loaded["proposals"]),
            "error": (loaded["errors"] or [""])[0][:80],
        }
        return not loaded["proposals"] and bool(loaded["errors"]), observed

    return run


for spec in (
    (
        "csv_accepted",
        "transactions.csv",
        "file_picker",
        "accepted",
        "csv",
        "A CSV selected with the file picker is accepted by content.",
    ),
    (
        "pdf_accepted_from_share_extension",
        "statement.pdf",
        "share_extension",
        "accepted",
        "pdf",
        "A PDF arriving from a future share extension takes the same intake path.",
    ),
    (
        "empty_file",
        "empty.csv",
        "file_picker",
        "empty",
        None,
        "An empty file is refused with a recovery step.",
    ),
    (
        "email_with_login_link",
        "statement-link.eml",
        "file_picker",
        "not_a_statement",
        None,
        "An email that only links to the bank's sign-in page is not an importable statement.",
    ),
    (
        "html_named_as_pdf",
        "login-page.pdf",
        "file_picker",
        "not_a_statement",
        None,
        "A saved sign-in page named .pdf is judged by content, not by its name.",
    ),
    (
        "excel_workbook",
        "movements.xlsx",
        "file_picker",
        "unsupported_type",
        None,
        "An Excel workbook is unsupported today and says so.",
    ),
    (
        "ofx_file",
        "movements.ofx",
        "file_picker",
        "unsupported_type",
        None,
        "An OFX file is unsupported today and says so.",
    ),
):
    case_id, name, entry, status, kind, claim = spec
    case(case_id, "intake", claim, recording=False)(
        intake_case(name, entry, status, kind)
    )

for spec in (
    (
        "image_without_ocr",
        "receipt.png",
        "png",
        "A photo is accepted, but no OCR runs, so it reaches review with no rows.",
    ),
    (
        "heic_photo_without_ocr",
        "photo.heic",
        "heic",
        "An iPhone HEIC photo is recognized as an image and yields no rows.",
    ),
    (
        "pdf_in_unknown_layout",
        "unknown-layout.pdf",
        "pdf",
        "A text PDF in an unknown layout yields no rows and an explicit error.",
    ),
    (
        "pdf_without_text_layer",
        "image-only.pdf",
        "pdf",
        "A PDF with no text layer yields no rows and an explicit error.",
    ),
    (
        "csv_with_unknown_header",
        "wrong-header.csv",
        "csv",
        "A CSV without the supported header yields no rows and an explicit error.",
    ),
):
    case_id, name, subtype, claim = spec
    case(case_id, "intake", claim, recording=False)(zero_rows_case(name, subtype))


NOTHING_HELD = {"in_memory": [], "on_disk": []}


@case(
    "too_large",
    "intake",
    "A file over the size limit is refused, and nothing from it is stored or held.",
    recording=False,
)
def too_large(fx, workdir):
    importer = Importer(None, workdir)
    session = importer.select(
        Selection("file_picker", "big.csv", b"a" * (SIZE_LIMIT + 1))
    )
    observed = {
        "status": session.intake.status,
        "limit_bytes": SIZE_LIMIT,
        "held": importer.held(),
    }
    return observed == {
        "status": "too_large",
        "limit_bytes": SIZE_LIMIT,
        "held": NOTHING_HELD,
    }, observed


@case(
    "password_protected_pdf",
    "intake",
    "A PDF that needs a password to open is refused with a recovery step, and nothing from it is stored or held.",
    recording=False,
)
def password_protected(fx, workdir):
    importer = Importer(None, workdir)
    session = importer.select(
        Selection("file_picker", "encrypted-statement.pdf", fx["encrypted-statement.pdf"])
    )
    unlocked = pdf_text(fx["encrypted-statement.pdf"], FIXTURE_PASSWORD) or ""
    observed = {
        "status": session.intake.status,
        "recovery": session.intake.recovery,
        "held": importer.held(),
        "fixture_opens_with_its_synthetic_password": "SYNTHETIC STATEMENT ROWS"
        in unlocked,
    }
    return observed == {
        "status": "password_protected",
        "recovery": "save_unlocked_copy",
        "held": NOTHING_HELD,
        "fixture_opens_with_its_synthetic_password": True,
    }, observed


@case(
    "pdf_with_copy_restriction_only",
    "intake",
    "An encrypted PDF that opens without a password but forbids copying is accepted and read.",
    recording=False,
)
def copy_restricted(fx, workdir):
    selection = Selection("file_picker", "copy-restricted.pdf", fx["copy-restricted.pdf"])
    result = check(selection)
    observed = {"status": result.status, "encrypted": b"/Encrypt" in selection.data}
    if result.status == "accepted":
        _, loaded = extract(workdir, selection, result)
        observed |= {"mode": loaded["mode"], "rows": len(loaded["proposals"])}
    return observed == {
        "status": "accepted",
        "encrypted": True,
        "mode": "actual_synthetic_pdf_text",
        "rows": 4,
    }, observed


def _csv_session(
    env: Env,
    entry: str = "file_picker",
    account_map: dict | None = None,
    name: str = "transactions.csv",
):
    session = env.importer.select(Selection(entry, name, FIXTURES["transactions.csv"]))
    mapping = account_map or {
        "cash-dop": env.ids["Efectivo"],
        "cash-usd": env.ids["Dolares"],
    }
    return env.importer.review(session, mapping)


def _statement_session(
    env: Env, name: str = "statement.pdf", entry: str = "share_extension"
):
    session = env.importer.select(Selection(entry, name, FIXTURES[name]))
    return env.importer.review(session, {"statement-dop": env.ids["Cuenta corriente"]})


@case(
    "uncertain_rows_stay_drafts",
    "review",
    "Clean rows confirm in one batch, and each uncertain row stays a draft with a named reason.",
)
def uncertain_rows(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env)
    codes = {
        env.label(item): blocking(env.store.preview(item)) for item in session.drafts
    }
    confirmed = env.importer.confirm_ready(session, "batch-1")
    observed = {
        "blocking": {k: v for k, v in sorted(codes.items()) if v},
        "summary": env.importer.summary(session),
    }
    expected_blocked = {
        "tx-dop-03": ["possible_duplicate"],
        "tx-dop-05": ["counter_account_missing"],
        "tx-currency": ["currency_unsupported"],
        "tx-date": ["date_invalid"],
        "tx-number": ["amount_invalid"],
        "tx-missing": ["field_missing"],
        "tx-household": ["field_missing"],
    }
    return (
        observed["blocking"] == expected_blocked
        and len(confirmed) == 4
        and observed["summary"]
        == {"added": 4, "already_imported": 0, "unresolved": 7, "discarded": 0}
    ), observed


@case(
    "identical_rows_asked_once",
    "review",
    "Two identical rows in one file are asked about once, then both confirm as distinct purchases.",
)
def identical_rows(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env)
    rows = env.by_label(session)
    first = blocking(env.store.preview(rows["tx-dop-02"]))
    second = blocking(env.store.preview(rows["tx-dop-03"]))
    env.store.resolve(rows["tx-dop-03"], distinct=True)
    env.importer.confirm_ready(session, "batch-1")
    states = [env.store.state.drafts[rows[k]].status for k in ("tx-dop-02", "tx-dop-03")]
    observed = {"first": first, "second": second, "after_resolution": states}
    return first == [] and second == ["possible_duplicate"] and states == [
        "confirmed",
        "confirmed",
    ], observed


@case(
    "statement_balance_reconciles",
    "review",
    "A statement's closing balance becomes one observation, needs a person-confirmed date, and reconciles to zero against its rows.",
)
def statement_balance(fx, workdir):
    env = make_env(workdir)
    session = _statement_session(env)
    rows = env.by_label(session)
    closing_codes = blocking(env.store.preview(rows["closing"]))
    env.store.resolve(rows["statement-03"], distinct=True)
    env.store.edit_draft(rows["closing"], as_of="2026-09-30T23:59:59-04:00")
    env.importer.confirm_ready(session, "batch-1")
    checking = env.ids["Cuenta corriente"]
    gaps = derive.observation_gaps(env.store.book, checking)
    activity = [
        r
        for r in derive.live_records(env.store.book)
        if isinstance(r.body, derive.Activity)
    ]
    observed = {
        "closing_before_date": closing_codes,
        "statement_balances": session.balances,
        "gap_minor_units": gaps[-1].amount if gaps else None,
        "activity_records": len(activity),
        "summary": env.importer.summary(session),
    }
    return (
        closing_codes == ["field_missing"]
        and observed["gap_minor_units"] == 0
        and len(activity) == 4
        and observed["summary"]["unresolved"] == 0
    ), observed


@case(
    "scanned_image_with_stub",
    "review",
    "A scanned image with an authored stub standing in for OCR proposes rows, and an unreadable amount stays blocked.",
)
def scanned_image(fx, workdir):
    env = make_env(workdir)
    selection = Selection(
        "file_picker", "scanned-statement.png", FIXTURES["scanned-statement.png"]
    )
    session = env.importer.select(selection)
    stub = workdir / "scanned-statement.png.stub.json"
    stub_json = json.loads(FIXTURES["scanned-statement.png.stub.json"])
    stub_json["source_file"] = f"{session.intake.digest[:16]}.png"
    stub.write_text(json.dumps(stub_json))
    env.importer.review(session, {"scan-dop": env.ids["Cuenta corriente"]}, stub)
    codes = {
        env.label(item): blocking(env.store.preview(item)) for item in session.drafts
    }
    observed = {"mode": session.mode, "blocking": codes}
    return session.mode == "stub" and codes.get("scan-01") == [] and codes.get(
        "scan-02"
    ) == ["field_missing"], observed


@case(
    "destination_space_chosen_before_confirming",
    "review",
    "A household row waits for the person to pick an account, then counts only in that account's space.",
)
def destination_space(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env)
    row = env.by_label(session)["tx-household"]
    before = blocking(env.store.preview(row))
    env.store.edit_draft(row, account_id=env.ids["Cuenta de la casa"])
    env.importer.confirm_ready(session, "batch-1")
    personal = derive.activity_totals(env.store.book, env.scope("Personal"))[
        "DOP"
    ].spending
    household = derive.activity_totals(env.store.book, env.scope("Household"))[
        "DOP"
    ].spending
    observed = {
        "before": before,
        "personal_dop_spending": personal,
        "household_dop_spending": household,
    }
    return before == [
        "field_missing"
    ] and household == 70000 and personal == 10000, observed


@case(
    "currency_mismatch_destination",
    "review",
    "A USD row pointed at a DOP account is blocked until the person picks a USD account.",
)
def currency_mismatch(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(
        env,
        account_map={"cash-dop": env.ids["Efectivo"], "cash-usd": env.ids["Efectivo"]},
    )
    row = env.by_label(session)["tx-usd-01"]
    before = blocking(env.store.preview(row))
    env.store.edit_draft(row, account_id=env.ids["Dolares"])
    after = blocking(env.store.preview(row))
    return before == ["currency_mismatch"] and after == [], {
        "before": before,
        "after": after,
    }


@case(
    "source_file_visibility",
    "review",
    "A Household account receives only the row confirmed into it, and records reference the source file without its contents or its original name.",
)
def source_visibility(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env, name="estado-cuenta-ana-perez.csv")
    row = env.by_label(session)["tx-household"]
    env.store.edit_draft(row, account_id=env.ids["Cuenta de la casa"])
    env.importer.confirm_ready(session, "batch-1")
    household = set(env.scope("Household"))
    keys, values, household_rows = set(), [], []
    for record in derive.live_records(env.store.book):
        for revision in record.revisions:
            reference = revision.provenance.source_ref or {}
            keys |= set(reference)
            values += [str(value) for value in reference.values()]
        if derive.accounts_of(record.body) & household:
            household_rows.append(reference.get("external_id"))
    observed = {
        "record_reference_keys": sorted(keys),
        "original_name_in_records": any("ana-perez" in value for value in values),
        "household_rows": household_rows,
    }
    return (
        keys <= REFERENCE_KEYS
        and not observed["original_name_in_records"]
        and household_rows == ["tx-household"]
    ), observed


@case(
    "same_file_from_two_entry_points",
    "duplicates",
    "The same file selected again from the share extension creates nothing new.",
)
def same_file_twice(fx, workdir):
    env = make_env(workdir)
    first = _csv_session(env, "file_picker")
    second = _csv_session(env, "share_extension")
    env.importer.confirm_ready(first, "batch-1")
    third = _csv_session(env, "file_picker")
    observed = {
        "first_drafts": len(first.drafts),
        "second_new_drafts": len(second.drafts),
        "second_already_imported": len(second.already_imported),
        "third_new_drafts": len(third.drafts),
    }
    return observed == {
        "first_drafts": 11,
        "second_new_drafts": 0,
        "second_already_imported": 11,
        "third_new_drafts": 0,
    }, observed


@case(
    "overlapping_statement",
    "duplicates",
    "An overlapping statement adds only its new row and its own closing balance.",
)
def overlapping_statement(fx, workdir):
    env = make_env(workdir)
    first = _statement_session(env)
    rows = env.by_label(first)
    env.store.resolve(rows["statement-03"], distinct=True)
    env.store.edit_draft(rows["closing"], as_of="2026-09-30T23:59:59-04:00")
    env.importer.confirm_ready(first, "batch-1")
    second = _statement_session(env, "statement-overlap.pdf")
    observed = {
        "already_imported": sorted(second.already_imported),
        "new": sorted(env.label(item) for item in second.drafts),
    }
    return (
        observed["already_imported"]
        == ["statement-01", "statement-02", "statement-03", "statement-04"]
        and observed["new"] == ["closing", "statement-05"]
    ), observed


@case(
    "manual_entry_then_import",
    "duplicates",
    "A purchase already entered by hand links to the imported row instead of counting twice.",
)
def manual_then_import(fx, workdir):
    env = make_env(workdir)
    manual = env.store.draft(
        {
            "kind": "expense",
            "account_id": env.ids["Efectivo"],
            "amount": "125.50",
            "currency": "DOP",
            "occurred_on": "2026-09-10",
        },
        derive.Provenance("manual", CLOCK),
    )
    [record] = env.store.confirm_batch([env.store.preview(manual.id)], "manual-1")
    session = _csv_session(env)
    rows = env.by_label(session)
    codes = blocking(env.store.preview(rows["tx-dop-02"]))
    env.store.resolve(rows["tx-dop-02"], duplicate_of=record.id)
    env.store.resolve(rows["tx-dop-03"], distinct=True)
    env.importer.confirm_ready(session, "batch-1")
    purchases = [
        r
        for r in derive.live_records(env.store.book)
        if isinstance(r.body, derive.Activity)
        and r.body.amount == 12550
        and r.body.kind == "expense"
    ]
    linked = len(env.store.book.records[record.id].linked)
    observed = {
        "import_row_codes": codes,
        "purchases_of_125_50": len(purchases),
        "links_on_manual_record": linked,
    }
    return codes == ["possible_duplicate"] and len(
        purchases
    ) == 2 and linked == 1, observed


@case(
    "same_day_balance_check_hands_off",
    "review",
    "Untimed rows on the same day as a timed balance check go to account review.",
)
def same_day_check(fx, workdir):
    codes = _rows_behind_balance_check(make_env(workdir), "2026-09-10T12:00:00-04:00")
    observed = {"blocking": codes}
    return all("observation_order_unknown" in value for value in codes.values()) and len(
        codes
    ) == 4, observed


@case(
    "earlier_day_rows_behind_a_balance_check",
    "review",
    "Rows dated the day before a confirmed balance check also go to account review.",
    known_gap="Pull request 724 at 720aad3fd asks only about same-day rows. The recording decision response in pull request 727 settles that review is not restricted to same-day records.",
)
def earlier_day_check(fx, workdir):
    codes = _rows_behind_balance_check(make_env(workdir), "2026-09-11T12:00:00-04:00")
    held = {
        label: sorted(set(value) - {"possible_duplicate"})
        for label, value in codes.items()
    }
    observed = {"held_for_review": held}
    return len(held) == 4 and all(held.values()), observed


def _rows_behind_balance_check(env: Env, as_of: str) -> dict[str, list[str]]:
    check_draft = env.store.draft(
        {
            "kind": "balance_observation",
            "account_id": env.ids["Cuenta corriente"],
            "amount": "2000.00",
            "as_of": as_of,
            "basis": "user_check",
        },
        derive.Provenance("manual", CLOCK),
    )
    env.store.confirm_batch([env.store.preview(check_draft.id)], "check-1")
    session = _statement_session(env)
    return {
        env.label(item): blocking(env.store.preview(item))
        for item in session.drafts
        if env.label(item) != "closing"
    }


@case(
    "cancel_before_review",
    "cancellation",
    "Cancelling after choosing a file and before review creates nothing and drops the file.",
)
def cancel_before_review(fx, workdir):
    env = make_env(workdir)
    session = env.importer.select(
        Selection("file_picker", "transactions.csv", FIXTURES["transactions.csv"])
    )
    held_before = env.importer.held()
    env.importer.cancel(session)
    observed = {
        "status": session.status,
        "drafts": len(env.store.state.drafts),
        "held_before": held_before,
        "held_after": env.importer.held(),
    }
    return observed == {
        "status": "cancelled",
        "drafts": 0,
        "held_before": {"in_memory": [session.id], "on_disk": []},
        "held_after": NOTHING_HELD,
    }, observed


@case(
    "cancel_during_review",
    "cancellation",
    "Cancelling during review records nothing, deletes the stored file, and lets the same file be imported afresh later.",
)
def cancel_during_review(fx, workdir):
    env = make_env(workdir)
    records_before = len(env.store.book.records)
    session = _csv_session(env)
    env.store.edit_draft(
        env.by_label(session)["tx-household"], account_id=env.ids["Cuenta de la casa"]
    )
    files_in_review = len(env.importer.held()["on_disk"])
    env.importer.cancel(session)
    held_after = env.importer.held()
    again = _csv_session(env, "share_extension")
    observed = {
        "records_added": len(env.store.book.records) - records_before,
        "summary": env.importer.summary(session),
        "files_in_review": files_in_review,
        "held_after_cancel": held_after,
        "fresh_drafts_on_reimport": len(again.drafts),
    }
    return observed == {
        "records_added": 0,
        "summary": {"added": 0, "already_imported": 0, "unresolved": 0, "discarded": 11},
        "files_in_review": 1,
        "held_after_cancel": NOTHING_HELD,
        "fresh_drafts_on_reimport": 11,
    }, observed


@case(
    "cancel_after_partial_confirmation",
    "cancellation",
    "Cancelling after a batch keeps the confirmed records, which still name the file by digest, and discards the unresolved rows and the file.",
)
def cancel_after_partial(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env)
    confirmed = env.importer.confirm_ready(session, "batch-1")
    env.importer.cancel(session)
    digests = {
        record.revisions[-1].provenance.source_ref.get("digest") for record in confirmed
    }
    observed = {
        "confirmed": len(confirmed),
        "summary": env.importer.summary(session),
        "held_after_cancel": env.importer.held(),
        "records_name_file_by_digest": digests == {session.intake.digest},
    }
    return observed == {
        "confirmed": 4,
        "summary": {"added": 4, "already_imported": 0, "unresolved": 0, "discarded": 7},
        "held_after_cancel": NOTHING_HELD,
        "records_name_file_by_digest": True,
    }, observed


@case(
    "pause_and_resume",
    "cancellation",
    "Leaving a review open keeps its drafts, and after the app restarts the same file adds no second copy.",
)
def pause_resume(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env)
    pending_before = env.importer.pending(session)
    env.importer = Importer(env.store, workdir)
    reopened = _csv_session(env, "share_extension")
    observed = {
        "pending": len(pending_before),
        "pending_kept": env.importer.pending(session) == pending_before,
        "second_copy_drafts": len(reopened.drafts),
        "already_imported": len(reopened.already_imported),
    }
    return observed == {
        "pending": 11,
        "pending_kept": True,
        "second_copy_drafts": 0,
        "already_imported": 11,
    }, observed


@case(
    "retry_with_same_key",
    "retry",
    "Retrying a confirmation with the same key returns the same records and writes nothing new.",
)
def retry_same_key(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env)
    ready = [
        p
        for p in (env.store.preview(i) for i in env.importer.pending(session))
        if not blocking(p)
    ]
    first = env.store.confirm_batch(ready, "batch-1")
    count = len(env.store.book.records)
    second = env.store.confirm_batch(ready, "batch-1")
    observed = {
        "same_records": [r.id for r in first] == [r.id for r in second],
        "records_unchanged": count == len(env.store.book.records),
    }
    return observed == {"same_records": True, "records_unchanged": True}, observed


@case(
    "retry_after_stale_preview",
    "retry",
    "A confirmation against a stale preview writes nothing, and a fresh preview then confirms.",
)
def retry_stale(fx, workdir):
    env = make_env(workdir)
    session = _csv_session(env)
    rows = env.by_label(session)
    stale = env.store.preview(rows["tx-dop-01"])
    env.store.confirm_batch([env.store.preview(rows["tx-dop-02"])], "other")
    count = len(env.store.book.records)
    try:
        env.store.confirm_batch([stale], "retry-1")
        refused = False
    except model.StalePreview:
        refused = True
    written = len(env.store.book.records) - count
    env.store.confirm_batch([env.store.preview(rows["tx-dop-01"])], "retry-2")
    observed = {
        "stale_refused": refused,
        "written_by_stale": written,
        "confirmed_after_refresh": env.store.state.drafts[rows["tx-dop-01"]].status,
    }
    return observed == {
        "stale_refused": True,
        "written_by_stale": 0,
        "confirmed_after_refresh": "confirmed",
    }, observed


@case(
    "unlocked_copy_after_refusal",
    "retry",
    "After a password-protected file is refused, an unlocked copy imports cleanly with nothing left from the refusal.",
)
def unlocked_after_refusal(fx, workdir):
    env = make_env(workdir)
    refused = env.importer.select(
        Selection(
            "file_picker", "encrypted-statement.pdf", FIXTURES["encrypted-statement.pdf"]
        )
    )
    held_after_refusal = env.importer.held()
    unlocked = _statement_session(env, entry="file_picker")
    observed = {
        "refused_status": refused.status,
        "held_after_refusal": held_after_refusal,
        "drafts_from_unlocked_copy": len(unlocked.drafts),
    }
    return observed == {
        "refused_status": "refused",
        "held_after_refusal": NOTHING_HELD,
        "drafts_from_unlocked_copy": 5,
    }, observed


@case(
    "reimport_after_partial_confirmation",
    "retry",
    "Re-importing after a partial batch re-adds neither confirmed rows nor rows still in review.",
)
def reimport_after_partial(fx, workdir):
    env = make_env(workdir)
    first = _csv_session(env)
    env.importer.confirm_ready(first, "batch-1")
    again = _csv_session(env, "share_extension")
    observed = {
        "new_drafts": len(again.drafts),
        "already_imported": len(again.already_imported),
    }
    return observed == {"new_drafts": 0, "already_imported": 11}, observed


@case(
    "nothing_posts_without_confirmation",
    "boundary",
    "Import creates drafts only. Records change only when the person confirms.",
)
def nothing_posts(fx, workdir):
    env = make_env(workdir)
    records_before = len(env.store.book.records)
    _csv_session(env)
    _statement_session(env)
    observed = {"records_added_by_import": len(env.store.book.records) - records_before}
    return observed == {"records_added_by_import": 0}, observed


FIXTURES: dict[str, bytes] = {}


def _digest(paths: list[Path]) -> str:
    return hashlib.sha256(b"".join(path.read_bytes() for path in paths)).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the synthetic selected-file import proof."
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--recording-ref",
        default="",
        help="Where the recording model came from, recorded as given.",
    )
    args = parser.parse_args()
    if not shutil.which("pdftotext"):
        parser.error("pdftotext from poppler is required, as in the ingestion kit")
    recording = None
    if model is not None:
        package = Path(model.__file__).parent
        recording = {
            "ref": args.recording_ref,
            "digest": _digest(
                [package / "model.py", package / "derive.py", package / "money.py"]
            ),
        }
    kit = Path(load_input.__code__.co_filename).parent
    results = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        FIXTURES.update(build_fixtures(root / "fixtures"))
        for case_id, group, needs_recording, claim, known_gap, function in CASES:
            workdir = root / case_id
            workdir.mkdir()
            if needs_recording and model is None:
                status, observed = (
                    "blocked",
                    {
                        "reason": "requires the recording contract's reference model (pull request 724)"
                    },
                )
            else:
                passed, observed = function(FIXTURES, workdir)
                status = "passed" if passed else "failed"
                if known_gap:
                    status = "unexpected_pass" if passed else "known_gap"
            results.append(
                {
                    "case": case_id,
                    "group": group,
                    "claim": claim,
                    "status": status,
                    "observed": observed,
                    **({"known_gap": known_gap} if known_gap else {}),
                }
            )
    report = {
        "format": "selected-file-import-proof-v1",
        "fictional": True,
        "size_limit_bytes": SIZE_LIMIT,
        "recording_model": recording,
        "kit_digest": _digest(sorted(kit.glob("*.py"))),
        "counts": {
            s: sum(r["status"] == s for r in results)
            for s in ("passed", "failed", "blocked", "known_gap", "unexpected_pass")
        },
        "cases": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )
    counts = report["counts"]
    print(
        ", ".join(f"{name.replace('_', ' ')} {count}" for name, count in counts.items())
        + f"; report at {args.report}"
    )
    for item in results:
        if item["status"] != "passed":
            print(f"{item['status'].upper()}: {item['case']}")
    return 1 if counts["failed"] or counts["unexpected_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
