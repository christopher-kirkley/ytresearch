import json

import pytest

from ytresearch.analyzer import build_prompt, parse_response
from ytresearch.types import Comment, VideoMetadata


class TestBuildPrompt:
    def test_contains_title(self, sample_metadata: VideoMetadata, sample_comments: list[Comment]) -> None:
        prompt = build_prompt(sample_metadata, sample_comments)
        assert "Captain Charlie - Josi (Official Video)" in prompt

    def test_contains_description(self, sample_metadata: VideoMetadata, sample_comments: list[Comment]) -> None:
        prompt = build_prompt(sample_metadata, sample_comments)
        assert "Bemba language" in prompt

    def test_contains_comments(self, sample_metadata: VideoMetadata, sample_comments: list[Comment]) -> None:
        prompt = build_prompt(sample_metadata, sample_comments)
        assert "This song is timeless!" in prompt
        assert "Greetings from New Caledonia" in prompt

    def test_comment_count(self, sample_metadata: VideoMetadata, sample_comments: list[Comment]) -> None:
        prompt = build_prompt(sample_metadata, sample_comments)
        assert "3 most-liked" in prompt


class TestParseResponse:
    def test_valid_json(self) -> None:
        raw = json.dumps({
            "artist": "Josi",
            "song": "Captain Charlie",
            "year": 2010,
            "country": "Zambia",
            "language_ethnic_group": "Bemba",
            "genre": "Zambian Pop",
            "summary": "A tribute song.",
            "summary_short": "Bemba tribute to artist's father.",
        })
        result = parse_response(raw)
        assert result["artist"] == "Josi"
        assert result["year"] == 2010

    def test_strips_markdown_fences(self) -> None:
        raw = '```json\n{"artist": "Josi", "song": "Captain Charlie", "year": 2010, "country": "Zambia", "language_ethnic_group": "Bemba", "genre": "Zambian Pop", "summary": "A tribute.", "summary_short": "Short."}\n```'
        result = parse_response(raw)
        assert result["artist"] == "Josi"

    def test_missing_fields_use_defaults(self) -> None:
        raw = json.dumps({"song": "Some Song"})
        result = parse_response(raw)
        assert result["artist"] == "Unknown"
        assert result["year"] is None

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            parse_response("not json at all")
