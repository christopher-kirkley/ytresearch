import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from ytresearch import analyzer, database, tagger, youtube
from ytresearch.types import ProcessingResult

logger = logging.getLogger(__name__)

DEFAULT_AUDIO_DIR = Path.home() / "music-archive" / "audio"
DEFAULT_VIDEO_DIR = Path.home() / "music-archive" / "video"
DEFAULT_DB_PATH = Path.home() / "music-archive" / "archive.db"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ytresearch",
        description="YouTube music research archiver",
    )
    parser.add_argument("url", help="YouTube video or playlist URL")
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--video-dir", type=Path, default=DEFAULT_VIDEO_DIR)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--audio-only", action="store_true", help="Skip video download")
    parser.add_argument("--no-db", action="store_true", help="Skip database write")
    parser.add_argument("--dry-run", action="store_true", help="Metadata + analysis only, no download")
    parser.add_argument("--reprocess", action="store_true", help="Re-run Claude + re-write tags, skip download")
    parser.add_argument("--model", default=analyzer.DEFAULT_MODEL, help="Claude model to use")
    parser.add_argument("--comment-limit", type=int, default=100, help="Max comments to fetch")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def process_video(
    url: str,
    args: argparse.Namespace,
    conn: database.sqlite3.Connection | None,
    index: int = 1,
    total: int = 1,
) -> ProcessingResult:
    """Process a single video through the full pipeline."""
    video_id = youtube.extract_video_id(url)

    # Check for existing track
    if conn and not args.reprocess and database.track_exists(conn, video_id):
        print(f"[{index}/{total}] Skipping (already archived): {url}")
        return ProcessingResult(
            video={"youtube_id": video_id, "youtube_url": url, "title": "", "description": "",
                   "uploader": "", "uploader_id": "", "upload_date": "", "duration_seconds": 0,
                   "view_count": 0, "like_count": None, "comment_count": None,
                   "tags": [], "categories": [], "channel_url": "", "thumbnail_path": None},
            analysis=None, audio_path=None, video_path=None,
            status="success", error=None,
        )

    # Fetch metadata and comments
    print(f"[{index}/{total}] Fetching metadata...")
    metadata = youtube.fetch_metadata(url)
    print(f"[{index}/{total}] {metadata['title']}")

    comments = youtube.fetch_comments(url, limit=args.comment_limit)
    print(f"         Fetched {len(comments)} comments")

    # Claude analysis
    print(f"         Analyzing with {args.model}...")
    try:
        analysis = analyzer.analyze(metadata, comments, model=args.model)
    except Exception as e:
        logger.error("Claude API error: %s", e)
        analysis = analyzer.TrackAnalysis(
            artist="Unknown", song=metadata["title"], year=None,
            country="Unknown", language_ethnic_group="Unknown",
            genre="Unknown",
            summary="",
            summary_short="",
        )

    if args.dry_run:
        _print_analysis(analysis, metadata)
        return ProcessingResult(
            video=metadata, analysis=analysis,
            audio_path=None, video_path=None,
            status="success", error=None,
        )

    # Reprocess: update analysis on existing file
    if args.reprocess and conn:
        existing_audio = database.get_track_audio_path(conn, video_id)
        if existing_audio:
            audio_path = Path(existing_audio)
            if audio_path.exists():
                tagger.write_tags(audio_path, analysis, metadata["view_count"])
                print(f"         Tags re-written to {audio_path}")
            database.update_track_analysis(conn, video_id, analysis)
            print(f"         Database updated")
        return ProcessingResult(
            video=metadata, analysis=analysis,
            audio_path=existing_audio, video_path=None,
            status="success", error=None,
        )

    # Download audio (yt-dlp names the file from the YouTube title)
    print(f"         Downloading audio...")
    try:
        audio_path = youtube.download_audio(url, args.audio_dir)
        print(f"         Audio: {audio_path}")
    except Exception as e:
        logger.error("Audio download failed: %s", e)
        return ProcessingResult(
            video=metadata, analysis=analysis,
            audio_path=None, video_path=None,
            status="failed", error=str(e),
        )

    # Download thumbnail and embed
    thumbnail_path = youtube.download_thumbnail(url, args.audio_dir)
    if thumbnail_path:
        tagger.embed_thumbnail(audio_path, thumbnail_path)
        thumbnail_path.unlink(missing_ok=True)
        print(f"         Thumbnail embedded")

    # Write tags (Claude data goes into ID3 tags only)
    tagger.write_tags(audio_path, analysis, metadata["view_count"])
    print(f"         Tags written")

    # Download video
    video_path: Path | None = None
    if not args.audio_only:
        print(f"         Downloading video...")
        try:
            video_path = youtube.download_video(url, args.video_dir)
            print(f"         Video: {video_path}")
        except Exception as e:
            logger.warning("Video download failed: %s", e)

    # Database
    result = ProcessingResult(
        video=metadata,
        analysis=analysis,
        audio_path=str(audio_path),
        video_path=str(video_path) if video_path else None,
        status="success",
        error=None,
    )

    if conn:
        database.insert_track(conn, result)
        print(f"         Database updated")

    print(f"         Done.")
    return result


def _print_analysis(analysis: analyzer.TrackAnalysis, metadata: youtube.VideoMetadata) -> None:
    """Print analysis results for --dry-run."""
    print(f"\n         Artist: {analysis['artist']}")
    print(f"         Song:   {analysis['song']}")
    print(f"         Year:   {analysis['year']}")
    print(f"         Country: {analysis['country']}")
    print(f"         Language/Ethnic Group: {analysis['language_ethnic_group']}")
    print(f"         Genre:  {analysis['genre']}")
    print(f"         Views:  {metadata['view_count']:,}")
    print(f"         Summary: {analysis['summary'][:200]}...")


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = parse_args(argv)
    setup_logging(args.verbose)

    conn = None
    if not args.no_db:
        conn = database.init_db(args.db_path)

    try:
        if youtube.is_playlist_url(args.url):
            print("Fetching playlist...")
            urls = youtube.get_playlist_video_urls(args.url)
            print(f"Found {len(urls)} videos\n")
            for i, url in enumerate(urls, 1):
                try:
                    process_video(url, args, conn, index=i, total=len(urls))
                except Exception as e:
                    logger.error("[%d/%d] Failed: %s — %s", i, len(urls), url, e)
                print()
        else:
            process_video(args.url, args, conn)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
