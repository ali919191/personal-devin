"""Adapter scaffolding for future provider-specific normalization."""

from app.context.adapters.aws_adapter import AWSContextAdapter
from app.context.adapters.azure_adapter import AzureContextAdapter
from app.context.adapters.base import ContextAdapter
from app.context.adapters.gcp_adapter import GCPContextAdapter

__all__ = [
    "ContextAdapter",
    "AWSContextAdapter",
    "AzureContextAdapter",
    "GCPContextAdapter",
]
