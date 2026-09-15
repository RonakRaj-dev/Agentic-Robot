"""Unit tests: ConfigService (in-memory implementation).

The in-memory implementation returns a valid default config.  The
file-backed implementation (``FileConfigService``) is tested
separately against a temp JSON file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio


async def test_get_config_returns_default(in_memory_services):
    svc = in_memory_services.config_service
    cfg = await svc.get_config()
    assert cfg["version"] == 3
    assert "model_roles" in cfg
    assert "agents" in cfg
    assert "generation" in cfg
    assert "validation" in cfg


async def test_validate_config_default_is_valid(in_memory_services):
    svc = in_memory_services.config_service
    errors = await svc.validate_config()
    assert errors == []


async def test_reload_config_returns_config(in_memory_services):
    svc = in_memory_services.config_service
    cfg = await svc.reload_config()
    assert "version" in cfg


async def test_create_indexes_no_op_in_memory(in_memory_services):
    svc = in_memory_services.config_service
    # Should not raise.
    await svc.create_indexes()
    assert svc._indexes_created is True


# ── FileConfigService ────────────────────────────────────────────────


async def test_file_config_service_loads_from_file(tmp_path: Path):
    from services.mongo.config_service import FileConfigService

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "version": 3,
        "model_roles": {
            "default": {"provider": "openai", "model_name": "gpt-4"},
        },
        "agents": {
            "planner": {"system_prompt": "", "model": "default", "tools": []},
        },
        "generation": {"temperature": 0.5, "max_refine": 2, "max_topup": 3},
        "validation": {"difficulty_confidence_min": 0.6, "dedup_text_threshold": 0.9},
    }))

    svc = FileConfigService(config_path=config_path)
    cfg = await svc.get_config()
    assert cfg["model_roles"]["default"]["model_name"] == "gpt-4"
    errors = await svc.validate_config()
    assert errors == []


async def test_file_config_service_falls_back_to_default_when_missing(tmp_path: Path):
    from services.mongo.config_service import FileConfigService

    config_path = tmp_path / "does-not-exist.json"
    svc = FileConfigService(config_path=config_path)
    cfg = await svc.get_config()
    # Default config is returned.
    assert cfg["version"] == 3


async def test_file_config_service_detects_missing_keys(tmp_path: Path):
    from services.mongo.config_service import FileConfigService

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "version": 3,
        # Missing: model_roles, agents, generation, validation
    }))
    svc = FileConfigService(config_path=config_path)
    errors = await svc.validate_config()
    assert len(errors) > 0
    assert any("Missing top-level keys" in e for e in errors)


async def test_file_config_service_reload_picks_up_changes(tmp_path: Path):
    from services.mongo.config_service import FileConfigService

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "version": 3,
        "model_roles": {"default": {"provider": "openai", "model_name": "v1"}},
        "agents": {"planner": {"system_prompt": "", "model": "default", "tools": []}},
        "generation": {"temperature": 0.4, "max_refine": 2, "max_topup": 3},
        "validation": {"difficulty_confidence_min": 0.6, "dedup_text_threshold": 0.9},
    }))
    svc = FileConfigService(config_path=config_path)
    cfg = await svc.get_config()
    assert cfg["model_roles"]["default"]["model_name"] == "v1"

    # Rewrite and reload.
    config_path.write_text(json.dumps({
        "version": 3,
        "model_roles": {"default": {"provider": "openai", "model_name": "v2"}},
        "agents": {"planner": {"system_prompt": "", "model": "default", "tools": []}},
        "generation": {"temperature": 0.4, "max_refine": 2, "max_topup": 3},
        "validation": {"difficulty_confidence_min": 0.6, "dedup_text_threshold": 0.9},
    }))
    cfg = await svc.reload_config()
    assert cfg["model_roles"]["default"]["model_name"] == "v2"
