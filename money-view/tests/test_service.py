from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from server.fixtures import get_countries, get_examples
from server.models import PlacementInputs
from server.providers import FixtureProvider
from server.service import PlacementService, ServiceError
from server.store import Store


@pytest.fixture
def service(tmp_path):
    value = PlacementService(Store(tmp_path / "clara.sqlite3"))
    value.bootstrap()
    return value


@pytest.fixture
def inputs():
    return PlacementInputs.model_validate(get_examples()[0]["inputs"])


def saved(service, inputs):
    confirmation = service.create_confirmation(inputs)
    result = service.compute(confirmation["id"], inputs)
    return service.save(result["id"])


def load(service, scenario, load_id=None):
    identity = service.begin_load(scenario, load_id=load_id)
    service.finish_load(identity, FixtureProvider(scenario))
    return identity


def test_complete_flow_is_persistent_and_idempotent(service, inputs):
    confirmation = service.create_confirmation(inputs)
    with service.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0] == 0
    result = service.compute(confirmation["id"], inputs)
    assert result["inputs"]["amount"] == "250000.00"
    assert service.compute(confirmation["id"], inputs) == result
    reformatted = inputs.model_copy(
        update={
            "amount": Decimal("250000.00"),
            "current_annual_rate_pct": Decimal("5.250"),
        }
    )
    assert service.compute(confirmation["id"], reformatted) == result
    decision = service.save(result["id"])
    assert service.save(result["id"]) == decision
    reopened = PlacementService(Store(service.store.path))
    reopened.bootstrap()
    assert reopened.decision(decision["id"]) == decision
    assert reopened.home("fixture")["source_status"]["state"] == "ready"
    with service.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM load_attempts").fetchone()[0] == 1


def test_edits_use_pinned_dataset_and_consumed_confirmation_rejects_new_body(
    service, inputs
):
    confirmation = service.create_confirmation(inputs)
    load(service, "leader_changed")
    edited = inputs.model_copy(update={"horizon_days": 365})
    result = service.compute(confirmation["id"], edited)
    assert result["dataset_id"] == confirmation["dataset_id"]
    assert result["inputs"]["horizon_days"] == 365
    with pytest.raises(ServiceError, match="confirmation_consumed"):
        service.compute(confirmation["id"], inputs)


def test_edit_country_uses_original_publication_bundle(service, inputs):
    confirmation = service.create_confirmation(inputs)
    second = PlacementInputs.model_validate(get_examples()[1]["inputs"])
    original = service.create_confirmation(second)
    load(service, "leader_changed")
    result = service.compute(confirmation["id"], second)
    assert result["inputs"]["country"] == "NZ"
    assert result["dataset_id"] == original["dataset_id"]


