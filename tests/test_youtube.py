import pytest

from ytresearch.youtube import extract_video_id, is_playlist_url, sanitize_filename


class TestExtractVideoId:
    def test_standard_url(self) -> None:
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self) -> None:
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_params(self) -> None:
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30") == "dQw4w9WgXcQ"

    def test_shorts_url(self) -> None:
        assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_url(self) -> None:
        with pytest.raises(ValueError):
            extract_video_id("https://example.com/notavideo")


class TestIsPlaylistUrl:
    def test_playlist_url(self) -> None:
        assert is_playlist_url("https://www.youtube.com/playlist?list=PLxyz123") is True

    def test_video_with_list(self) -> None:
        assert is_playlist_url("https://www.youtube.com/watch?v=abc&list=PLxyz123") is True

    def test_regular_video(self) -> None:
        assert is_playlist_url("https://www.youtube.com/watch?v=abc") is False


class TestSanitizeFilename:
    def test_removes_illegal_chars(self) -> None:
        assert sanitize_filename('Song: "The Best" <version>') == "Song The Best version"

    def test_preserves_unicode(self) -> None:
        assert sanitize_filename("Musique Africaine") == "Musique Africaine"

    def test_preserves_non_latin(self) -> None:
        assert sanitize_filename("песня мира") == "песня мира"

    def test_collapses_whitespace(self) -> None:
        assert sanitize_filename("Too   Many   Spaces") == "Too Many Spaces"

    def test_empty_string(self) -> None:
        assert sanitize_filename("") == "Unknown"

    def test_only_illegal_chars(self) -> None:
        assert sanitize_filename(':"<>|') == "Unknown"
