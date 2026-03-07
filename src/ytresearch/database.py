import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ytresearch.types import ProcessingResult, TrackAnalysis

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url           TEXT UNIQUE,
    youtube_id            TEXT,

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


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize the database and return a connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def track_exists(conn: sqlite3.Connection, youtube_id: str) -> bool:
    """Check if a track already exists in the database."""
    cursor = conn.execute(
        "SELECT 1 FROM tracks WHERE youtube_id = ?", (youtube_id,)
    )
    return cursor.fetchone() is not None


def insert_track(conn: sqlite3.Connection, result: ProcessingResult) -> None:
    """Insert a fully processed track into the database."""
    video = result["video"]
    analysis = result.get("analysis") or {}

    conn.execute(
        """INSERT OR REPLACE INTO tracks (
            youtube_url, youtube_id,
            artist, song, year, country, language_ethnic_group,
            genre, view_count, summary, summary_short,
            uploader, uploader_id, upload_date, duration_seconds,
            like_count, comment_count, description, tags, categories,
            channel_url, audio_path, video_path, thumbnail_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            video["youtube_url"],
            video["youtube_id"],
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
            json.dumps(video["tags"], ensure_ascii=False),
            json.dumps(video["categories"], ensure_ascii=False),
            video["channel_url"],
            result.get("audio_path"),
            result.get("video_path"),
            video.get("thumbnail_path"),
        ),
    )
    conn.commit()


def update_track_analysis(
    conn: sqlite3.Connection, youtube_id: str, analysis: TrackAnalysis
) -> None:
    """Update analysis fields on an existing track (for --reprocess)."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
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
    conn.commit()


def get_track_audio_path(conn: sqlite3.Connection, youtube_id: str) -> str | None:
    """Get the audio path for an existing track."""
    cursor = conn.execute(
        "SELECT audio_path FROM tracks WHERE youtube_id = ?", (youtube_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None
