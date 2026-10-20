import subprocess

from wwmm import clipboard


def test_returns_false_when_no_tool_available(monkeypatch):
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
    assert clipboard.copy_with_command("路径") is False


def test_falls_back_when_first_tool_fails(monkeypatch):
    calls = []
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        calls.append(command)
        code = 1 if command[0].endswith("wl-copy") else 0
        return subprocess.CompletedProcess(command, code)

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.copy_with_command("路径") is True
    assert calls[0] == ["/usr/bin/wl-copy"]
    assert calls[1] == ["/usr/bin/xclip", "-selection", "clipboard"]


def test_continues_after_oserror(monkeypatch):
    calls = []
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0].endswith("wl-copy"):
            raise OSError("boom")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.copy_with_command("路径") is True
    assert calls[-1][0].endswith("xclip")
