"""The one place client values come from: config/client.yaml (the secrets stay in .env)."""

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
REQUIRED = ["car_key", "inputs.catalogue", "rules.undercut_pct", "sellers"]
SELLER_KEYS = {"seller_id", "name", "base_url", "scraper", "robots_verdict", "crawl_delay_s"}


def load_config():
    """The settings in config/client.yaml, plus input_dir. car_key is the environment variable
    CAR_KEY when it is set and not empty, else the file's car_key (null = all cars)."""
    path = ROOT / "config" / "client.yaml"
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        raise SystemExit(f"config/client.yaml is not valid YAML{f' at line {mark.line + 1}' if mark else ''}"
                         " (quote a value with # or :)") from None
    for key in REQUIRED:
        node = cfg
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise SystemExit(f"config/client.yaml is missing {key}")
            node = node[part]
    for seller in cfg["sellers"]:
        if set(seller) != SELLER_KEYS:
            raise SystemExit(f"config/client.yaml seller {seller.get('seller_id', '?')}: needs exactly "
                             + ", ".join(sorted(SELLER_KEYS)))
    cfg["car_key"] = os.environ.get("CAR_KEY") or cfg["car_key"]
    cfg["input_dir"] = ROOT / "data" / "input"
    return cfg
