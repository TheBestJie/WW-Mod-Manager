import json

import pytest

from scripts.build_roster import main as build_main


@pytest.fixture
def arikatsu_fixture(tmp_path):
    directory = tmp_path / "arikatsu"
    directory.mkdir()
    roles = [
        {"Id": 1102, "Name": "RoleInfo_1102_Name", "RoleType": 1, "QualityId": 5, "ElementId": 1},
        {"Id": 1210, "Name": "RoleInfo_1210_Name", "RoleType": 1, "QualityId": 5, "ElementId": 2},
        {"Id": 1311, "Name": "RoleInfo_1311_Name", "RoleType": 1, "QualityId": 5, "ElementId": 3},
        {"Id": 1402, "Name": "RoleInfo_1402_Name", "RoleType": 1, "QualityId": 5, "ElementId": 4},
        {"Id": 1501, "Name": "RoleInfo_1501_Name", "RoleType": 1, "QualityId": 5, "ElementId": 5},
        {"Id": 1604, "Name": "RoleInfo_1604_Name", "RoleType": 1, "QualityId": 5, "ElementId": 6},
    ]
    zh = [
        ("RoleInfo_1102_Name", "散华"),
        ("RoleInfo_1210_Name", "爱弥斯"),
        ("RoleInfo_1311_Name", "心"),
        ("RoleInfo_1402_Name", "秧秧"),
        ("RoleInfo_1501_Name", "漂泊者·衍射"),
        ("RoleInfo_1604_Name", "漂泊者·湮灭"),
    ]
    en = [
        ("RoleInfo_1102_Name", "Sanhua"),
        ("RoleInfo_1210_Name", "Aemeath"),
        ("RoleInfo_1311_Name", "Hsin"),
        ("RoleInfo_1402_Name", "Yangyang"),
        ("RoleInfo_1501_Name", "Rover: Spectro"),
        ("RoleInfo_1604_Name", "Rover: Havoc"),
    ]
    (directory / "roleinfo.json").write_text(
        json.dumps(roles, ensure_ascii=False), encoding="utf-8"
    )
    (directory / "zh.json").write_text(
        json.dumps([{"Id": i, "Content": c} for i, c in zh], ensure_ascii=False),
        encoding="utf-8",
    )
    (directory / "en.json").write_text(
        json.dumps([{"Id": i, "Content": c} for i, c in en], ensure_ascii=False),
        encoding="utf-8",
    )
    return directory


def _args(fixture, out, *extra):
    return [
        "--roleinfo",
        str(fixture / "roleinfo.json"),
        "--zh",
        str(fixture / "zh.json"),
        "--en",
        str(fixture / "en.json"),
        "--branch",
        "test",
        "--commit",
        "abc",
        "--committed-at",
        "2026-10-19T00:00:00Z",
        "--out",
        str(out),
        "--min-characters",
        "1",
        *extra,
    ]


def test_build_from_local_files(tmp_path, arikatsu_fixture):
    out = tmp_path / "roster.json"
    rc = build_main(_args(arikatsu_fixture, out))
    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["characters"]) == 6
    assert data["game_version"] == "test"
    assert data["source"]["commit"] == "abc"


def test_skip_when_commit_unchanged(tmp_path, arikatsu_fixture, capsys):
    out = tmp_path / "roster.json"
    assert build_main(_args(arikatsu_fixture, out)) == 0
    before_bytes = out.read_bytes()
    before_mtime = out.stat().st_mtime_ns
    capsys.readouterr()

    assert build_main(_args(arikatsu_fixture, out)) == 0
    assert "unchanged" in capsys.readouterr().out
    assert out.read_bytes() == before_bytes
    assert out.stat().st_mtime_ns == before_mtime


def test_dry_run_does_not_write(tmp_path, arikatsu_fixture):
    out = tmp_path / "roster.json"
    rc = build_main(_args(arikatsu_fixture, out, "--dry-run"))
    assert rc == 0
    assert not out.exists()


def test_validation_failure_keeps_old_file(tmp_path, arikatsu_fixture):
    out = tmp_path / "roster.json"
    out.write_text("old-content", encoding="utf-8")

    (arikatsu_fixture / "roleinfo.json").write_text(
        json.dumps(
            [
                {
                    "Id": 1210,
                    "Name": "RoleInfo_1210_Name",
                    "RoleType": 1,
                    "QualityId": 5,
                    "ElementId": 2,
                }
            ]
        ),
        encoding="utf-8",
    )
    rc = build_main(_args(arikatsu_fixture, out))
    assert rc == 1
    assert out.read_text(encoding="utf-8") == "old-content"
