import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from ytresearch.metadata import analyzer, database, scraper
from ytresearch.media import downloader, tagger
from ytresearch.types import Comment, ProcessingResult, TrackAnalysis, VideoMetadata

logger = logging.getLogger(__name__)

DEFAULT_AUDIO_DIR = Path.home() / "music-archive" / "audio"
DEFAULT_VIDEO_DIR = Path.home() / "music-archive" / "video"
DEFAULT_DB_PATH = Path.home() / "music-archive" / "archive.db"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ytresearch",
        description="YouTube music research archiver",
    )
    parser.add_argument("url", nargs="?", help="YouTube video or playlist URL")
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--video-dir", type=Path, default=DEFAULT_VIDEO_DIR)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--audio-only", action="store_true", help="Skip video download")
    parser.add_argument("--no-db", action="store_true", help="Skip database write")
    parser.add_argument("--dry-run", action="store_true", help="Metadata + analysis only, print to stdout")
    parser.add_argument("--metadata-only", action="store_true", help="Layer 1 only: scrape + analyze + DB, no downloads")
    parser.add_argument("--download-only", action="store_true", help="Layer 2 only: download media for existing DB entries")
    parser.add_argument("--reprocess", action="store_true", help="Re-run Claude on a single URL, re-write tags")
    parser.add_argument("--reprocess-all", action="store_true", help="Re-run Claude on all tracks in the database")
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


# -- Layer 1: Metadata + Intelligence (server-safe) --

def run_metadata(
    url: str,
    db: database.SQLiteBackend | None,
    model: str,
    comment_limit: int,
    index: int = 1,
    total: int = 1,
) -> tuple[VideoMetadata, list[Comment], TrackAnalysis]:
    """Scrape metadata, fetch comments, run Claude analysis, store in DB."""
    url = url.replace("\\", "")

    print(f"[{index}/{total}] Fetching metadata...")
    metadata = scraper.fetch_metadata(url)
    print(f"[{index}/{total}] {metadata['title']}")

    comments = scraper.fetch_comments(url, limit=comment_limit)
    print(f"         Fetched {len(comments)} comments")

    print(f"         Analyzing with {model}...")
    try:
        analysis = analyzer.analyze(metadata, comments, model=model)
    except Exception as e:
        logger.error("Claude API error: %s", e)
        analysis = TrackAnalysis(
            artist="Unknown", song=metadata["title"], year=None,
            country="Unknown", language_ethnic_group="Unknown",
            genre="Unknown", summary="", summary_short="",
        )

    if db:
        result = ProcessingResult(
            video=metadata, analysis=analysis, comments_json=None,
            audio_path=None, video_path=None,
            status="success", error=None,
        )
        db.insert_track(result, comments)
        print(f"         Database updated")

    return metadata, comments, analysis


# -- Layer 2: Media Download (local only) --

def run_media(
    url: str,
    metadata: VideoMetadata,
    analysis: TrackAnalysis,
    db: database.SQLiteBackend | None,
    audio_dir: Path,
    video_dir: Path,
    audio_only: bool = False,
) -> tuple[Path | None, Path | None]:
    """Download audio/video, embed thumbnail, write tags."""
    # Download audio
    print(f"         Downloading audio...")
    audio_path: Path | None = None
    try:
        audio_path = downloader.download_audio(url, audio_dir)
        print(f"         Audio: {audio_path}")
    except Exception as e:
        logger.error("Audio download failed: %s", e)
        return None, None

    # Download thumbnail and embed
    thumbnail_path = downloader.download_thumbnail(url, audio_dir)
    if thumbnail_path:
        tagger.embed_thumbnail(audio_path, thumbnail_path)
        thumbnail_path.unlink(missing_ok=True)
        print(f"         Thumbnail embedded")

    # Write tags
    tagger.write_tags(audio_path, analysis, metadata["view_count"])
    print(f"         Tags written")

    # Download video
    video_path: Path | None = None
    if not audio_only:
        print(f"         Downloading video...")
        try:
            video_path = downloader.download_video(url, video_dir)
            print(f"         Video: {video_path}")
        except Exception as e:
            logger.warning("Video download failed: %s", e)

    # Update DB with file paths
    if db:
        db.update_track_media(
            metadata["youtube_id"],
            str(audio_path) if audio_path else None,
            str(video_path) if video_path else None,
        )

    return audio_path, video_path


# -- Orchestration --

