import logging
from pathlib import Path

from mutagen.id3 import APIC, COMM, GRP1, TCON, TDRC, TIT2, TPE1, USLT, ID3

from ytresearch.types import TrackAnalysis

logger = logging.getLogger(__name__)


def _format_genre(analysis: TrackAnalysis) -> str:
    """Build compound genre string: Genre - Ethnic Group - Country."""
    parts = [
        analysis["genre"],
        analysis["language_ethnic_group"],
        analysis["country"],
    ]
    return " - ".join(p for p in parts if p and p != "Unknown")


def _format_lyrics(analysis: TrackAnalysis, view_count: int = 0) -> str:
    """Format the USLT (lyrics) field: full summary + view count."""
    views = f"{view_count:,}" if view_count else "Unknown"
    return f"{analysis['summary']}\n\nViews: {views}"


def write_tags(audio_path: Path, analysis: TrackAnalysis, view_count: int = 0) -> None:
    """Write ID3 tags to an MP3 file."""
    try:
        tags = ID3(str(audio_path))
    except Exception:
        tags = ID3()

    tags.add(TIT2(encoding=3, text=[analysis["song"]]))
    tags.add(TPE1(encoding=3, text=[analysis["artist"]]))
    if analysis["year"]:
        tags.add(TDRC(encoding=3, text=[str(analysis["year"])]))
    tags.add(TCON(encoding=3, text=[_format_genre(analysis)]))
    tags.add(GRP1(encoding=3, text=[analysis["language_ethnic_group"]]))
    tags.add(
        COMM(
            encoding=3,
            lang="eng",
            desc="",
            text=[analysis["summary_short"]],
        )
    )
    tags.add(
        USLT(
            encoding=3,
            lang="eng",
            desc="",
            text=_format_lyrics(analysis, view_count),
        )
    )

    tags.save(str(audio_path))
    logger.info("Tags written to %s", audio_path)


def embed_thumbnail(audio_path: Path, thumbnail_path: Path) -> None:
    """Embed a thumbnail image as album art in an MP3 file."""
    if not thumbnail_path.exists():
        logger.warning("Thumbnail not found: %s", thumbnail_path)
        return

    image_data = thumbnail_path.read_bytes()

    try:
        tags = ID3(str(audio_path))
    except Exception:
        tags = ID3()

    tags.add(
        APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,  # front cover
            desc="Cover",
            data=image_data,
        )
    )
    tags.save(str(audio_path))
    logger.info("Thumbnail embedded in %s", audio_path)
