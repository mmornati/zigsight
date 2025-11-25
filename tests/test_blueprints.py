"""Test automation blueprint YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

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


class TestBlueprintFilesExist:
    """Test that all expected blueprint files exist."""

    def test_automations_directory_exists(self) -> None:
        """Test that the automations directory exists."""
        assert AUTOMATIONS_DIR.exists(), "automations/ directory does not exist"
        assert AUTOMATIONS_DIR.is_dir(), "automations/ is not a directory"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_file_exists(self, blueprint_file: str) -> None:
        """Test that each blueprint file exists."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        assert filepath.exists(), f"Blueprint file {blueprint_file} does not exist"


class TestBlueprintYamlValidity:
    """Test that blueprint YAML files are valid."""

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_is_valid_yaml(self, blueprint_file: str) -> None:
        """Test that blueprint files are valid YAML."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        try:
            data = load_yaml_file(filepath)
            assert data is not None, f"{blueprint_file} is empty"
        except yaml.YAMLError as e:
            pytest.fail(f"{blueprint_file} contains invalid YAML: {e}")

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_has_required_keys(self, blueprint_file: str) -> None:
        """Test that blueprint files have required top-level keys."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)

        assert "blueprint" in data, f"{blueprint_file} missing 'blueprint' key"
        assert "trigger" in data, f"{blueprint_file} missing 'trigger' key"
        assert "action" in data, f"{blueprint_file} missing 'action' key"


class TestBlueprintMetadata:
    """Test blueprint metadata is properly defined."""

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_has_name(self, blueprint_file: str) -> None:
        """Test that blueprint has a name."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})

        assert "name" in blueprint, f"{blueprint_file} blueprint missing 'name'"
        assert blueprint["name"], f"{blueprint_file} blueprint name is empty"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_has_description(self, blueprint_file: str) -> None:
        """Test that blueprint has a description."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})

        assert (
            "description" in blueprint
        ), f"{blueprint_file} blueprint missing 'description'"
        assert blueprint["description"], f"{blueprint_file} blueprint description is empty"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_has_domain(self, blueprint_file: str) -> None:
        """Test that blueprint has domain set to 'automation'."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})

        assert "domain" in blueprint, f"{blueprint_file} blueprint missing 'domain'"
        assert (
            blueprint["domain"] == "automation"
        ), f"{blueprint_file} blueprint domain should be 'automation'"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_has_author(self, blueprint_file: str) -> None:
        """Test that blueprint has an author."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})

        assert "author" in blueprint, f"{blueprint_file} blueprint missing 'author'"
        assert blueprint["author"] == "ZigSight", f"{blueprint_file} author should be 'ZigSight'"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_has_source_url(self, blueprint_file: str) -> None:
        """Test that blueprint has a source URL."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})

        assert (
            "source_url" in blueprint
        ), f"{blueprint_file} blueprint missing 'source_url'"
        assert blueprint["source_url"].startswith(
            "https://github.com/mmornati/zigsight"
        ), f"{blueprint_file} source_url should point to zigsight repository"


class TestBlueprintInputs:
    """Test blueprint input definitions."""

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_blueprint_has_inputs(self, blueprint_file: str) -> None:
        """Test that blueprint has input definitions."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})

        assert "input" in blueprint, f"{blueprint_file} blueprint missing 'input'"
        assert blueprint["input"], f"{blueprint_file} blueprint has no inputs defined"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_inputs_have_required_fields(self, blueprint_file: str) -> None:
        """Test that each input has required fields."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})
        inputs = blueprint.get("input", {})

        for input_name, input_def in inputs.items():
            assert (
                "name" in input_def
            ), f"{blueprint_file} input '{input_name}' missing 'name'"
            assert (
                "description" in input_def
            ), f"{blueprint_file} input '{input_name}' missing 'description'"
            assert (
                "selector" in input_def or "default" in input_def
            ), f"{blueprint_file} input '{input_name}' needs 'selector' or 'default'"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_has_notify_service_input(self, blueprint_file: str) -> None:
        """Test that blueprints have a notify_service input."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)
        blueprint = data.get("blueprint", {})
        inputs = blueprint.get("input", {})

        assert (
            "notify_service" in inputs
        ), f"{blueprint_file} missing 'notify_service' input"


