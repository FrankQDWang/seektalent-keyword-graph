from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keyword-graph")
    subcommands = parser.add_subparsers(dest="command", required=True)

    import_jds = subcommands.add_parser("import-jds")
    import_jds.add_argument("input", type=Path)
    import_jds.add_argument("--build-db", required=True, type=Path)
    import_jds.set_defaults(func=_cmd_import_jds)

    extract_surfaces = subcommands.add_parser("extract-surfaces")
    extract_surfaces.add_argument("text")
    extract_surfaces.set_defaults(func=_cmd_extract_surfaces)

    build_relations = subcommands.add_parser("build-relations")
    build_relations.add_argument("surfaces", nargs="+")
    build_relations.set_defaults(func=_cmd_build_relations)

    probe_cts = subcommands.add_parser("probe-cts")
    probe_cts.add_argument("keyword")
    probe_cts.add_argument("--dry-run", action="store_true")
    probe_cts.add_argument("--real", action="store_true")
    probe_cts.set_defaults(func=_cmd_probe_cts)

    build_snapshot = subcommands.add_parser("build-snapshot")
    build_snapshot.add_argument("--output", required=True, type=Path)
    build_snapshot.set_defaults(func=_cmd_build_snapshot)

    validate_snapshot = subcommands.add_parser("validate-snapshot")
    validate_snapshot.add_argument("--snapshot", required=True, type=Path)
    validate_snapshot.add_argument("--manifest", required=True, type=Path)
    validate_snapshot.set_defaults(func=_cmd_validate_snapshot)

    return parser


def _cmd_import_jds(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.import_jds import import_jds

    import_jds(args.input, args.build_db)
    return 0


def _cmd_extract_surfaces(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.extract_surfaces import extract_surface_mentions

    print(json.dumps(extract_surface_mentions(args.text), ensure_ascii=False))
    return 0


def _cmd_build_relations(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.build_relations import build_seed_relations

    print(json.dumps(build_seed_relations(args.surfaces), ensure_ascii=False))
    return 0


def _cmd_probe_cts(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.cts.count_client import CtsCountClient
    from seektalent_keyword_graph.cts.probe_window import can_run_real_probe

    client = CtsCountClient(
        base_url=os.environ.get("KEYWORD_GRAPH_CTS_BASE_URL", ""),
        tenant_key=os.environ.get("KEYWORD_GRAPH_CTS_TENANT_KEY", ""),
        tenant_secret=os.environ.get("KEYWORD_GRAPH_CTS_TENANT_SECRET", ""),
    )
    if args.dry_run or not args.real:
        print(json.dumps(client.build_payload(args.keyword), ensure_ascii=False))
        return 0

    now = datetime.now().time()
    if not can_run_real_probe(False, now, time(9, 0), time(21, 0)):
        print("real CTS probe blocked outside 09:00-21:00", file=sys.stderr)
        return 2

    print("real CTS probe requires an explicit implementation gate", file=sys.stderr)
    return 2


def _cmd_build_snapshot(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.build_snapshot import build_runtime_snapshot

    build_runtime_snapshot(args.output)
    return 0


def _cmd_validate_snapshot(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.release_validation import validate_snapshot_artifact

    return 0 if validate_snapshot_artifact(args.snapshot, args.manifest) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
