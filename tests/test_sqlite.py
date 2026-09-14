import sqlite3
from pathlib import Path

import pytest

from youai.adapters.sqlite import SqliteStoryRepository
from youai.domain import MediaAsset, PreparedStory, StoryCandidate

LEGACY_SCHEMA = """
CREATE TABLE media (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    file_path   TEXT    NOT NULL,
    extension   TEXT    NOT NULL,
    date_added  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE stories (
    id          TEXT    PRIMARY KEY,
    title       TEXT    NOT NULL,
    category    TEXT,
    gender      TEXT,
    date_added  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE story_parts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id     TEXT    NOT NULL,
    part_text    TEXT    NOT NULL,
    order_index  INTEGER NOT NULL,
    media_id     INTEGER NOT NULL,
    date_added   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE,
    FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
);
"""


def make_story(
    source_id: str = "story-1",
    parts: tuple[str, ...] = ("First", "Second"),
) -> PreparedStory:
    candidate = StoryCandidate(
        source_id=source_id,
        title="Original title",
        body="Original body",
        category="pettyrevenge",
        url=f"https://example.test/{source_id}",
    )
    return PreparedStory(
        source=candidate,
        title="Edited title",
        parts=parts,
    )


def make_media(directory: Path) -> tuple[MediaAsset, ...]:
    return (
        MediaAsset(directory / "first.mp4", "generator-a"),
        MediaAsset(directory / "second.webm", "generator-a"),
    )


def table_count(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def test_save_persists_complete_story_and_contains(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "youai.sqlite3"
    story = make_story()
    media = make_media(tmp_path)

    with SqliteStoryRepository(database) as repository:
        assert not repository.contains("story-1")
        repository.save(story, media)
        assert repository.contains("story-1")

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT id, title, category, gender FROM stories"
        ).fetchall() == [("story-1", "Edited title", "pettyrevenge", None)]
        assert connection.execute(
            "SELECT filename, file_path, extension FROM media ORDER BY id"
        ).fetchall() == [
            ("first.mp4", str(tmp_path / "first.mp4"), "mp4"),
            ("second.webm", str(tmp_path / "second.webm"), "webm"),
        ]
        assert connection.execute(
            """
            SELECT story_id, part_text, order_index, media_id
            FROM story_parts
            ORDER BY order_index
            """
        ).fetchall() == [
            ("story-1", "First", 1, 1),
            ("story-1", "Second", 2, 2),
        ]


def test_save_rolls_back_every_table_when_an_insert_fails(
    tmp_path: Path,
) -> None:
    database = tmp_path / "youai.sqlite3"
    with SqliteStoryRepository(database):
        pass
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TRIGGER reject_second_asset
            BEFORE INSERT ON media
            WHEN NEW.filename = 'second.webm'
            BEGIN
                SELECT RAISE(ABORT, 'rejected asset');
            END;
            """
        )

    with SqliteStoryRepository(database) as repository:
        with pytest.raises(sqlite3.IntegrityError, match="rejected asset"):
            repository.save(make_story(), make_media(tmp_path))
        assert not repository.contains("story-1")

    with sqlite3.connect(database) as connection:
        assert table_count(connection, "stories") == 0
        assert table_count(connection, "media") == 0
        assert table_count(connection, "story_parts") == 0


def test_save_rejects_part_asset_count_mismatch_before_inserting(
    tmp_path: Path,
) -> None:
    database = tmp_path / "youai.sqlite3"
    story = make_story()
    one_asset = (MediaAsset(tmp_path / "only.mp4", "generator-a"),)

    with SqliteStoryRepository(database) as repository:
        with pytest.raises(
            ValueError,
            match=r"zip\(\) argument 2 is shorter",
        ):
            repository.save(story, one_asset)
        assert not repository.contains("story-1")

    with sqlite3.connect(database) as connection:
        assert table_count(connection, "stories") == 0
        assert table_count(connection, "media") == 0
        assert table_count(connection, "story_parts") == 0


def test_repository_uses_the_existing_legacy_schema(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            """
            INSERT INTO stories (id, title, category, gender)
            VALUES ('legacy-story', 'Legacy', 'archive', 'unknown')
            """
        )

    with SqliteStoryRepository(database) as repository:
        assert repository.contains("legacy-story")
        repository.save(
            make_story(source_id="new-story", parts=("New part",)),
            (MediaAsset(tmp_path / "new.mp4", "generator-a"),),
        )
        repository.close()
        repository.close()

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id FROM stories ORDER BY id").fetchall() == [
            ("legacy-story",),
            ("new-story",),
        ]
        assert table_count(connection, "media") == 1
        assert table_count(connection, "story_parts") == 1
