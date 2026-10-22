"""Where Veil stores config — AppData when frozen, project when developing."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        # Bundled resources (PyInstaller)
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "VeilIDE"
    # Dev: keep machine-local overrides out of git
    return Path(__file__).resolve().parent / ".veil"


def ensure_user_config() -> Path:
    """First run: copy default.toml → user config.toml. Returns config path."""
    data = user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    cfg = data / "config.toml"
    if not cfg.exists():
        default = project_root() / "config" / "default.toml"
        if default.exists():
            shutil.copy(default, cfg)
        else:
            cfg.write_text("# Veil IDE config\n", encoding="utf-8")
    return cfg