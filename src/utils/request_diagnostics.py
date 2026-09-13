"""Opt-in, request-owned observations. Never graph state or execution authority."""

from contextlib import contextmanager
from contextvars import ContextVar
import json
from threading import Lock
from typing import Any, Iterator, Literal, TypedDict


class RequestDiagnosticSnapshot(TypedDict):
    schema_version: Literal["request_diagnostics_v1"]
    events: list[dict[str, Any]]


class _Recorder:
    def __init__(self) -> None:
        self._events: list[str] = []
        self._lock = Lock()

    def append(self, kind: str, data: Any) -> None:
        event = {"kind": kind, "location": dict(_LOCATION.get()), "data": data}
        try:
            encoded = json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            # Observability must not mask the original runtime/provider outcome.
            # Do not stringify arbitrary objects or exception bodies.
            event["data"] = {"observation_unavailable": type(error).__name__}
            encoded = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._events.append(encoded)

    def snapshot(self) -> RequestDiagnosticSnapshot:
        with self._lock:
            return {"schema_version": "request_diagnostics_v1",
                    "events": [json.loads(event) for event in self._events]}


_ACTIVE: ContextVar[_Recorder | None] = ContextVar("request_diagnostic_recorder", default=None)
_LOCATION: ContextVar[dict[str, Any]] = ContextVar("request_diagnostic_location", default={})
_CAPTURE: ContextVar[list[RequestDiagnosticSnapshot] | None] = ContextVar("request_diagnostic_capture", default=None)


@contextmanager
def capture_request_diagnostics() -> Iterator[list[RequestDiagnosticSnapshot]]:
    """Caller-owned delivery across exceptions; each run publishes a fresh copy.

    Does not enable collection: the run must still explicitly request debug.
    No observer is attached to shared exceptions, agent instances or graph state.
    """
    delivered: list[RequestDiagnosticSnapshot] = []
    token = _CAPTURE.set(delivered)
    try:
        yield delivered
    finally:
        _CAPTURE.reset(token)


@contextmanager
def request_diagnostic_scope(enabled: bool) -> Iterator[_Recorder | None]:
    recorder = _Recorder() if enabled else None
    token = _ACTIVE.set(recorder)
    location_token = _LOCATION.set({})
    try:
        yield recorder
    finally:
        _LOCATION.reset(location_token)
        _ACTIVE.reset(token)
        capture = _CAPTURE.get()
        if recorder is not None and capture is not None:
            capture.append(recorder.snapshot())


def diagnostics_enabled() -> bool:
    return _ACTIVE.get() is not None


def record_diagnostic(kind: str, data: Any) -> None:
    recorder = _ACTIVE.get()
    if recorder is not None:
        recorder.append(kind, data)


@contextmanager
def diagnostic_location(**fields: Any) -> Iterator[None]:
    if not diagnostics_enabled():
        yield
        return
    token = _LOCATION.set({**_LOCATION.get(), **fields})
    try:
        yield
    finally:
        _LOCATION.reset(token)
