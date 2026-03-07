# ytresearch

A CLI tool for archiving and analyzing YouTube music videos. Given a YouTube URL (single video or playlist), it:

1. Downloads the best available audio (native format, no re-encoding)
2. Downloads a preservation copy of the video
3. Scrapes comments and metadata
4. Sends the data to Claude for structured music analysis
5. Writes the analysis as ID3/MP4 tags into the audio file
6. Stores everything in a local SQLite database

Built for researching obscure music, microgenres, and non-English language recordings.

## Prerequisites

- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/)
- An [Anthropic API key](https://console.anthropic.com/)

### Install system dependencies

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
pip install yt-dlp
```

**macOS (Homebrew):**
```bash
brew install ffmpeg yt-dlp
```

## Setup

1. Clone the repo:
```bash
git clone https://github.com/christopher-kirkley/ytresearch.git
cd ytresearch
```

2. Install with uv:
```bash
uv sync
```

3. Create your `.env` file:
```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

## Usage

```bash
# Single video
ytresearch "https://www.youtube.com/watch?v=VIDEO_ID"

# Playlist
ytresearch "https://www.youtube.com/playlist?list=PLAYLIST_ID"

# Audio only (skip video preservation)
ytresearch "https://..." --audio-only

# Dry run (fetch metadata + analyze, no downloads)
ytresearch "https://..." --dry-run

# Re-run analysis on already-downloaded files
ytresearch "https://..." --reprocess

# Use a different Claude model
ytresearch "https://..." --model claude-opus-4-6-20250514

# Custom output directories
ytresearch "https://..." --audio-dir ~/Music/Archive --video-dir /Volumes/External/video
```

## Output structure

```
~/music-archive/
├── archive.db
├── audio/
│   └── {Artist}/
│       └── {Song Title}.m4a      # tagged audio
└── video/
    └── {Artist}/
        └── {Song Title}.mp4      # preservation copy
```

## Running tests

```bash
uv run pytest
```

Note: tagger tests require ffmpeg to be installed (for generating test audio files).

## Configuration

All settings are controlled via CLI flags. Key defaults:

| Setting | Default | Flag |
|---|---|---|
| Audio directory | `~/music-archive/audio` | `--audio-dir` |
| Video directory | `~/music-archive/video` | `--video-dir` |
| Database path | `~/music-archive/archive.db` | `--db-path` |
| Claude model | `claude-sonnet-4-6-20250514` | `--model` |
| Comment limit | 100 | `--comment-limit` |
