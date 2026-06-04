"""Public package metadata and runtime facade export."""

from seektalent_keyword_graph.contracts import (
    QueryPlanRequest,
    QueryPlanResponse,
    QueryRecallRequest,
    QueryRecallResponse,
)
from seektalent_keyword_graph.engine import KeywordGraph
from seektalent_keyword_graph.runtime.errors import (
    KeywordGraphRuntimeError,
    SnapshotChecksumError,
    SnapshotError,
    SnapshotFormatError,
    SnapshotPrivacyError,
    SnapshotSchemaError,
    UnsupportedSnapshotVersionError,
)

__version__ = "0.1.0"

__all__ = [
    "KeywordGraph",
    "KeywordGraphRuntimeError",
    "QueryPlanRequest",
    "QueryPlanResponse",
    "QueryRecallRequest",
    "QueryRecallResponse",
    "SnapshotChecksumError",
    "SnapshotError",
    "SnapshotFormatError",
    "SnapshotPrivacyError",
    "SnapshotSchemaError",
    "UnsupportedSnapshotVersionError",
    "__version__",
]
