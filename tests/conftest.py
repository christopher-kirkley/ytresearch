import pytest

from ytresearch.types import Comment, TrackAnalysis, VideoMetadata


@pytest.fixture
def sample_metadata() -> VideoMetadata:
    return VideoMetadata(
        youtube_id="dQw4w9WgXcQ",
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Captain Charlie - Josi (Official Video)",
        description="Official music video for Captain Charlie by Josi.\nBemba language.",
        uploader="JosiMusic",
        uploader_id="UC1234567890",
        upload_date="20100523",
        duration_seconds=245,
        view_count=1674214,
        like_count=12000,
        comment_count=850,
        tags=["zambian music", "bemba", "josi"],
        categories=["Music"],
        channel_url="https://www.youtube.com/channel/UC1234567890",
        thumbnail_path=None,
    )


@pytest.fixture
def sample_comments() -> list[Comment]:
    return [
        Comment(text="This song is timeless!", likes=120, author="User1", timestamp="2 years ago"),
        Comment(text="Greetings from New Caledonia", likes=85, author="User2", timestamp="1 year ago"),
        Comment(text="RIP Captain Charlie", likes=60, author="User3", timestamp="3 months ago"),
    ]


@pytest.fixture
def sample_analysis() -> TrackAnalysis:
    return TrackAnalysis(
        artist="Josi",
        song="Captain Charlie",
        year=2010,
        country="Zambia",
        language_ethnic_group="Bemba",
        genre="Zambian Pop",
        summary="A tribute song by Josi to his father, Captain Charlie.",
    )
