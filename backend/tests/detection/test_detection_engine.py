"""Engine: coordinates rules, skips disabled / invalid ones, never alerts."""

from app.models.rule import DetectionRule
from tests.detection.conftest import make, store


def test_engine_returns_a_result_per_enabled_rule(engine, event_repo, rules):
    events = store(event_repo, [make(i * 5) for i in range(5)])
    detection = engine.evaluate_event(events[-1], list(rules.values()))
    assert detection.rules_evaluated == 5 and len(detection.results) == 5
    assert [r.rule_id for r in detection.matches] == ["AUTH-001"]
    assert {r.rule_id for r in detection.results} == set(rules)


def test_engine_no_match_for_a_benign_event(engine, event_repo, rules):
    event = store(event_repo, [make(0, status="success")])[0]
    detection = engine.evaluate_event(event, list(rules.values()))
    assert detection.matches == [] and detection.rules_evaluated == 5


def test_disabled_rules_are_not_evaluated_and_never_match(engine, event_repo, rules):
    events = store(event_repo, [make(i * 5) for i in range(5)])
    disabled = {k: r.model_copy(update={"enabled": False}) for k, r in rules.items()}
    detection = engine.evaluate_event(events[-1], list(disabled.values()))
    assert detection.results == [] and detection.rules_evaluated == 0 and detection.matches == []


def test_invalid_rule_is_skipped_and_others_still_run(engine, event_repo, rules):
    broken = DetectionRule(rule_id="AUTH-099", name="Broken", category="authentication", severity="high",
                           description="bad", conditions={"event_type": "authentication", "stages": []})
    events = store(event_repo, [make(i * 5) for i in range(5)])
    detection = engine.evaluate_event(events[-1], [broken, rules["AUTH-001"]])
    assert detection.skipped_rule_ids == ["AUTH-099"]
    assert detection.rules_evaluated == 1 and [r.rule_id for r in detection.matches] == ["AUTH-001"]


def test_step3_seed_rule_with_stages_is_skipped_not_fatal(engine, event_repo):
    legacy = DetectionRule(rule_id="AUTH-002", name="Old", category="authentication", severity="critical",
                           description="Step 3 sample", conditions={"window_minutes": 10, "stages": [{"status": "failed"}]})
    event = store(event_repo, [make(0)])[0]
    assert engine.evaluate_event(event, [legacy]).skipped_rule_ids == ["AUTH-002"]


def test_result_shapes_match_the_spec(engine, event_repo, rules):
    events = store(event_repo, [make(i * 5) for i in range(5)])
    detection = engine.evaluate_event(events[-1], [rules["AUTH-001"]])
    matched = detection.results[0].model_dump(mode="json")
    assert matched["matched"] is True and matched["rule_id"] == "AUTH-001" and matched["severity"] == "high"
    assert matched["event_id"] == events[-1].event_id and matched["reason"]

    single = store(event_repo, [make(0, source_ip="10.8.8.8")])[0]
    unmatched = engine.evaluate_event(single, [rules["AUTH-001"]]).results[0].model_dump(mode="json")
    assert unmatched["matched"] is False and unmatched["severity"] is None and unmatched["reason"]


def test_engine_does_not_write_anything(engine, event_repo, mongo_db, rules):
    events = store(event_repo, [make(i * 5) for i in range(5)])
    before = {name: mongo_db[name].count_documents({}) for name in mongo_db.list_collection_names()}
    engine.evaluate_event(events[-1], list(rules.values()))
    after = {name: mongo_db[name].count_documents({}) for name in mongo_db.list_collection_names()}
    assert before == after
    assert mongo_db["alerts"].count_documents({}) == 0
