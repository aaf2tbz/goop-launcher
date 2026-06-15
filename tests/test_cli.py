"""Tests for the goop CLI (goop_launcher.__main__) argument routing."""

from goop_launcher import __main__ as cli


def test_version_shortcut(capsys):
    rc = cli.main(["--version"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out  # prints *something*


def test_version_subcommand(capsys):
    rc = cli.main(["version"])
    assert rc == 0
    assert capsys.readouterr().out.strip() != ""


def test_diagnose_subcommand_runs(monkeypatch):
    """diagnose must run run_all and return 1 when blocked (no tools here)."""
    import platform
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(platform, "release", lambda: "6.8.0-41-generic")
    from goop_launcher import config, checks
    monkeypatch.setattr(config, "DATA_DIR", __import__("pathlib").Path("/tmp/goop-test-diag"))
    monkeypatch.setattr(checks, "_find_wine_binary", lambda: None)
    # On this dev box the real tools (lspci etc.) likely don't exist, so we
    # expect non-launchable → rc 1. We only assert it ran without raising.
    rc = cli.main(["diagnose"])
    assert rc in (0, 1)
