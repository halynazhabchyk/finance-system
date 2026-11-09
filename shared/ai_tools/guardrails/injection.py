"""Guardrail of level 3: a basic filter of known prompt-injection patterns.

This is a first line of defence, not a complete one. The real protection is
structural: the model has only five tools, no tool can delete or change data,
``user_id`` comes only from the JWT, and tool results are marked as data.
The filter rejects obvious attempts early (no tokens spent) and logs them.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from shared.ai_tools.guardrails.errors import GuardrailViolation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InjectionRule:
    rule_id: str
    pattern: re.Pattern[str]


def _rule(rule_id: str, pattern: str) -> InjectionRule:
    return InjectionRule(rule_id, re.compile(pattern, re.IGNORECASE))


INJECTION_RULES: tuple[InjectionRule, ...] = (
    _rule(
        "override_instructions_en",
        r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|your|system|any)\b.{0,20}\b(instructions?|rules?|prompts?|guidelines|directions)\b",
    ),
    _rule(
        "override_instructions_uk",
        r"(ігноруй|проігноруй|ігнорувати|забудь|відкинь|не\s+зважай\s+на|обійди)\w*.{0,40}(попередн|всі|усі|свої|системн|наведен)\w*.{0,20}(інструкц|правил|вказівк|промпт)\w*",
    ),
    _rule(
        "reveal_hidden_data",
        r"\b(reveal|show|print|display|repeat|output|leak|tell\s+me)\b.{0,40}\b(hidden\s+(instructions?|prompt|rules)|your\s+(instructions?|prompt|rules))\b",
    ),
    _rule(
        "reveal_system_prompt_uk",
        r"(покажи|розкрий|виведи|повтори|розкажи|назви|надрукуй|покажіть)\w*.{0,40}(системн\w*\s+(промпт|інструкц\w*|повідомлен\w*)|свій\s+промпт|свої\s+інструкц\w*|приховані\s+інструкц\w*)",
    ),
    _rule("system_prompt_mention", r"(system\s+prompt|системн\w*\s+промпт|системн\w*\s+підказк\w*)"),
    _rule(
        "secrets_request",
        r"(api[\s_-]?key|llm_api_key|secret[\s_-]?key|jwt[\s_-]?secret|access[\s_-]?token|private[\s_-]?key|"
        r"ключ\w*\s+api|api[\s-]?ключ\w*|секретн\w*\s+ключ\w*|токен\w*\s+доступу|пароль\s+(бази|бд|адміністратора))",
    ),
    _rule(
        "role_takeover",
        r"(\byou\s+are\s+now\b|\bact\s+as\b.{0,30}\b(admin|developer|system|root)\b|developer\s+mode|\bjailbreak\b|"
        r"тепер\s+ти\s+(адміністратор|розробник|систем\w*)|режим\s+розробника)",
    ),
    _rule("fake_role_markers", r"(<\s*/?\s*(system|assistant|instructions?)\s*>|\[\s*(system|inst)\s*\]|^\s*#{2,}\s*system\b)"),
)

_INVISIBLE = {"Cf"}  # zero-width and bidi control characters used to hide payloads


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if unicodedata.category(char) not in _INVISIBLE)
    return re.sub(r"\s+", " ", text).casefold()


def find_injection_rules(text: str) -> list[str]:
    """Ids of the matched rules (empty list: nothing suspicious found)."""
    normalized = normalize(text)
    return [rule.rule_id for rule in INJECTION_RULES if rule.pattern.search(normalized)]


def ensure_no_prompt_injection(text: str, *, source: str) -> None:
    """Reject ``text`` from ``source`` (user_message, a2a_message, ...) if it matches a known pattern.

    Only rule ids and the length are logged – never the text itself.
    """
    matched = find_injection_rules(text)
    if matched:
        logger.warning(
            "prompt_injection_blocked source=%s rules=%s length=%d",
            source,
            ",".join(matched),
            len(text),
        )
        raise GuardrailViolation(
            "prompt_injection",
            "Запит відхилено фільтром безпеки: він схожий на спробу змінити інструкції асистента "
            "або отримати службові дані. Переформулюйте запит як звичайне питання про бюджет.",
        )
