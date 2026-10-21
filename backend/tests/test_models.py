from datetime import UTC, datetime

from app.models.businessmap import BmCard, parse_board_structure
from app.models.cards import derive_status, normalize_card, priority_level
from tests.businessmap_fake import load_fixture


def test_all_fixture_cards_parse():
    for name in ("cards_active_96.json", "cards_archived_96.json"):
        for raw in load_fixture(name):
            card = BmCard.model_validate(raw)
            assert card.board_id == 96


def test_tolerates_blanks_unknown_fields_and_bad_shapes():
    card = BmCard.model_validate(
        {
            "card_id": 1,
            "board_id": 96,
            "title": "",
            "deadline": "",
            "first_end_time": "0000-00-00 00:00:00",
            "is_blocked": 1,
            "block_reason": [],
            "tag_ids": None,
            "new_field": {"x": 1},
            "transitions": [{"column_id": 3, "start_time": "2026-10-01T10:00:00Z", "end": None}],
        }
    )
    assert card.title == "" and card.deadline is None and card.first_end_time is None
    assert card.is_blocked is True and card.block_reason is None and card.tag_ids == []
    assert card.transitions[0].start == datetime(2026, 10, 1, 10, tzinfo=UTC)


def test_structure_is_ordered_with_sections():
    structure = parse_board_structure(load_fixture("current_structure_96.json")["data"])
    assert [c.name for c in structure.columns][:3] == ["Backlog", "To Do", "Em curso"]
    assert {c.section for c in structure.columns} == {1, 2, 3, 4, 5}
    assert [lane.name for lane in structure.lanes] == ["Default Swimlane", "Expedite"]


def test_subcolumn_inherits_parent_section():
    structure = parse_board_structure(
        {
            "workflow_order": [1],
            "workflows": {"1": {"name": "w", "top_columns": [10, 11]}},
            "columns": {"10": {"workflow_id": 1, "section": 3, "name": "Dev"}, "11": {"workflow_id": 1, "section": None, "parent_column_id": 10, "name": "Doing"}},
            "lanes": {},
        }
    )
    assert structure.column(11).section == 3


def test_status_and_priority_rules():
    end = datetime(2026, 10, 1, tzinfo=UTC)
    assert derive_status("active", 3, None) == "in_progress"
    assert derive_status("active", 5, None) == "done"
    assert derive_status("archived", None, end) == "done"
    assert derive_status("archived", None, None) == "archived"
    assert derive_status("discarded", 3, end) == "discarded"
    assert [priority_level(p) for p in (None, 1, 4, 99)] == [3, 1, 4, 4]


def test_normalize_card_document():
    raw = load_fixture("cards_active_96.json")[2]
    doc = normalize_card(BmCard.model_validate(raw), state="active", columns={}, base_url="https://x", raw=raw)
    assert doc["status"] == "in_progress"
    assert doc["isBlocked"] and doc["blockReason"]["comment"]
    assert doc["url"] == "https://x/ctrl_board/96/cards/5003/details/"
    assert doc["priorityLabel"] == "Crítica"
    assert doc["endTime"] is None


def test_capture_samples_anonymizes_and_reports(tmp_path, monkeypatch):
    import asyncio
    import json

    from app.integrations import businessmap
    from app.jobs import capture_samples
    from tests.businessmap_fake import FakeBusinessmap

    fake = FakeBusinessmap()
    fake.cards["active"][0]["transitions"] = [{"column_id": 2001, "start": "2026-09-01T09:00:00Z", "end": None}]
    original = businessmap.BusinessmapClient.from_settings.__func__
    monkeypatch.setattr(
        businessmap.BusinessmapClient,
        "from_settings",
        classmethod(lambda cls, s, **kw: original(cls, s, transport=fake.transport(), **kw)),
    )
    monkeypatch.setenv("BUSINESSMAP_API_KEY", "test-key")
    capture_samples.get_settings.cache_clear()
    report = asyncio.run(capture_samples.capture(96, tmp_path, 10))
    capture_samples.get_settings.cache_clear()
    assert report["dto_errors"] == []
    assert report["expanded_keys"]["transitions"] == ["column_id", "end", "start"]
    cards = json.loads((tmp_path / "cards_active_96.json").read_text())
    assert cards[0]["title"].startswith("<title-")