def test_expiry_and_unknown_confirmation_are_rejected(service, inputs):
    confirmation = service.create_confirmation(inputs)
    with service.store.connection(write=True) as db:
        db.execute(
            "UPDATE confirmations SET expires_at=? WHERE id=?",
            (
                (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
                confirmation["id"],
            ),
        )
    with pytest.raises(ServiceError, match="confirmation_expired"):
        service.compute(confirmation["id"], inputs)
    with pytest.raises(ServiceError, match="confirmation_not_found"):
        service.compute("missing", inputs)


def test_unchanged_checks_are_silent_and_changed_notice_preserves_receipts(
    service, inputs
):
    decision = saved(service, inputs)
    load(service, "same_winner", "same-logical-load")
    load(service, "same_winner", "same-logical-load")
    after_same = service.decision(decision["id"])
    assert len(after_same["checks"]) == 1
    assert after_same["checks"][0]["status"] == "unchanged"
    assert service.notices() == {"items": []}
    load(service, "leader_changed")
    notice = service.notices()["items"][0]
    assert notice["reasons"] == ["winner_changed"]
    assert notice["before"] == after_same["latest"]
    latest = service.decision(decision["id"])
    assert notice["after"] == latest["latest"]
    assert latest["baseline"] == decision["baseline"]
    first_read = service.read_notice(notice["id"])
    assert first_read["read_at"] is not None
    assert service.read_notice(notice["id"]) == first_read


def test_inflation_crossing_records_personal_reference(service, inputs):
    decision = saved(service, inputs)
    load(service, "inflation_crossed")
    notice = service.notices()["items"][0]
    assert notice["reasons"] == ["inflation_crossed"]
    assert notice["reference_annual_rate_pct"] == "5.25"
    assert notice["before"] == decision["baseline"]
    assert (
        notice["after"]["inflation"]["annual_rate_pct"]
        != notice["before"]["inflation"]["annual_rate_pct"]
    )


def test_failed_and_partial_loads_retain_last_good_results(service, inputs):
    decision = saved(service, inputs)
    original_status = service.home("fixture")["source_status"]

    class PartialProvider:
        def fetch(self, country):
            if country == "NZ":
                raise ValueError("unpublishable second country")
            return FixtureProvider("leader_changed").fetch(country)

    attempt = service.begin_load("partial")
    service.finish_load(attempt, PartialProvider())
    load(service, "failure")
    after = service.decision(decision["id"])
    assert after["latest"] == decision["baseline"]
    assert [check["status"] for check in after["checks"]] == ["failed", "failed"]
    status = service.home("fixture")["source_status"]
    assert status["state"] == "stale"
    assert status["dataset_id"] == original_status["dataset_id"]
    assert status["last_success_at"] == original_status["last_success_at"]
    assert service.notices() == {"items": []}


def test_late_load_cannot_replace_newer_publication(service, inputs):
    decision = saved(service, inputs)
    old = service.begin_load("same_winner")
    load(service, "leader_changed")
    new_latest = service.decision(decision["id"])["latest"]
    service.finish_load(old, FixtureProvider("same_winner"))
    after = service.decision(decision["id"])
    assert after["latest"] == new_latest
    assert after["checks"][-1]["error_code"] == "superseded_load"
    assert service.home("fixture")["source_status"]["state"] == "ready"
    assert len(service.notices()["items"]) == 1


def test_concurrent_compute_and_load_retries_have_one_result_each(service, inputs):
    confirmation = service.create_confirmation(inputs)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: service.compute(confirmation["id"], inputs), range(4))
        )
    assert len({result["id"] for result in results}) == 1
    decision = service.save(results[0]["id"])
    attempt = service.begin_load("leader_changed")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda _: service.finish_load(attempt, FixtureProvider("leader_changed")),
                range(4),
            )
        )
    after = service.decision(decision["id"])
    assert len(after["checks"]) == 1
    assert after["checks"][0]["status"] == "changed"
    assert len(service.notices()["items"]) == 1


def test_load_identity_cannot_change_scenario(service):
    service.begin_load("same_winner", load_id="stable")
    with pytest.raises(ServiceError, match="load_identity_conflict"):
        service.begin_load("leader_changed", load_id="stable")


def test_new_attempt_with_older_publication_cannot_roll_back_data(service, inputs):
    decision = saved(service, inputs)
    load(service, "leader_changed")
    accepted = service.decision(decision["id"])["latest"]
    load(service, "same_winner")
    after = service.decision(decision["id"])
    assert after["latest"] == accepted
    assert after["checks"][-1]["error_code"] == "stale_dataset"
    assert service.home("fixture")["source_status"]["state"] == "stale"
    assert len(service.notices()["items"]) == 1


def test_unchanged_content_still_records_check_and_loading_state(service, inputs):
    decision = saved(service, inputs)
    attempt = service.begin_load("baseline")
    assert service.home("fixture")["source_status"]["state"] == "loading"
    service.finish_load(attempt, FixtureProvider("baseline"))
    after = service.decision(decision["id"])
    assert after["latest"] == decision["baseline"]
    assert len(after["checks"]) == 1
    assert after["checks"][0]["status"] == "unchanged"
    assert after["checks"][0]["load_id"] == attempt


def test_changed_tied_winner_set_including_cash_produces_notice(service, inputs):
    from server.models import dataset_content_id

    decision = saved(service, inputs)

    class TiedProvider:
        def fetch(self, country):
            dataset = FixtureProvider("baseline").fetch(country)
            rates = [
                rate.model_copy(
                    update={
                        "annual_rate_pct": inputs.current_annual_rate_pct,
                        "annual_fee": None,
                        "fee_source": None,
                    }
                )
                for rate in dataset.rates
            ]
            result = dataset.model_copy(update={"rates": rates})
            return result.model_copy(update={"id": dataset_content_id(result)})

    attempt = service.begin_load("tied")
    service.finish_load(attempt, TiedProvider())
    latest = service.decision(decision["id"])["latest"]
    assert set(latest["winner_ids"]) == {
        "cash",
        "deposit:do-savings",
        "deposit:do-certificate-180",
    }
    assert service.notices()["items"][0]["reasons"] == ["winner_changed"]


