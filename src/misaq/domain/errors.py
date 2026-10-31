class MisaqError(Exception):
    """Base class. Catch this, never a bare `except:`."""


class ParsingError(MisaqError):
    pass


class DataValidationError(MisaqError):
    """A data-quality gate failed. The pipeline must stop."""

    def __init__(self, message: str, failures: list[str] | None = None):
        self.failures = failures or []
        detail = f": {'; '.join(self.failures)}" if self.failures else ""
        super().__init__(message + detail)


class RetrievalError(MisaqError):
    pass


class BackendError(MisaqError):
    retryable = False


class RateLimitError(BackendError):
    retryable = True


class BackendTimeoutError(BackendError):
    retryable = True


class ContentFilterError(BackendError):
    pass


class AuthError(BackendError):
    pass


class ManifestError(MisaqError):
    pass
