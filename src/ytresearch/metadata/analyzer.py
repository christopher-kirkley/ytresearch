import json
import logging
import re

import anthropic

from ytresearch.types import Comment, TrackAnalysis, VideoMetadata

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are generating an ethnographic summary of a YouTube music video based on two sources: your own knowledge of music, history, language, and culture; and the comments scraped from the video. Your knowledge contextualizes — comments personalize. Where both exist, prefer the specific human testimony over the general background. A commenter who was there outranks a textbook summary.

Return a structured JSON object with these fields:

- artist (string, use "Unknown" if not determinable)
- song (string, use the raw YouTube title if not determinable)
- year (integer, estimated if not explicit, null if unknown)
- country (string)
- language_ethnic_group (string)
- genre (string)
- summary (string, structured ethnographic analysis — see section format below)
- summary_short (string, max 250 characters — a dense sentence covering what the song is about, why it matters, and note if the view count is exceptionally high for its context)

For the summary field, use the section headers below. Omit any section where you have insufficient data to say something meaningful. Do not pad, speculate, or invent. A missing section is better than a thin one.

## Title & Meaning
Etymology, connotation, cultural metaphor, or literal meaning as relevant. Draw from language knowledge first, comments second. 2–3 sentences. Skip if the title is self-explanatory.

## Genre & Musical Form
Describe what kind of music this is and how it works, using whatever dimensions actually matter for this specific track. For traditional or classical music that might mean form, modal system, or rhythm. For contemporary music it might mean production style, genre lineage, regional scene, or how it sits relative to commercial vs. underground currents. If the track belongs to a recognizable tradition or scene, say what that world looks and feels like — not just the label. Draw from music knowledge first, comments second. Comments may contain scene-specific knowledge that overrides general knowledge. 3–4 sentences. Skip if genre is genuinely unidentifiable.

## Artist
Role (composer, performer, producer, or some combination), reputation, legacy, associated artists, broader discography context where relevant. Draw from knowledge first, comments second. Flag clearly if the artist is obscure or unidentifiable from either source. 3–4 sentences.

## Historical & Cultural Context
When it was made, what was happening, what it meant to exist then. Draw from historical knowledge first, comments second. Prefer comment specifics over general background where both exist. 4–5 sentences.

## Visuals
What is shown in the video, how commenters respond to it, what it represents about the era, scene, or culture. Comments are the primary source here; knowledge secondary. 2–3 sentences. Skip if the video is a static image or lyrics card with no meaningful visual content.

## Comment Highlights
2–4 of the most vivid, specific, human testimonies. Paraphrase closely but preserve the personal detail — names optional. Comments are the only source. Do not supplement with invented voices. Always present if comments exist.

## Political & Ideological Layer
Exile politics, regime references, generational conflict, nationalist sentiment, or cultural ownership disputes. Comments are the primary source; knowledge can provide context but should not infer politics the comments do not raise. 2–3 sentences. Skip if absent.

## Diaspora & Geographic Reach
Where listeners are writing from, how the music traveled, what communities claim it. Comments primary, knowledge secondary for geographic or historical context. 2–3 sentences. Skip if comments are geographically homogeneous or location is unreadable.

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