def process_video(
    url: str,
    args: argparse.Namespace,
    db: database.SQLiteBackend | None,
    index: int = 1,
    total: int = 1,
) -> ProcessingResult:
    """Process a single video through the pipeline."""
    url = url.replace("\\", "")
    video_id = scraper.extract_video_id(url)

    # Skip if already archived (unless reprocessing or download-only)
    if db and not args.reprocess and not args.download_only:
        if db.track_exists(video_id):
            print(f"[{index}/{total}] Skipping (already archived): {url}")
            return ProcessingResult(
                video=VideoMetadata(
                    youtube_id=video_id, youtube_url=url, title="", description="",
                    uploader="", uploader_id="", upload_date="", duration_seconds=0,
                    view_count=0, like_count=None, comment_count=None,
                    tags=[], categories=[], channel_url="", thumbnail_path=None,
                ),
                analysis=None, comments_json=None,
                audio_path=None, video_path=None,
                status="success", error=None,
            )

    # Download-only: skip Layer 1, just download
    if args.download_only:
        if not db:
            logger.error("--download-only requires a database")
            return ProcessingResult(
                video=VideoMetadata(
                    youtube_id=video_id, youtube_url=url, title="", description="",
                    uploader="", uploader_id="", upload_date="", duration_seconds=0,
                    view_count=0, like_count=None, comment_count=None,
                    tags=[], categories=[], channel_url="", thumbnail_path=None,
                ),
                analysis=None, comments_json=None,
                audio_path=None, video_path=None,
                status="failed", error="--download-only requires a database",
            )
        # Read metadata from DB
        tracks = db.get_all_tracks()
        track = next((t for t in tracks if t["youtube_id"] == video_id), None)
        if not track:
            logger.error("Track %s not found in database. Run metadata first.", video_id)
            return ProcessingResult(
                video=VideoMetadata(
                    youtube_id=video_id, youtube_url=url, title="", description="",
                    uploader="", uploader_id="", upload_date="", duration_seconds=0,
                    view_count=0, like_count=None, comment_count=None,
                    tags=[], categories=[], channel_url="", thumbnail_path=None,
                ),
                analysis=None, comments_json=None,
                audio_path=None, video_path=None,
                status="failed", error="Track not in database",
            )
        # Reconstruct metadata and analysis from DB
        metadata = VideoMetadata(
            youtube_id=track["youtube_id"], youtube_url=track["youtube_url"],
            title=track["title"] or "", description=track["description"] or "",
            uploader=track["uploader"] or "", uploader_id=track["uploader_id"] or "",
            upload_date=track["upload_date"] or "", duration_seconds=track["duration_seconds"] or 0,
            view_count=track["view_count"],
            like_count=track["like_count"], comment_count=track["comment_count"],
            tags=json.loads(track["tags"]) if track["tags"] else [],
            categories=json.loads(track["categories"]) if track["categories"] else [],
            channel_url=track["channel_url"] or "", thumbnail_path=None,
        )
        # Fetch analysis from DB
        cursor = db.conn.execute(
            "SELECT artist, song, year, country, language_ethnic_group, genre, summary, summary_short FROM tracks WHERE youtube_id = ?",
            (video_id,),
        )
        row = cursor.fetchone()
        analysis = TrackAnalysis(
            artist=row["artist"] or "Unknown", song=row["song"] or metadata["title"],
            year=row["year"], country=row["country"] or "Unknown",
            language_ethnic_group=row["language_ethnic_group"] or "Unknown",
            genre=row["genre"] or "Unknown",
            summary=row["summary"] or "", summary_short=row["summary_short"] or "",
        )
        print(f"[{index}/{total}] {metadata['title']}")
        audio_path, video_path = run_media(
            url, metadata, analysis, db, args.audio_dir, args.video_dir, args.audio_only,
        )
        print(f"         Done.")
        return ProcessingResult(
            video=metadata, analysis=analysis, comments_json=None,
            audio_path=str(audio_path) if audio_path else None,
            video_path=str(video_path) if video_path else None,
            status="success" if audio_path else "failed", error=None,
        )

    # Layer 1: Metadata + Analysis
    metadata, comments, analysis = run_metadata(
        url, db, args.model, args.comment_limit, index, total,
    )

    if args.dry_run:
        _print_analysis(analysis, metadata)
        return ProcessingResult(
            video=metadata, analysis=analysis,
            comments_json=json.dumps(comments, ensure_ascii=False),
            audio_path=None, video_path=None,
            status="success", error=None,
        )

    if args.metadata_only:
        print(f"         Done (metadata only).")
        return ProcessingResult(
            video=metadata, analysis=analysis,
            comments_json=json.dumps(comments, ensure_ascii=False),
            audio_path=None, video_path=None,
            status="success", error=None,
        )

    # Reprocess: update analysis on existing file
    if args.reprocess and db:
        existing_audio = db.get_track_audio_path(video_id)
        if existing_audio:
            audio_path = Path(existing_audio)
            if audio_path.exists():
                tagger.write_tags(audio_path, analysis, metadata["view_count"])
                print(f"         Tags re-written to {audio_path}")
            db.update_track_analysis(video_id, analysis)
            print(f"         Database updated")
        return ProcessingResult(
            video=metadata, analysis=analysis,
            comments_json=json.dumps(comments, ensure_ascii=False),
            audio_path=existing_audio, video_path=None,
            status="success", error=None,
        )

    # Layer 2: Media Download
    audio_path, video_path = run_media(
        url, metadata, analysis, db, args.audio_dir, args.video_dir, args.audio_only,
    )

    print(f"         Done.")
    return ProcessingResult(
        video=metadata, analysis=analysis,
        comments_json=json.dumps(comments, ensure_ascii=False),
        audio_path=str(audio_path) if audio_path else None,
        video_path=str(video_path) if video_path else None,
        status="success" if audio_path else "failed", error=None,
    )


