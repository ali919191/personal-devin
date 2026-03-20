"""Built-in integration providers."""

from app.integrations.providers.filesystem import FilesystemIntegration
from app.integrations.providers.http import HTTPIntegration
from app.integrations.providers.mock import MockIntegration
from app.integrations.providers.shell import ShellIntegration

__all__ = ["FilesystemIntegration", "HTTPIntegration", "MockIntegration", "ShellIntegration"]
