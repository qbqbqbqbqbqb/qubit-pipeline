"""
Prompt injection module for randomised response length instructions.

Draws a length instruction each generation from a weighted pool, biased
by source type so the instruction fits the context:

  stt_filtered      — streamer talking directly, bias toward short
  monologue_prompt  — filling dead air, bias toward longer
  chat / community  — default conversational weights

This runs at the prompt level rather than trimming output post-generation,
so the model produces the right amount rather than having thoughts cut off.
"""

import random
from src.qubit.prompting.injections import PromptInjection


# (instruction, weight) — weights are relative, not percentages
_DEFAULT = [
    ("One sentence. Be direct.",                                          0.30),
    ("Keep it to two sentences.",                                         0.35),
    ("Two to three sentences, you can elaborate a bit.",                  0.25),
    ("Take your time with this one — three to four sentences is fine.",   0.10),
]

_STT = [
    ("One sentence. Be direct.",                                          0.50),
    ("Keep it to two sentences.",                                         0.35),
    ("Two to three sentences, you can elaborate a bit.",                  0.13),
    ("Take your time with this one — three to four sentences is fine.",   0.02),
]

_MONOLOGUE = [
    ("One sentence. Be direct.",                                          0.10),
    ("Keep it to two sentences.",                                         0.25),
    ("Two to three sentences, you can elaborate a bit.",                  0.40),
    ("Take your time with this one — three to four sentences is fine.",   0.25),
]


def _draw(pool: list[tuple[str, float]]) -> str:
    instructions, weights = zip(*pool)
    return random.choices(instructions, weights=weights, k=1)[0]


def length_module(event_type: str | None = None, source: str | None = None) -> PromptInjection:
    """
    Return a length instruction injection appropriate for the event source.

    Priority 35 — injected after vision context, just before the input message,
    so it's the last thing the model reads before generating.

    Parameters
    ----------
    event_type : str | None
        The event type string from the triggering event
        (e.g. "monologue_prompt", "response_prompt").
    source : str | None
        The platform source string
        (e.g. "stt_filtered", "twitch_chat_filtered").
    """
    if source == "stt_filtered":
        instruction = _draw(_STT)
    elif event_type == "monologue_prompt":
        instruction = _draw(_MONOLOGUE)
    else:
        instruction = _draw(_DEFAULT)

    return PromptInjection(
        content=instruction,
        priority=35,
    )