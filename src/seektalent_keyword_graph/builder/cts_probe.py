from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.cts.config import CtsClientConfig
from seektalent_keyword_graph.cts.count_client import CtsCountClient, CtsCountResult
from seektalent_keyword_graph.cts.fake_client import FakeCtsClient
from seektalent_keyword_graph.cts.probe_window import (
    ProbeWindowConfig,
    RealProbeGateError,
    ensure_real_probe_allowed,
)
from seektalent_keyword_graph.cts.rate_limit import CtsProbeRateLimitConfig
from seektalent_keyword_graph.cts.retry import RetryPolicy


class CtsCountLike(Protocol):
    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult: ...


@dataclass(frozen=True)
class CtsProbeConfig:
    builder_run_id: str
    mode: str = "dry_run"
    now: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 86_400
    gate_file: str | Path | None = None
    credentials: CtsClientConfig | None = None
    window_config: ProbeWindowConfig = field(default_factory=ProbeWindowConfig)
    rate_limit: CtsProbeRateLimitConfig = field(default_factory=CtsProbeRateLimitConfig)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if self.mode not in {"dry_run", "fake", "real"}:
            raise ValueError("mode must be dry_run, fake, or real")
        if self.ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")


@dataclass(frozen=True)
class CtsProbeRunSummary:
    scheduled: int = 0
    skipped_fresh: int = 0
    completed: int = 0
    retry_scheduled: int = 0
    auth_paused: int = 0


class CtsProbeRunner:
    def __init__(
        self,
        store: BuildStore,
        config: CtsProbeConfig,
        *,
        client: CtsCountLike | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self._client = client

    def query_hash(self, query_text: str, mode: str) -> str:
        return hashlib.sha256(f"{mode}\0{query_text}".encode()).hexdigest()

    def schedule_and_run(self) -> CtsProbeRunSummary:
        self._validate_mode()
        scheduled, skipped_fresh = self.schedule_active_surfaces()
        run_summary = self.run_due_jobs()
        return CtsProbeRunSummary(
            scheduled=scheduled,
            skipped_fresh=skipped_fresh,
            completed=run_summary.completed,
            retry_scheduled=run_summary.retry_scheduled,
            auth_paused=run_summary.auth_paused,
        )

    def schedule_active_surfaces(self) -> tuple[int, int]:
        scheduled = 0
        skipped_fresh = 0
        observed_after = self.config.now - timedelta(seconds=self.config.ttl_seconds)

        for surface in self.store.list_active_probe_surfaces():
            query_text = str(surface["display_text"])
            query_hash = self.query_hash(query_text, self.config.mode)
            if self.store.find_observation_since(
                surface_id=str(surface["surface_id"]),
                query_hash=query_hash,
                query_mode=self.config.mode,
                observed_after=observed_after.isoformat(),
            ):
                skipped_fresh += 1
                continue

            probe_job_id = (
                f"cts-probe-{self.config.mode}-"
                f"{surface['surface_id']}-{query_hash[:16]}"
            )
            inserted = self.store.insert_probe_job_if_absent(
                probe_job_id=probe_job_id,
                surface_id=str(surface["surface_id"]),
                query_text=query_text,
                query_mode=self.config.mode,
                priority=0,
                dedupe_key=f"{surface['surface_id']}:{query_hash}",
                scheduled_at=self.config.now.isoformat(),
                not_before=self.config.now.isoformat(),
                attempt_count=0,
                status="scheduled",
                rate_limit_bucket=self.config.mode,
                created_reason="active_surface",
                last_error_code=None,
            )
            if inserted:
                scheduled += 1

        return scheduled, skipped_fresh

    def run_due_jobs(self) -> CtsProbeRunSummary:
        client = self._resolve_client()
        completed = 0
        retry_scheduled = 0
        auth_paused = 0

        for job in self.store.list_due_probe_jobs(self.config.now.isoformat()):
            result = client.count(str(job["query_text"]), str(job["query_mode"]))
            attempt_count = int(job["attempt_count"]) + 1
            self._insert_observation(job, result)

            if result.status == "ok":
                self.store.update_probe_job(
                    probe_job_id=str(job["probe_job_id"]),
                    status="succeeded",
                    attempt_count=attempt_count,
                    not_before=str(job["not_before"]),
                    last_error_code=None,
                )
                completed += 1
                continue

            if result.status == "auth_error":
                self.store.update_probe_job(
                    probe_job_id=str(job["probe_job_id"]),
                    status="auth_error",
                    attempt_count=attempt_count,
                    not_before=str(job["not_before"]),
                    last_error_code=result.error_code,
                )
                self.store.pause_pending_probe_jobs(
                    paused_status="paused_auth",
                    error_code=result.error_code,
                    exclude_probe_job_id=str(job["probe_job_id"]),
                )
                auth_paused += 1
                break

            should_retry = (
                result.retryable
                and attempt_count < self.config.retry_policy.max_attempts
            )
            if should_retry:
                not_before = self.config.now + timedelta(
                    seconds=self._backoff_seconds(attempt_count)
                )
                self.store.update_probe_job(
                    probe_job_id=str(job["probe_job_id"]),
                    status="retry_scheduled",
                    attempt_count=attempt_count,
                    not_before=not_before.isoformat(),
                    last_error_code=result.error_code,
                )
                retry_scheduled += 1
                continue

            self.store.update_probe_job(
                probe_job_id=str(job["probe_job_id"]),
                status="failed",
                attempt_count=attempt_count,
                not_before=str(job["not_before"]),
                last_error_code=result.error_code,
            )

        return CtsProbeRunSummary(
            completed=completed,
            retry_scheduled=retry_scheduled,
            auth_paused=auth_paused,
        )

    def _validate_mode(self) -> None:
        ensure_real_probe_allowed(
            mode=self.config.mode,
            gate_file=self.config.gate_file,
            now=self.config.now,
            window_config=self.config.window_config,
        )
        if self.config.mode == "real" and self.config.credentials is None:
            raise RealProbeGateError("real CTS probe mode requires credentials")

    def _resolve_client(self) -> CtsCountLike:
        if self._client is not None:
            return self._client
        if self.config.mode == "real":
            if self.config.credentials is None:
                raise RealProbeGateError("real CTS probe mode requires credentials")
            return CtsCountClient(self.config.credentials)
        return FakeCtsClient({})

    def _insert_observation(
        self, job: dict[str, object], result: CtsCountResult
    ) -> None:
        query_text = str(job["query_text"])
        query_mode = str(job["query_mode"])
        query_hash = self.query_hash(query_text, query_mode)
        observation_id = (
            f"cts-obs-{job['probe_job_id']}-{int(job['attempt_count']) + 1}"
        )
        self.store.insert_cts_recall_observation(
            observation_id=observation_id,
            probe_job_id=str(job["probe_job_id"]),
            surface_id=str(job["surface_id"]),
            query_text=query_text,
            query_hash=query_hash,
            query_mode=query_mode,
            total=result.total if result.status == "ok" else None,
            latency_ms=result.latency_ms,
            status=result.status,
            error_code=result.error_code,
            observed_at=self.config.now.isoformat(),
            cts_api_version=self._cts_api_version(),
            builder_run_id=self.config.builder_run_id,
        )

    def _cts_api_version(self) -> str:
        if self.config.mode != "real":
            return "fake-v1"
        if self.config.credentials is None:
            return "real"
        return self.config.credentials.api_version

    def _backoff_seconds(self, attempt_count: int) -> float:
        return self.config.retry_policy.initial_delay_seconds * (
            self.config.retry_policy.backoff_multiplier ** (attempt_count - 1)
        )
