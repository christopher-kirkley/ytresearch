import json
import logging
import re

import anthropic

from ytresearch.types import Comment, TrackAnalysis, VideoMetadata

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """Parse the following YouTube video data and return a structured JSON object with these fields:

- artist (string, use "Unknown" if not determinable)
- song (string, use the raw YouTube title if not determinable)
- year (integer, estimated if not explicit, null if unknown)
- country (string)
- language_ethnic_group (string)
- genre (string)
- summary (string, detailed — no length limit)
- summary_short (string, max 250 characters — a dense sentence covering what the song is about, why it matters, and note if the view count is exceptionally high for its context)

For the summary field, be thorough. Include:
- What the song is about (theme, story, meaning)
- Any lyric translations or key lines gleaned from comments or description
- Geographic reach — note any unexpected countries or regions where the song found an audience
- Longevity signals — comment timestamps showing how many years the song has stayed relevant
- Human detail — tributes, personal stories, grief, nostalgia from commenters
- Any lore about the artist — career trajectory, personal life, current status hints
- Anything culturally significant or surprising

Return only valid JSON. No preamble, no markdown fences.

Here is the data:

TITLE: {title}

DESCRIPTION:
{description}

COMMENTS ({comment_count} most-liked):
{comments}"""

DEFAULT_MODEL = "claude-sonnet-4-6"


def build_prompt(metadata: VideoMetadata, comments: list[Comment]) -> str:
    """Build the analysis prompt from video metadata and comments."""
    comments_text = "\n\n".join(
        f"[{c['author']}] ({c['timestamp']}, {c['likes']} likes)\n{c['text']}"
        for c in comments
    )

    return PROMPT_TEMPLATE.format(
        title=metadata["title"],
        description=metadata["description"],
        comment_count=len(comments),
        comments=comments_text,
    )


def parse_response(raw: str) -> TrackAnalysis:
    """Parse Claude's JSON response into a TrackAnalysis."""
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    data = json.loads(cleaned)

    return TrackAnalysis(
        artist=data.get("artist", "Unknown"),
        song=data.get("song", "Unknown"),
        year=data.get("year"),
        country=data.get("country", "Unknown"),
        language_ethnic_group=data.get("language_ethnic_group", "Unknown"),
        genre=data.get("genre", "Unknown"),
        summary=data.get("summary", ""),
        summary_short=data.get("summary_short", "")[:250],
    )


def analyze(
    metadata: VideoMetadata,
    comments: list[Comment],
    model: str = DEFAULT_MODEL,
) -> TrackAnalysis:
    """Send video data to Claude and return structured analysis."""
    prompt = build_prompt(metadata, comments)

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_response = message.content[0].text
    logger.debug("Raw Claude response:\n%s", raw_response)

    try:
        return parse_response(raw_response)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse Claude response: %s", e)
        return TrackAnalysis(
            artist="Unknown",
            song=metadata["title"],
            year=None,
            country="Unknown",
            language_ethnic_group="Unknown",
            genre="Unknown",
            summary=raw_response,
            summary_short="",
        )
