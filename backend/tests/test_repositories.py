import pymongo
import pytest

from app.repositories.boards import BoardRepository


def test_board_upsert_is_idempotent_and_keeps_local_config(db):
    repo = BoardRepository(db)
    repo.upsert_metadata(96, {"name": "Team Board", "workspaceId": 35})
    repo.update(96, {"enabled": False})
    board = repo.upsert_metadata(96, {"name": "Team Board v2", "workspaceId": 35})
    assert board["name"] == "Team Board v2"
    assert board["enabled"] is False
    assert db.boards.count_documents({}) == 1


def test_board_search_by_name_and_id(db):
    repo = BoardRepository(db)
    repo.upsert_metadata(96, {"name": "Nave"})
    repo.upsert_metadata(12, {"name": "Outro"})
    assert [b["boardId"] for b in repo.find_all("nav")] == [96]
    assert [b["boardId"] for b in repo.find_all("12")] == [12]
    assert repo.enabled_ids() == [12, 96]


def test_unique_index_on_cards(db):
    db.cards.insert_one({"boardId": 96, "cardId": 1})
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        db.cards.insert_one({"boardId": 96, "cardId": 1})


def test_ensure_indexes_replaces_global_report_name_index(db):
    from app.core.config import Settings
    from app.core.indexes import ensure_indexes

    db.report_definitions.drop_index("board_name_unique")
    db.report_definitions.create_index("name", name="name_unique", unique=True)
    ensure_indexes(db, Settings(_env_file=None))
    assert "name_unique" not in db.report_definitions.index_information()
    db.report_definitions.insert_many([{"boardId": 1, "name": "A"}, {"boardId": 2, "name": "A"}])
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        db.report_definitions.insert_one({"boardId": 1, "name": "A"})
