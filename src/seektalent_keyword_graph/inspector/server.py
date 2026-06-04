"""Stdlib HTTP server for the local snapshot inspector."""

from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pydantic import ValidationError

from seektalent_keyword_graph import (
    KeywordGraph,
    KeywordGraphRuntimeError,
    QueryRecallRequest,
    SnapshotError,
)

ASSET_PACKAGE = "seektalent_keyword_graph.inspector.assets"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MAX_ALTERNATIVES = 10
DEFAULT_MAX_PRECISION_COMPANIONS = 3


@dataclass(frozen=True)
class InspectorServerConfig:
    """Startup configuration for the local inspector server."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    snapshot_path: Path | None = None
    manifest_path: Path | None = None

    def __post_init__(self) -> None:
        if self.host != DEFAULT_HOST:
            raise ValueError("inspect-ui only supports host 127.0.0.1")
        if not 0 <= self.port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if self.manifest_path is not None and self.snapshot_path is None:
            raise ValueError("manifest override requires --snapshot")


class InspectorStartupError(RuntimeError):
    """Startup error with a stable local API-style code."""

    def __init__(
        self, code: str, message: str, details: dict[str, object] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = {} if details is None else details


class InspectorApp:
    """Opened read-only runtime snapshot plus presentation metadata."""

    def __init__(
        self,
        *,
        snapshot_source: str,
        snapshot_path: Path,
        manifest_path: Path | None,
        meta: dict[str, str],
        providers: list[str],
    ) -> None:
        self.snapshot_source = snapshot_source
        self.snapshot_path = snapshot_path
        self.manifest_path = manifest_path
        self.meta = meta
        self.providers = providers

    @classmethod
    def open(cls, config: InspectorServerConfig) -> InspectorApp:
        try:
            if config.snapshot_path is not None:
                graph = KeywordGraph.open(config.snapshot_path, config.manifest_path)
                try:
                    return cls(
                        snapshot_source="override",
                        snapshot_path=config.snapshot_path,
                        manifest_path=config.manifest_path,
                        meta=graph.store.meta(),
                        providers=graph.store.list_supported_providers(),
                    )
                finally:
                    graph.close()
            graph = KeywordGraph.open_default({})
            try:
                snapshot_path = graph.store.path
                manifest_path = snapshot_path.with_name("snapshot-manifest.json")
                return cls(
                    snapshot_source="bundled",
                    snapshot_path=snapshot_path,
                    manifest_path=manifest_path if manifest_path.is_file() else None,
                    meta=graph.store.meta(),
                    providers=graph.store.list_supported_providers(),
                )
            finally:
                graph.close()
        except SnapshotError as exc:
            raise InspectorStartupError(
                "invalid_snapshot",
                str(exc),
                {"snapshot_path": _path_detail(config.snapshot_path)},
            ) from exc

    def close(self) -> None:
        return

    def open_graph(self) -> KeywordGraph:
        return KeywordGraph.open(self.snapshot_path, self.manifest_path)

    def default_provider(self) -> str:
        if "cts" in self.providers:
            return "cts"
        return self.providers[0]

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "source": self.snapshot_source,
            "path": str(self.snapshot_path),
            "manifest_path": (
                None if self.manifest_path is None else str(self.manifest_path)
            ),
        }


class InspectorHTTPServer(ThreadingHTTPServer):
    """HTTP server that owns an opened inspector app."""

    allow_reuse_address = True

    def __init__(
        self, server_address: tuple[str, int], app: InspectorApp
    ) -> None:
        self.app = app
        super().__init__(server_address, InspectorRequestHandler)

    def server_close(self) -> None:
        try:
            self.app.close()
        finally:
            super().server_close()


class InspectorRequestHandler(BaseHTTPRequestHandler):
    """Route static assets and local JSON inspector API calls."""

    server: InspectorHTTPServer
    server_version = "KeywordGraphInspector/0.1"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._write_asset("index.html")
            return
        if path.startswith("/assets/"):
            self._write_asset(unquote(path.removeprefix("/assets/")))
            return
        if path == "/api/providers":
            self._write_json(
                HTTPStatus.OK,
                {
                    "providers": self.server.app.providers,
                    "default": self.server.app.default_provider(),
                },
            )
            return
        if path == "/api/meta":
            app = self.server.app
            self._write_json(
                HTTPStatus.OK,
                {
                    "snapshot": app.snapshot_payload(),
                    "meta": app.meta,
                    "providers": app.providers,
                },
            )
            return
        self._write_error(
            HTTPStatus.NOT_FOUND,
            "invalid_request",
            "Unknown inspector route.",
            {"path": path},
        )

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != "/api/query-recall":
            self._write_error(
                HTTPStatus.NOT_FOUND,
                "invalid_request",
                "Unknown inspector route.",
                {"path": path},
            )
            return
        self._handle_query_recall()

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _handle_query_recall(self) -> None:
        try:
            payload = query_recall_payload(
                self.server.app,
                self._read_json_request(),
            )
        except json.JSONDecodeError:
            self._write_error(
                HTTPStatus.BAD_REQUEST,
                "invalid_request",
                "Request body must be valid JSON.",
                {},
            )
            return
        except ValueError as exc:
            self._write_error(
                HTTPStatus.BAD_REQUEST,
                "invalid_request",
                str(exc),
                {},
            )
            return
        except ValidationError as exc:
            self._write_error(
                HTTPStatus.BAD_REQUEST,
                "invalid_request",
                "Query recall request is invalid.",
                {"errors": exc.errors(include_url=False, include_context=False)},
            )
            return
        except SnapshotError as exc:
            self._write_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "invalid_snapshot",
                str(exc),
                {"snapshot_path": str(self.server.app.snapshot_path)},
            )
            return
        except KeywordGraphRuntimeError as exc:
            if str(exc).startswith("unsupported provider:"):
                self._write_error(
                    HTTPStatus.BAD_REQUEST,
                    "unsupported_provider",
                    "Provider is not available in this snapshot.",
                    {"providers": self.server.app.providers},
                )
                return
            self._write_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                "Query recall failed.",
                {"reason": type(exc).__name__},
            )
            return
        except Exception as exc:
            self._write_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                "Unexpected inspector failure.",
                {"reason": type(exc).__name__},
            )
            return

        empty_state = _empty_state(payload)
        if empty_state is not None:
            status, code, message = empty_state
            self._write_error(
                status,
                code,
                message,
                {"response": payload["response"]},
            )
            return
        self._write_json(HTTPStatus.OK, payload)

    def _read_json_request(self) -> object:
        raw_length = self.headers.get("content-length", "0")
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ValueError("content-length must be an integer") from exc
        if content_length > 65_536:
            raise ValueError("request body must be 65536 bytes or smaller")
        body = self.rfile.read(content_length)
        if not body:
            raise ValueError("request body is required")
        return json.loads(body.decode("utf-8"))

    def _write_asset(self, name: str) -> None:
        if "/" in name or "\\" in name or name in {"", ".", ".."}:
            self._write_error(
                HTTPStatus.NOT_FOUND,
                "invalid_request",
                "Static asset path is not available.",
                {"path": name},
            )
            return
        asset = resources.files(ASSET_PACKAGE).joinpath(name)
        if not asset.is_file():
            self._write_error(
                HTTPStatus.NOT_FOUND,
                "invalid_request",
                "Static asset path is not available.",
                {"path": name},
            )
            return
        content = asset.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }.get(Path(name).suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(content)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _write_error(
        self,
        status: HTTPStatus,
        code: str,
        message: str,
        details: dict[str, object],
    ) -> None:
        self._write_json(
            status,
            {"error": {"code": code, "message": message, "details": details}},
        )


def create_server(config: InspectorServerConfig) -> InspectorHTTPServer:
    app = InspectorApp.open(config)
    try:
        return InspectorHTTPServer((config.host, config.port), app)
    except Exception:
        app.close()
        raise


def run_server(
    *,
    port: int = DEFAULT_PORT,
    snapshot_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> int:
    config = InspectorServerConfig(
        port=port,
        snapshot_path=None if snapshot_path is None else Path(snapshot_path),
        manifest_path=None if manifest_path is None else Path(manifest_path),
    )
    server = create_server(config)
    host, bound_port = server.server_address[:2]
    print(
        json.dumps(
            {
                "command": "inspect-ui",
                "status": "listening",
                "url": f"http://{host}:{bound_port}",
                "snapshot": server.app.snapshot_payload(),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def query_recall_payload(app: InspectorApp, raw_payload: object) -> dict[str, object]:
    """Return query recall response payload for API and focused unit tests."""

    if not isinstance(raw_payload, dict):
        raise ValueError("JSON request body must be an object")
    provider = _required_string(raw_payload, "provider")
    query_text = _required_string(raw_payload, "query_text")
    query_mode = raw_payload.get("query_mode", "keyword")
    max_alternatives = raw_payload.get(
        "max_alternatives", DEFAULT_MAX_ALTERNATIVES
    )
    max_precision_companions = raw_payload.get(
        "max_precision_companions", DEFAULT_MAX_PRECISION_COMPANIONS
    )
    if provider not in app.providers:
        raise KeywordGraphRuntimeError(f"unsupported provider: {provider}")

    request = QueryRecallRequest(
        request_id=_request_id(provider, query_mode, query_text),
        provider=provider,
        query_text=query_text,
        query_mode=query_mode,
        max_alternatives=max_alternatives,
        max_precision_companions=max_precision_companions,
    )
    graph = app.open_graph()
    try:
        response = graph.analyze_query_recall(request)
    finally:
        graph.close()
    return {
        "request": request.model_dump(mode="json"),
        "response": response.model_dump(mode="json"),
    }


def _empty_state(
    payload: dict[str, object],
) -> tuple[HTTPStatus, str, str] | None:
    response = payload["response"]
    if not isinstance(response, dict):
        return None
    warnings = response.get("warnings", [])
    if not isinstance(warnings, list):
        return None
    warning_codes = {
        warning.get("code")
        for warning in warnings
        if isinstance(warning, dict)
    }
    if (
        "no_match" in warning_codes
        and response.get("input_observations") == []
    ):
        return (
            HTTPStatus.NOT_FOUND,
            "no_match",
            "No active graph match was found for this query.",
        )
    if "matched_without_observation" in warning_codes:
        return (
            HTTPStatus.CONFLICT,
            "matched_without_observation",
            "The query matched a graph surface without a provider observation.",
        )
    return None


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _request_id(provider: str, query_mode: object, query_text: str) -> str:
    normalized = "|".join((provider, str(query_mode), query_text.strip().casefold()))
    safe = "".join(
        character if character.isalnum() else "-" for character in normalized
    ).strip("-")
    return f"inspector-{safe[:96]}"


def _path_detail(path: Path | None) -> str | None:
    return None if path is None else str(path)
