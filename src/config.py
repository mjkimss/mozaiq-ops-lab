"""One place to load config.yaml and find the repo root, so every module reads assumptions the same way."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config():
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)
