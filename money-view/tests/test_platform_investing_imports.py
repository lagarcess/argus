"""Holding CSV intake shares the bounded parser and preserves import ownership."""

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from faker import Faker
from server.platform import identity, investing, statement_parser
from server.platform.common import Context, PlatformError
from server.store import Store

fake = Faker()
HEADERS = tuple(investing.HoldingCreate.model_fields)


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "holdings.sqlite3", busy_timeout_ms=100)
    identity.initialize(value)
    investing.initialize(value)
    return value


@pytest.fixture
def context():
    return Context("user-demo", "household-demo", "owner", fake.uuid4())


def row(**overrides):
    return {
        "symbol": "ALT-CARD",
        "name": fake.word(),
        "quantity": "1",
        "total_cost": "1200.00",
        "currency": "USD",
        "as_of": investing.FIXTURE_AS_OF.isoformat(),
        **overrides,
    }


def file_content(rows, headers=HEADERS):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def holding_csv(*rows):
    return file_content([[item[key] for key in HEADERS] for item in rows])


@pytest.mark.parametrize("attempt", ["invalid", "blank", "valid"])
def test_every_attempted_row_counts_toward_shared_limit(store, context, attempt):
    invalid = list(row(quantity="invalid").values())
    cells = {"invalid": invalid, "blank": [], "valid": list(row().values())}[attempt]
    content = file_content([cells] * (statement_parser.DEFAULT_LIMITS.max_rows + 1))
    with pytest.raises(PlatformError, match="^import_too_many_rows$"):
        investing.preview_holding_csv(store, context, content)
    with store.connection() as db:
        assert (
            db.execute("SELECT count(*) FROM p_investment_import_previews").fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    ("tail", "code"),
    [
        ('ALT-CARD,"unterminated,1,1200.00,USD,2026-09-20\n', "invalid_csv_quoting"),
        ('ALT-CARD,bad"quote,1,1200.00,USD,2026-09-20\n', "invalid_csv_quoting"),
        ('ALT-CARD,"closed"extra,1,1200.00,USD,2026-09-20\n', "invalid_csv_quoting"),
    ],
)
def test_malformed_quoting_is_a_typed_file_error(store, context, tail, code):
    with pytest.raises(PlatformError, match=f"^{code}$"):
        investing.preview_holding_csv(store, context, ",".join(HEADERS) + "\n" + tail)


@pytest.mark.parametrize("bound", ["bytes", "cell", "columns"])
def test_parser_bounds_apply_before_holding_validation(store, context, bound):
    limits = statement_parser.DEFAULT_LIMITS
    content, code = {
        "bytes": ("é" * (limits.max_bytes // 2 + 1), "import_too_large"),
        "cell": (
            holding_csv(row(name="x" * (limits.max_cell_chars + 1))),
            "import_cell_too_large",
        ),
        "columns": (
            file_content([["x"] * (limits.max_columns + 1)]),
            "import_too_many_columns",
        ),
    }[bound]
    with pytest.raises(PlatformError, match=f"^{code}$"):
        investing.preview_holding_csv(store, context, content)


def test_partial_valid_rows_stay_inert_and_wrong_column_width_is_reported(store, context):
    valid = row(name='Collection, called "keepsakes"\nfrom family')
    content = file_content(
        [[], list(valid.values()), list(row().values())[:-1], [*row().values(), "extra"]]
    )
    before = investing.list_holdings(store, context)
    preview = investing.preview_holding_csv(store, context, content)
    assert preview["valid_count"] == 1
    assert preview["rows"][0]["name"] == valid["name"]
    assert [error["code"] for error in preview["errors"]] == ["invalid_holding_row"] * 2
    assert preview["can_commit"] is False
    assert investing.list_holdings(store, context) == before
    with pytest.raises(PlatformError, match="holding_import_has_errors"):
        investing.commit_holding_import(store, context, preview["id"], fake.uuid4())


def test_duplicates_are_currency_scoped_and_commit_is_owned_and_idempotent(
    store, context
):
    current = investing.list_holdings(store, context)["items"][0]
    shared_symbol = row(symbol=current["symbol"], currency=current["currency"])
    alternative = row(symbol=current["symbol"], currency="EUR")
    preview = investing.preview_holding_csv(
        store, context, holding_csv(shared_symbol, alternative, alternative)
    )
    assert preview["duplicate_count"] == 2
    assert preview["valid_count"] == 1
    assert preview["can_commit"] is True
    other = Context("user-other", "household-other", "owner", fake.uuid4())
    with pytest.raises(PlatformError, match="holding_import_not_found"):
        investing.commit_holding_import(store, other, preview["id"], fake.uuid4())
    key = fake.uuid4()
    receipt = investing.commit_holding_import(store, context, preview["id"], key)
    assert receipt["imported"] == 1
    assert receipt["duplicates"] == 2
    assert investing.commit_holding_import(store, context, preview["id"], key) == receipt
    imported = investing.get_holding(store, context, receipt["holding_ids"][0])
    assert imported["currency"] == alternative["currency"]
    assert imported["total_cost"] == alternative["total_cost"]


def test_parser_runs_before_database_access_and_never_holds_write_lock(
    store, context, monkeypatch
):
    connections = []
    original_connection = store.connection
    parser_calls = []

    @contextmanager
    def traced_connection(*, write=False):
        connections.append(write)
        with original_connection(write=write) as connection:
            yield connection

    def competing_writer():
        with original_connection(write=True) as db:
            db.execute("SELECT 1").fetchone()

    def checked_parser(content, **options):
        assert connections == []
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(competing_writer).result(timeout=2)
        parser_calls.append(content)
        return statement_parser.parse_delimited(content, **options)

    monkeypatch.setattr(store, "connection", traced_connection)
    monkeypatch.setattr(investing, "parse_delimited", checked_parser, raising=False)
    content = holding_csv(row())
    assert investing.preview_holding_csv(store, context, content)["can_commit"] is True
    assert parser_calls == [content]
    assert connections == [False, True]


def test_exact_row_limit_is_accepted_and_blank_lines_remain_ignored(store, context):
    count = statement_parser.DEFAULT_LIMITS.max_rows
    content = file_content([[]] * (count - 1) + [list(row().values())])
    preview = investing.preview_holding_csv(store, context, content)
    assert preview["can_commit"] is True
    assert preview["valid_count"] == 1
    assert preview["rows"][0]["line"] == count + 1


@pytest.mark.parametrize("headers", [HEADERS[:-1], (*HEADERS, "unexpected")])
def test_holding_columns_keep_the_existing_header_error(store, context, headers):
    with pytest.raises(PlatformError, match="^invalid_csv_header$"):
        investing.preview_holding_csv(store, context, file_content([], headers))
