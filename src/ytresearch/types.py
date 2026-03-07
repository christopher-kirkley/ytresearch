from typing import Literal, TypedDict


class VideoMetadata(TypedDict):
    youtube_id: str
    youtube_url: str
    title: str
    description: str
    uploader: str
    uploader_id: str
    upload_date: str  # YYYYMMDD
    duration_seconds: int
    view_count: int
    like_count: int | None
    comment_count: int | None
    tags: list[str]
    categories: list[str]
    channel_url: str
    thumbnail_path: str | None


class Comment(TypedDict):
    text: str
    likes: int
    author: str
    timestamp: str


class TrackAnalysis(TypedDict):
    artist: str
    song: str
    year: int | None
    country: str
    language_ethnic_group: str
    genre: str
    summary: str
    summary_short: str


class ProcessingResult(TypedDict):
    video: VideoMetadata
    analysis: TrackAnalysis | None
    audio_path: str | None
    video_path: str | None
    status: Literal["success", "partial", "failed"]
    error: str | None
