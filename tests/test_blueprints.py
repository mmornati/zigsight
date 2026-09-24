"""Test automation blueprint YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

AUTOMATIONS_DIR = Path(__file__).parent.parent / "automations"

BLUEPRINT_FILES = [
    "battery_drain.yaml",
    "reconnect_flap.yaml",
    "network_health_daily_report.yaml",
]


class HomeAssistantLoader(yaml.SafeLoader):
    """YAML loader that handles Home Assistant custom tags like !input."""

    pass


def input_constructor(loader: yaml.Loader, node: yaml.Node) -> str:
    """Handle !input tags by returning the input name as a string."""
    return f"!input:{loader.construct_scalar(node)}"


# Register constructors for Home Assistant tags
HomeAssistantLoader.add_constructor("!input", input_constructor)


def load_yaml_file(filepath: Path) -> dict[str, Any]:
    """Load and parse a YAML file with Home Assistant tag support."""
    with filepath.open(encoding="utf-8") as f:
        return yaml.load(f, Loader=HomeAssistantLoader)


@pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
def test_blueprint_is_valid(blueprint_file: str) -> None:
    """Test that blueprint files are valid YAML with required structure."""
    filepath = AUTOMATIONS_DIR / blueprint_file
    assert filepath.exists(), f"Blueprint file {blueprint_file} does not exist"

    try:
        data = load_yaml_file(filepath)
        assert data is not None, f"{blueprint_file} is empty"

        # Check required top-level keys
        assert "blueprint" in data, f"{blueprint_file} missing 'blueprint' key"
        assert "trigger" in data, f"{blueprint_file} missing 'trigger' key"
        assert "action" in data, f"{blueprint_file} missing 'action' key"

        # Check blueprint metadata
        blueprint = data.get("blueprint", {})
        assert "name" in blueprint, f"{blueprint_file} blueprint missing 'name'"
        assert (
            "description" in blueprint
        ), f"{blueprint_file} blueprint missing 'description'"
        assert (
            blueprint.get("domain") == "automation"
        ), f"{blueprint_file} domain should be 'automation'"

        # Check triggers and actions are lists
        assert isinstance(
            data.get("trigger"), list
        ), f"{blueprint_file} trigger should be a list"
        assert isinstance(
            data.get("action"), list
        ), f"{blueprint_file} action should be a list"
        assert (
            len(data.get("trigger", [])) > 0
        ), f"{blueprint_file} should have at least one trigger"
        assert (
            len(data.get("action", [])) > 0
        ), f"{blueprint_file} should have at least one action"

    except yaml.YAMLError as e:
        pytest.fail(f"{blueprint_file} contains invalid YAML: {e}")
