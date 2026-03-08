# ytresearch — Project Spec

## What it does

A CLI tool that takes a YouTube URL (single video or playlist), downloads the audio as 320kbps MP3, archives a preservation copy of the video, scrapes comments, sends the data to Claude for structured music metadata analysis, writes that metadata as ID3 tags into the MP3, and stores everything in a local SQLite database.

Built for researching obscure music — microgenres, non-English languages, ethnic recordings — where YouTube is often the only source and videos disappear without warning.

## Pipeline

```
YouTube URL (video or playlist)
        |
  yt-dlp                        <- fetch video metadata (title, description, etc.)
  youtube-comment-downloader     <- scrape top 100 comments by likes
        |
  yt-dlp + ffmpeg                <- download audio as 320kbps MP3
  yt-dlp                         <- download best video (preservation copy)
  yt-dlp                         <- download thumbnail
        |
  mutagen                        <- embed thumbnail as album art
        |
  Claude API (Sonnet 4.6)        <- generate structured metadata from title + description + comments
        |
  mutagen                        <- write ID3 tags to MP3
        |
  sqlite3                        <- write row to local database
```

## Claude analysis

The LLM receives the video title, description, and top comments (sorted by likes). It returns a JSON object with:

- **artist** — identified from title/description/comments, or "Unknown"
- **song** — song name, or raw YouTube title if unclear
- **year** — from upload date or estimated from context, or null
- **country** — country of origin
- **language_ethnic_group** — language or ethnic group
- **genre** — musical genre
- **summary** — detailed analysis (no length limit): theme, lyric translations, geographic reach, longevity signals, human stories from comments, artist lore, cultural significance
- **summary_short** — max 250 characters for Apple Music's Comment field

View count is never sourced from Claude — it comes from yt-dlp metadata.

Default model is `claude-sonnet-4-6`. Configurable via `--model` flag.

## ID3 tag mapping

| Data | ID3 Tag | Apple Music Field |
|---|---|---|
| Song title | `TIT2` | Name |
| Artist | `TPE1` | Artist |
| Year | `TDRC` | Year |
| Genre - Ethnic Group - Country | `TCON` | Genre |
| Language / Ethnic Group | `GRP1` | Grouping |
| Short summary (max 250 chars) | `COMM` | Comments |
| Full summary + view count | `USLT` | Lyrics |
| Thumbnail | `APIC` | Album Art |

The genre field is a compound string (e.g., "Zambian Pop - Bemba - Zambia") to pack three dimensions into one searchable field in Apple Music.

## Audio format

All audio is downloaded as **320kbps MP3** via yt-dlp + ffmpeg. This ensures Apple Music compatibility. The video preservation copy retains the original quality.

## File organization

```
~/music-archive/
├── archive.db
├── audio/
│   └── {YouTube Title}.mp3          <- tagged, for Apple Music import
└── video/
    └── {YouTube Title}.mp4          <- preservation copy
```

Filenames come from yt-dlp (the YouTube title), not from Claude analysis. Claude data lives only in ID3 tags and the database.

## SQLite schema

```sql
CREATE TABLE IF NOT EXISTS tracks (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url           TEXT UNIQUE,
    youtube_id            TEXT,

    -- Claude-generated
    artist                TEXT,
    song                  TEXT,
    year                  INTEGER,
    country               TEXT,
    language_ethnic_group TEXT,
    genre                 TEXT,
    view_count            INTEGER,
    summary               TEXT,
    summary_short         TEXT,

    -- yt-dlp metadata
    uploader              TEXT,
    uploader_id           TEXT,
    upload_date           TEXT,
    duration_seconds      INTEGER,
    like_count            INTEGER,
    comment_count         INTEGER,
    description           TEXT,
    tags                  TEXT,       -- JSON array
    categories            TEXT,       -- JSON array
    channel_url           TEXT,

    -- File paths
    audio_path            TEXT,
    video_path            TEXT,
    thumbnail_path        TEXT,

    -- Housekeeping
    downloaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reprocessed_at        TIMESTAMP
);
```

## CLI usage

```bash
# Single video
ytresearch "https://www.youtube.com/watch?v=VIDEO_ID"

# Playlist
ytresearch "https://www.youtube.com/playlist?list=PLAYLIST_ID"

# Flags
--audio-only          Skip video preservation download
--dry-run             Fetch metadata + analyze only, no downloads
--reprocess           Re-run Claude + re-write tags on existing files
--model MODEL         Claude model (default: claude-sonnet-4-6)
--comment-limit N     Max comments to fetch (default: 100)
--audio-dir PATH      Audio output directory (default: ~/music-archive/audio)
--video-dir PATH      Video output directory (default: ~/music-archive/video)
--db-path PATH        Database path (default: ~/music-archive/archive.db)
--no-db               Skip database write
--verbose             Debug logging
```

## Batch / playlist behavior

- yt-dlp handles playlist URLs natively
- Each video runs through the full pipeline sequentially
- Before processing, checks `archive.db` for existing `youtube_id` — skips if found
- On error, logs and continues to next video — does not abort batch

## Error handling

- Claude API failures: writes partial tags (title from YouTube), logs error, continues
- yt-dlp failures: logs to stderr with context, continues to next video
- Shell-escaped URLs (macOS zsh pastes `\?` and `\=`): stripped automatically

## Dependencies

| Package | Purpose |
|---|---|
| `yt-dlp` | Download audio/video, fetch metadata |
| `youtube-comment-downloader` | Scrape comments without API key |
| `anthropic` | Claude API SDK |
| `mutagen` | Write ID3 tags |
| `python-dotenv` | Load API key from `.env` |

System dependency: **ffmpeg** (must be installed separately).

## Project structure

```
src/ytresearch/
├── cli.py              # argparse + orchestration
├── types.py            # TypedDicts for all data shapes
├── youtube.py          # yt-dlp + comment scraping
├── analyzer.py         # Claude prompt + response parsing
├── tagger.py           # ID3 tag writing
└── database.py         # SQLite operations
```
