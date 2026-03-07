import sqlite3

import pytest

from ytresearch.database import (
    get_track_audio_path,
    init_db,
    insert_track,
    track_exists,
    update_track_analysis,
)
from ytresearch.types import ProcessingResult, TrackAnalysis, VideoMetadata


@pytest.fixture
def db(tmp_path) -> sqlite3.Connection:
    return init_db(tmp_path / "test.db")


@pytest.fixture
def sample_result(sample_metadata: VideoMetadata, sample_analysis: TrackAnalysis) -> ProcessingResult:
    return ProcessingResult(
        video=sample_metadata,
        analysis=sample_analysis,
        audio_path="/tmp/audio/Josi/Captain Charlie.m4a",
        video_path="/tmp/video/Josi/Captain Charlie.mp4",
        status="success",
        error=None,
    )


class TestInitDb:
    def test_creates_table(self, db: sqlite3.Connection) -> None:
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'")
        assert cursor.fetchone() is not None


class TestInsertAndQuery:
    def test_insert_and_exists(self, db: sqlite3.Connection, sample_result: ProcessingResult) -> None:
        insert_track(db, sample_result)
        assert track_exists(db, "dQw4w9WgXcQ") is True

    def test_not_exists(self, db: sqlite3.Connection) -> None:
        assert track_exists(db, "nonexistent") is False

    def test_get_audio_path(self, db: sqlite3.Connection, sample_result: ProcessingResult) -> None:
        insert_track(db, sample_result)
        path = get_track_audio_path(db, "dQw4w9WgXcQ")
        assert path == "/tmp/audio/Josi/Captain Charlie.m4a"

    def test_duplicate_insert_replaces(self, db: sqlite3.Connection, sample_result: ProcessingResult) -> None:
        insert_track(db, sample_result)
        sample_result["audio_path"] = "/tmp/new_path.m4a"
        insert_track(db, sample_result)
        path = get_track_audio_path(db, "dQw4w9WgXcQ")
        assert path == "/tmp/new_path.m4a"


class TestUpdateAnalysis:
    def test_updates_fields(self, db: sqlite3.Connection, sample_result: ProcessingResult) -> None:
        insert_track(db, sample_result)
        updated = TrackAnalysis(
            artist="Josi Beats",
            song="Captain Charlie (Remastered)",
            year=2010,
            country="Zambia",
            language_ethnic_group="Bemba",
            genre="Zambian Pop",
            summary="Updated summary.",
        )
        update_track_analysis(db, "dQw4w9WgXcQ", updated)

        cursor = db.execute("SELECT artist, song, summary FROM tracks WHERE youtube_id = ?", ("dQw4w9WgXcQ",))
        row = cursor.fetchone()
        assert row[0] == "Josi Beats"
        assert row[1] == "Captain Charlie (Remastered)"
        assert row[2] == "Updated summary."
