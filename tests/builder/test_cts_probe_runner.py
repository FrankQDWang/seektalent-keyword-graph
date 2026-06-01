from __future__ import annotations

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
from seektalent_keyword_graph.cts.retry import RetryPolicy

NOW = datetime(2026, 6, 1, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class RecordingClient:
    def __init__(self, results: list[CtsCountResult]) -> None:
        self.results = results
        self.requests: list[tuple[str, str]] = []

    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult:
        self.requests.append((query_text, query_mode))
        return self.results.pop(0)


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
    assert observation["query_mode"] == "dry_run"


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
    assert client.requests == [("Python", "real")]
    assert store.list_observations("surface-python")[0]["total"] == 7


def test_ttl_dedupe_skips_fresh_observations_with_same_query_hash_and_mode(
    store: BuildStore,
) -> None:
    insert_surface(store, "surface-python", "Python")
    runner = CtsProbeRunner(store, config(mode="dry_run"))
    query_hash = runner.query_hash("Python", "dry_run")
    store.insert_probe_job(
        probe_job_id="probe-existing",
        surface_id="surface-python",
        query_text="Python",
        query_mode="dry_run",
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
        query_mode="dry_run",
        total=99,
        latency_ms=1,
        status="ok",
        error_code=None,
        observed_at=(NOW - timedelta(minutes=5)).isoformat(),
        cts_api_version="fake-v1",
        builder_run_id="run-1",
    )

    summary = runner.schedule_and_run()

    assert summary.skipped_fresh == 1
    jobs = store.list_probe_jobs("surface-python")
    assert len(jobs) == 1
    assert jobs[0]["probe_job_id"] == "probe-existing"


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
        "Python", "dry_run"
    )
    store.insert_cts_recall_observation(
        observation_id="obs-old",
        probe_job_id="probe-old",
        surface_id="surface-python",
        query_text="Python",
        query_hash=old_hash,
        query_mode="dry_run",
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
