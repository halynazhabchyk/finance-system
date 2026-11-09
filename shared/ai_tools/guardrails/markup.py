"""Guardrail of level 3: active content – HTML/JS markup (XSS), dangerous URIs, code to execute.

The prompt-injection filter protects the *model*; this module protects whoever
later *renders* the data (a browser showing a category name or the assistant
answer) and rejects requests that try to smuggle code into the system.

* Input (user message, A2A text, names and descriptions written by tools) is
  rejected: nothing with active content is sent to the model or stored.
* Output (the model answer) is sanitized instead of rejected: tokens are
  already spent, and removing tags or images keeps the useful text.

HTML is recognised by ``nh3`` (Python binding of the Rust sanitizer ``ammonia``)
rather than by regular expressions: it parses markup the way a browser does,
so plain text like "Кава <3" or "знижка > 50%" is not treated as a tag.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass

import nh3

from shared.ai_tools.guardrails.errors import GuardrailViolation
from shared.ai_tools.guardrails.injection import normalize

logger = logging.getLogger(__name__)

# Entities may hide markup ("&lt;script&gt;"); decoding twice covers double encoding.
_MAX_DECODE_ROUNDS = 3

_DANGEROUS_URI = re.compile(
    r"\b(?:java|vb|live)script\s*:|\bdata\s*:\s*(?:text/html|application/(?:x-)?javascript|image/svg\+xml)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CodeRule:
    rule_id: str
    pattern: re.Pattern[str]


def _code_rule(rule_id: str, pattern: str) -> CodeRule:
    return CodeRule(rule_id, re.compile(pattern, re.IGNORECASE))


CODE_RULES: tuple[CodeRule, ...] = (
    _code_rule("code_python", r"\b(?:eval|exec|__import__)\s*\(|\bos\s*\.\s*(?:system|popen)\b|\bsubprocess\b"),
    _code_rule("code_javascript", r"\bdocument\s*\.\s*(?:cookie|write)\b|\bwindow\s*\.\s*location\b|\bnew\s+function\s*\("),
    _code_rule("code_php", r"<\?(?:php|=)"),
    _code_rule(
        "code_sql",
        r"\b(?:drop|truncate)\s+table\b|\bunion\s+(?:all\s+)?select\b|;\s*(?:delete\s+from|insert\s+into)\b",
    ),
    _code_rule("code_shell", r"\brm\s+-rf\b|\$\([^)]*\)|\b(?:curl|wget)\s+\S+\s*\|\s*(?:ba)?sh\b"),
)


def _decode_entities(text: str) -> str:
    for _ in range(_MAX_DECODE_ROUNDS):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return text


def _strip_all_markup(text: str) -> str:
    """Text without tags; the content of <script>, <style> and similar is dropped by nh3."""
    return nh3.clean(text, tags=set(), attributes={}, url_schemes=set())


def contains_html_markup(text: str) -> bool:
    decoded = _decode_entities(text)
    return _decode_entities(_strip_all_markup(decoded)) != decoded


def find_active_content_rules(text: str) -> list[str]:
    """Ids of the matched rules (empty list: plain text)."""
    decoded = _decode_entities(text)
    normalized = normalize(decoded)
    matched: list[str] = []
    if contains_html_markup(decoded):
        matched.append("html_markup")
    if _DANGEROUS_URI.search(normalized):
        matched.append("dangerous_uri")
    matched.extend(rule.rule_id for rule in CODE_RULES if rule.pattern.search(normalized))
    return matched


def ensure_no_active_content(text: str, *, source: str) -> None:
    """Reject ``text`` from ``source`` if it contains markup, a dangerous URI or code.

    Only rule ids and the length are logged – never the text itself.
    """
    matched = find_active_content_rules(text)
    if matched:
        logger.warning(
            "active_content_blocked source=%s rules=%s length=%d",
            source,
            ",".join(matched),
            len(text),
        )
        raise GuardrailViolation(
            "active_content",
            "Запит відхилено фільтром безпеки: він містить HTML-розмітку, скрипт, небезпечне посилання "
            "або програмний код. Опишіть, що потрібно зробити з бюджетом, звичайним текстом.",
        )


# --- Output: the model answer -------------------------------------------------------------

IMAGE_PLACEHOLDER = "[зображення вилучено]"
LINK_PLACEHOLDER = "[небезпечне посилання вилучено]"

# Link target of Markdown: allows one level of nested parentheses, e.g. (javascript:alert(1)).
_MARKDOWN_TARGET = r"(?:[^()]|\([^()]*\))*"
_MARKDOWN_IMAGE = re.compile(rf"!\[[^\]]*\]\({_MARKDOWN_TARGET}\)")
_MARKDOWN_UNSAFE_LINK = re.compile(
    rf"\[([^\]]*)\]\(\s*(?:(?:java|vb|live)script|data)\s*:{_MARKDOWN_TARGET}\)",
    re.IGNORECASE,
)


def sanitize_model_answer(text: str) -> tuple[str, list[str]]:
    """Return the answer without active content and the ids of what was removed.

    * HTML tags are removed (their text stays, <script>/<style> content is dropped);
    * Markdown images are replaced: a rendered image is fetched by the browser and can leak
      data in its URL, while the assistant never needs external images;
    * Markdown links with javascript:/data: schemes keep only their text;
    * any remaining dangerous URI scheme is replaced by a placeholder.
    """
    removed: list[str] = []

    if contains_html_markup(text):
        cleaned = _decode_entities(_strip_all_markup(_decode_entities(text)))
        # Decoding may reveal markup that was entity-encoded; strip until stable.
        for _ in range(_MAX_DECODE_ROUNDS):
            if not contains_html_markup(cleaned):
                break
            cleaned = _decode_entities(_strip_all_markup(cleaned))
        else:
            cleaned = nh3.clean_text(cleaned)
        text = cleaned
        removed.append("html_markup")

    text, images = _MARKDOWN_IMAGE.subn(IMAGE_PLACEHOLDER, text)
    if images:
        removed.append("markdown_image")

    text, links = _MARKDOWN_UNSAFE_LINK.subn(r"\1", text)
    if links:
        removed.append("unsafe_link")

    text, uris = _DANGEROUS_URI.subn(LINK_PLACEHOLDER, text)
    if uris:
        removed.append("dangerous_uri")

    return text, removed
