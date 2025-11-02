"""Test manifest.json."""
import json
from pathlib import Path


def test_manifest_exists() -> None:
    """Test that manifest.json exists."""
    manifest_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "zigsight"
        / "manifest.json"
    )
    assert manifest_path.exists(), "manifest.json does not exist"


def test_manifest_has_required_fields() -> None:
    """Test that manifest.json contains required fields."""
    manifest_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "zigsight"
        / "manifest.json"
    )

    with manifest_path.open() as f:
        manifest = json.load(f)

    required_fields = [
        "domain",
        "name",
        "version",
        "codeowners",
    ]

    for field in required_fields:
        assert field in manifest, f"manifest.json missing required field: {field}"

    assert manifest["domain"] == "zigsight", "manifest.json domain should be 'zigsight'"
    assert isinstance(
        manifest["version"], str
    ), "manifest.json version should be a string"
