import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[3] / "sample_logs" / "raw"


def raw_lines(name: str) -> list[str]:
    return [line for line in (RAW_DIR / name).read_text().splitlines() if line.strip()]


def raw_json(name: str) -> list[dict]:
    return json.loads((RAW_DIR / name).read_text())
