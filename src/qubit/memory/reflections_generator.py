"""
Module for generating reflections from chat history.

Produces 3 Q&A pairs that capture key patterns from recent conversation.
These are stored as memories and injected into future prompts.

The LLM is asked for JSON output. A tolerant fallback parser handles the
most common ways local models deviate from strict JSON (trailing commas,
markdown fences, extra preamble) so a minor formatting slip doesn't
silently produce zero reflections.
"""

import json
import re
from typing import TYPE_CHECKING, Any, List, Tuple

from src.qubit.models.llm_service import LLMService
from src.utils.log_utils import get_logger

if TYPE_CHECKING:
    from src.qubit.memory.memory_manager import MemoryManager


_FENCE_RE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


class ReflectionGenerator:
    """
    Generates reflective Q&A pairs from recent chat history.

    Asks the reflection profile for a JSON array of {q, a} objects.
    Falls back to a tolerant text parser if JSON cannot be decoded.
    """

    SYSTEM_PROMPT = (
        "You are a memory assistant. Analyse the conversation and return "
        "ONLY a JSON array — no explanation, no markdown, no preamble. "
        "The array must contain exactly 3 objects, each with keys \"q\" and \"a\"."
    )

    USER_PROMPT = """\
Given the following recent conversation, produce exactly 3 question-answer pairs \
that capture the most important and distinctive aspects. Focus on insights, patterns, \
or key information valuable to remember for future interactions.

Recent conversation:
{recent_messages}

Return ONLY valid JSON in this exact shape (no other text):
[
  {{"q": "...", "a": "..."}},
  {{"q": "...", "a": "..."}},
  {{"q": "...", "a": "..."}}
]"""

    def __init__(
        self,
        llm_service: LLMService,
        reflection_profile: str = "reflection",
        reflection_threshold: int = 20,
    ):
        self.logger = get_logger("ReflectionGenerator")
        self.llm_service = llm_service
        self.reflection_profile = reflection_profile
        self.reflection_threshold = reflection_threshold

    async def perform_reflection(
        self, memory_manager: "MemoryManager"
    ) -> List[Tuple[str, str]]:
        """
        Perform reflection on recent messages and return up to 3 (q, a) tuples.
        Returns [] if there are not enough messages or the model fails entirely.
        """
        recent_messages = memory_manager.get_recent_items("chat", limit=self.reflection_threshold)

        if len(recent_messages) < 10:
            self.logger.info("[perform_reflection] Not enough messages for reflection (%d)", len(recent_messages))
            return []

        messages_text = self._format_messages(recent_messages)

        reflection_messages = [
            {"role": "System", "content": self.SYSTEM_PROMPT},
            {"role": "User", "content": self.USER_PROMPT.format(recent_messages=messages_text)},
        ]

        self.logger.info("[perform_reflection] Requesting reflection from model")
        try:
            response = await self.llm_service.generate_with_retries(
                profile=self.reflection_profile,
                input=reflection_messages,
                max_attempts=3,
            )
            self.logger.info("[perform_reflection] Raw response: %s", response)

            qa_pairs = self._parse_qa_pairs(response)
            self.logger.info("[perform_reflection] Parsed %d pair(s)", len(qa_pairs))
            return qa_pairs

        except Exception as e:
            self.logger.error("[perform_reflection] Error: %s", e)
            return []

    def _format_messages(self, messages: list) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "Unknown")
            content = msg.get("content", "")
            user_id = msg.get("user_id", "Unknown")
            if role == "User":
                lines.append(f"User {user_id}: {content}")
            else:
                lines.append(f"Qubit: {content}")
        return "\n".join(lines)

    def _parse_qa_pairs(self, response: str) -> List[Tuple[str, str]]:
        """
        Parse (question, answer) tuples from the model response.

        Strategy (in order):
        1. Strip markdown fences and any preamble before the first '['.
        2. Fix common JSON errors (trailing commas).
        3. json.loads() — ideal path.
        4. If JSON fails, fall back to tolerant line-by-line text parser that
           handles Q1:/A1:, Question 1:, numbered lists, and bold variants.
        """
        pairs = self._try_json_parse(response)
        if pairs:
            return pairs[:3]

        self.logger.warning(
            "[_parse_qa_pairs] JSON parse failed — falling back to text parser"
        )
        pairs = self._try_text_parse(response)
        if not pairs:
            self.logger.error(
                "[_parse_qa_pairs] Both parsers failed. Raw response was: %s", response
            )
        return pairs[:3]

    def _try_json_parse(self, response: str) -> List[Tuple[str, str]]:
        """Attempt to extract a JSON array from the response."""
        text = response.strip()

        # Strip markdown fences if present
        fence_match = _FENCE_RE.search(text)
        if fence_match:
            text = fence_match.group(1).strip()

        # Find the first '[' — strip any preamble the model added before the array
        bracket = text.find("[")
        if bracket != -1:
            text = text[bracket:]

        # Fix trailing commas before } or ] which are common model errors
        text = _TRAILING_COMMA_RE.sub(r"\1", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        pairs = []
        for item in data:
            if not isinstance(item, dict):
                continue
            # Accept "q"/"a", "question"/"answer", or "Q"/"A" as keys
            q = item.get("q") or item.get("question") or item.get("Q", "")
            a = item.get("a") or item.get("answer") or item.get("A", "")
            q, a = str(q).strip(), str(a).strip()
            if q and a:
                pairs.append((q, a))

        return pairs

    def _try_text_parse(self, response: str) -> List[Tuple[str, str]]:
        """
        Tolerant text parser for when the model ignores JSON entirely.

        Handles:
          Q1: ... / A1: ...
          Question 1: ... / Answer 1: ...
          **Q1:** ... / **A1:** ...
          1. ... (numbered list where odd = Q, even = A)
        """
        # Normalise bold markdown: **Q1:** -> Q1:
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", response)
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        pairs = []
        current_q: str | None = None
        current_a: str | None = None

        q_re = re.compile(r"^(?:Q\d+|Question\s*\d+)\s*[:\.\-]\s*(.+)", re.IGNORECASE)
        a_re = re.compile(r"^(?:A\d+|Answer\s*\d+)\s*[:\.\-]\s*(.+)", re.IGNORECASE)

        for line in lines:
            q_match = q_re.match(line)
            a_match = a_re.match(line)

            if q_match:
                if current_q and current_a:
                    pairs.append((current_q, current_a))
                current_q = q_match.group(1).strip()
                current_a = None
            elif a_match and current_q is not None:
                current_a = a_match.group(1).strip()

        if current_q and current_a:
            pairs.append((current_q, current_a))

        return pairs
