"""Command line parser for keyword graph tooling."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seektalent_keyword_graph import __version__

_FAKE_CTS_ERRORS: dict[str, tuple[str, str, bool]] = {
    "timeout": ("timeout", "timeout", True),
    "rate_limited": ("rate_limited", "http_429", True),
    "server_error": ("server_error", "http_5xx", True),
    "auth_error": ("auth_error", "auth_error", False),
    "network_error": ("network_error", "network_error", True),
    "invalid_query": ("invalid_query", "invalid_query", False),
    "invalid_response": ("invalid_response", "invalid_response", False),
}
_VERSION_SUFFIX = re.compile(r"^(?P<base>.+?)\s+\d+(?:\.\d+)*$")
DEFAULT_BUILDER_RUN_ID = "local-cli-run"
DEFAULT_SNAPSHOT_ID = "local-cli-snapshot"
DEFAULT_SOURCE_CORPUS_VERSION = "local-cli-corpus"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keyword-graph")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_jds = subparsers.add_parser(
        "import-jds", help="Import local JD JSONL records into a build DB."
    )
    import_jds.add_argument("input_jsonl", metavar="INPUT_JSONL")
    import_jds.add_argument("--build-db", required=True)
    import_jds.add_argument("--builder-run-id", default=DEFAULT_BUILDER_RUN_ID)
    import_jds.add_argument("--corpus-version", default=DEFAULT_SOURCE_CORPUS_VERSION)
    import_jds.set_defaults(handler=_handle_import_jds)

    extract = subparsers.add_parser(
        "extract-surfaces", help="Extract keyword surfaces from imported JDs."
    )
    _add_build_db_and_run_id(extract)
    extract.add_argument("--report", required=True)
    extract.set_defaults(handler=_handle_extract_surfaces)

    relations = subparsers.add_parser(
        "build-relations",
        help="Build concepts, relations, co-occurrence edges, and sampling reports.",
    )
    _add_build_db_and_run_id(relations)
    relations.add_argument("--sampling-csv", required=True)
    relations.add_argument("--sampling-jsonl", required=True)
    relations.set_defaults(handler=_handle_build_relations)

    probe = subparsers.add_parser(
        "probe-cts",
        help="Probe active surfaces against CTS using fake or gated real mode.",
    )
    _add_build_db_and_run_id(probe)
    mode = probe.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--real", action="store_true")
    probe.add_argument("--fake-response")
    probe.add_argument("--gate-file")
    probe.set_defaults(handler=_handle_probe_cts)

    snapshot = subparsers.add_parser(
        "build-snapshot", help="Build runtime snapshot artifacts from a build DB."
    )
    _add_build_db_and_run_id(snapshot)
    snapshot.add_argument("--output-dir")
    snapshot.add_argument("--kg-snapshot-id", default=DEFAULT_SNAPSHOT_ID)
    snapshot.add_argument("--source-corpus-version")
    snapshot.add_argument("--provider-probe-window-start")
    snapshot.add_argument("--provider-probe-window-end")
    snapshot.add_argument("--built-at")
    snapshot.add_argument("--snapshot")
    snapshot.add_argument("--manifest")
    snapshot.add_argument("--compressed-snapshot")
    snapshot.add_argument("--build-report")
    snapshot.set_defaults(handler=_handle_build_snapshot)

    validate = subparsers.add_parser(
        "validate-snapshot", help="Validate runtime snapshot release artifacts."
    )
    validate.add_argument("--snapshot", required=True)
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--compressed-snapshot")
    validate.set_defaults(handler=_handle_validate_snapshot)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    try:
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _add_build_db_and_run_id(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--build-db", required=True)
    parser.add_argument("--builder-run-id", default=DEFAULT_BUILDER_RUN_ID)


def _handle_import_jds(args: argparse.Namespace) -> int:
    BuildStore = _load_attr(
        "seektalent_keyword_graph.builder.build_store", "BuildStore"
    )
    import_jsonl_jds = _load_attr(
        "seektalent_keyword_graph.builder.import_jds", "import_jsonl_jds"
    )

    store = BuildStore.open(args.build_db)
    try:
        report = import_jsonl_jds(
            store, args.input_jsonl, builder_run_id=args.builder_run_id
        )
        if args.corpus_version:
            _update_corpus_version(store, args.builder_run_id, args.corpus_version)
        payload = {
            "command": "import-jds",
            "status": "ok",
            "build_db": str(Path(args.build_db)),
            "report": report.as_dict(),
        }
    finally:
        store.close()

    _print_json(payload)
    return 0


def _handle_extract_surfaces(args: argparse.Namespace) -> int:
    BuildStore = _load_attr(
        "seektalent_keyword_graph.builder.build_store", "BuildStore"
    )
    extract_surfaces = _load_attr(
        "seektalent_keyword_graph.builder.extract_surfaces", "extract_surfaces"
    )

    store = BuildStore.open(args.build_db)
    try:
        report = extract_surfaces(store, builder_run_id=args.builder_run_id)
        payload = {
            "command": "extract-surfaces",
            "status": "ok",
            "build_db": str(Path(args.build_db)),
            "report": report.as_dict(),
        }
    finally:
        store.close()

    _write_json(Path(args.report), payload)
    _print_json(payload)
    return 0


def _handle_build_relations(args: argparse.Namespace) -> int:
    BuildStore = _load_attr(
        "seektalent_keyword_graph.builder.build_store", "BuildStore"
    )
    build_relations = _load_attr(
        "seektalent_keyword_graph.builder.build_relations", "build_relations"
    )
    build_cooccurrence_edges = _load_attr(
        "seektalent_keyword_graph.builder.cooccurrence", "build_cooccurrence_edges"
    )
    write_sampling_reports = _load_attr(
        "seektalent_keyword_graph.builder.sampling_report", "write_sampling_reports"
    )

    store = BuildStore.open(args.build_db)
    try:
        relation_report = build_relations(
            store, builder_run_id=args.builder_run_id
        )
        cooccurrence_report = build_cooccurrence_edges(
            store, builder_run_id=args.builder_run_id
        )
        sampling_report = write_sampling_reports(
            store,
            csv_path=args.sampling_csv,
            jsonl_path=args.sampling_jsonl,
            builder_run_id=args.builder_run_id,
        )
        payload = {
            "command": "build-relations",
            "status": "ok",
            "build_db": str(Path(args.build_db)),
            "relations": _object_dict(relation_report),
            "cooccurrence": cooccurrence_report.as_dict(),
            "sampling": sampling_report.as_dict(),
        }
    finally:
        store.close()

    _print_json(payload)
    return 0


def _handle_probe_cts(args: argparse.Namespace) -> int:
    BuildStore = _load_attr(
        "seektalent_keyword_graph.builder.build_store", "BuildStore"
    )
    CtsProbeConfig = _load_attr(
        "seektalent_keyword_graph.builder.cts_probe", "CtsProbeConfig"
    )
    CtsProbeRunner = _load_attr(
        "seektalent_keyword_graph.builder.cts_probe", "CtsProbeRunner"
    )

    mode = "real" if args.real else "dry_run"
    store = BuildStore.open(args.build_db)
    try:
        client = None
        if args.fake_response:
            client = _fake_cts_client(args.fake_response, store)
        config = CtsProbeConfig(
            builder_run_id=args.builder_run_id,
            mode=mode,
            gate_file=args.gate_file,
        )
        summary = CtsProbeRunner(store, config, client=client).schedule_and_run()
        payload = {
            "command": "probe-cts",
            "status": "ok",
            "mode": mode,
            "build_db": str(Path(args.build_db)),
            "summary": _object_dict(summary),
        }
    finally:
        store.close()

    _print_json(payload)
    return 0


def _handle_build_snapshot(args: argparse.Namespace) -> int:
    BuildSnapshotConfig = _load_attr(
        "seektalent_keyword_graph.builder.build_snapshot", "BuildSnapshotConfig"
    )
    built_at = args.built_at or _utc_now()
    window_start, window_end = _provider_probe_window_defaults(
        Path(args.build_db),
        built_at=built_at,
        explicit_start=args.provider_probe_window_start,
        explicit_end=args.provider_probe_window_end,
    )

    config = BuildSnapshotConfig(
        kg_snapshot_id=args.kg_snapshot_id,
        built_at=built_at,
        source_corpus_version=args.source_corpus_version
        or _latest_source_corpus_version(Path(args.build_db)),
        builder_run_id=args.builder_run_id,
        provider_probe_window_start=window_start,
        provider_probe_window_end=window_end,
    )
    paths = _build_snapshot_artifacts(args, config)
    _print_json(
        {
            "command": "build-snapshot",
            "status": "ok",
            "build_db": str(Path(args.build_db)),
            "paths": paths,
        }
    )
    return 0


def _handle_validate_snapshot(args: argparse.Namespace) -> int:
    validate_release_artifacts = _load_attr(
        "seektalent_keyword_graph.release_validation", "validate_release_artifacts"
    )
    compressed_snapshot = args.compressed_snapshot
    if compressed_snapshot is None:
        sibling = Path(f"{args.snapshot}.gz")
        if sibling.exists():
            compressed_snapshot = str(sibling)

    result = validate_release_artifacts(
        args.snapshot,
        args.manifest,
        compressed_snapshot_path=compressed_snapshot,
    )
    errors = [_object_dict(error) for error in result.errors]
    payload = {
        "command": "validate-snapshot",
        "status": "ok" if result.ok else "error",
        "ok": result.ok,
        "snapshot": str(result.artifact_path),
        "manifest": str(result.manifest_path),
        "compressed_snapshot": (
            str(result.compressed_snapshot_path)
            if result.compressed_snapshot_path is not None
            else None
        ),
        "snapshot_sha256": result.snapshot_sha256,
        "gzip_sha256": result.gzip_sha256,
        "errors": errors,
    }
    _print_json(payload)
    return 0 if result.ok else 1


def _fake_cts_client(fake_response_path: str, store: Any) -> Any:
    FakeCtsClient = _load_attr(
        "seektalent_keyword_graph.cts.fake_client", "FakeCtsClient"
    )
    CtsCountResult = _load_attr(
        "seektalent_keyword_graph.cts.count_client", "CtsCountResult"
    )

    raw = json.loads(Path(fake_response_path).read_text(encoding="utf-8"))
    queries = raw.get("queries")
    if not isinstance(queries, dict):
        raise ValueError("fake CTS fixture must contain a queries object")

    normalized: dict[str, Any] = {}
    responses: dict[str, Any] = {}
    for query_text, value in queries.items():
        if not isinstance(query_text, str):
            raise ValueError("fake CTS query keys must be strings")
        result = _parse_fake_result(CtsCountResult, query_text, value)
        responses[query_text] = result
        normalized[query_text.casefold()] = result

    for surface in store.list_active_probe_surfaces():
        display_text = str(surface["display_text"])
        for key in _fake_lookup_keys(display_text):
            result = normalized.get(key)
            if result is not None:
                responses[display_text] = result
                break

    return FakeCtsClient(responses)


def _parse_fake_result(CtsCountResult: Any, query_text: str, value: Any) -> Any:
    if not isinstance(value, dict):
        raise ValueError(f"fake CTS fixture for {query_text!r} must be an object")

    status = value.get("status")
    if status is None:
        total = value.get("total")
        if isinstance(total, bool) or not isinstance(total, int):
            raise ValueError(f"fake CTS fixture for {query_text!r} needs integer total")
        return CtsCountResult(status="ok", total=total)

    if status not in _FAKE_CTS_ERRORS:
        raise ValueError(f"unsupported fake CTS status for {query_text!r}: {status!r}")
    result_status, error_code, retryable = _FAKE_CTS_ERRORS[status]
    return CtsCountResult(
        status=result_status,
        error_code=error_code,
        retryable=retryable,
    )


def _fake_lookup_keys(display_text: str) -> tuple[str, ...]:
    casefolded = display_text.casefold()
    version_match = _VERSION_SUFFIX.fullmatch(casefolded)
    if version_match is None:
        return (casefolded,)
    return (casefolded, version_match.group("base"))


def _update_corpus_version(
    store: Any, builder_run_id: str, corpus_version: str
) -> None:
    connection = vars(store)["connection"]
    connection.execute(
        """
        update builder_runs
        set input_corpus_version = ?
        where builder_run_id = ?
        """,
        (corpus_version, builder_run_id),
    )
    connection.commit()


def _copy_alias(path: Path, alias: str | None) -> str:
    if alias is None:
        return str(path)
    alias_path = Path(alias)
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    if alias_path.resolve() != path.resolve():
        shutil.copy2(path, alias_path)
    return str(alias_path)


def _build_snapshot_artifacts(
    args: argparse.Namespace, config: Any
) -> dict[str, str]:
    build_runtime_snapshot = _load_attr(
        "seektalent_keyword_graph.builder.build_snapshot", "build_runtime_snapshot"
    )
    validate_release_artifacts = _load_attr(
        "seektalent_keyword_graph.release_validation", "validate_release_artifacts"
    )

    has_aliases = any(
        (args.snapshot, args.manifest, args.compressed_snapshot, args.build_report)
    )
    if has_aliases:
        with tempfile.TemporaryDirectory(prefix="keyword-graph-snapshot-") as temp_dir:
            result = build_runtime_snapshot(args.build_db, temp_dir, config)
            paths = _finalize_snapshot_artifacts(result, args)
    else:
        result = build_runtime_snapshot(
            args.build_db, _snapshot_output_dir(args), config
        )
        paths = {
            "snapshot": str(result.snapshot_path),
            "manifest": str(result.manifest_path),
            "compressed_snapshot": str(result.compressed_snapshot_path),
            "build_report": str(result.build_report_path),
        }

    validation = validate_release_artifacts(
        paths["snapshot"],
        paths["manifest"],
        compressed_snapshot_path=paths["compressed_snapshot"],
    )
    if not validation.ok:
        messages = "; ".join(error.message for error in validation.errors)
        raise RuntimeError(f"built snapshot failed release validation: {messages}")
    return paths


def _finalize_snapshot_artifacts(
    result: Any, args: argparse.Namespace
) -> dict[str, str]:
    manifest_identity_sha256 = _load_attr(
        "seektalent_keyword_graph.contracts.snapshot", "manifest_identity_sha256"
    )

    source_snapshot = Path(result.snapshot_path)
    output_dir = _aliased_snapshot_output_dir(args)
    snapshot_path = (
        Path(args.snapshot) if args.snapshot else output_dir / "keyword-graph.sqlite3"
    )
    compressed_path = (
        Path(args.compressed_snapshot)
        if args.compressed_snapshot
        else Path(f"{snapshot_path}.gz")
    )
    manifest_path = (
        Path(args.manifest) if args.manifest else output_dir / "snapshot-manifest.json"
    )
    build_report_path = Path(args.build_report) if args.build_report else Path(
        output_dir / "build-report.json"
    )

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_snapshot, snapshot_path)
    build_report_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(result.build_report_path), build_report_path)

    manifest_payload = json.loads(
        Path(result.manifest_path).read_text(encoding="utf-8")
    )
    manifest_payload["artifacts"]["sqlite"] = snapshot_path.name
    manifest_payload["artifacts"]["sqlite_gzip"] = compressed_path.name
    manifest_identity = manifest_identity_sha256(manifest_payload)

    connection = sqlite3.connect(snapshot_path)
    try:
        connection.execute(
            "update snapshot_meta set value = ? where key = ?",
            (manifest_identity, "manifest_sha256"),
        )
        connection.commit()
    finally:
        connection.close()

    snapshot_bytes = snapshot_path.read_bytes()
    compressed_bytes = gzip.compress(snapshot_bytes, mtime=0)
    compressed_path.parent.mkdir(parents=True, exist_ok=True)
    compressed_path.write_bytes(compressed_bytes)

    manifest_payload["byte_sizes"]["sqlite"] = len(snapshot_bytes)
    manifest_payload["sha256"]["sqlite"] = hashlib.sha256(snapshot_bytes).hexdigest()
    manifest_payload["byte_sizes"]["sqlite_gzip"] = len(compressed_bytes)
    manifest_payload["sha256"]["sqlite_gzip"] = hashlib.sha256(
        compressed_bytes
    ).hexdigest()

    _write_json(manifest_path, manifest_payload)
    return {
        "snapshot": str(snapshot_path),
        "manifest": str(manifest_path),
        "compressed_snapshot": str(compressed_path),
        "build_report": str(build_report_path),
    }


def _aliased_snapshot_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    for alias in (
        args.snapshot,
        args.manifest,
        args.compressed_snapshot,
        args.build_report,
    ):
        if alias:
            return Path(alias).parent
    raise ValueError("snapshot aliases require at least one artifact path")


def _snapshot_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    for alias in (
        args.snapshot,
        args.manifest,
        args.compressed_snapshot,
        args.build_report,
    ):
        if alias:
            return Path(alias).parent
    raise ValueError(
        "build-snapshot requires --output-dir unless an artifact alias path is provided"
    )


def _latest_source_corpus_version(build_db: Path) -> str:
    connection = sqlite3.connect(build_db)
    try:
        row = connection.execute(
            """
            select input_corpus_version
            from builder_runs
            where input_corpus_version is not null
              and trim(input_corpus_version) != ''
            order by started_at desc, builder_run_id desc
            limit 1
            """
        ).fetchone()
    except sqlite3.Error:
        return DEFAULT_SOURCE_CORPUS_VERSION
    finally:
        connection.close()
    if row is None:
        return DEFAULT_SOURCE_CORPUS_VERSION
    return str(row[0])


def _provider_probe_window_defaults(
    build_db: Path,
    *,
    built_at: str,
    explicit_start: str | None,
    explicit_end: str | None,
) -> tuple[str, str]:
    observed_start: str | None = None
    observed_end: str | None = None
    connection = sqlite3.connect(build_db)
    try:
        row = connection.execute(
            """
            select min(observed_at), max(observed_at)
            from provider_recall_observations
            """
        ).fetchone()
    except sqlite3.Error:
        row = None
    finally:
        connection.close()
    if row is not None:
        observed_start = row[0]
        observed_end = row[1]

    return (
        explicit_start or observed_start or built_at,
        explicit_end or observed_end or built_at,
    )


def _object_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "as_dict"):
        return value.as_dict()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _load_attr(module_name: str, attr_name: str) -> Any:
    return getattr(importlib.import_module(module_name), attr_name)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
