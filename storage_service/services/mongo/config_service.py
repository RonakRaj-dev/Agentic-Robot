"""Config service — file-backed implementation.

The architecture document (section 8) requires every AI-tunable knob —
system prompts, tool bindings, model routing, generation/validation
params — to live in Config, not code.  The MVP ships the file backend.

This implementation loads a JSON config file (default path:
``./config.json``) on first access, validates it, and caches it in
memory.  ``reload_config()`` re-reads the file.

The ``create_indexes()`` method delegates to :func:`db.indexes.create_indexes`
so application startup can go through the service layer instead of
calling the bootstrap function directly.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from interfaces.config_service import IConfigService

logger = get_logger(__name__)


# Required top-level keys in the config document (architecture doc 8).
_REQUIRED_TOP_KEYS = {"version", "model_roles", "agents", "generation", "validation"}

# Required keys inside ``model_roles``.
_REQUIRED_MODEL_ROLE_KEYS = {"default"}


class FileConfigService(IConfigService):
    """File-backed ConfigService.

    Loads ``config.json`` from the project root (override with the
    ``config_path`` constructor arg).  Returns a sensible default config
    when the file is missing so unit tests don't require a config file.
    """

    DEFAULT_CONFIG: dict[str, Any] = {
        "version": 3,
        "model_roles": {
            "default": {"provider": "openai", "model_name": "<general>"},
            "math": {"provider": "dashscope", "model_name": "<reasoning>"},
            "validator": {"provider": "anthropic", "model_name": "<general>"},
            "vision": {"provider": "openai", "model_name": "<multimodal>"},
        },
        "agents": {
            "planner": {
                "system_prompt": "",
                "model": "default",
                "tools": ["allocate", "conformance_count"],
            },
            "subject.math": {
                "system_prompt": "",
                "model": "math",
                "tools": ["sympy_check"],
            },
            "component_provider": {
                "system_prompt": "",
                "model": "vision",
                "tools": ["sympy_check", "object_fetch"],
            },
            "qa_validator": {
                "system_prompt": "",
                "model": "validator",
                "tools": ["sympy_check", "numeric_eval"],
            },
        },
        "generation": {
            "temperature": 0.4,
            "max_refine": 2,
            "max_topup": 3,
        },
        "validation": {
            "difficulty_confidence_min": 0.6,
            "dedup_text_threshold": 0.9,
        },
    }

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or Path("./config.json")
        self._config: dict[str, Any] | None = None

    async def get_config(self) -> dict[str, Any]:
        if self._config is None:
            await self.reload_config()
        assert self._config is not None
        return self._config

    async def validate_config(self) -> list[str]:
        cfg = await self.get_config()
        errors: list[str] = []
        missing_top = _REQUIRED_TOP_KEYS - set(cfg.keys())
        if missing_top:
            errors.append(f"Missing top-level keys: {sorted(missing_top)}")
        model_roles = cfg.get("model_roles", {})
        missing_roles = _REQUIRED_MODEL_ROLE_KEYS - set(model_roles.keys())
        if missing_roles:
            errors.append(
                f"Missing required model_roles: {sorted(missing_roles)}"
            )
        agents = cfg.get("agents", {})
        if not agents:
            errors.append("agents block is empty")
        gen = cfg.get("generation", {})
        if not isinstance(gen.get("temperature"), (int, float)):
            errors.append("generation.temperature must be a number")
        if not isinstance(gen.get("max_refine"), int):
            errors.append("generation.max_refine must be an int")
        if not isinstance(gen.get("max_topup"), int):
            errors.append("generation.max_topup must be an int")
        return errors

    async def reload_config(self) -> dict[str, Any]:
        if self._config_path.exists():
            try:
                self._config = json.loads(self._config_path.read_text())
                logger.info(
                    "config_loaded_from_file", path=str(self._config_path),
                )
            except Exception as exc:
                logger.error(
                    "config_load_failed",
                    path=str(self._config_path), error=str(exc),
                )
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            logger.info(
                "config_file_missing_using_defaults",
                path=str(self._config_path),
            )
            self._config = self.DEFAULT_CONFIG.copy()
        return self._config

    async def create_indexes(self) -> None:
        """Ensure all MongoDB indexes are created.

        Delegates to :func:`db.indexes.create_indexes` so the bootstrap
        path goes through the service layer.  Safe to call multiple times
        — MongoDB ``create_index`` is idempotent.
        """
        from db.indexes import create_indexes
        await create_indexes()
