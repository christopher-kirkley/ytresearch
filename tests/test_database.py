import json

import pytest

from ytresearch.metadata.database import SQLiteBackend
from ytresearch.types import Comment, ProcessingResult, TrackAnalysis, VideoMetadata


@pytest.fixture
def db(tmp_path) -> SQLiteBackend:
    backend = SQLiteBackend(tmp_path / "test.db")
    backend.init()
    return backend


@pytest.fixture
def sample_result(sample_metadata: VideoMetadata, sample_analysis: TrackAnalysis) -> ProcessingResult:
    return ProcessingResult(
        video=sample_metadata,
        analysis=sample_analysis,
        comments_json=None,
        audio_path="/tmp/audio/Josi/Captain Charlie.m4a",
        video_path="/tmp/video/Josi/Captain Charlie.mp4",
        status="success",
        error=None,
    )


@pytest.fixture
def sample_comments_list() -> list[Comment]:
    return [
        Comment(text="Great song!", likes=50, author="User1", timestamp="1 year ago"),
    ]


class TestInitDb:
    def test_creates_table(self, db: SQLiteBackend) -> None:
        cursor = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'")
        assert cursor.fetchone() is not None


class TestInsertAndQuery:
    def test_insert_and_exists(self, db: SQLiteBackend, sample_result: ProcessingResult) -> None:
        db.insert_track(sample_result)
        assert db.track_exists("dQw4w9WgXcQ") is True

    def test_not_exists(self, db: SQLiteBackend) -> None:
        assert db.track_exists("nonexistent") is False

    def test_get_audio_path(self, db: SQLiteBackend, sample_result: ProcessingResult) -> None:
        db.insert_track(sample_result)
        path = db.get_track_audio_path("dQw4w9WgXcQ")
        assert path == "/tmp/audio/Josi/Captain Charlie.m4a"

    def test_duplicate_insert_replaces(self, db: SQLiteBackend, sample_result: ProcessingResult) -> None:
        db.insert_track(sample_result)
        sample_result["audio_path"] = "/tmp/new_path.m4a"
        db.insert_track(sample_result)
        path = db.get_track_audio_path("dQw4w9WgXcQ")
        assert path == "/tmp/new_path.m4a"

    def test_insert_with_comments(self, db: SQLiteBackend, sample_result: ProcessingResult, sample_comments_list: list[Comment]) -> None:
        db.insert_track(sample_result, comments=sample_comments_list)
        cursor = db.conn.execute("SELECT comments_json FROM tracks WHERE youtube_id = ?", ("dQw4w9WgXcQ",))
        row = cursor.fetchone()
        comments = json.loads(row[0])
        assert len(comments) == 1
        assert comments[0]["text"] == "Great song!"


class TestUpdateAnalysis:
    def test_updates_fields(self, db: SQLiteBackend, sample_result: ProcessingResult) -> None:
        db.insert_track(sample_result)
        updated = TrackAnalysis(
            artist="Josi Beats",
            song="Captain Charlie (Remastered)",
            year=2010,
            country="Zambia",
            language_ethnic_group="Bemba",
            genre="Zambian Pop",
            summary="Updated summary.",
            summary_short="Updated short.",
        )
        db.update_track_analysis("dQw4w9WgXcQ", updated)

        cursor = db.conn.execute("SELECT artist, song, summary FROM tracks WHERE youtube_id = ?", ("dQw4w9WgXcQ",))
        row = cursor.fetchone()
        assert row[0] == "Josi Beats"
        assert row[1] == "Captain Charlie (Remastered)"
        assert row[2] == "Updated summary."


class TestUpdateMedia:
    def test_updates_paths(self, db: SQLiteBackend, sample_result: ProcessingResult) -> None:
        db.insert_track(sample_result)
        db.update_track_media("dQw4w9WgXcQ", "/new/audio.mp3", "/new/video.mp4")
        cursor = db.conn.execute("SELECT audio_path, video_path FROM tracks WHERE youtube_id = ?", ("dQw4w9WgXcQ",))
        row = cursor.fetchone()
        assert row[0] == "/new/audio.mp3"
        assert row[1] == "/new/video.mp4"


class TestGetAllTracks:
    def test_returns_all(self, db: SQLiteBackend, sample_result: ProcessingResult) -> None:
        db.insert_track(sample_result)
        tracks = db.get_all_tracks()
        assert len(tracks) == 1
        assert tracks[0]["youtube_id"] == "dQw4w9WgXcQ"
