"""Terminal admission failures, separate from repairable model output errors."""


class ProviderAdmissionError(RuntimeError):
    """A caller's execution boundary forbids continuing or retrying a request."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
