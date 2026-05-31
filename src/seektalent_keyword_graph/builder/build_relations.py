"""Build deterministic concepts, concept memberships, and surface relations."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.domain.classification import classify_surface
from seektalent_keyword_graph.domain.models import RelationBuildReport

CREATED_BY = "build_relations:v1"

_SEED_ALIASES = {
    "k8s": "kubernetes",
}
_VERSION_SUFFIX = re.compile(r"^(?P<base>.+?)\s+\d+(?:\.\d+)*$")


@dataclass(frozen=True)
class _Surface:
    surface_id: str
    text_norm: str
    display_text: str
    token_class: str
    jd_df: int
    query_safe: bool


class _DisjointSet:
    def __init__(self, values: list[str]) -> None:
        self._parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self._parent[value]
        if parent != value:
            self._parent[value] = self.find(parent)
        return self._parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            winner, loser = sorted((left_root, right_root))
            self._parent[loser] = winner


def build_relations(store: BuildStore, *, builder_run_id: str) -> RelationBuildReport:
    """Cluster active surfaces into concepts and persist alias/version evidence."""
    now = _utc_now()
    _ensure_builder_run(store, builder_run_id=builder_run_id, now=now)
    _clear_existing_relations(store)

    surfaces = _load_surfaces(store)
    by_norm = {surface.text_norm: surface for surface in surfaces}
    groups = _DisjointSet([surface.text_norm for surface in surfaces])
    relation_specs: list[tuple[_Surface, _Surface, str, float, str]] = []

    for alias_norm, canonical_norm in _SEED_ALIASES.items():
        alias = by_norm.get(alias_norm)
        canonical = by_norm.get(canonical_norm)
        if alias is None or canonical is None:
            continue
        if not _has_jd_relation_evidence(store, alias_norm, canonical_norm):
            continue
        groups.union(alias_norm, canonical_norm)
        relation_specs.append(
            (alias, canonical, "alias", 0.95, "seed_alias_with_jd_evidence")
        )

    for surface in surfaces:
        base_norm = _version_base(surface.text_norm)
        if base_norm is None:
            continue
        base_surface = by_norm.get(base_norm)
        if base_surface is None:
            continue
        groups.union(surface.text_norm, base_norm)
        relation_specs.append(
            (surface, base_surface, "version_variant", 0.9, "version_suffix")
        )

    grouped: dict[str, list[_Surface]] = defaultdict(list)
    for surface in surfaces:
        grouped[groups.find(surface.text_norm)].append(surface)

    concept_count = 0
    concept_surface_count = 0
    for members in sorted(grouped.values(), key=_concept_sort_key):
        safe_members = [member for member in members if member.query_safe]
        if not safe_members:
            continue
        primary = _primary_surface(safe_members)
        concept_id = f"concept:{primary.text_norm}"
        store.insert_concept(
            concept_id=concept_id,
            canonical_label=primary.display_text,
            concept_type=primary.token_class,
            description=f"Canonical concept for {primary.display_text}",
            primary_surface_id=primary.surface_id,
            surface_count=len(members),
            jd_df=_concept_jd_df(store, members),
            stability_score=1.0 if len(members) == 1 else 0.95,
            review_status="pending",
            created_at=now,
            updated_at=now,
        )
        concept_count += 1
        for member in sorted(members, key=lambda item: item.surface_id):
            store.insert_concept_surface(
                concept_id=concept_id,
                surface_id=member.surface_id,
                confidence=1.0 if member.surface_id == primary.surface_id else 0.9,
                source="exact_norm" if len(members) == 1 else "derived_relation",
                status="active",
            )
            concept_surface_count += 1

    for (
        from_surface,
        to_surface,
        relation_type,
        confidence,
        evidence_type,
    ) in relation_specs:
        store.insert_surface_relation(
            relation_id=_relation_id(from_surface, to_surface, relation_type),
            from_surface_id=from_surface.surface_id,
            to_surface_id=to_surface.surface_id,
            relation_type=relation_type,
            confidence=confidence,
            evidence_type=evidence_type,
            created_by=CREATED_BY,
            status="active",
        )

    relation_count = len(relation_specs)
    _upsert_build_event(
        store,
        event_id=f"event:{builder_run_id}:build-relations",
        builder_run_id=builder_run_id,
        event_type="build_relations",
        message="built concepts and surface relations",
        payload_json=(
            f'{{"concept_count":{concept_count},'
            f'"concept_surface_count":{concept_surface_count},'
            f'"relation_count":{relation_count}}}'
        ),
        created_at=now,
    )
    return RelationBuildReport(
        concept_count=concept_count,
        concept_surface_count=concept_surface_count,
        relation_count=relation_count,
    )


def _load_surfaces(store: BuildStore) -> list[_Surface]:
    rows = store.connection.execute(
        """
        select surface_id, text_norm, display_text, token_class, jd_df
        from surfaces
        where serving_status = 'active'
        order by text_norm, surface_id
        """
    ).fetchall()
    return [
        _Surface(
            surface_id=row["surface_id"],
            text_norm=row["text_norm"],
            display_text=row["display_text"],
            token_class=row["token_class"],
            jd_df=row["jd_df"],
            query_safe=classify_surface(row["display_text"]).query_safe,
        )
        for row in rows
    ]


def _clear_existing_relations(store: BuildStore) -> None:
    store.connection.execute("delete from surface_relations")
    store.connection.execute("delete from concept_surfaces")
    store.connection.execute("delete from concepts")
    store.connection.commit()


def _has_jd_relation_evidence(
    store: BuildStore, left_norm: str, right_norm: str
) -> bool:
    row = store.connection.execute(
        """
        select 1
        from keyword_mentions left_mention
        join keyword_mentions right_mention
          on right_mention.jd_id = left_mention.jd_id
        where left_mention.surface_text_norm = ?
          and right_mention.surface_text_norm = ?
          and left_mention.mention_id != right_mention.mention_id
        limit 1
        """,
        (left_norm, right_norm),
    ).fetchone()
    return row is not None


def _concept_jd_df(store: BuildStore, members: list[_Surface]) -> int:
    norms = [member.text_norm for member in members]
    placeholders = ",".join("?" for _ in norms)
    rows = store.connection.execute(
        f"""
        select distinct jd_id
        from keyword_mentions
        where surface_text_norm in ({placeholders})
        """,
        tuple(norms),
    ).fetchall()
    if rows:
        return len(rows)
    return sum(member.jd_df for member in members)


def _version_base(text_norm: str) -> str | None:
    match = _VERSION_SUFFIX.fullmatch(text_norm)
    if match is None:
        return None
    return match.group("base")


def _primary_surface(members: list[_Surface]) -> _Surface:
    return sorted(
        members,
        key=lambda surface: (
            _primary_rank(surface),
            -surface.jd_df,
            len(surface.text_norm),
            surface.text_norm,
        ),
    )[0]


def _primary_rank(surface: _Surface) -> int:
    if surface.text_norm in _SEED_ALIASES.values():
        return 0
    if _version_base(surface.text_norm) is None:
        return 1
    return 2


def _concept_sort_key(members: list[_Surface]) -> tuple[str, str]:
    primary = _primary_surface(members)
    return (primary.text_norm, primary.surface_id)


def _relation_id(
    from_surface: _Surface, to_surface: _Surface, relation_type: str
) -> str:
    digest = hashlib.sha256(
        (
            f"{relation_type}\0{from_surface.text_norm}"
            f"\0{to_surface.text_norm}"
        ).encode()
    ).hexdigest()[:16]
    return f"relation:{relation_type}:{digest}"


def _ensure_builder_run(store: BuildStore, *, builder_run_id: str, now: str) -> None:
    existing = store.connection.execute(
        "select builder_run_id from builder_runs where builder_run_id = ?",
        (builder_run_id,),
    ).fetchone()
    if existing is None:
        store.insert_builder_run(
            builder_run_id=builder_run_id,
            started_at=now,
            input_corpus_version="local-build-db",
            status="running",
            report_json="{}",
        )


def _upsert_build_event(
    store: BuildStore,
    *,
    event_id: str,
    builder_run_id: str,
    event_type: str,
    message: str,
    payload_json: str,
    created_at: str,
) -> None:
    store.connection.execute(
        """
        insert into build_events(
          event_id, builder_run_id, event_type, message, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?)
        on conflict(event_id) do update set
          event_type = excluded.event_type,
          message = excluded.message,
          payload_json = excluded.payload_json,
          created_at = excluded.created_at
        """,
        (event_id, builder_run_id, event_type, message, payload_json, created_at),
    )
    store.connection.commit()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
