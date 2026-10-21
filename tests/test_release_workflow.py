"""Release pipeline contract plus the version-source invariant.

``.github/workflows/release.yml`` is the only thing that turns a ``v*`` tag into a
GitHub release; ``wwmm.self_update`` compares local versions against that release,
so a regression here silently disables the whole update feature.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

from wwmm import __version__

RELEASE_WORKFLOW = Path(".github/workflows/release.yml")


def test_release_workflow_contract():
    wf = yaml.load(
        RELEASE_WORKFLOW.read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert wf["on"]["push"]["tags"][0] == "v*"
    assert wf["permissions"]["contents"] == "write"
    runs = " ".join(step.get("run", "") for step in wf["jobs"]["release"]["steps"])
    assert "gh release create" in runs
    assert "--generate-notes" in runs


def test_release_workflow_uses_ref_name_and_github_token():
    wf = yaml.load(
        RELEASE_WORKFLOW.read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    job = wf["jobs"]["release"]
    assert job["runs-on"] == "ubuntu-latest"
    steps = job["steps"]
    assert any("actions/checkout" in step.get("uses", "") for step in steps)
    release_steps = [step for step in steps if "gh release create" in step.get("run", "")]
    assert len(release_steps) == 1
    step = release_steps[0]
    assert "$GITHUB_REF_NAME" in step["run"]
    assert step["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"


def test_version_is_synced_across_sources():
    """``__version__`` and ``pyproject.toml`` must never drift apart.

    ``check_for_update`` talks about the packaged version while
    ``perform_self_update._read_version`` reads ``pyproject.toml``; bumping only
    one of them either reports an update forever or keeps showing the old version
    after a successful update.
    """
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__
