import pytest
from pydantic import ValidationError

from app.models.investigation import Investigation, InvestigationNote, InvestigationStatus


def test_status_values_and_default():
    assert [s.value for s in InvestigationStatus] == ["open", "in_progress", "closed"]
    assert Investigation(investigation_id="INV-1", title="t", alert_ids=["a"]).status == "open"


def test_note_gets_id_and_timestamp_and_rejects_blank():
    note = InvestigationNote(text="  hi ")
    assert note.text == "hi" and note.note_id.startswith("note_") and note.created_at.tzinfo
    assert InvestigationNote(text="a").note_id != InvestigationNote(text="a").note_id
    for bad in ("", "   ", "x" * 2001):
        with pytest.raises(ValidationError):
            InvestigationNote(text=bad)


def test_legacy_step3_document_still_loads():
    # Step 3 stored notes as {text, created_at} with no note_id.
    doc = {"investigation_id": "INV-1", "title": "t", "alert_ids": ["a"], "status": "open",
           "notes": [{"text": "old", "created_at": "2026-10-01T00:00:00Z"}]}
    assert Investigation.model_validate(doc).notes[0].text == "old"


def test_alert_ids_rules():
    for bad in ([], ["a", "a"]):
        with pytest.raises(ValidationError):
            Investigation(investigation_id="INV-1", title="t", alert_ids=bad)
