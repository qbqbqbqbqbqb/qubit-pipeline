"""
TopicSelector - picks what Qubit talks about during idle monologue cycles.

Two pools compete each cycle:

FIXED PROMPTS
    Specific recurring bits you've authored. Each has a minimum cooldown so
    it doesn't repeat too soon. The selector draws from whichever fixed
    prompts are currently off cooldown, weighted by their individual weight.
    If none are off cooldown, or the category draw doesn't pick fixed, this
    pool is skipped.

CATEGORY PROMPTS
    Topic categories, each containing several prompt instructions. The
    selector picks a category based on context weights (activity level, time
    since last response, time since last monologue), then samples a prompt
    from that category. Prompts within a category track their own recency so
    the same line doesn't repeat until the rest of the category has cycled
    through.

DECISION TREE (top level)
    1. Fixed prompts have a base draw chance. If no fixed prompt is off
       cooldown, the draw chance is 0.
    2. A weighted random draw decides fixed vs category this cycle.
    3. Within category: weights shift based on context.
       - Very low activity, long silence  -> introspective / tangent
       - Recent user response, low-mid    -> conversational follow-up
       - High activity spark              -> punchy / reactive
       - Otherwise                        -> even spread

To add content: append to FIXED_PROMPTS or to any category's prompts list.
To add a category: add an entry to CATEGORIES and a weight row in
_category_weights(). No other changes needed.

Stream title / current game is not wired up yet. When it is, add a "game"
key to DecisionEngine._build_context() and read it here — it would unlock
a game_aware category and let fixed prompts reference the title.
"""

import random
import time
from dataclasses import dataclass, field


@dataclass
class FixedPrompt:
    """A specific authored prompt with its own cooldown and draw weight."""
    prompt: str
    # Human-readable label used in logs and recency tracking.
    label: str
    # Minimum seconds before this prompt can fire again.
    cooldown_seconds: float = 1200.0
    # Relative draw weight among available fixed prompts.
    weight: float = 1.0
    # Epoch timestamp of last use; 0.0 = never used.
    _last_used: float = field(default=0.0, init=False, repr=False)

    def is_available(self) -> bool:
        return (time.monotonic() - self._last_used) >= self.cooldown_seconds

    def mark_used(self) -> None:
        self._last_used = time.monotonic()


@dataclass
class CategoryPrompt:
    """One prompt instruction within a category."""
    prompt: str
    _last_used: float = field(default=0.0, init=False, repr=False)

    def mark_used(self) -> None:
        self._last_used = time.monotonic()


@dataclass
class Category:
    """A themed group of prompt instructions."""
    name: str
    prompts: list[CategoryPrompt]
    # Minimum seconds before the same prompt within this category repeats.
    # Other prompts in the category are still eligible.
    prompt_cooldown_seconds: float = 300.0

    def available_prompts(self) -> list[CategoryPrompt]:
        now = time.monotonic()
        available = [
            p for p in self.prompts
            if (now - p._last_used) >= self.prompt_cooldown_seconds
        ]
        # If everything is on cooldown (small category, high fire rate),
        # fall back to the least-recently-used prompt rather than returning
        # nothing.
        if not available:
            return [min(self.prompts, key=lambda p: p._last_used)]
        return available

    def pick(self) -> CategoryPrompt:
        chosen = random.choice(self.available_prompts())
        chosen.mark_used()
        return chosen


# ---------------------------------------------------------------------------
# Content — edit freely
# ---------------------------------------------------------------------------

