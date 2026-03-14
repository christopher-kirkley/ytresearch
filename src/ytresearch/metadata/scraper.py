import json
import logging
import re

import requests
from youtube_comment_downloader import YoutubeCommentDownloader

from ytresearch.types import Comment, VideoMetadata

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"
)
YT_INITIAL_DATA_RE = (
    r"(?:window\s*\[\s*[\"']ytInitialData[\"']\s*\]|ytInitialData)\s*=\s*"
    r"({.+?})\s*;\s*(?:var\s+meta|</script|\n)"
)


def extract_video_id(url: str) -> str:
    """Extract the video ID from a YouTube URL."""
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


def _create_session() -> requests.Session:
    """Create an HTTP session mimicking a browser."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.cookies.set("CONSENT", "YES+cb", domain=".youtube.com")
    return session


def _fetch_yt_initial_data(url: str, session: requests.Session | None = None) -> dict:
    """Fetch a YouTube page and extract ytInitialData JSON."""
    if session is None:
        session = _create_session()

    response = session.get(url)
    response.raise_for_status()

    match = re.search(YT_INITIAL_DATA_RE, response.text)
    if not match:
        raise RuntimeError(f"Could not extract ytInitialData from {url}")

    return json.loads(match.group(1))


def _search_dict(data: dict | list, target_key: str) -> list:
    """Recursively search for a key in nested dicts/lists."""
    results = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key:
                results.append(value)
            results.extend(_search_dict(value, target_key))
    elif isinstance(data, list):
        for item in data:
            results.extend(_search_dict(item, target_key))
    return results


def fetch_metadata(url: str) -> VideoMetadata:
    """Fetch video metadata via HTTP scraping (no yt-dlp)."""
    video_id = extract_video_id(url)
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"

    session = _create_session()
    response = session.get(canonical_url)
    response.raise_for_status()
    html = response.text

    # Extract ytInitialData
    match = re.search(YT_INITIAL_DATA_RE, html)
    if not match:
        raise RuntimeError(f"Could not extract ytInitialData for {url}")
    initial_data = json.loads(match.group(1))

    # Extract videoDetails from the page source (separate from ytInitialData)
    vd_match = re.search(
        r'"videoDetails"\s*:\s*({.+?})\s*,\s*"(?:annotations|playerConfig|microformat)',
        html,
    )
    video_details: dict = {}
    if vd_match:
        try:
            video_details = json.loads(vd_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to get metadata from videoPrimaryInfoRenderer
    primary_info = _search_dict(initial_data, "videoPrimaryInfoRenderer")
    secondary_info = _search_dict(initial_data, "videoSecondaryInfoRenderer")

    # Title
    title = video_details.get("title", "")
    if not title and primary_info:
        title_runs = _search_dict(primary_info[0].get("title", {}), "text")
        title = "".join(title_runs) if title_runs else ""

    # Description
    description = video_details.get("shortDescription", "")

    # View count
    view_count = int(video_details.get("viewCount", 0))

    # Duration
    duration = int(video_details.get("lengthSeconds", 0))

    # Channel info
    uploader = video_details.get("author", "")
    uploader_id = video_details.get("channelId", "")
    channel_url = f"https://www.youtube.com/channel/{uploader_id}" if uploader_id else ""

    # Upload date — try dateText from primaryInfoRenderer
    upload_date = ""
    if primary_info:
        date_text_results = _search_dict(primary_info[0], "dateText")
        if date_text_results:
            raw_date = date_text_results[0].get("simpleText", "") if isinstance(date_text_results[0], dict) else str(date_text_results[0])
            # Try to parse "Jan 1, 2020" style dates
            upload_date = _parse_upload_date(raw_date)

    # Like count — from videoPrimaryInfoRenderer
    like_count = None
    if primary_info:
        # Look for toggle button with like info
        like_results = _search_dict(primary_info[0], "defaultText")
        for lr in like_results:
            if isinstance(lr, dict) and "accessibility" in lr:
                acc_label = lr.get("accessibility", {}).get("accessibilityData", {}).get("label", "")
                if "like" in acc_label.lower():
                    # Extract number from "1,234 likes"
                    num_match = re.search(r"[\d,]+", acc_label)
                    if num_match:
                        like_count = int(num_match.group().replace(",", ""))

    # Tags/keywords
    tags = video_details.get("keywords", []) or []

    return VideoMetadata(
        youtube_id=video_id,
        youtube_url=canonical_url,
        title=title,
        description=description,
        uploader=uploader,
        uploader_id=uploader_id,
        upload_date=upload_date,
        duration_seconds=duration,
        view_count=view_count,
        like_count=like_count,
        comment_count=None,  # Not reliably available without API
        tags=tags,
        categories=[],  # Not in ytInitialData
        channel_url=channel_url,
        thumbnail_path=None,
    )


def _parse_upload_date(raw: str) -> str:
    """Try to parse a date string into YYYYMMDD format."""
    import re as _re
    from datetime import datetime

    # Strip common prefixes
    raw = raw.replace("Premiered ", "").replace("Streamed live ", "").strip()

    # Try common YouTube date formats
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue

    return ""


def get_playlist_video_urls(url: str) -> list[str]:
    """Extract video URLs from a playlist via HTTP scraping."""
    session = _create_session()
    data = _fetch_yt_initial_data(url, session)

    video_ids: list[str] = []
    playlist_items = _search_dict(data, "playlistVideoRenderer")
    for item in playlist_items:
        vid = item.get("videoId")
        if vid:
            video_ids.append(vid)

    return [f"https://www.youtube.com/watch?v={vid}" for vid in video_ids]


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