def test_failed_recheck_retains_previous_result_and_records_error(service, inputs):
    from server.models import dataset_content_id

    decision = saved(service, inputs)

    class ExpensiveProvider:
        def fetch(self, country):
            dataset = FixtureProvider("baseline").fetch(country)
            fee_receipt = next(
                rate.fee_source for rate in dataset.rates if rate.fee_source is not None
            )
            rates = [
                rate.model_copy(
                    update={
                        "annual_fee": Decimal("1000000000"),
                        "fee_source": fee_receipt,
                    }
                )
                for rate in dataset.rates
            ]
            result = dataset.model_copy(update={"rates": rates})
            return result.model_copy(update={"id": dataset_content_id(result)})

    attempt = service.begin_load("fee-change")
    service.finish_load(attempt, ExpensiveProvider())
    after = service.decision(decision["id"])
    assert after["latest"] == decision["baseline"]
    assert after["checks"][0]["status"] == "failed"
    assert after["checks"][0]["error_code"] == "nonpositive_end_value"
    assert service.notices() == {"items": []}


def test_missing_personal_rate_uses_fixed_saved_leading_deposit_reference(
    service, inputs
):
    inputs = inputs.model_copy(update={"current_annual_rate_pct": None})
    decision = saved(service, inputs)
    load(service, "same_winner")
    load(service, "leader_changed")
    checks = service.decision(decision["id"])["checks"]
    reference = max(
        Decimal(row["effective_annual_rate_pct"])
        for row in decision["baseline"]["rows"]
        if not row["is_baseline"]
    )
    assert Decimal(checks[0]["reference_annual_rate_pct"]) == reference
    assert Decimal(checks[1]["reference_annual_rate_pct"]) == reference


@pytest.mark.parametrize(
    "current_rate,source_kind", [(Decimal("5.25"), "user"), (None, "assumption")]
)
def test_recheck_preserves_original_confirmation_receipts(
    service, inputs, monkeypatch, current_rate, source_kind
):
    inputs = inputs.model_copy(update={"current_annual_rate_pct": current_rate})
    decision = saved(service, inputs)
    original = decision["baseline"]
    recorded_at = datetime.fromisoformat(
        original["input_source"]["recorded_on"].replace("Z", "+00:00")
    )
    next_day = recorded_at + timedelta(days=1)
    monkeypatch.setattr("server.service.now", lambda: next_day.isoformat())
    load(service, "leader_changed")
    latest = service.decision(decision["id"])["latest"]
    assert latest["created_at"][:10] == next_day.date().isoformat()
    assert latest["input_source"]["kind"] == source_kind
    assert latest["input_source"] == original["input_source"]
    original_cash = next(row for row in original["rows"] if row["is_baseline"])
    latest_cash = next(row for row in latest["rows"] if row["is_baseline"])
    assert latest_cash["source"] == original_cash["source"]
    assert (
        service.notices()["items"][0]["after"]["input_source"] == original["input_source"]
    )


def test_bootstrap_is_atomic_across_workers(tmp_path):
    from threading import Barrier

    from server.platform.runtime import initialize

    store = Store(tmp_path / "concurrent-seed.sqlite")
    initialize(store)
    barrier = Barrier(4)

    def start_worker(_):
        service = PlacementService(store)
        barrier.wait()
        service.bootstrap()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(start_worker, range(4)))
    with store.connection() as db:
        attempts = db.execute("SELECT status FROM load_attempts").fetchall()
        assert [row["status"] for row in attempts] == ["succeeded"]
        assert db.execute("SELECT COUNT(*) FROM load_datasets").fetchone()[0] == len(
            get_countries()
        )


@pytest.mark.parametrize("state", ["queued", "running", "expired"])
def test_startup_preserves_queue_owned_loads_and_recovers_legacy_orphans(service, state):
    from server.platform.jobs_runtime import claim, enqueue_job
    from server.platform.runtime import initialize

    initialize(service.store)
    job = enqueue_job(
        service.store,
        None,
        "deposit_load",
        {"scenario": "leader_changed", "load_id": "queue-owned"},
        "queue-owned",
    )
    if state != "queued":
        claimed = claim(service.store)
        assert claimed["id"] == job["id"]
        if state == "expired":
            with service.store.connection(write=True) as db:
                db.execute(
                    "UPDATE p_runtime_jobs SET lease_until=0 WHERE id=?", (job["id"],)
                )
    orphan = service.begin_load("baseline", load_id="legacy-orphan")
    service.bootstrap()
    assert service.load_status("queue-owned")["status"] == "loading"
    assert service.load_status(orphan)["error_code"] == "load_interrupted"


