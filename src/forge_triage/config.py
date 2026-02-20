"""User command configuration: load and validate commands.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    """Raised when commands.toml is malformed or missing required fields."""


@dataclass
class UserCommand:
    """A user-defined command from commands.toml."""

    name: str
    args: list[str]
    mode: str  # "foreground" | "background"
    cwd: str | None = None  # optional working directory, supports template vars
    env: dict[str, str] | None = None  # optional extra env vars, values support template vars


def get_config_path() -> Path:
    """Return the path to commands.toml, respecting XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "forge-triage" / "commands.toml"


def load_commands(path: Path) -> list[UserCommand]:
    """Load and validate commands from a TOML file.

    Returns an empty list if the file does not exist.
    Raises ConfigError on parse errors or missing required fields.
    """
    if not path.exists():
        return []

    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        msg = f"Invalid TOML in {path}: {e}"
        raise ConfigError(msg) from e

    raw_commands = data.get("commands", [])
    commands: list[UserCommand] = []
    for i, entry in enumerate(raw_commands):
        for field in ("name", "args", "mode"):
            if field not in entry:
                msg = f"Command {i} in {path} is missing required field '{field}'"
                raise ConfigError(msg)
        commands.append(
            UserCommand(
                name=entry["name"],
                args=entry["args"],
                mode=entry["mode"],
                cwd=entry.get("cwd"),
                env=entry.get("env"),
            )
        )
    return commands