class TestBlueprintTriggers:
    """Test blueprint trigger definitions."""

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_triggers_are_list(self, blueprint_file: str) -> None:
        """Test that triggers are defined as a list."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)

        triggers = data.get("trigger", [])
        assert isinstance(triggers, list), f"{blueprint_file} trigger should be a list"
        assert len(triggers) > 0, f"{blueprint_file} should have at least one trigger"

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_triggers_have_platform(self, blueprint_file: str) -> None:
        """Test that each trigger has a platform defined."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)

        triggers = data.get("trigger", [])
        for i, trigger in enumerate(triggers):
            assert (
                "platform" in trigger
            ), f"{blueprint_file} trigger {i} missing 'platform'"


class TestBlueprintActions:
    """Test blueprint action definitions."""

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_actions_are_list(self, blueprint_file: str) -> None:
        """Test that actions are defined as a list."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)

        actions = data.get("action", [])
        assert isinstance(actions, list), f"{blueprint_file} action should be a list"
        assert len(actions) > 0, f"{blueprint_file} should have at least one action"


class TestSpecificBlueprints:
    """Test specific blueprint requirements."""

    def test_battery_drain_has_threshold_input(self) -> None:
        """Test battery_drain blueprint has battery threshold input."""
        filepath = AUTOMATIONS_DIR / "battery_drain.yaml"
        data = load_yaml_file(filepath)
        inputs = data.get("blueprint", {}).get("input", {})

        assert "battery_threshold" in inputs, "battery_drain missing battery_threshold input"
        threshold = inputs["battery_threshold"]
        assert "default" in threshold, "battery_threshold should have a default value"
        assert threshold["default"] == 20, "battery_threshold default should be 20"

    def test_reconnect_flap_has_count_threshold(self) -> None:
        """Test reconnect_flap blueprint has reconnect count threshold."""
        filepath = AUTOMATIONS_DIR / "reconnect_flap.yaml"
        data = load_yaml_file(filepath)
        inputs = data.get("blueprint", {}).get("input", {})

        assert (
            "reconnect_count_threshold" in inputs
        ), "reconnect_flap missing reconnect_count_threshold input"

    def test_daily_report_has_time_input(self) -> None:
        """Test network_health_daily_report blueprint has report time input."""
        filepath = AUTOMATIONS_DIR / "network_health_daily_report.yaml"
        data = load_yaml_file(filepath)
        inputs = data.get("blueprint", {}).get("input", {})

        assert "report_time" in inputs, "daily report missing report_time input"
        report_time = inputs["report_time"]
        assert "default" in report_time, "report_time should have a default value"


class TestBlueprintVariables:
    """Test blueprint variables are correctly defined."""

    @pytest.mark.parametrize("blueprint_file", BLUEPRINT_FILES)
    def test_variables_at_top_level(self, blueprint_file: str) -> None:
        """Test that variables are defined at blueprint top level, not nested."""
        filepath = AUTOMATIONS_DIR / blueprint_file
        data = load_yaml_file(filepath)

        # Variables should be at top level if they exist
        if "variables" in data:
            assert isinstance(
                data["variables"], dict
            ), f"{blueprint_file} variables should be a dict"

        # Check conditions don't have improperly nested variables
        conditions = data.get("condition", [])
        for i, condition in enumerate(conditions):
            if condition.get("condition") == "template":
                # Template conditions should not have variables at this level
                # Variables should be at the blueprint top level
                assert (
                    "variables" not in condition
                ), f"{blueprint_file} condition {i} has nested variables - move to top level"
