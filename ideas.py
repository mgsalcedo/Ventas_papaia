import os
import re
import json
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

import anthropic
import cache
from idea_filters import filter_comments, filter_messages

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "ideas_system.md").read_text()

_ID_PATTERN_LONG = re.compile(r"\b(post|comment|message)[\s_-]?id[:\s]*\d+\b", re.IGNORECASE)
_ID_PATTERN_LABELED = re.compile(r"\b(post|comment|message)\s+\d{10,}\b", re.IGNORECASE)
_ID_PATTERN_BARE = re.compile(r"\b\d{12,}\b")

BACKOFF = [2, 3, 5, 9]


def _clean_ids(text: str) -> str:
    text = _ID_PATTERN_LONG.sub(lambda m: m.group(1), text)
    text = _ID_PATTERN_LABELED.sub(lambda m: m.group(1), text)
    text = _ID_PATTERN_BARE.sub("", text)
    return text


def _clean_idea(idea: dict) -> dict:
    for field in ("angle", "why_good_idea", "suggested_angle", "rationale"):
        if idea.get(field):
            idea[field] = _clean_ids(idea[field])
    return idea


def _build_discards_block() -> str:
    discards = cache.get_recent_discards(50)
    if not discards:
        return ""
    lines = ["## Ideas que el usuario YA descartó previamente (NO repitas ni hagas variantes muy similares)"]
    for d in discards:
        reason = d.get("reason_quick", "")
        note = d.get("reason_text", "")
        bucket = d.get("source_bucket", "")
        angle = d.get("angle", "")
        line = f'- [{bucket}] "{angle}"'
        if reason:
            line += f" — razón: {reason}"
        if note:
            line += f" ({note})"
        lines.append(line)
    lines.append("")
    lines.append("Aprende de estos descartes: identifica el patrón (qué ángulos, formatos o temas no le gustan) y NO propongas variantes similares en esta generación.")
    return "\n".join(lines)


def _build_context_block(platform: str, posts: list, comments: list, messages: list = None) -> str:
    parts = []

    # Top posts
    top_posts = sorted(posts, key=lambda p: p.get("likes", 0) + p.get("comments", 0) * 2, reverse=True)[:20]
    if top_posts:
        parts.append("## Posts con mejor engagement")
        for p in top_posts:
            pid = p.get("id", "")
            cap = (p.get("caption") or "")[:300]
            likes = p.get("likes", 0)
            coms = p.get("comments", 0)
            permalink = p.get("permalink", "")
            parts.append(f'- ID:{pid} | Likes:{likes} Comentarios:{coms} | "{cap}" | {permalink}')
        parts.append("")

    # Comments
    if comments:
        parts.append(f"## Comentarios sustantivos ({len(comments)} total)")
        for c in comments[:300]:
            cid = c.get("id", "")
            text = c.get("text") or c.get("message", "")
            post_id = c.get("post_id", "")
            parts.append(f'- ID:{cid} | Post:{post_id} | "{text}"')
        parts.append("")

    # DMs
    if messages:
        parts.append(f"## DMs sustantivos ({len(messages)} total)")
        for m in messages[:150]:
            mid = m.get("id", "")
            text = m.get("text") or m.get("message", "")
            parts.append(f'- ID:{mid} | "{text}"')
        parts.append("")

    return "\n".join(parts)


def _call_claude(context_block: str, instruction: str, discards_block: str) -> list[dict]:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    last_exc = None
    for attempt, wait in enumerate([0] + BACKOFF):
        if wait:
            time.sleep(wait)
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=16000,
                system=_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": context_block,
                                "cache_control": {"type": "ephemeral"},
                            },
                            {
                                "type": "text",
                                "text": f"{instruction}\n\n{discards_block}",
                            },
                        ],
                    }
                ],
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)
            ideas = parsed.get("ideas", [])
            return [_clean_idea(i) for i in ideas]
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            last_exc = e
            if hasattr(e, "status_code") and e.status_code not in (429, 500, 502, 503, 529):
                raise
        except json.JSONDecodeError as e:
            last_exc = e

    raise last_exc or RuntimeError("No se pudo generar ideas después de varios intentos")


def generate_all_ideas_ig() -> tuple[list, str]:
    """Single call, distribución 10 comments + 5 DMs + 10 top_content = ~25 ideas."""
    posts = cache.get_posts("instagram", limit=50)
    all_comments = filter_comments(cache.get_comments("instagram"))
    all_messages = filter_messages(cache.get_messages())

    context = _build_context_block("instagram", posts, all_comments, all_messages)
    discards = _build_discards_block()
    instruction = (
        "Genera ideas de contenido para Instagram con la siguiente distribución TARGET:\n"
        "- 10 ideas basadas en COMENTARIOS (source_bucket: comments)\n"
        "- 5 ideas basadas en DMs (source_bucket: dms) — si no hay suficientes DMs sustantivos, entrega menos\n"
        "- 10 ideas basadas en el CONTENIDO TOP (source_bucket: top_content)\n\n"
        "Recuerda: calidad sobre cantidad. Si no encuentras sustancia suficiente para algún bucket, entrega menos ideas."
    )

    batch_id = str(uuid.uuid4())[:8]
    ideas = _call_claude(context, instruction, discards)
    cache.save_ideas(ideas, batch_id)
    return ideas, batch_id


def generate_all_ideas_yt() -> tuple[list, str]:
    """Single call, distribución 10 comments + 10 top_content = ~20 ideas (sin DMs)."""
    posts = cache.get_posts("youtube", limit=50)
    all_comments = filter_comments(cache.get_comments("youtube"))

    context = _build_context_block("youtube", posts, all_comments)
    discards = _build_discards_block()
    instruction = (
        "Genera ideas de contenido para YouTube con la siguiente distribución TARGET:\n"
        "- 10 ideas basadas en COMENTARIOS de YouTube (source_bucket: comments)\n"
        "- 10 ideas basadas en el CONTENIDO TOP de YouTube (source_bucket: top_content)\n\n"
        "Nota: YouTube no tiene DMs, así que no hay bucket de dms.\n"
        "Recuerda: calidad sobre cantidad."
    )

    batch_id = str(uuid.uuid4())[:8]
    ideas = _call_claude(context, instruction, discards)
    cache.save_ideas(ideas, batch_id)
    return ideas, batch_id


def generate_bucket(platform: str, bucket: str) -> tuple[list, str]:
    """Regenera un solo bucket (5-10 ideas)."""
    posts = cache.get_posts(platform, limit=50)
    comments = filter_comments(cache.get_comments(platform))
    messages = filter_messages(cache.get_messages()) if platform == "instagram" else []

    context = _build_context_block(platform, posts, comments, messages if bucket == "dms" else [])
    discards = _build_discards_block()

    bucket_instructions = {
        "comments": f"Genera SOLAMENTE ideas basadas en COMENTARIOS de {platform} (source_bucket: comments). Target: 10 ideas. Calidad sobre cantidad.",
        "dms": "Genera SOLAMENTE ideas basadas en DMs de Instagram (source_bucket: dms). Target: 5 ideas. Calidad sobre cantidad.",
        "top_content": f"Genera SOLAMENTE ideas basadas en el CONTENIDO TOP de {platform} (source_bucket: top_content). Target: 10 ideas. Propón evoluciones, no copias.",
    }
    instruction = bucket_instructions.get(bucket, f"Genera ideas para el bucket {bucket}.")

    batch_id = str(uuid.uuid4())[:8]
    ideas = _call_claude(context, instruction, discards)
    cache.save_ideas(ideas, batch_id)
    return ideas, batch_id
