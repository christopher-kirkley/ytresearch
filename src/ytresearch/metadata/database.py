import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from ytresearch.types import Comment, ProcessingResult, TrackAnalysis, TrackRow

logger = logging.getLogger(__name__)


class DatabaseBackend(Protocol):
    """Protocol for database backends. Implement this for PostgreSQL, etc."""

    def init(self) -> None: ...
    def close(self) -> None: ...
    def track_exists(self, youtube_id: str) -> bool: ...
    def insert_track(
        self, result: ProcessingResult, comments: list[Comment] | None = None
    ) -> None: ...
    def update_track_analysis(
        self, youtube_id: str, analysis: TrackAnalysis
    ) -> None: ...
    def update_track_media(
        self, youtube_id: str, audio_path: str | None, video_path: str | None
    ) -> None: ...
    def get_track_audio_path(self, youtube_id: str) -> str | None: ...
    def get_all_tracks(self) -> list[TrackRow]: ...


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url           TEXT UNIQUE,
    youtube_id            TEXT,
    title                 TEXT,

    artist                TEXT,
    song                  TEXT,
    year                  INTEGER,
    country               TEXT,
    language_ethnic_group TEXT,
    genre                 TEXT,
    view_count            INTEGER,
    summary               TEXT,
    summary_short         TEXT,

    uploader              TEXT,
    uploader_id           TEXT,
    upload_date           TEXT,
    duration_seconds      INTEGER,
    like_count            INTEGER,
    comment_count         INTEGER,
    description           TEXT,
    comments_json         TEXT,
    tags                  TEXT,
    categories            TEXT,
    channel_url           TEXT,

    audio_path            TEXT,
    video_path            TEXT,
    thumbnail_path        TEXT,

    downloaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reprocessed_at        TIMESTAMP
);
"""


class SQLiteBackend:
    """SQLite implementation of DatabaseBackend."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SQLITE_SCHEMA)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._conn

    def track_exists(self, youtube_id: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM tracks WHERE youtube_id = ?", (youtube_id,)
        )
        return cursor.fetchone() is not None

    def insert_track(
        self, result: ProcessingResult, comments: list[Comment] | None = None
    ) -> None:
        video = result["video"]
        analysis = result.get("analysis") or {}
        comments_json = json.dumps(comments, ensure_ascii=False) if comments else result.get("comments_json")

        self.conn.execute(
            """INSERT OR REPLACE INTO tracks (
                youtube_url, youtube_id, title,
                artist, song, year, country, language_ethnic_group,
                genre, view_count, summary, summary_short,
                uploader, uploader_id, upload_date, duration_seconds,
                like_count, comment_count, description, comments_json,
                tags, categories, channel_url,
                audio_path, video_path, thumbnail_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                video["youtube_url"],
                video["youtube_id"],
                video["title"],
                analysis.get("artist"),
                analysis.get("song"),
                analysis.get("year"),
                analysis.get("country"),
                analysis.get("language_ethnic_group"),
                analysis.get("genre"),
                video.get("view_count"),
                analysis.get("summary"),
                analysis.get("summary_short"),
                video["uploader"],
                video["uploader_id"],
                video["upload_date"],
                video["duration_seconds"],
                video["like_count"],
                video["comment_count"],
                video["description"],
                comments_json,
                json.dumps(video["tags"], ensure_ascii=False),
                json.dumps(video["categories"], ensure_ascii=False),
                video["channel_url"],
                result.get("audio_path"),
                result.get("video_path"),
                video.get("thumbnail_path"),
            ),
        )
        self.conn.commit()

    def update_track_analysis(
        self, youtube_id: str, analysis: TrackAnalysis
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """UPDATE tracks SET
                artist = ?, song = ?, year = ?, country = ?,
                language_ethnic_group = ?, genre = ?,
                summary = ?, summary_short = ?, reprocessed_at = ?
            WHERE youtube_id = ?""",
            (
                analysis["artist"],
                analysis["song"],
                analysis["year"],
                analysis["country"],
                analysis["language_ethnic_group"],
                analysis["genre"],
                analysis["summary"],
                analysis["summary_short"],
                now,
                youtube_id,
            ),
        )
        self.conn.commit()

    def update_track_media(
        self, youtube_id: str, audio_path: str | None, video_path: str | None
    ) -> None:
        self.conn.execute(
            """UPDATE tracks SET audio_path = ?, video_path = ?
            WHERE youtube_id = ?""",
            (audio_path, video_path, youtube_id),
        )
        self.conn.commit()

    def get_track_audio_path(self, youtube_id: str) -> str | None:
        cursor = self.conn.execute(
            "SELECT audio_path FROM tracks WHERE youtube_id = ?", (youtube_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def get_all_tracks(self) -> list[TrackRow]:
        cursor = self.conn.execute(
            """SELECT youtube_id, youtube_url, view_count, comments_json,
                      audio_path, title, description, uploader, uploader_id,
                      upload_date, duration_seconds, like_count, comment_count,
                      tags, categories, channel_url
            FROM tracks"""
        )
        rows = cursor.fetchall()
        return [
            TrackRow(
                youtube_id=row["youtube_id"],
                youtube_url=row["youtube_url"],
                view_count=row["view_count"] or 0,
                comments_json=row["comments_json"],
                audio_path=row["audio_path"],
                title=row["title"],
                description=row["description"],
                uploader=row["uploader"],
                uploader_id=row["uploader_id"],
                upload_date=row["upload_date"],
                duration_seconds=row["duration_seconds"],
                like_count=row["like_count"],
                comment_count=row["comment_count"],
                tags=row["tags"],
                categories=row["categories"],
                channel_url=row["channel_url"],
            )
            for row in rows
        ]
