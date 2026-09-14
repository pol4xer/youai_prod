"""SQLite persistence adapter for fully generated stories."""

import sqlite3
from pathlib import Path
from types import TracebackType

from youai.domain import MediaAsset, PreparedStory


class SqliteStoryRepository:
    """Own a SQLite connection and persist complete stories atomically."""

    def __init__(self, database: str | Path) -> None:
        self._database = Path(database)
        if str(database) != ":memory:":
            self._database.parent.mkdir(parents=True, exist_ok=True)

        self._connection: sqlite3.Connection | None = sqlite3.connect(self._database)
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._create_tables()
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> "SqliteStoryRepository":
        self._require_connection()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the owned connection; repeated calls are harmless."""

        connection = self._connection
        if connection is not None:
            connection.close()
            self._connection = None

    def contains(self, story_id: str) -> bool:
        connection = self._require_connection()
        row = connection.execute(
            "SELECT 1 FROM stories WHERE id = ? LIMIT 1",
            (story_id,),
        ).fetchone()
        return row is not None

    def save(
        self,
        story: PreparedStory,
        media: tuple[MediaAsset, ...],
    ) -> None:
        connection = self._require_connection()
        parts_and_media = tuple(zip(story.parts, media, strict=True))

        with connection:
            connection.execute(
                """
                INSERT INTO stories (id, title, category, gender)
                VALUES (?, ?, ?, NULL)
                """,
                (
                    story.source.source_id,
                    story.title,
                    story.source.category,
                ),
            )

            for order_index, (part, asset) in enumerate(
                parts_and_media,
                start=1,
            ):
                media_cursor = connection.execute(
                    """
                    INSERT INTO media (filename, file_path, extension)
                    VALUES (?, ?, ?)
                    """,
                    (
                        asset.path.name,
                        str(asset.path),
                        asset.path.suffix.removeprefix("."),
                    ),
                )
                media_id = media_cursor.lastrowid
                if media_id is None:
                    raise RuntimeError("SQLite did not return a media id")

                connection.execute(
                    """
                    INSERT INTO story_parts
                        (story_id, part_text, order_index, media_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        story.source.source_id,
                        part,
                        order_index,
                        media_id,
                    ),
                )

    def _create_tables(self) -> None:
        connection = self._require_connection()
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS media (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT    NOT NULL,
                file_path   TEXT    NOT NULL,
                extension   TEXT    NOT NULL,
                date_added  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stories (
                id          TEXT    PRIMARY KEY,
                title       TEXT    NOT NULL,
                category    TEXT,
                gender      TEXT,
                date_added  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS story_parts (
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
        )
        connection.commit()

    def _require_connection(self) -> sqlite3.Connection:
        connection = self._connection
        if connection is None:
            raise RuntimeError("SQLite repository is closed")
        return connection
