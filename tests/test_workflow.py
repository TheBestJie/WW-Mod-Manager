from pathlib import Path

import yaml


def test_workflow_contract():
    wf = yaml.load(
        Path(".github/workflows/update-roster.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert wf["on"]["schedule"][0]["cron"] == "0 19 * * *"
    assert "workflow_dispatch" in wf["on"]
    assert wf["permissions"]["contents"] == "write"
    runs = " ".join(step.get("run", "") for step in wf["jobs"]["update"]["steps"])
    assert "scripts/build_roster.py" in runs
    assert "--bundled-out" in runs
    assert "src/wwmm/data/roster.json" in runs
    assert "git push" in runs
