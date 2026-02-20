"""Tests for config.py: get_config_path() and load_commands()."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from forge_triage.config import ConfigError, UserCommand, get_config_path, load_commands

# === get_config_path() ===


def test_get_config_path_respects_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """XDG_CONFIG_HOME overrides the default config location."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = get_config_path()
    assert result == tmp_path / "forge-triage" / "commands.toml"


def test_get_config_path_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without XDG_CONFIG_HOME, defaults to ~/.config/forge-triage/commands.toml."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    result = get_config_path()
    assert result == Path.home() / ".config" / "forge-triage" / "commands.toml"


# === load_commands() ===


def test_load_commands_valid_toml(tmp_path: Path) -> None:
    """Valid TOML returns a correct UserCommand list."""
    config_file = tmp_path / "commands.toml"
    config_file.write_text(
        textwrap.dedent("""\
        [[commands]]
        name = "Checkout"
        args = ["gh", "pr", "checkout", "{pr_number}"]
        mode = "foreground"

        [[commands]]
        name = "Open CI"
        args = ["open", "https://github.com/{repo}/actions"]
        mode = "background"
        """)
    )
    result = load_commands(config_file)
    assert result == [
        UserCommand(
            name="Checkout", args=["gh", "pr", "checkout", "{pr_number}"], mode="foreground"
        ),
        UserCommand(
            name="Open CI", args=["open", "https://github.com/{repo}/actions"], mode="background"
        ),
    ]


def test_load_commands_missing_file_returns_empty(tmp_path: Path) -> None:
    """Missing config file returns an empty list without raising."""
    result = load_commands(tmp_path / "nonexistent.toml")
    assert result == []


def test_load_commands_malformed_toml_raises(tmp_path: Path) -> None:
    """Malformed TOML raises ConfigError."""
    config_file = tmp_path / "commands.toml"
    config_file.write_text("[[commands\nbroken = ")
    with pytest.raises(ConfigError):
        load_commands(config_file)


@pytest.mark.parametrize(
    ("_missing_field", "toml"),
    [
        ("name", "[[commands]]\nargs = ['gh', 'pr']\nmode = 'foreground'\n"),
        ("args", "[[commands]]\nname = 'Checkout'\nmode = 'foreground'\n"),
        ("mode", "[[commands]]\nname = 'Checkout'\nargs = ['gh', 'pr']\n"),
    ],
)
def test_load_commands_missing_required_field_raises(
    tmp_path: Path, _missing_field: str, toml: str
) -> None:
    """Command missing a required field raises ConfigError."""
    config_file = tmp_path / "commands.toml"
    config_file.write_text(toml)
    with pytest.raises(ConfigError):
        load_commands(config_file)