def test_empty_startup_preserves_owned_seed_without_publishing_over_it(tmp_path):
    from server.platform.jobs_runtime import enqueue_job, worker_tick
    from server.platform.runtime import initialize

    store = Store(tmp_path / "owned-seed.sqlite")
    initialize(store)
    enqueue_job(
        store,
        None,
        "deposit_load",
        {"scenario": "baseline", "load_id": "owned-seed"},
        "owned-seed",
    )
    service = PlacementService(store)
    service.bootstrap()
    assert service.load_status("owned-seed")["status"] == "loading"
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM load_attempts").fetchone()[0] == 1
    assert worker_tick(store)["status"] == "succeeded"
    assert service.home("fixture")["source_status"]["state"] == "ready"


def test_terminal_queue_failure_records_domain_failure_atomically(service, inputs):
    from server.platform.jobs_runtime import claim, enqueue_job, fail
    from server.platform.runtime import initialize

    initialize(service.store)
    decision = saved(service, inputs)
    enqueue_job(
        service.store,
        None,
        "deposit_load",
        {"scenario": "leader_changed", "load_id": "failed-job"},
        "failed-job",
    )
    job = claim(service.store)
    assert fail(service.store, job, "job_failed")
    assert service.load_status("failed-job")["error_code"] == "job_failed"
    service.fail_load("failed-job", "another-failure")
    after = service.decision(decision["id"])
    assert after["latest"] == decision["baseline"]
    assert after["checks"] == []
    assert service.load_status("failed-job")["recheck_status"] == "failed"


def test_notice_summary_pages_and_counts_owned_dated_sources(service, inputs):
    first = saved(service, inputs)
    second = saved(service, inputs.model_copy(update={"amount": Decimal("500000")}))
    other = PlacementService(service.store, household_id="household-other")
    saved(other, inputs)
    load(service, "leader_changed")
    summary = service.notice_summaries(limit=1)
    assert summary["total"] == summary["unread_count"] == 2
    assert len(summary["items"]) == 1
    item = summary["items"][0]
    assert item["decision_id"] in {first["id"], second["id"]}
    assert all(
        source["published_on"] and source["kind"] == "synthetic"
        for source in item["source_dates"]
    )
    assert "before" not in item and "after" not in item
    service.read_notice(item["id"])
    next_page = service.notice_summaries(limit=1, offset=1)
    assert next_page["unread_count"] == 1
    assert next_page["items"][0]["id"] != item["id"]
    assert other.notice_summaries()["total"] == 1
    with pytest.raises(ServiceError, match="invalid_notice_page"):
        service.notice_summaries(limit=101)


def test_rechecks_resume_committed_batches_without_refetch_or_duplicate_checks(
    service, inputs, monkeypatch
):
    import server.service as module

    monkeypatch.setattr(module, "RECHECK_BATCH_SIZE", 2)
    decisions = [
        saved(service, inputs.model_copy(update={"amount": Decimal(1000 + index)}))
        for index in range(5)
    ]
    load_id = service.begin_load("leader_changed")
    real_batch = service._recheck_batch

    def crash_after_commit(*args):
        assert real_batch(*args)
        raise RuntimeError("simulated worker exit after committed batch")

    monkeypatch.setattr(service, "_recheck_batch", crash_after_commit)
    with pytest.raises(RuntimeError, match="simulated worker exit"):
        service.finish_load(load_id, FixtureProvider("leader_changed"))
    assert service.load_status(load_id)["status"] == "succeeded"
    assert service.load_status(load_id)["checked_count"] == 2
    assert service.load_status(load_id)["recheck_status"] == "pending"

    class NoFetch:
        def fetch(self, country):
            pytest.fail("An already-published load must resume its pinned data")

    reopened = PlacementService(service.store)
    reopened.finish_load(load_id, NoFetch())
    assert reopened.load_status(load_id)["recheck_status"] == "completed"
    assert reopened.load_status(load_id)["checked_count"] == len(decisions)
    for decision in decisions:
        after = reopened.decision(decision["id"])
        assert len(after["checks"]) == 1
        assert after["baseline"] == decision["baseline"]


