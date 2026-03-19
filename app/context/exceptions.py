"""Context engine explicit error types."""


class MissingEnvironmentContextError(ValueError):
    """Raised when required environment context is missing."""


class InvalidEnvironmentConfigurationError(ValueError):
    """Raised when provided environment context is invalid."""
