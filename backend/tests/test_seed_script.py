import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_database.py"


@pytest.fixture(scope="module")
def seed_module():
    spec = importlib.util.spec_from_file_location("seed_database", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_inserts_expected_counts_and_is_idempotent(seed_module, mongo_db):
    first = seed_module.seed(mongo_db)
    assert first == {"security_events": (8, 0), "detection_rules": (3, 0), "alerts": (2, 0)}
    second = seed_module.seed(mongo_db)  # nothing duplicated, nothing deleted
    assert second == {"security_events": (0, 8), "detection_rules": (0, 3), "alerts": (0, 2)}
    assert mongo_db["security_events"].count_documents({}) == 8


def test_seed_data_is_clearly_synthetic(seed_module):
    assert all(e.metadata.get("synthetic") is True for e in seed_module.build_events())
    assert all(r.description.startswith("[Synthetic seed]") for r in seed_module.build_rules())
    assert all(a.description.startswith("[Synthetic seed]") for a in seed_module.build_alerts())
    assert {e.source_ip for e in seed_module.build_events()} <= {"192.168.1.20", "192.168.1.30"}


def test_seed_does_not_run_on_import_or_app_startup():
    import app.main  # noqa: F401  (importing the app must not seed anything)
    assert "seed" not in Path(app.main.__file__).read_text().lower()
