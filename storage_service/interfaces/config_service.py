"""Config service interface.

The architecture document (section 8) requires every AI-tunable knob —
system prompts, tool bindings, model routing, generation/validation
params — to live in Config, not code.  Config is read through a
ConfigProvider interface with swappable backends (a JSON file or a
Mongo configs collection); the MVP ships the file backend.

Versioned, validated on load, hot-reloadable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IConfigService(ABC):
    """Externalized AI/agent/model configuration."""

    @abstractmethod
    async def get_config(self) -> dict[str, Any]:
        """Return the full config document.

        Shape (illustrative)::

            {
              "version": 3,
              "model_roles": { "default": {...}, "math": {...}, ... },
              "agents": { "planner": {...}, "subject.math": {...}, ... },
              "generation": { "temperature": 0.4, "max_refine": 2, ... },
              "validation": { "difficulty_confidence_min": 0.6, ... }
            }
        """
        ...

    @abstractmethod
    async def validate_config(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        ...

    @abstractmethod
    async def reload_config(self) -> dict[str, Any]:
        """Re-read the config from the backend and return the new value."""
        ...

    @abstractmethod
    async def create_indexes(self) -> None:
        """Ensure all MongoDB indexes are created.

        This is a bootstrap operation that the application calls once
        at startup.  It is exposed on the config service (rather than
        the book service) because index creation is a cross-cutting
        infrastructure concern, not a per-aggregate business operation.
        """
        ...
