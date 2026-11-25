"""Manages settings in a config.json file in the AppData folder."""

import json
import os
import sys
from pathlib import Path


APP_NAME = "SerienStream"
VERSION = "2.0.0"


def get_config_dir() -> Path:
    """Returns the cross-platform config directory."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")

    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"

PROVIDERS = ["VOE", "Doodstream", "Streamtape", "Vidoza"]
QUALITIES = ["480p", "720p", "1080p", "Best available"]

# Aspect ratio correction modes
ASPECT_OFF = "Off (keep original)"
ASPECT_CHECK = "Check and report"
ASPECT_SAR1 = "Set SAR to 1:1"
ASPECT_169 = "Force 16:9"
ASPECT_MODES = [ASPECT_OFF, ASPECT_CHECK, ASPECT_SAR1, ASPECT_169]

# Migration map for old German config values
_VALUE_MIGRATION = {
    "Aus (Original behalten)": ASPECT_OFF,
    "Prüfen und melden": ASPECT_CHECK,
    "SAR auf 1:1 setzen": ASPECT_SAR1,
    "16:9 erzwingen": ASPECT_169,
    "Beste verfügbare": "Best available",
}

DEFAULTS = {
    "download_path": str(Path.home() / "Downloads" / "SerienStream"),
    "preferred_provider": "VOE",
    "menu_effects": False,
    "preferred_quality": "1080p",
    "notifications": True,
    "resume_downloads": True,
    "skip_existing": True,
    "aspect_correction": ASPECT_CHECK,
}


def load_settings() -> dict:
    """Loads settings, filling missing values with defaults."""
    data = dict(DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                data.update(saved)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[!] Could not read config.json: {e}")

    # Remove obsolete keys from earlier versions
    data.pop("concurrent_downloads", None)

    # Migrate old German values to English
    for key in ("aspect_correction", "preferred_quality"):
        val = data.get(key, "")
        if val in _VALUE_MIGRATION:
            data[key] = _VALUE_MIGRATION[val]

    return data


def save_settings(settings: dict) -> None:
    """Saves settings persistently."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[!] Could not save config.json: {e}")
