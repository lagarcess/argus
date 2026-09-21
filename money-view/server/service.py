"""Placement lifecycle and atomic dataset publication, with no model calls."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .calculator import (
    CalculationError,
    calculate,
    confirmation_assumptions,
    present_result,
    validate_comparison_inputs,
)
from .fixtures import get_countries, get_examples, get_source_document
from .models import ComparisonResult, PlacementInputs, RateDataset, dataset_content_id
from .providers import FixtureProvider
from .store import Store


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier() -> str:
    return str(uuid4())


def encoded(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def input_identity(inputs: PlacementInputs) -> str:
    document = inputs.model_dump(mode="json")
    document["amount"] = format(inputs.amount.normalize(), "f")
    if inputs.current_annual_rate_pct is not None:
        document["current_annual_rate_pct"] = format(
            inputs.current_annual_rate_pct.normalize(), "f"
        )
    return encoded(document)


class ServiceError(Exception):
    def __init__(self, code: str, status: int = 422, detail: str | None = None):
        self.code, self.status, self.detail = code, status, detail
        super().__init__(code)


class PlacementService:
    def __init__(self, store: Store, household_id: str = "household-demo"):
        self.store = store
        self.household_id = household_id

    def _require_confirmation(self, db, confirmation_id: str) -> None:
        if not db.execute(
            "SELECT 1 FROM p_placement_confirmations WHERE id=? AND household_id=?",
            (confirmation_id, self.household_id),
        ).fetchone():
            raise ServiceError("confirmation_not_found", 404)

    def _require_comparison(self, db, comparison_id: str) -> None:
        if not db.execute(
            "SELECT 1 FROM p_placement_comparisons WHERE id=? AND household_id=?",
            (comparison_id, self.household_id),
        ).fetchone():
            raise ServiceError("comparison_not_found", 404)

    def bootstrap(self) -> None:
        """Recover abandoned jobs at single-owner app startup, then seed if empty."""
        with self.store.connection(write=True) as db:
            interrupted = db.execute(
                "SELECT id FROM load_attempts WHERE status='loading' ORDER BY sequence"
            ).fetchall()
            for attempt in interrupted:
                self._complete_attempt(db, attempt["id"], [], "load_interrupted")
            if db.execute("SELECT 1 FROM datasets LIMIT 1").fetchone():
                return
            previous_seed = db.execute(
                "SELECT 1 FROM load_attempts WHERE id='fixture-bootstrap-v1'"
            ).fetchone()
        load_id = self.begin_load(
            "baseline", load_id=identifier() if previous_seed else "fixture-bootstrap-v1"
        )
        self.finish_load(load_id, FixtureProvider("baseline"))

    def load_status(self, load_id: str) -> dict:
        with self.store.connection() as db:
            attempt = db.execute(
                "SELECT id, status, created_at, completed_at, error_code "
                "FROM load_attempts WHERE id=?",
                (load_id,),
            ).fetchone()
            if attempt is None:
                raise ServiceError("load_not_found", 404)
            return dict(attempt)

    def begin_load(
        self, scenario: str, *, load_id: str | None = None, provider: str = "fixture"
    ) -> str:
        load_id = load_id or identifier()
        with self.store.connection(write=True) as db:
            db.execute(
                "INSERT OR IGNORE INTO load_attempts"
                "(id,provider,scenario,created_at,status) VALUES(?,?,?,?, 'loading')",
                (load_id, provider, scenario, now()),
            )
            existing = db.execute(
                "SELECT * FROM load_attempts WHERE id=?", (load_id,)
            ).fetchone()
            if existing["scenario"] != scenario or existing["provider"] != provider:
                raise ServiceError("load_identity_conflict", 409)
        return load_id

    def finish_load(self, load_id: str, provider) -> None:
        with self.store.connection() as db:
            attempt = db.execute(
                "SELECT * FROM load_attempts WHERE id=?", (load_id,)
            ).fetchone()
            if attempt is None:
                raise ServiceError("load_not_found", 404)
            if attempt["status"] != "loading":
                return
        error = None
        datasets = []
        try:
            for country in get_countries():
                dataset = RateDataset.model_validate(provider.fetch(country["code"]))
                if dataset.country != country["code"]:
                    raise ServiceError("dataset_country_mismatch")
                if dataset.id != dataset_content_id(dataset):
                    raise ServiceError("dataset_identity_mismatch")
                datasets.append(dataset)
        except Exception as exc:
            # A provider boundary records failures without exposing transport secrets.
            error = getattr(exc, "code", "provider_load_failed")
        with self.store.connection(write=True) as db:
            attempt = db.execute(
                "SELECT * FROM load_attempts WHERE id=?", (load_id,)
            ).fetchone()
            if attempt["status"] != "loading":
                return
            newer = db.execute(
                "SELECT 1 FROM load_attempts WHERE sequence>? AND status='succeeded' LIMIT 1",
                (attempt["sequence"],),
            ).fetchone()
            if newer:
                error = "superseded_load"
            if not error:
                current = self._current_datasets(db)
                if any(
                    dataset.country in current
                    and dataset.published_on
                    < self._dataset(db, current[dataset.country]).published_on
                    for dataset in datasets
                ):
                    error = "stale_dataset"
            if not error:
                for dataset in datasets:
                    self._insert_dataset(db, dataset)
                    db.execute(
                        "INSERT INTO load_datasets VALUES(?,?,?)",
                        (load_id, dataset.country, dataset.id),
                    )
            self._complete_attempt(db, load_id, datasets, error)

    def _complete_attempt(
        self, db, load_id: str, datasets: list[RateDataset], error: str | None
    ) -> None:
        completed_at = now()
        for decision in db.execute("SELECT * FROM saved_decisions").fetchall():
            self._check(db, decision, load_id, completed_at, datasets, error)
        db.execute(
            "UPDATE load_attempts SET completed_at=?,status=?,error_code=? WHERE id=?",
            (completed_at, "failed" if error else "succeeded", error, load_id),
        )

    def _insert_dataset(self, db, dataset: RateDataset) -> None:
        document = dataset.model_dump(mode="json")
        rates = document.pop("rates")
        inflation = document.pop("inflation")
        inserted = db.execute(
            "INSERT OR IGNORE INTO datasets VALUES(?,?,?)",
            (dataset.id, dataset.country, encoded(document)),
        )
        if not inserted.rowcount:
            return
        db.executemany(
            "INSERT INTO deposit_rates VALUES(?,?,?)",
            [(dataset.id, row["id"], encoded(row)) for row in rates],
        )
        db.executemany(
            "INSERT INTO inflation_rates VALUES(?,?,?)",
            [(dataset.id, row["currency"], encoded(row)) for row in inflation],
        )

    def _dataset(self, db, dataset_id: str) -> RateDataset:
        row = db.execute(
            "SELECT metadata FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
        if row is None:
            raise ServiceError("dataset_unavailable", 503)
        document = json.loads(row["metadata"])
        document["rates"] = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT document FROM deposit_rates WHERE dataset_id=? ORDER BY id",
                (dataset_id,),
            )
        ]
        document["inflation"] = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT document FROM inflation_rates WHERE dataset_id=? ORDER BY currency",
                (dataset_id,),
            )
        ]
        return RateDataset.model_validate(document)

    def _current_datasets(self, db) -> dict[str, str]:
        rows = db.execute(
            "SELECT ld.country,ld.dataset_id FROM load_datasets ld "
            "JOIN load_attempts la ON la.id=ld.load_id "
            "WHERE la.sequence=(SELECT MAX(sequence) FROM load_attempts WHERE status='succeeded')"
        ).fetchall()
        return {row["country"]: row["dataset_id"] for row in rows}

    def _result(self, db, comparison_id: str) -> ComparisonResult:
        row = db.execute(
            "SELECT document FROM comparisons WHERE id=?", (comparison_id,)
        ).fetchone()
        if row is None:
            raise ServiceError("comparison_not_found", 404)
        return ComparisonResult.model_validate_json(row["document"])

    def _insert_result(
        self, db, result: ComparisonResult, household_id: str | None = None
    ) -> None:
        db.execute(
            "INSERT INTO comparisons VALUES(?,?)", (result.id, result.model_dump_json())
        )
        db.execute(
            "INSERT INTO p_placement_comparisons VALUES(?,?)",
            (result.id, household_id if household_id is not None else self.household_id),
        )

    def create_confirmation(self, inputs: PlacementInputs) -> dict:
        created_at = now()
        expires_at = (
            datetime.fromisoformat(created_at) + timedelta(minutes=30)
        ).isoformat()
        confirmation_id = identifier()
        with self.store.connection(write=True) as db:
            pinned = self._current_datasets(db)
            if inputs.country not in pinned:
                raise ServiceError("unsupported_country")
            dataset = self._dataset(db, pinned[inputs.country])
            validate_comparison_inputs(inputs, dataset)
            db.execute(
                "INSERT INTO confirmations VALUES(?,?,?,?,?,NULL,NULL)",
                (
                    confirmation_id,
                    encoded(inputs.model_dump(mode="json")),
                    encoded(pinned),
                    created_at,
                    expires_at,
                ),
            )
            db.execute(
                "INSERT INTO p_placement_confirmations VALUES(?,?)",
                (confirmation_id, self.household_id),
            )
        return {
            "id": confirmation_id,
            "inputs": inputs.model_dump(mode="json"),
            "dataset_id": dataset.id,
            "created_at": created_at,
            "expires_at": expires_at,
            "assumptions": confirmation_assumptions(inputs),
            "synthetic": dataset.synthetic,
        }

    def compute(self, confirmation_id: str, inputs: PlacementInputs) -> dict:
        input_document = input_identity(inputs)
        with self.store.connection(write=True) as db:
            self._require_confirmation(db, confirmation_id)
            confirmation = db.execute(
                "SELECT * FROM confirmations WHERE id=?", (confirmation_id,)
            ).fetchone()
            if confirmation is None:
                raise ServiceError("confirmation_not_found", 404)
            if confirmation["comparison_id"]:
                if confirmation["consumed_inputs"] != input_document:
                    raise ServiceError("confirmation_consumed", 409)
                return present_result(self._result(db, confirmation["comparison_id"]))
            if datetime.fromisoformat(confirmation["expires_at"]) <= datetime.now(
                timezone.utc
            ):
                raise ServiceError("confirmation_expired", 410)
            pinned = json.loads(confirmation["pinned_datasets"])
            if inputs.country not in pinned:
                raise ServiceError("unsupported_country")
            dataset = self._dataset(db, pinned[inputs.country])
            result = calculate(
                inputs,
                dataset,
                comparison_id=identifier(),
                created_at=datetime.now(timezone.utc),
            )
            self._insert_result(db, result)
            db.execute(
                "UPDATE confirmations SET consumed_inputs=?,comparison_id=? WHERE id=?",
                (input_document, result.id, confirmation_id),
            )
            return present_result(result)

    def save(self, comparison_id: str) -> dict:
        with self.store.connection(write=True) as db:
            self._require_comparison(db, comparison_id)
            self._result(db, comparison_id)
            db.execute(
                "INSERT OR IGNORE INTO saved_decisions VALUES(?,?,?)",
                (identifier(), comparison_id, now()),
            )
            row = db.execute(
                "SELECT id FROM saved_decisions WHERE comparison_id=?", (comparison_id,)
            ).fetchone()
            return self._decision(db, row["id"])

    def _latest(self, db, decision) -> ComparisonResult:
        row = db.execute(
            "SELECT after_id FROM decision_checks WHERE decision_id=? AND status='succeeded' "
            "ORDER BY sequence DESC LIMIT 1",
            (decision["id"],),
        ).fetchone()
        return self._result(db, row["after_id"] if row else decision["comparison_id"])

    def _check(
        self,
        db,
        decision,
        load_id: str,
        created_at: str,
        datasets: list[RateDataset],
        load_error: str | None,
    ) -> None:
        before = self._latest(db, decision)
        after = before
        error = load_error
        reasons = []
        original = self._result(db, decision["comparison_id"])
        reference = before.inputs.current_annual_rate_pct
        if reference is None:
            deposits = [row for row in original.rows if not row.is_baseline]
            reference = max(row.effective_annual_rate_pct for row in deposits)
        if not error:
            dataset = next(
                (value for value in datasets if value.country == before.inputs.country),
                None,
            )
            if dataset is None:
                error = "dataset_unavailable"
            elif dataset.id != before.dataset_id:
                try:
                    after = calculate(
                        before.inputs,
                        dataset,
                        comparison_id=identifier(),
                        created_at=datetime.fromisoformat(created_at),
                    )
                    after = after.model_copy(
                        update={
                            "input_source": original.input_source,
                            "rows": [
                                row.model_copy(update={"source": original.input_source})
                                if row.is_baseline
                                else row
                                for row in after.rows
                            ],
                        }
                    )
                    owner = db.execute(
                        "SELECT household_id FROM p_placement_comparisons WHERE id=?",
                        (original.id,),
                    ).fetchone()
                    self._insert_result(db, after, owner["household_id"])
                    if set(before.winner_ids) != set(after.winner_ids):
                        reasons.append("winner_changed")
                    if (
                        before.inflation.annual_rate_pct
                        <= reference
                        < after.inflation.annual_rate_pct
                    ):
                        reasons.append("inflation_crossed")
                except CalculationError as exc:
                    error = exc.code
        db.execute(
            "INSERT INTO decision_checks(id,decision_id,load_id,created_at,status,before_id,after_id,"
            "reasons,reference_rate_pct,error_code) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                identifier(),
                decision["id"],
                load_id,
                created_at,
                "failed" if error else "succeeded",
                before.id,
                after.id,
                encoded(reasons),
                str(reference),
                error,
            ),
        )

    def _check_document(self, row) -> dict:
        reasons = json.loads(row["reasons"])
        status = (
            "failed"
            if row["status"] == "failed"
            else "changed"
            if reasons
            else "unchanged"
        )
        return {
            "id": row["id"],
            "decision_id": row["decision_id"],
            "load_id": row["load_id"],
            "created_at": row["created_at"],
            "status": status,
            "before_comparison_id": row["before_id"],
            "after_comparison_id": row["after_id"] if status != "failed" else None,
            "reasons": reasons,
            "reference_annual_rate_pct": row["reference_rate_pct"],
            "error_code": row["error_code"],
            "read_at": row["read_at"],
        }

    def _decision(self, db, decision_id: str) -> dict:
        row = db.execute(
            "SELECT sd.* FROM saved_decisions sd JOIN p_placement_comparisons pc "
            "ON pc.id=sd.comparison_id WHERE sd.id=? AND pc.household_id=?",
            (decision_id, self.household_id),
        ).fetchone()
        if row is None:
            raise ServiceError("decision_not_found", 404)
        return {
            "id": row["id"],
            "comparison_id": row["comparison_id"],
            "created_at": row["created_at"],
            "baseline": present_result(self._result(db, row["comparison_id"])),
            "latest": present_result(self._latest(db, row)),
            "checks": [
                self._check_document(check)
                for check in db.execute(
                    "SELECT * FROM decision_checks WHERE decision_id=? ORDER BY sequence",
                    (decision_id,),
                )
            ],
        }

    def decision(self, decision_id: str) -> dict:
        with self.store.connection() as db:
            return self._decision(db, decision_id)

    def _notice(self, db, row) -> dict:
        return {
            "id": row["id"],
            "decision_id": row["decision_id"],
            "created_at": row["created_at"],
            "reasons": json.loads(row["reasons"]),
            "before": present_result(self._result(db, row["before_id"])),
            "after": present_result(self._result(db, row["after_id"])),
            "read_at": row["read_at"],
            "reference_annual_rate_pct": row["reference_rate_pct"],
        }

    def _notices(self, db) -> list[dict]:
        return [
            self._notice(db, row)
            for row in db.execute(
                "SELECT dc.* FROM decision_checks dc JOIN saved_decisions sd "
                "ON sd.id=dc.decision_id JOIN p_placement_comparisons pc ON pc.id=sd.comparison_id "
                "WHERE dc.reasons!='[]' AND pc.household_id=? ORDER BY dc.sequence DESC",
                (self.household_id,),
            )
        ]

    def notices(self) -> dict:
        with self.store.connection() as db:
            return {"items": self._notices(db)}

    def read_notice(self, notice_id: str) -> dict:
        with self.store.connection(write=True) as db:
            row = db.execute(
                "SELECT dc.* FROM decision_checks dc JOIN saved_decisions sd "
                "ON sd.id=dc.decision_id JOIN p_placement_comparisons pc ON pc.id=sd.comparison_id "
                "WHERE dc.id=? AND dc.reasons!='[]' AND pc.household_id=?",
                (notice_id, self.household_id),
            ).fetchone()
            if row is None:
                raise ServiceError("notice_not_found", 404)
            db.execute(
                "UPDATE decision_checks SET read_at=COALESCE(read_at,?) WHERE id=?",
                (now(), notice_id),
            )
            return self._notice(
                db,
                db.execute(
                    "SELECT * FROM decision_checks WHERE id=?", (notice_id,)
                ).fetchone(),
            )

    def _source_status(self, db) -> dict:
        latest = db.execute(
            "SELECT * FROM load_attempts ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        success = db.execute(
            "SELECT * FROM load_attempts WHERE status='succeeded' ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        datasets = self._current_datasets(db)
        state = "unavailable"
        if latest:
            state = (
                "loading"
                if latest["status"] == "loading"
                else (
                    "ready"
                    if latest["status"] == "succeeded"
                    else "stale"
                    if success
                    else "unavailable"
                )
            )
        return {
            "state": state,
            "last_success_at": success["completed_at"] if success else None,
            "last_attempt_at": latest["created_at"] if latest else None,
            "error_code": latest["error_code"] if latest else None,
            "dataset_id": next(iter(datasets.values()), None),
            "load_id": latest["id"] if latest else None,
        }

    def home(self, interpreter_mode: str) -> dict:
        with self.store.connection() as db:
            return {
                "demo": True,
                "interpreter_mode": interpreter_mode,
                "countries": get_countries(),
                "examples": get_examples(),
                "source_status": self._source_status(db),
                "saved": [
                    self._decision(db, row["id"])
                    for row in db.execute(
                        "SELECT sd.id FROM saved_decisions sd JOIN p_placement_comparisons pc "
                        "ON pc.id=sd.comparison_id WHERE pc.household_id=? ORDER BY sd.created_at DESC",
                        (self.household_id,),
                    )
                ],
                "notices": self._notices(db),
            }

    def source(self, source_id: str) -> dict:
        with self.store.connection() as db:
            for dataset_row in db.execute("SELECT id FROM datasets"):
                dataset = self._dataset(db, dataset_row["id"])
                for rate in dataset.rates:
                    if rate.source.id == source_id:
                        return rate.source.model_dump(mode="json") | {
                            "synthetic": dataset.synthetic,
                            "raw_inputs": rate.model_dump(
                                mode="json", exclude={"source", "fee_source"}
                            ),
                        }
                    if rate.fee_source is not None and rate.fee_source.id == source_id:
                        return rate.fee_source.model_dump(mode="json") | {
                            "synthetic": dataset.synthetic,
                            "raw_inputs": {
                                "country": rate.country,
                                "currency": rate.currency,
                                "annual_fee": str(rate.annual_fee),
                            },
                        }
                for inflation in dataset.inflation:
                    if inflation.source.id == source_id:
                        return inflation.source.model_dump(mode="json") | {
                            "synthetic": dataset.synthetic,
                            "raw_inputs": inflation.model_dump(
                                mode="json", exclude={"source"}
                            ),
                        }
        document = get_source_document(source_id)
        if document is None:
            raise ServiceError("source_not_found", 404)
        return document
