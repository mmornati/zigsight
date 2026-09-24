"""Static guards for the frontend files in custom_components/zigsight/www.

The JavaScript itself is unit tested with ``node --test tests/js/*.test.mjs``
(see the CI workflow); these checks run with pytest so they can't be skipped.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WWW = Path(__file__).parent.parent / "custom_components" / "zigsight" / "www"
VENDOR = WWW / "vendor"

OWN_JS = sorted(path for path in WWW.rglob("*.js") if VENDOR not in path.parents)

# Sinks that parse strings as HTML. API data (device names, models, ...) is
# attacker controllable (anyone who can rename a Zigbee device), so the code
# must only use Lit templates / textContent.
HTML_SINKS = re.compile(
    r"\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML|document\.write|unsafeHTML"
    r"|unsafeSVG|\beval\s*\(|new\s+Function\s*\("
)
REMOTE_IMPORT = re.compile(r"""https?://|//unpkg|cdn\.jsdelivr|cdnjs""")
IMPORT_SPEC = re.compile(r"""(?:import|from)\s*["']([^"']+)["']""")


def test_frontend_files_found() -> None:
    """Sanity check of the file discovery."""
    names = {path.name for path in OWN_JS}
    assert {
        "zigsight-panel.js",
        "topology-card.js",
        "topology-visualization.js",
        "topology-graph.js",
    } <= names


@pytest.mark.parametrize("path", OWN_JS, ids=lambda p: p.name)
def test_no_html_string_sinks(path: Path) -> None:
    """No innerHTML & co: every string reaches the DOM escaped."""
    matches = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if HTML_SINKS.search(line) and not line.strip().startswith(("*", "//"))
    ]
    assert not matches, f"HTML string sinks in {path.name}: {matches}"


@pytest.mark.parametrize("path", OWN_JS, ids=lambda p: p.name)
def test_only_relative_imports(path: Path) -> None:
    """Everything is served locally: works offline, no CDN at runtime."""
    text = path.read_text()
    for spec in IMPORT_SPEC.findall(text):
        assert spec.startswith("./") or spec.startswith("../"), (path.name, spec)
        assert (path.parent / spec).resolve().is_file(), (path.name, spec)
    code = "\n".join(
        line
        for line in text.splitlines()
        if not line.strip().startswith(("*", "//", "/*"))
    )
    assert not REMOTE_IMPORT.search(code), path.name


def test_vendored_files_documented() -> None:
    """Vendored builds ship with their license and provenance."""
    assert (VENDOR / "lit-core.min.js").is_file()
    assert (VENDOR / "LICENSE-lit").is_file()
    readme = (VENDOR / "README.md").read_text()
    assert "lit-core.min.js" in readme
    assert "3.3.3" in readme
