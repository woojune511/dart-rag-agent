"""Caller-owned persistence of opt-in run observations, including terminal stops."""

from contextlib import contextmanager
import json
import logging
from pathlib import Path
from typing import Iterator

from src.utils.request_diagnostics import capture_request_diagnostics


logger = logging.getLogger(__name__)


@contextmanager
def persist_request_diagnostics(path: Path) -> Iterator[None]:
    """Save the delivered snapshots as a JSON array without changing run outcomes.

    Collection still requires include_debug_bundle on the agent call. No file is
    created when no snapshot was delivered. Existing files are never overwritten;
    persistence errors are logged by class only and cannot replace the original
    result or exception. Process crashes and partial filesystem writes are not
    covered by this exception-delivery boundary.
    """
    with capture_request_diagnostics() as snapshots:
        try:
            yield
        finally:
            if snapshots:
                try:
                    data = json.dumps(snapshots, ensure_ascii=False, allow_nan=False,
                                      separators=(",", ":"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("x", encoding="utf-8") as stream:
                        stream.write(data)
                except (OSError, TypeError, ValueError) as error:
                    logger.error("Request diagnostics were not saved (%s)", type(error).__name__)
