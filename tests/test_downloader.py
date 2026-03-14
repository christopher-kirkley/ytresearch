from ytresearch.media.downloader import sanitize_filename


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