def test_new_publication_supersedes_pending_rechecks_without_rollback(
    service, inputs, monkeypatch
):
    import server.service as module

    monkeypatch.setattr(module, "RECHECK_BATCH_SIZE", 2)
    decisions = [
        saved(service, inputs.model_copy(update={"amount": Decimal(1000 + index)}))
        for index in range(5)
    ]
    older = service.begin_load("same_winner")
    datasets, error = service._fetch_datasets(FixtureProvider("same_winner"))
    with service.store.connection(write=True) as db:
        service._publish_load(db, older, datasets, error)
    assert service._recheck_batch(older, datasets)
    newer = load(service, "leader_changed")
    service.finish_load(older, FixtureProvider("same_winner"))
    assert service.load_status(older)["recheck_status"] == "superseded"
    assert service.load_status(older)["checked_count"] == 2
    assert service.source_status()["load_id"] == newer
    for decision in decisions:
        after = service.decision(decision["id"])
        assert after["checks"][-1]["load_id"] == newer
        assert after["baseline"] == decision["baseline"]


def test_save_during_rechecks_uses_published_bundle_and_stays_outside_snapshot(
    service, inputs, monkeypatch
):
    import server.service as module

    monkeypatch.setattr(module, "RECHECK_BATCH_SIZE", 2)
    for index in range(5):
        saved(service, inputs.model_copy(update={"amount": Decimal(1000 + index)}))
    load_id = service.begin_load("leader_changed")
    datasets, error = service._fetch_datasets(FixtureProvider("leader_changed"))
    with service.store.connection(write=True) as db:
        service._publish_load(db, load_id, datasets, error)
    assert service._recheck_batch(load_id, datasets)
    decision = saved(service, inputs.model_copy(update={"amount": Decimal(9000)}))
    assert decision["baseline"]["dataset_id"] == next(
        dataset.id for dataset in datasets if dataset.country == inputs.country
    )
    service.finish_load(load_id, FixtureProvider("leader_changed"))
    assert service.decision(decision["id"])["checks"] == []
    assert service.load_status(load_id)["checked_count"] == 5


def test_terminal_job_failure_preserves_published_bundle_and_completed_batch(
    service, inputs, monkeypatch
):
    import server.service as module

    monkeypatch.setattr(module, "RECHECK_BATCH_SIZE", 2)
    decisions = [
        saved(service, inputs.model_copy(update={"amount": Decimal(1000 + index)}))
        for index in range(5)
    ]
    load_id = service.begin_load("leader_changed")
    datasets, error = service._fetch_datasets(FixtureProvider("leader_changed"))
    with service.store.connection(write=True) as db:
        service._publish_load(db, load_id, datasets, error)
    assert service._recheck_batch(load_id, datasets)
    service.fail_load(load_id, "job_attempts_exhausted")
    status = service.load_status(load_id)
    assert status["status"] == "succeeded"
    assert status["recheck_status"] == "failed" and status["checked_count"] == 2
    assert status["recheck_error_code"] == "job_attempts_exhausted"
    assert service.source_status()["load_id"] == load_id
    assert len(service.decision(decisions[0]["id"])["checks"]) == 1


def test_competing_writer_commits_between_recheck_batches(service, inputs, monkeypatch):
    from threading import Event

    import server.service as module

    monkeypatch.setattr(module, "RECHECK_BATCH_SIZE", 2)
    for index in range(5):
        saved(service, inputs.model_copy(update={"amount": Decimal(1000 + index)}))
    with service.store.connection(write=True) as db:
        db.execute("CREATE TABLE competing_writer(value INTEGER)")
    first_batch = Event()
    writer_done = Event()

    def write_during_job():
        assert first_batch.wait(2)
        with service.store.connection(write=True) as db:
            db.execute("INSERT INTO competing_writer VALUES(1)")
        writer_done.set()

    original = service._recheck_batch

    def batch_with_competing_writer(*args):
        pending = original(*args)
        if not first_batch.is_set():
            first_batch.set()
            assert writer_done.wait(2), (
                "A completed batch retained the SQLite writer lock"
            )
        return pending

    monkeypatch.setattr(service, "_recheck_batch", batch_with_competing_writer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        writer = pool.submit(write_during_job)
        load(service, "leader_changed")
        writer.result()
