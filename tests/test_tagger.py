import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.id3 import ID3

from ytresearch.tagger import embed_thumbnail, write_tags
from ytresearch.types import TrackAnalysis

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not installed",
)


def _create_silent_mp3(path: Path) -> None:
    """Create a minimal valid MP3 file using ffmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", "1", "-q:a", "9", str(path)],
        capture_output=True, check=True,
    )


@pytest.fixture
def mp3_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.mp3"
    _create_silent_mp3(path)
    return path


@pytest.fixture
def thumbnail_file(tmp_path: Path) -> Path:
    """Create a tiny valid JPEG file."""
    path = tmp_path / "thumb.jpg"
    path.write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    )
    return path


class TestWriteTags:
    def test_writes_basic_tags(self, mp3_file: Path, sample_analysis: TrackAnalysis) -> None:
        write_tags(mp3_file, sample_analysis)
        tags = ID3(str(mp3_file))
        assert str(tags["TIT2"]) == "Captain Charlie"
        assert str(tags["TPE1"]) == "Josi"
        assert str(tags["TDRC"]) == "2010"

    def test_genre_is_compound(self, mp3_file: Path, sample_analysis: TrackAnalysis) -> None:
        write_tags(mp3_file, sample_analysis)
        tags = ID3(str(mp3_file))
        assert "Zambian Pop" in str(tags["TCON"])
        assert "Bemba" in str(tags["TCON"])
        assert "Zambia" in str(tags["TCON"])

    def test_comment_has_short_summary(self, mp3_file: Path, sample_analysis: TrackAnalysis) -> None:
        write_tags(mp3_file, sample_analysis, view_count=1674214)
        tags = ID3(str(mp3_file))
        comment = str(tags["COMM::eng"])
        assert "Pacific Islands" in comment
        assert len(comment) <= 250

    def test_lyrics_has_full_summary(self, mp3_file: Path, sample_analysis: TrackAnalysis) -> None:
        write_tags(mp3_file, sample_analysis, view_count=1674214)
        tags = ID3(str(mp3_file))
        lyrics = str(tags["USLT::eng"])
        assert lyrics.startswith("A tribute song")
        assert "Views: 1,674,214" in lyrics

    def test_grouping_tag(self, mp3_file: Path, sample_analysis: TrackAnalysis) -> None:
        write_tags(mp3_file, sample_analysis)
        tags = ID3(str(mp3_file))
        assert str(tags["GRP1"]) == "Bemba"

    def test_no_year_when_none(self, mp3_file: Path, sample_analysis: TrackAnalysis) -> None:
        sample_analysis["year"] = None
        write_tags(mp3_file, sample_analysis)
        tags = ID3(str(mp3_file))
        assert "TDRC" not in tags


class TestEmbedThumbnail:
    def test_embeds_in_mp3(self, mp3_file: Path, thumbnail_file: Path, sample_analysis: TrackAnalysis) -> None:
        write_tags(mp3_file, sample_analysis)
        embed_thumbnail(mp3_file, thumbnail_file)
        tags = ID3(str(mp3_file))
        assert "APIC:Cover" in tags

    def test_missing_thumbnail(self, mp3_file: Path, tmp_path: Path, sample_analysis: TrackAnalysis) -> None:
        write_tags(mp3_file, sample_analysis)
        embed_thumbnail(mp3_file, tmp_path / "nonexistent.jpg")
        # Should not raise, just log warning
