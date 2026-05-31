"""Public snapshot artifact contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from seektalent_keyword_graph.contracts.query_plan import ContractModel, NonEmptyString

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
ArtifactMap = dict[NonEmptyString, NonEmptyString]
ByteSizeMap = dict[NonEmptyString, Annotated[int, Field(ge=0)]]
ChecksumMap = dict[NonEmptyString, Sha256Hex]


class SnapshotMeta(ContractModel):
    """Required metadata embedded in a runtime snapshot."""

    kg_snapshot_id: NonEmptyString
    snapshot_schema_version: Literal["snapshot-v1"]
    selection_policy_version: Literal["policy-v1"]
    built_at: NonEmptyString
    source_corpus_version: NonEmptyString
    builder_run_id: NonEmptyString
    build_report_sha256: Sha256Hex
    manifest_sha256: Sha256Hex
    cts_probe_window_start: NonEmptyString
    cts_probe_window_end: NonEmptyString
    created_by_package_version: NonEmptyString


class SnapshotManifest(ContractModel):
    """External release manifest for runtime snapshot artifacts."""

    schema_version: Literal["snapshot-v1"] = "snapshot-v1"
    kg_snapshot_id: NonEmptyString
    snapshot_schema_version: Literal["snapshot-v1"]
    selection_policy_version: Literal["policy-v1"]
    built_at: NonEmptyString
    source_corpus_version: NonEmptyString
    builder_run_id: NonEmptyString
    artifacts: ArtifactMap = Field(min_length=1)
    byte_sizes: ByteSizeMap = Field(min_length=1)
    sha256: ChecksumMap = Field(min_length=1)

    @model_validator(mode="after")
    def validate_artifact_metadata(self) -> SnapshotManifest:
        artifact_items = [*self.artifacts.items()]
        if any(not key.strip() or not path.strip() for key, path in artifact_items):
            raise ValueError("artifact names and paths must be non-empty")

        artifact_keys = set(self.artifacts)
        if artifact_keys != set(self.byte_sizes) or artifact_keys != set(self.sha256):
            raise ValueError("artifacts, byte_sizes, and sha256 keys must match")

        return self
