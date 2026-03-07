import json
import logging
import re
import subprocess
from pathlib import Path

from youtube_comment_downloader import YoutubeCommentDownloader

from ytresearch.types import Comment, VideoMetadata

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> str:
    """Extract the video ID from a YouTube URL."""
    # Strip shell escape characters (zsh pastes \? \= etc.)
    url = url.replace("\\", "")
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def is_playlist_url(url: str) -> bool:
    """Check if a URL is a playlist URL."""
    return "playlist?list=" in url or "&list=" in url


def get_playlist_video_urls(url: str) -> list[str]:
    """Extract individual video URLs from a playlist."""
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "url", url],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def fetch_metadata(url: str) -> VideoMetadata:
    """Fetch video metadata using yt-dlp."""
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(result.stdout)

    return VideoMetadata(
        youtube_id=info.get("id", ""),
        youtube_url=url,
        title=info.get("title", ""),
        description=info.get("description", ""),
        uploader=info.get("uploader", ""),
        uploader_id=info.get("uploader_id", ""),
        upload_date=info.get("upload_date", ""),
        duration_seconds=info.get("duration", 0),
        view_count=info.get("view_count", 0),
        like_count=info.get("like_count"),
        comment_count=info.get("comment_count"),
        tags=info.get("tags", []) or [],
        categories=info.get("categories", []) or [],
        channel_url=info.get("channel_url", ""),
        thumbnail_path=None,
    )


def fetch_comments(url: str, limit: int = 100) -> list[Comment]:
    """Fetch comments using youtube-comment-downloader, sorted by likes."""
    video_id = extract_video_id(url)
    downloader = YoutubeCommentDownloader()
    comments: list[Comment] = []

    try:
        generator = downloader.get_comments_from_url(
            f"https://www.youtube.com/watch?v={video_id}",
            sort_by=1,  # sort by top/likes
        )
        for raw_comment in generator:
            comments.append(
                Comment(
                    text=raw_comment.get("text", ""),
                    likes=raw_comment.get("votes", 0),
                    author=raw_comment.get("author", ""),
                    timestamp=raw_comment.get("time", ""),
                )
            )
            if len(comments) >= limit:
                break
    except Exception:
        logger.warning("Failed to fetch comments for %s", url, exc_info=True)

    return comments


def download_audio(url: str, output_dir: Path) -> Path:
    """Download best audio as 320kbps MP3. Returns path to downloaded file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title)s.%(ext)s")

    result = subprocess.run(
        [
            "yt-dlp",
            "-f", "bestaudio/best",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", output_template,
            "--print", "after_move:filepath",
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("yt-dlp stderr: %s", result.stderr)
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")
    filepath = result.stdout.strip().splitlines()[-1]
    return Path(filepath)


def download_video(url: str, output_dir: Path) -> Path:
    """Download best video+audio merged as MP4. Returns path to downloaded file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title)s.%(ext)s")

    result = subprocess.run(
        [
            "yt-dlp",
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--print", "after_move:filepath",
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("yt-dlp stderr: %s", result.stderr)
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")
    filepath = result.stdout.strip().splitlines()[-1]
    return Path(filepath)


def download_thumbnail(url: str, output_dir: Path) -> Path | None:
    """Download video thumbnail. Returns path to thumbnail file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title)s.%(ext)s")

    result = subprocess.run(
        [
            "yt-dlp",
            "--write-thumbnail",
            "--skip-download",
            "--convert-thumbnails", "jpg",
            "-o", output_template,
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("Failed to download thumbnail for %s", url)
        return None

    # Find the thumbnail file
    for f in output_dir.iterdir():
        if f.suffix == ".jpg" and f.stem != "":
            return f
    return None


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename, preserving Unicode."""
    # Remove filesystem-illegal characters
    illegal = r'[<>:"/\\|?*]'
    sanitized = re.sub(illegal, "", name)
    # Collapse whitespace
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    # Prevent empty filenames
    return sanitized or "Unknown"
