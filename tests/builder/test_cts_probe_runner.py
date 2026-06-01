from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.cts_probe import CtsProbeConfig, CtsProbeRunner
from seektalent_keyword_graph.cts.config import CtsClientConfig
from seektalent_keyword_graph.cts.count_client import CtsCountResult
from seektalent_keyword_graph.cts.fake_client import FakeCtsClient
from seektalent_keyword_graph.cts.probe_window import (
    REAL_CTS_GATE_TOKEN,
    RealProbeGateError,
)
from seektalent_keyword_graph.cts.rate_limit import CtsProbeRateLimitConfig
from seektalent_keyword_graph.cts.retry import RetryPolicy

NOW = datetime(2026, 6, 1, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class RecordingClient:
    def __init__(self, results: list[CtsCountResult]) -> None:
        self.results = results
        self.requests: list[tuple[str, str]] = []

    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult:
        self.requests.append((query_text, query_mode))
        return self.results.pop(0)


class TrackingClient:
    def __init__(self, total: int, sleep_seconds: float = 0.0) -> None:
        self._remaining = total
        self._sleep_seconds = sleep_seconds
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.started_at: list[float] = []

    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult:
        with self._lock:
            self._remaining -= 1
            total = self._remaining
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started_at.append(time.monotonic())
        try:
            if self._sleep_seconds:
                time.sleep(self._sleep_seconds)
            return CtsCountResult(status="ok", total=total)
        finally:
            with self._lock:
                self.active -= 1


class BlockingClient:
    def __init__(self, results: list[CtsCountResult]) -> None:
        self.results = results
        self.started: list[str] = []
        self.release = threading.Event()
        self._lock = threading.Lock()

    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult:
        with self._lock:
            self.started.append(query_text)
            result = self.results.pop(0)
        self.release.wait(timeout=0.05)
        return result


class LeaseCheckingClient:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.seen_statuses: list[str] = []

    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult:
        connection = sqlite3.connect(self.db_path)
        try:
            row = connection.execute(
                "select status from probe_jobs where query_text = ? and query_mode = ?",
                (query_text, query_mode),
            ).fetchone()
        finally:
            connection.close()
        assert row is not None
        self.seen_statuses.append(str(row[0]))
        return CtsCountResult(status="ok", total=1)


@pytest.fixture
def store(tmp_path: Path) -> BuildStore:
    build_store = BuildStore.open(tmp_path / "build.sqlite3")
    build_store.insert_builder_run(
        builder_run_id="run-1",
        started_at="2026-06-01T00:00:00+08:00",
        input_corpus_version="corpus-1",
        status="running",
        report_json="{}",
    )
    yield build_store
    build_store.close()


def insert_surface(store: BuildStore, surface_id: str, text: str) -> None:
    store.insert_surface(
        surface_id=surface_id,
        text_raw=text,
        text_norm=text.lower(),
        display_text=text,
        language="en",
        token_class="skill",
        query_safe=True,
        is_exact_phrase_preferred=False,
        ambiguity_score=0.1,
        specificity_score=0.9,
        jd_df=1,
        jd_tf_total=1,
        serving_status="active",
        created_at="2026-06-01T00:00:00+08:00",
        updated_at="2026-06-01T00:00:00+08:00",
    )


def config(**overrides: object) -> CtsProbeConfig:
    values = {
        "builder_run_id": "run-1",
        "mode": "dry_run",
        "now": NOW,
        "retry_policy": RetryPolicy(max_attempts=3, initial_delay_seconds=60.0),
    }
    values.update(overrides)
    return CtsProbeConfig(**values)


def credentials() -> CtsClientConfig:
    return CtsClientConfig(
        base_url="https://cts.invalid",
        tenant_key="tenant",
        tenant_secret="secret",
        timeout_seconds=1.0,
    )


def write_gate(tmp_path: Path, first_line: str = REAL_CTS_GATE_TOKEN) -> Path:
    gate_file = tmp_path / "real-cts.gate"
    gate_file.write_text(f"{first_line}\n", encoding="utf-8")
    return gate_file


def test_run_due_jobs_enforces_real_gate_before_any_network_like_call(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    CtsProbeRunner(store, config(mode="dry_run")).schedule_active_surfaces()
    client = RecordingClient([CtsCountResult(status="ok", total=1)])
    runner = CtsProbeRunner(
        store,
        config(mode="real", credentials=credentials()),
        client=client,
    )

    with pytest.raises(RealProbeGateError, match="gate file"):
        runner.run_due_jobs()

    assert client.requests == []


def test_schedule_active_surfaces_enforces_real_gate_before_enqueue(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    runner = CtsProbeRunner(
        store,
        config(mode="real", credentials=credentials()),
        client=RecordingClient([CtsCountResult(status="ok", total=1)]),
    )

    with pytest.raises(RealProbeGateError, match="gate file"):
        runner.schedule_active_surfaces()

    assert store.list_probe_jobs("surface-python") == []


def test_fake_dry_run_persists_observations_and_probe_job_status(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    client = FakeCtsClient({"Python": CtsCountResult(status="ok", total=42)})
    runner = CtsProbeRunner(store, config(mode="dry_run"), client=client)

    summary = runner.schedule_and_run()

    assert summary.scheduled == 1
    assert summary.completed == 1
    assert store.list_probe_jobs("surface-python")[0]["status"] == "succeeded"
    observation = store.list_observations("surface-python")[0]
    assert observation["status"] == "ok"
    assert observation["total"] == 42
    assert observation["query_mode"] == "keyword"
    assert client.requests[0].query_mode == "keyword"


def test_real_mode_requires_gate_file_before_running(store: BuildStore) -> None:
    insert_surface(store, "surface-python", "Python")
    runner = CtsProbeRunner(
        store,
        config(mode="real", credentials=credentials()),
        client=RecordingClient([CtsCountResult(status="ok", total=1)]),
    )

    with pytest.raises(RealProbeGateError, match="gate file"):
        runner.schedule_and_run()


def test_real_mode_rejects_invalid_gate_file_before_running(
    store: BuildStore, tmp_path: Path
) -> None:
    insert_surface(store, "surface-python", "Python")
    client = RecordingClient([CtsCountResult(status="ok", total=1)])
    runner = CtsProbeRunner(
        store,
        config(
            mode="real",
            gate_file=write_gate(tmp_path, "NOPE"),
            credentials=credentials(),
        ),
        client=client,
    )

    with pytest.raises(RealProbeGateError, match="invalid CTS real-mode gate token"):
        runner.schedule_and_run()
    assert client.requests == []


def test_real_mode_with_valid_gate_credentials_and_window_uses_injected_client(
    store: BuildStore, tmp_path: Path
) -> None:
    insert_surface(store, "surface-python", "Python")
    client = RecordingClient([CtsCountResult(status="ok", total=7)])
    runner = CtsProbeRunner(
        store,
        config(mode="real", gate_file=write_gate(tmp_path), credentials=credentials()),
        client=client,
    )

    summary = runner.schedule_and_run()

    assert summary.completed == 1
    assert client.requests == [("Python", "keyword")]
    assert store.list_observations("surface-python")[0]["total"] == 7


def test_runner_serializes_cts_calls_to_preserve_auth_accounting(
    store: BuildStore,
) -> None:
    for name in ("Python", "Java", "SQL", "Kafka"):
        insert_surface(store, f"surface-{name.lower()}", name)
    client = TrackingClient(total=4, sleep_seconds=0.02)
    runner = CtsProbeRunner(
        store,
        config(
            mode="dry_run",
            rate_limit=CtsProbeRateLimitConfig(
                requests_per_second=1000.0, concurrency=2
            ),
        ),
        client=client,
    )

    summary = runner.schedule_and_run()

    assert summary.completed == 4
    assert client.max_active == 1


def test_runner_applies_configured_rps_spacing(store: BuildStore) -> None:
    for name in ("Python", "Java", "SQL"):
        insert_surface(store, f"surface-{name.lower()}", name)
    client = TrackingClient(total=3)
    runner = CtsProbeRunner(
        store,
        config(
            mode="dry_run",
            rate_limit=CtsProbeRateLimitConfig(requests_per_second=20.0, concurrency=3),
        ),
        client=client,
    )

    summary = runner.schedule_and_run()

    assert summary.completed == 3
    start_gaps = [
        right - left
        for left, right in zip(client.started_at, client.started_at[1:], strict=False)
    ]
    assert min(start_gaps) >= 0.035


def test_schedule_skips_existing_open_probe_job_without_observation(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    first_runner = CtsProbeRunner(store, config(mode="dry_run", now=NOW))
    second_runner = CtsProbeRunner(
        store, config(mode="dry_run", now=NOW + timedelta(minutes=5))
    )

    first_summary = first_runner.schedule_active_surfaces()
    second_summary = second_runner.schedule_active_surfaces()

    assert first_summary == (1, 0)
    assert second_summary == (0, 0)
    jobs = store.list_probe_jobs("surface-python")
    assert len(jobs) == 1
    assert jobs[0]["status"] == "scheduled"


def test_runner_leases_due_jobs_before_counting(store: BuildStore) -> None:
    insert_surface(store, "surface-python", "Python")
    client = LeaseCheckingClient(store.path)
    runner = CtsProbeRunner(store, config(mode="dry_run"), client=client)

    summary = runner.schedule_and_run()

    assert summary.completed == 1
    assert client.seen_statuses == ["running"]
    assert store.list_probe_jobs("surface-python")[0]["status"] == "succeeded"


def test_dry_run_runner_does_not_execute_real_pending_job(
    store: BuildStore, tmp_path: Path
) -> None:
    insert_surface(store, "surface-python", "Python")
    CtsProbeRunner(
        store,
        config(
            mode="real",
            gate_file=write_gate(tmp_path),
            credentials=credentials(),
        ),
    ).schedule_active_surfaces()
    dry_client = RecordingClient([CtsCountResult(status="ok", total=1)])

    summary = CtsProbeRunner(
        store,
        config(mode="dry_run"),
        client=dry_client,
    ).run_due_jobs()

    assert summary.completed == 0
    assert dry_client.requests == []
    assert store.list_probe_jobs("surface-python")[0]["status"] == "scheduled"


def test_auth_error_with_configured_concurrency_records_started_calls_before_pausing(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    insert_surface(store, "surface-java", "Java")
    insert_surface(store, "surface-sql", "SQL")
    client = BlockingClient(
        [
            CtsCountResult(status="auth_error", error_code="auth_error"),
            CtsCountResult(status="ok", total=2),
            CtsCountResult(status="ok", total=3),
        ]
    )
    runner = CtsProbeRunner(
        store,
        config(
            mode="dry_run",
            rate_limit=CtsProbeRateLimitConfig(
                requests_per_second=1000.0, concurrency=3
            ),
        ),
        client=client,
    )

    summary = runner.schedule_and_run()

    assert summary.auth_paused == 1
    assert client.started == ["Java"]
    observations = [
        row["query_text"]
        for surface_id in ("surface-java", "surface-python", "surface-sql")
        for row in store.list_observations(surface_id)
    ]
    assert observations == ["Java"]


def test_auth_error_after_prior_success_does_not_drop_started_call_accounting(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    insert_surface(store, "surface-java", "Java")
    insert_surface(store, "surface-sql", "SQL")
    client = BlockingClient(
        [
            CtsCountResult(status="ok", total=1),
            CtsCountResult(status="auth_error", error_code="auth_error"),
            CtsCountResult(status="ok", total=3),
        ]
    )
    runner = CtsProbeRunner(
        store,
        config(
            mode="dry_run",
            rate_limit=CtsProbeRateLimitConfig(
                requests_per_second=1000.0, concurrency=3
            ),
        ),
        client=client,
    )

    summary = runner.schedule_and_run()

    assert summary.completed == 1
    assert summary.auth_paused == 1
    assert client.started == ["Java", "Python"]
    observations = {
        row["query_text"]: row["status"]
        for surface_id in ("surface-java", "surface-python", "surface-sql")
        for row in store.list_observations(surface_id)
    }
    assert observations == {"Java": "ok", "Python": "auth_error"}


def test_auth_pause_is_scoped_to_matching_mode_and_api_bucket(
    store: BuildStore, tmp_path: Path
) -> None:
    insert_surface(store, "surface-python", "Python")
    CtsProbeRunner(store, config(mode="dry_run")).schedule_active_surfaces()
    v2_credentials = CtsClientConfig(
        base_url="https://cts.invalid",
        tenant_key="tenant",
        tenant_secret="secret",
        timeout_seconds=1.0,
        api_version="v2",
    )
    CtsProbeRunner(
        store,
        config(
            mode="real",
            gate_file=write_gate(tmp_path),
            credentials=v2_credentials,
        ),
    ).schedule_active_surfaces()
    real_v1_runner = CtsProbeRunner(
        store,
        config(
            mode="real",
            gate_file=write_gate(tmp_path),
            credentials=credentials(),
        ),
        client=RecordingClient(
            [CtsCountResult(status="auth_error", error_code="auth_error")]
        ),
    )

    summary = real_v1_runner.schedule_and_run()

    assert summary.auth_paused == 1
    jobs = store.list_probe_jobs("surface-python")
    assert sorted((job["rate_limit_bucket"], job["status"]) for job in jobs) == [
        ("dry_run:dry-run-v1", "scheduled"),
        ("real:v1", "auth_error"),
        ("real:v2", "scheduled"),
    ]


def test_dry_run_observations_do_not_suppress_real_probe_with_same_query(
    store: BuildStore, tmp_path: Path
) -> None:
    insert_surface(store, "surface-python", "Python")
    dry_client = FakeCtsClient({"Python": CtsCountResult(status="ok", total=42)})
    CtsProbeRunner(store, config(mode="dry_run"), client=dry_client).schedule_and_run()

    real_client = RecordingClient([CtsCountResult(status="ok", total=7)])
    summary = CtsProbeRunner(
        store,
        config(mode="real", gate_file=write_gate(tmp_path), credentials=credentials()),
        client=real_client,
    ).schedule_and_run()

    assert summary.skipped_fresh == 0
    assert summary.completed == 1
    assert real_client.requests == [("Python", "keyword")]
    assert sorted(
        row["cts_api_version"] for row in store.list_observations("surface-python")
    ) == ["dry-run-v1", "v1"]


def test_ttl_dedupe_skips_fresh_observations_with_same_query_hash_and_mode(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    runner = CtsProbeRunner(store, config(mode="dry_run"))
    query_hash = runner.query_hash("Python", "keyword")
    store.insert_probe_job(
        probe_job_id="probe-existing",
        surface_id="surface-python",
        query_text="Python",
        query_mode="keyword",
        priority=0,
        dedupe_key="existing-dedupe",
        scheduled_at=(NOW - timedelta(minutes=5)).isoformat(),
        not_before=(NOW - timedelta(minutes=5)).isoformat(),
        attempt_count=1,
        status="succeeded",
        rate_limit_bucket="dry_run",
        created_reason="test",
        last_error_code=None,
    )
    store.insert_cts_recall_observation(
        observation_id="obs-existing",
        probe_job_id="probe-existing",
        surface_id="surface-python",
        query_text="Python",
        query_hash=query_hash,
        query_mode="keyword",
        total=99,
        latency_ms=1,
        status="ok",
        error_code=None,
        observed_at=(NOW - timedelta(minutes=5)).isoformat(),
        cts_api_version="dry-run-v1",
        builder_run_id="run-1",
    )

    summary = runner.schedule_and_run()

    assert summary.skipped_fresh == 1
    jobs = store.list_probe_jobs("surface-python")
    assert len(jobs) == 1
    assert jobs[0]["probe_job_id"] == "probe-existing"


def test_stale_observation_schedules_new_probe_job(store: BuildStore) -> None:
    insert_surface(store, "surface-python", "Python")
    stale_runner = CtsProbeRunner(
        store,
        config(mode="dry_run", now=NOW - timedelta(days=2)),
        client=FakeCtsClient({"Python": CtsCountResult(status="ok", total=12)}),
    )
    stale_runner.schedule_and_run()

    summary = CtsProbeRunner(
        store,
        config(mode="dry_run", ttl_seconds=60),
        client=FakeCtsClient({"Python": CtsCountResult(status="ok", total=13)}),
    ).schedule_and_run()

    assert summary.scheduled == 1
    assert summary.completed == 1
    jobs = store.list_probe_jobs("surface-python")
    assert len(jobs) == 2
    assert {job["status"] for job in jobs} == {"succeeded"}
    assert store.list_observations("surface-python")[0]["total"] == 13


def test_real_api_version_change_schedules_distinct_probe_job(
    store: BuildStore, tmp_path: Path
) -> None:
    insert_surface(store, "surface-python", "Python")
    CtsProbeRunner(
        store,
        config(
            mode="real",
            gate_file=write_gate(tmp_path),
            credentials=credentials(),
        ),
        client=RecordingClient([CtsCountResult(status="ok", total=7)]),
    ).schedule_and_run()
    v2_credentials = CtsClientConfig(
        base_url="https://cts.invalid",
        tenant_key="tenant",
        tenant_secret="secret",
        timeout_seconds=1.0,
        api_version="v2",
    )
    summary = CtsProbeRunner(
        store,
        config(
            mode="real",
            gate_file=write_gate(tmp_path),
            credentials=v2_credentials,
        ),
        client=RecordingClient([CtsCountResult(status="ok", total=8)]),
    ).schedule_and_run()

    assert summary.scheduled == 1
    assert summary.completed == 1
    assert len(store.list_probe_jobs("surface-python")) == 2
    assert sorted(
        row["cts_api_version"] for row in store.list_observations("surface-python")
    ) == ["v1", "v2"]


@pytest.mark.parametrize(
    "result",
    [
        CtsCountResult(status="timeout", error_code="timeout", retryable=True),
        CtsCountResult(status="rate_limited", error_code="http_429", retryable=True),
        CtsCountResult(status="server_error", error_code="http_5xx", retryable=True),
        CtsCountResult(
            status="network_error", error_code="network_error", retryable=True
        ),
    ],
)
def test_retryable_errors_schedule_backoff_retry_jobs(
    store: BuildStore, result: CtsCountResult
) -> None:
    insert_surface(store, "surface-python", "Python")
    runner = CtsProbeRunner(
        store,
        config(mode="dry_run"),
        client=RecordingClient([result]),
    )

    summary = runner.schedule_and_run()

    job = store.list_probe_jobs("surface-python")[0]
    assert summary.retry_scheduled == 1
    assert job["status"] == "retry_scheduled"
    assert job["attempt_count"] == 1
    assert job["last_error_code"] == result.error_code
    assert job["not_before"] == (NOW + timedelta(seconds=60)).isoformat()


def test_auth_error_pauses_pending_jobs_and_does_not_retry(store: BuildStore) -> None:
    insert_surface(store, "surface-python", "Python")
    insert_surface(store, "surface-java", "Java")
    runner = CtsProbeRunner(
        store,
        config(mode="dry_run"),
        client=RecordingClient(
            [CtsCountResult(status="auth_error", error_code="auth_error")]
        ),
    )

    summary = runner.schedule_and_run()

    jobs = [
        store.list_probe_jobs("surface-python")[0],
        store.list_probe_jobs("surface-java")[0],
    ]
    assert summary.auth_paused == 1
    assert sorted(job["status"] for job in jobs) == ["auth_error", "paused_auth"]
    assert [job["status"] for job in jobs].count("retry_scheduled") == 0
    assert next(job for job in jobs if job["status"] == "auth_error")[
        "attempt_count"
    ] == 1


def test_failure_observations_do_not_overwrite_old_successful_totals(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    store.insert_probe_job(
        probe_job_id="probe-old",
        surface_id="surface-python",
        query_text="Python",
        query_mode="dry_run",
        priority=0,
        dedupe_key="old-dedupe",
        scheduled_at=(NOW - timedelta(days=2)).isoformat(),
        not_before=(NOW - timedelta(days=2)).isoformat(),
        attempt_count=1,
        status="succeeded",
        rate_limit_bucket="dry_run",
        created_reason="test",
        last_error_code=None,
    )
    old_hash = CtsProbeRunner(store, config(mode="dry_run")).query_hash(
        "Python", "keyword"
    )
    store.insert_cts_recall_observation(
        observation_id="obs-old",
        probe_job_id="probe-old",
        surface_id="surface-python",
        query_text="Python",
        query_hash=old_hash,
        query_mode="keyword",
        total=55,
        latency_ms=1,
        status="ok",
        error_code=None,
        observed_at=(NOW - timedelta(days=2)).isoformat(),
        cts_api_version="fake-v1",
        builder_run_id="run-1",
    )
    runner = CtsProbeRunner(
        store,
        config(mode="dry_run", ttl_seconds=0),
        client=RecordingClient(
            [
                CtsCountResult(
                    status="server_error", error_code="http_5xx", retryable=True
                )
            ]
        ),
    )

    runner.schedule_and_run()

    observations = store.list_observations("surface-python")
    assert observations[0]["status"] == "server_error"
    assert observations[0]["total"] is None
    assert store.latest_successful_observation_total("surface-python") == 55


def test_insert_probe_job_if_absent_does_not_swallow_integrity_errors(
    store: BuildStore,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_probe_job_if_absent(
            probe_job_id="probe-missing-surface",
            surface_id="missing-surface",
            query_text="Python",
            query_mode="keyword",
            priority=0,
            dedupe_key="missing-surface:keyword:python",
            scheduled_at=NOW.isoformat(),
            not_before=NOW.isoformat(),
            attempt_count=0,
            status="scheduled",
            rate_limit_bucket="dry_run",
            created_reason="test",
            last_error_code=None,
        )