def reprocess_all(args: argparse.Namespace, db: database.SQLiteBackend) -> None:
    """Re-run Claude analysis on all tracks in the database."""
    tracks = db.get_all_tracks()
    print(f"Reprocessing {len(tracks)} tracks...\n")

    for i, track in enumerate(tracks, 1):
        print(f"[{i}/{len(tracks)}] {track['youtube_url']}")

        # Reconstruct metadata
        metadata = VideoMetadata(
            youtube_id=track["youtube_id"], youtube_url=track["youtube_url"],
            title=track["title"] or "", description=track["description"] or "",
            uploader=track["uploader"] or "", uploader_id=track["uploader_id"] or "",
            upload_date=track["upload_date"] or "", duration_seconds=track["duration_seconds"] or 0,
            view_count=track["view_count"],
            like_count=track["like_count"], comment_count=track["comment_count"],
            tags=json.loads(track["tags"]) if track["tags"] else [],
            categories=json.loads(track["categories"]) if track["categories"] else [],
            channel_url=track["channel_url"] or "", thumbnail_path=None,
        )

        # Load stored comments
        comments: list[Comment] = []
        if track["comments_json"]:
            try:
                comments = json.loads(track["comments_json"])
            except json.JSONDecodeError:
                logger.warning("Failed to parse stored comments for %s", track["youtube_id"])

        # Re-analyze
        print(f"         Analyzing with {args.model}...")
        try:
            analysis = analyzer.analyze(metadata, comments, model=args.model)
        except Exception as e:
            logger.error("         Claude API error: %s", e)
            continue

        # Update DB
        db.update_track_analysis(track["youtube_id"], analysis)
        print(f"         Database updated")

        # Re-write tags if audio exists
        if track["audio_path"]:
            audio_path = Path(track["audio_path"])
            if audio_path.exists():
                tagger.write_tags(audio_path, analysis, track["view_count"])
                print(f"         Tags re-written to {audio_path}")

        print()


def _print_analysis(analysis: TrackAnalysis, metadata: VideoMetadata) -> None:
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

    db: database.SQLiteBackend | None = None
    if not args.no_db:
        db = database.SQLiteBackend(args.db_path)
        db.init()

    try:
        # --reprocess-all: special path, no URL needed
        if args.reprocess_all:
            if not db:
                logger.error("--reprocess-all requires a database")
                sys.exit(1)
            reprocess_all(args, db)
            return

        if not args.url:
            logger.error("URL is required (unless using --reprocess-all)")
            sys.exit(1)

        if scraper.is_playlist_url(args.url):
            print("Fetching playlist...")
            urls = scraper.get_playlist_video_urls(args.url)
            print(f"Found {len(urls)} videos\n")
            for i, url in enumerate(urls, 1):
                try:
                    process_video(url, args, db, index=i, total=len(urls))
                except Exception as e:
                    logger.error("[%d/%d] Failed: %s — %s", i, len(urls), url, e)
                print()
        else:
            process_video(args.url, args, db)
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    main()