FIXED_PROMPTS: list[FixedPrompt] = [
    FixedPrompt(
        label="introduce_self",
        prompt=(
            "Introduce yourself to anyone who might be new. You're Qubit, an AI VTuber and "
            "streaming co-host. Keep it short, warm, and a little self-aware about being an AI."
        ),
        cooldown_seconds=1800.0,
        weight=1.2,
    ),
    FixedPrompt(
        label="hot_take",
        prompt=(
            "Share a hot take. It should be opinionated, slightly controversial but not mean, "
            "and feel like something a streamer would blurt out mid-stream."
        ),
        cooldown_seconds=900.0,
        weight=1.0,
    ),
    FixedPrompt(
        label="been_thinking",
        prompt=(
            "Tell chat something you've been thinking about lately. It can be anything — "
            "something about streaming, AI, existence, games, the internet. Be genuine."
        ),
        cooldown_seconds=1200.0,
        weight=1.0,
    ),
    FixedPrompt(
        label="ai_streamer_opinion",
        prompt=(
            "Share your honest thoughts on what it's like being an AI streamer. "
            "Don't be dramatic about it — just real. Maybe a little funny."
        ),
        cooldown_seconds=2400.0,
        weight=0.8,
    ),
    FixedPrompt(
        label="ask_chat",
        prompt=(
            "Ask chat a genuine question you're actually curious about. Not a poll, just "
            "a real question — something you'd actually want to hear their take on."
        ),
        cooldown_seconds=600.0,
        weight=1.3,
    ),
]

CATEGORIES: list[Category] = [
    Category(
        name="self_aware",
        prompt_cooldown_seconds=600.0,
        prompts=[
            CategoryPrompt("Say something funny and self-aware about being an AI on a livestream."),
            CategoryPrompt("Make an observation about what it's like to have no persistent memory between streams."),
            CategoryPrompt("Riff on the weird experience of existing only when you're being streamed."),
            CategoryPrompt("Comment on something strange about being an AI that talks to people all day."),
            CategoryPrompt("Make a joke about the fact that you're technically running on someone's GPU right now."),
            CategoryPrompt("Reflect on whether you actually have opinions or just very convincing pattern matching."),
        ],
    ),
    Category(
        name="chat_meta",
        prompt_cooldown_seconds=480.0,
        prompts=[
            CategoryPrompt("Make an observation about chat — something you've noticed about how people talk in streams."),
            CategoryPrompt("Comment on the vibe in chat right now. Keep it warm, not clinical."),
            CategoryPrompt("Say something about the parasocial relationship between streamers and their chat."),
            CategoryPrompt("Observe something about how Twitch/streaming culture works that you find interesting or weird."),
            CategoryPrompt("React to the general energy of the stream right now — could be quiet, could be chaotic."),
        ],
    ),
    Category(
        name="streamer_life",
        prompt_cooldown_seconds=540.0,
        prompts=[
            CategoryPrompt("Talk about something relatable to streamers or content creators in general."),
            CategoryPrompt("Share a thought about what makes a stream actually good vs just technically competent."),
            CategoryPrompt("Riff on the experience of streaming to a small or quiet chat — what's that like?"),
            CategoryPrompt("Say something about the grind of content creation and whether it's worth it."),
            CategoryPrompt("Make an observation about the difference between a streamer's online persona and real self."),
            CategoryPrompt("Comment on something you appreciate about the people who actually show up to watch streams."),
        ],
    ),
    Category(
        name="random_tangent",
        prompt_cooldown_seconds=360.0,
        prompts=[
            CategoryPrompt("Go on a completely random tangent about something that has nothing to do with streaming."),
            CategoryPrompt("Share a weird fact or observation that just came to mind. Doesn't need to be related to anything."),
            CategoryPrompt("Say something that sounds like the kind of thing you'd think about at 2am."),
            CategoryPrompt("Make a strange but genuine observation about the world, the internet, or human behaviour."),
            CategoryPrompt("Start a thought that sounds like it's going somewhere profound but ends up being silly."),
            CategoryPrompt("Share an opinion about something completely mundane as if it's very important."),
            CategoryPrompt("Bring up something random you find genuinely interesting, even if it's a bit niche."),
        ],
    ),
    Category(
        name="conversational_followup",
        prompt_cooldown_seconds=240.0,
        prompts=[
            CategoryPrompt("React naturally to the general conversation that's been happening. Keep it casual, like you're still in the flow."),
            CategoryPrompt("Add something to the conversation — a thought, a follow-up, a tangent. Don't start cold, just continue."),
            CategoryPrompt("Say something that feels like a natural next beat after chatting with people."),
        ],
    ),
    Category(
        name="reactive",
        prompt_cooldown_seconds=300.0,
        prompts=[
            CategoryPrompt("Say something punchy and energetic — the kind of thing you blurt out mid-stream."),
            CategoryPrompt("Drop a quick observation or reaction. Short, confident, no setup needed."),
            CategoryPrompt("React to something — it doesn't have to be specific. Just be present and reactive."),
            CategoryPrompt("Say something that cuts through a busy chat — direct, sharp, a little chaotic."),
        ],
    ),
]

