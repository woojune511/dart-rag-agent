"""Terminal admission failures, separate from repairable model output errors."""


class ProviderAdmissionError(RuntimeError):
    """A caller's execution boundary forbids continuing or retrying a request."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


# Standard RPC names only; provider messages/details can contain credentials.
_PUBLIC_RPC_STATUSES = frozenset({
    "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT", "DEADLINE_EXCEEDED", "NOT_FOUND",
    "ALREADY_EXISTS", "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "FAILED_PRECONDITION",
    "ABORTED", "OUT_OF_RANGE", "UNIMPLEMENTED", "INTERNAL", "UNAVAILABLE", "DATA_LOSS",
    "UNAUTHENTICATED",
})


def provider_error_projection(error: BaseException) -> dict[str, str | int | None]:
    """Copy safe codes from explicit causes, never messages, URLs or SDK bodies."""
    result: dict[str, str | int | None] = {"error_type": type(error).__name__,
        "code": error.code if isinstance(error, ProviderAdmissionError) else None,
        "http_status": None, "provider_status": None}
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for field in ("status_code", "code"):
            code = getattr(current, field, None)
            if result["http_status"] is None and type(code) is int and 400 <= code <= 599:
                result["http_status"] = code
        status = getattr(current, "status", None)
        if result["provider_status"] is None and type(status) is str and status in _PUBLIC_RPC_STATUSES:
            result["provider_status"] = status
        current = current.__cause__
    return result
