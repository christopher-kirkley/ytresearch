import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _check_ytdlp() -> None:
    """Check if yt-dlp is available."""
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        raise RuntimeError(
            "yt-dlp is required for downloads. "
            "Install with: pip install yt-dlp"
        )


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
            "-f", "bestvideo+bestaudio/best",
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

    for f in output_dir.iterdir():
        if f.suffix == ".jpg" and f.stem != "":
            return f
    return None


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename, preserving Unicode."""
    illegal = r'[<>:"/\\|?*]'
    sanitized = re.sub(illegal, "", name)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized or "Unknown"