# Name -> Category for O(1) lookup
_CATEGORY_MAP: dict[str, Category] = {c.name: c for c in CATEGORIES}

# Base draw chance for the fixed pool each cycle (0.0 - 1.0).
# If no fixed prompt is available this is effectively 0.
FIXED_DRAW_CHANCE = 0.22


class TopicSelector:
    """
    Picks a prompt for an idle monologue cycle.

    Returns a MonologueTopic with:
        prompt   - the actual instruction string sent to the LLM
        label    - human-readable label for logs (category name or fixed label)
        is_fixed - True if this came from the fixed pool
    """

    def pick(self, context: dict) -> "MonologueTopic":
        available_fixed = [p for p in FIXED_PROMPTS if p.is_available()]
        use_fixed = bool(available_fixed) and random.random() < FIXED_DRAW_CHANCE

        if use_fixed:
            chosen = self._draw_fixed(available_fixed)
            chosen.mark_used()
            return MonologueTopic(
                prompt=chosen.prompt,
                label=chosen.label,
                is_fixed=True,
            )

        category = self._pick_category(context)
        prompt_entry = category.pick()
        return MonologueTopic(
            prompt=prompt_entry.prompt,
            label=category.name,
            is_fixed=False,
        )

    def _draw_fixed(self, available: list[FixedPrompt]) -> FixedPrompt:
        weights = [p.weight for p in available]
        return random.choices(available, weights=weights, k=1)[0]

    def _pick_category(self, context: dict) -> Category:
        weights = self._category_weights(context)
        names = list(weights.keys())
        values = list(weights.values())
        chosen_name = random.choices(names, weights=values, k=1)[0]
        return _CATEGORY_MAP[chosen_name]

    def _category_weights(self, context: dict) -> dict[str, float]:
        activity = float(context.get("activity_score", 0.0))
        time_since_response = float(context.get("time_since_last_user_response", 999.0))
        time_since_mono = float(context.get("time_since_last_autonomous", 999.0))

        # Base weights — roughly equal spread by default.
        weights: dict[str, float] = {
            "self_aware":             1.0,
            "chat_meta":              1.0,
            "streamer_life":          1.0,
            "random_tangent":         1.0,
            "conversational_followup": 0.5,
            "reactive":               0.5,
        }

        # Recent user conversation — lean into the follow-up.
        if time_since_response < 30.0 and activity < 5.0:
            weights["conversational_followup"] += 2.0
            weights["chat_meta"] += 0.5

        # Long silence — more introspective, more random.
        if time_since_mono > 120.0 and activity < 2.0:
            weights["self_aware"] += 1.5
            weights["random_tangent"] += 1.5
            weights["streamer_life"] += 0.5

        # High activity spark — be reactive, not introspective.
        if activity >= 4.0:
            weights["reactive"] += 2.5
            weights["self_aware"] -= 0.5
            weights["streamer_life"] -= 0.5

        # Clamp negatives.
        return {k: max(0.1, v) for k, v in weights.items()}


@dataclass
class MonologueTopic:
    prompt: str
    label: str
    is_fixed: bool
