"""The seed script must stay idempotent now that rules are managed through the API."""

from app.repositories.detection_rule_repository import DetectionRuleRepository


def test_seed_twice_creates_no_duplicates(seed_module, mongo_db):
    first = seed_module.seed(mongo_db)
    second = seed_module.seed(mongo_db)
    assert set(first.values()) == {"created"}
    assert set(second.values()) == {"updated"}
    assert mongo_db["detection_rules"].count_documents({}) == 5


def test_reseed_keeps_operator_changes_to_enabled(seed_module, mongo_db):
    seed_module.seed(mongo_db)
    repo = DetectionRuleRepository(mongo_db)
    repo.set_enabled("AUTH-001", False)
    seed_module.seed(mongo_db)
    assert repo.get_rule("AUTH-001").enabled is False


def test_reseed_recreates_a_force_deleted_rule(seed_module, mongo_db):
    seed_module.seed(mongo_db)
    repo = DetectionRuleRepository(mongo_db)
    repo.delete_rule("WEB-001")
    assert seed_module.seed(mongo_db)["WEB-001"] == "created"
