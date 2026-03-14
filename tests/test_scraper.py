import pytest

from ytresearch.metadata.scraper import extract_video_id, is_playlist_url


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

    def test_escaped_url(self) -> None:
        assert extract_video_id("https://www.youtube.com/watch\\?v\\=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


class TestIsPlaylistUrl:
    def test_playlist_url(self) -> None:
        assert is_playlist_url("https://www.youtube.com/playlist?list=PLxyz123") is True

    def test_video_with_list(self) -> None:
        assert is_playlist_url("https://www.youtube.com/watch?v=abc&list=PLxyz123") is True

    def test_regular_video(self) -> None:
        assert is_playlist_url("https://www.youtube.com/watch?v=abc") is False
