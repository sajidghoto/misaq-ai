class MisaqError(Exception):
    """Base class. Catch this, never a bare `except:`."""


class ParsingError(MisaqError):
    pass


class DataValidationError(MisaqError):
    """A data-quality gate failed. The pipeline must stop."""

    def __init__(self, message: str, failures: list[str] | None = None):
        super().__init__(message)
        self.failures = failures or []


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
