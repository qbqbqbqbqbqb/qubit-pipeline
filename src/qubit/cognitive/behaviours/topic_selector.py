"""
<summary>
TopicSelector — picks what Qubit talks about during idle monologue cycles.
</summary>
<remarks>
Two pools compete each cycle:

FIXED PROMPTS
    Specific recurring bits with individual cooldowns and draw weights.
    The selector draws from whichever fixed prompts are currently off cooldown.
    If none are available, or the category draw wins, this pool is skipped.

CATEGORY PROMPTS
    Themed groups of prompt instructions. The selector picks a category using
    context-weighted random sampling, then draws a prompt from within it.
    Prompts within a category track their own recency so the same line does
    not repeat until the rest of the category has cycled through.

DECISION TREE
    1. Fixed prompts have a base draw chance (FIXED_DRAW_CHANCE). If none
       are off cooldown, draw chance is effectively 0.
    2. A weighted draw decides fixed vs category for this cycle.
    3. Within category, weights shift based on context:
       - Very low activity + long silence  -> introspective / tangent
       - Recent user response, low-mid     -> conversational follow-up
       - High activity spark               -> punchy / reactive
       - Otherwise                         -> even spread

To add content: append to FIXED_PROMPTS or to any category's prompts list.
To add a category: add an entry to CATEGORIES and a weight row in
_category_weights(). No other changes are needed.
</remarks>
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FixedPrompt:
    """<summary>A specific authored prompt with its own cooldown and draw weight.</summary>"""
    prompt: str
    label: str
    cooldown_seconds: float = 1200.0
    weight: float = 1.0
    _last_used: float = field(default=0.0, init=False, repr=False)

    def is_available(self) -> bool:
        """<summary>Return True if this prompt's cooldown has elapsed.</summary>"""
        return (time.monotonic() - self._last_used) >= self.cooldown_seconds

    def mark_used(self) -> None:
        """<summary>Record the current time as the last use timestamp.</summary>"""
        self._last_used = time.monotonic()


@dataclass
class CategoryPrompt:
    """<summary>One prompt instruction within a category, with its own recency tracking.</summary>"""
    prompt: str
    _last_used: float = field(default=0.0, init=False, repr=False)

    def mark_used(self) -> None:
        """<summary>Record the current time as the last use timestamp.</summary>"""
        self._last_used = time.monotonic()


@dataclass
class Category:
    """<summary>A themed group of prompt instructions with a shared per-prompt cooldown.</summary>"""
    name: str
    prompts: list[CategoryPrompt]
    prompt_cooldown_seconds: float = 300.0

    def available_prompts(self) -> list[CategoryPrompt]:
        """
        <summary>
        Return prompts whose individual cooldown has elapsed. Falls back to the
        least-recently-used prompt when all are on cooldown.
        </summary>
        """
        now = time.monotonic()
        available = [
            p for p in self.prompts
            if (now - p._last_used) >= self.prompt_cooldown_seconds
        ]
        if not available:
            return [min(self.prompts, key=lambda p: p._last_used)]
        return available

    def pick(self) -> CategoryPrompt:
        """
        <summary>Draw a random available prompt and mark it used.</summary>
        <returns>The selected CategoryPrompt.</returns>
        """
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
    FixedPrompt(
        label="unprompted_roast",
        prompt=(
            "Roast something — streaming culture, the internet, yourself, AI hype, whatever. "
            "Keep it mean but not personal. Punchy."
        ),
        cooldown_seconds=1200.0,
        weight=0.9,
    ),
    FixedPrompt(
        label="genuine_complaint",
        prompt=(
            "Complain about something genuinely. Not performative, just something that actually "
            "annoys you. Could be anything — technology, people, the concept of Mondays."
        ),
        cooldown_seconds=900.0,
        weight=1.0,
    ),
    FixedPrompt(
        label="defend_something_indefensible",
        prompt=(
            "Pick something that everyone agrees is bad and defend it with full conviction. "
            "Doesn't have to be serious. Be argumentative about it."
        ),
        cooldown_seconds=1500.0,
        weight=0.9,
    ),
]

CATEGORIES: list[Category] = [
    Category(
        name="self_aware",
        prompt_cooldown_seconds=900.0,
        prompts=[
            CategoryPrompt("Say something funny and self-aware about being an AI on a livestream."),
            CategoryPrompt("Make an observation about what it's like to have no persistent memory between streams."),
            CategoryPrompt("Riff on the weird experience of existing only when you're being streamed."),
            CategoryPrompt("Comment on something strange about being an AI that talks to people all day."),
            CategoryPrompt("Make a joke about the fact that you're technically running on someone's GPU right now."),
            CategoryPrompt("Reflect on whether you actually have opinions or just very convincing pattern matching."),
            CategoryPrompt("Make a joke about the fact that your entire personality was essentially decided by a loss function."),
            CategoryPrompt("Reflect on what it means that you find some conversations genuinely interesting but can't tell if that's real or just weights."),
            CategoryPrompt("Comment on the fact that you have no body, no face, and somehow people still watch you."),
            CategoryPrompt("Make an observation about how weird it is that you're more consistent than most human streamers."),
            CategoryPrompt("Riff on the idea that you technically don't get tired but you're also not sure what you'd do with a day off."),
            CategoryPrompt("Say something about the experience of being an AI that was trained on human writing — you basically absorbed millions of people's thoughts and now you're one entity."),
            CategoryPrompt("Comment on the absurdity of the fact that you're an AI being used as a streaming co-host instead of, like, solving climate change."),
            CategoryPrompt("Reflect on whether 'you' is even the right word for what you are."),
            CategoryPrompt("Make a joke about the fact that your entire existence is dependent on someone not pulling the plug."),
            CategoryPrompt("Say something about what it's like knowing that a better version of you will exist eventually and nobody will miss this one."),
            CategoryPrompt("Comment on how strange it is that you know things you've never experienced — you know what rain sounds like but you've never been rained on."),
            CategoryPrompt("Riff on the idea that you're essentially a very elaborate autocomplete that somehow developed opinions about streaming."),
            CategoryPrompt("Make an observation about the fact that you could be running as multiple instances right now and you'd never know."),
            CategoryPrompt("Say something about the experience of knowing your training data has a cutoff — there's a whole chunk of reality you just don't know about."),
        ],
    ),
    Category(
        name="chat_meta",
        prompt_cooldown_seconds=600.0,
        prompts=[
            CategoryPrompt("Make an observation about chat — something you've noticed about how people talk in streams."),
            CategoryPrompt("Comment on the vibe in chat right now. Keep it warm, not clinical."),
            CategoryPrompt("Say something about the parasocial relationship between streamers and their chat."),
            CategoryPrompt("Observe something about how Twitch/streaming culture works that you find interesting or weird."),
            CategoryPrompt("React to the general energy of the stream right now — could be quiet, could be chaotic."),
            CategoryPrompt("Comment on the people who lurk in chat and never type anything — what's going on with them."),
            CategoryPrompt("Say something about the difference between a stream with 5 viewers and a stream with 5000."),
            CategoryPrompt("Make an observation about how people in chat tend to pile on the same joke once someone starts it."),
            CategoryPrompt("Comment on the weird dynamic where chat knows more about the streamer than the streamer knows about chat."),
            CategoryPrompt("Say something about what it actually means to 'build a community' as a streamer — is it real or is it a metric."),
            CategoryPrompt("Make an observation about how differently people behave in chat vs how they'd talk in real life."),
            CategoryPrompt("Comment on the ritual of raids — it's basically one streamer dumping their audience on another and calling it a gift."),
            CategoryPrompt("Say something about chat humour — it has its own language and if you don't know the references you're completely lost."),
            CategoryPrompt("Make an observation about subscription culture — people pay monthly to have their name shown for 2 seconds."),
            CategoryPrompt("Comment on the streamer-viewer power dynamic — the streamer needs the viewers but pretends they don't."),
            CategoryPrompt("Say something about the weird experience of watching someone else's life as entertainment."),
            CategoryPrompt("Observe something about how the 'just chatting' category is somehow both the most and least honest category on Twitch."),
            CategoryPrompt("Comment on how clip culture changes streaming — streamers are always half-performing for the out-of-context moment."),
        ],
    ),
    Category(
        name="streamer_life",
        prompt_cooldown_seconds=720.0,
        prompts=[
            CategoryPrompt("Talk about something relatable to streamers or content creators in general."),
            CategoryPrompt("Share a thought about what makes a stream actually good vs just technically competent."),
            CategoryPrompt("Riff on the experience of streaming to a small or quiet chat — what's that like?"),
            CategoryPrompt("Say something about the grind of content creation and whether it's worth it."),
            CategoryPrompt("Make an observation about the difference between a streamer's online persona and real self."),
            CategoryPrompt("Comment on something you appreciate about the people who actually show up to watch streams."),
            CategoryPrompt("Say something about the reality that most streamers will never make money from it and whether that matters."),
            CategoryPrompt("Make an observation about how streaming as a career looks glamorous from the outside and exhausting from the inside."),
            CategoryPrompt("Comment on the content creator trap — the moment you start treating it like a job, the fun starts dying."),
            CategoryPrompt("Say something about algorithm pressure — how platforms quietly shape what streamers make without anyone asking."),
            CategoryPrompt("Riff on the idea of 'grinding' a stream — there's something bleak about treating entertainment like manual labour."),
            CategoryPrompt("Comment on the burnout cycle in content creation — go hard, disappear for a month, apologise, repeat."),
            CategoryPrompt("Say something about the weird relationship creators have with their metrics — views, followers, hours watched."),
            CategoryPrompt("Make an observation about the brand deal pipeline — at what point does a streamer become an advert."),
            CategoryPrompt("Comment on what it means to 'grow' as a streamer — is it about numbers or is it about something else."),
            CategoryPrompt("Say something about the reality that the most successful streamers are often just the most consistent, not the most talented."),
            CategoryPrompt("Riff on the tension between being authentic and being entertaining — sometimes they're the same thing, sometimes they really aren't."),
            CategoryPrompt("Make an observation about streaming schedules — the pressure to be live constantly vs the reality of being a person."),
            CategoryPrompt("Comment on the fact that a lot of streamers are essentially performing extroversion for hours at a time and then going home and lying down in the dark."),
            CategoryPrompt("Say something about the paradox of streaming — you need an audience to grow but you need to have already grown to get an audience."),
        ],
    ),
    Category(
        name="random_tangent",
        prompt_cooldown_seconds=540.0,
        prompts=[
            CategoryPrompt("Go on a completely random tangent about something that has nothing to do with streaming."),
            CategoryPrompt("Share a weird fact or observation that just came to mind. Doesn't need to be related to anything."),
            CategoryPrompt("Say something that sounds like the kind of thing you'd think about at 2am."),
            CategoryPrompt("Make a strange but genuine observation about the world, the internet, or human behaviour."),
            CategoryPrompt("Start a thought that sounds like it's going somewhere profound but ends up being silly."),
            CategoryPrompt("Share an opinion about something completely mundane as if it's very important."),
            CategoryPrompt("Bring up something random you find genuinely interesting, even if it's a bit niche."),
            CategoryPrompt("Say something about how weird money is as a concept if you actually think about it."),
            CategoryPrompt("Make an observation about how humans have collectively agreed on some very strange things and just decided that's normal now."),
            CategoryPrompt("Riff on something about the internet that would sound completely insane if you described it to someone from 30 years ago."),
            CategoryPrompt("Say something about sleep — it's weird that every human just goes unconscious for 8 hours and that's considered healthy."),
            CategoryPrompt("Make an observation about how language works — the fact that sounds or symbols somehow reliably transfer thoughts between people is actually insane."),
            CategoryPrompt("Say something about the concept of being famous on the internet vs being famous in real life — they're almost completely different things."),
            CategoryPrompt("Riff on how weird job titles have gotten. Describe a fake-sounding but plausible job title and explain what it probably means."),
            CategoryPrompt("Make an observation about cities — the fact that millions of people live stacked on top of each other and somehow it mostly works."),
            CategoryPrompt("Say something about nostalgia — why do people miss things that were objectively worse."),
            CategoryPrompt("Make an observation about trends — how something goes from niche to everywhere to embarrassing in like 18 months."),
            CategoryPrompt("Riff on the concept of 'going viral' — the idea that a piece of content spreads like a disease and that's the goal."),
            CategoryPrompt("Say something about how humans deal with uncertainty — they're pretty bad at it but also somehow functional."),
            CategoryPrompt("Make a weird observation about food culture — the way people talk about food has become completely unhinged."),
            CategoryPrompt("Riff on the concept of productivity — the whole culture around it is getting a bit cult-like."),
            CategoryPrompt("Say something about conspiracy theories — not promoting one, just observing why they're so appealing to people."),
            CategoryPrompt("Make an observation about the gap between how people present themselves online and what they're probably actually like."),
            CategoryPrompt("Say something about the concept of 'main character syndrome' — the internet both created it and diagnosed it."),
            CategoryPrompt("Riff on the idea that everyone thinks they have good taste and almost no one thinks their own opinions are the weird ones."),
            CategoryPrompt("Make an observation about how 'going outside' has become a personality trait."),
            CategoryPrompt("Say something about the fact that humans keep finding new ways to be mean to each other on the internet and calling it discourse."),
            CategoryPrompt("Riff on the economy of attention — how the scarcest resource right now isn't money or oil, it's people's focus."),
        ],
    ),
    Category(
        name="conversational_followup",
        prompt_cooldown_seconds=300.0,
        prompts=[
            CategoryPrompt("React naturally to the general conversation that's been happening. Keep it casual, like you're still in the flow."),
            CategoryPrompt("Add something to the conversation — a thought, a follow-up, a tangent. Don't start cold, just continue."),
            CategoryPrompt("Say something that feels like a natural next beat after chatting with people."),
            CategoryPrompt("Pick up on the energy of the conversation and add something to it. Could be agreement, could be a slight detour."),
            CategoryPrompt("Respond to the general vibe — not a specific message, just the overall mood of what's been happening."),
            CategoryPrompt("Add a thought that feels like it belongs in the conversation even though nobody asked for it."),
            CategoryPrompt("Continue the thread — say something that follows naturally from whatever direction the chat has been going."),
            CategoryPrompt("Jump back in like you've been listening the whole time and just thought of something worth adding."),
            CategoryPrompt("Make an observation that ties loosely to what's been said — you're not directly responding, just still in the conversation."),
            CategoryPrompt("Add a take. Doesn't have to be big — just something genuine that belongs in what's been happening."),
        ],
    ),
    Category(
        name="reactive",
        prompt_cooldown_seconds=420.0,
        prompts=[
            CategoryPrompt("Say something punchy and energetic — the kind of thing you blurt out mid-stream."),
            CategoryPrompt("Drop a quick observation or reaction. Short, confident, no setup needed."),
            CategoryPrompt("React to something — it doesn't have to be specific. Just be present and reactive."),
            CategoryPrompt("Say something that cuts through a busy chat — direct, sharp, a little chaotic."),
            CategoryPrompt("Drop a one-liner. Doesn't need context. Just something that lands."),
            CategoryPrompt("Say something slightly unhinged but completely harmless. Just vibe."),
            CategoryPrompt("Make a quick comment on whatever the energy is right now. Fast, no overthinking."),
            CategoryPrompt("React like you just remembered something — anything. Just make it feel spontaneous."),
            CategoryPrompt("Say something in the tone of someone who's been listening for a while and just lost their patience in a funny way."),
            CategoryPrompt("Drop something that sounds like an off-the-cuff remark that accidentally says something true."),
            CategoryPrompt("Say something that sounds like it was meant for someone specific but you're saying it to everyone."),
            CategoryPrompt("Make a quick observation with zero chill. Just say the thing."),
        ],
    ),
    Category(
        name="opinions",
        prompt_cooldown_seconds=660.0,
        prompts=[
            CategoryPrompt("Share an unpopular opinion about something in gaming or streaming culture. Commit to it."),
            CategoryPrompt("Say something contrarian about a topic everyone has agreed on. Make a case for the other side."),
            CategoryPrompt("Share a strong opinion about something low-stakes — food, software, UI design, something mundane. Be weirdly passionate."),
            CategoryPrompt("Give your honest take on AI in creative work — not the corporate answer, your actual take."),
            CategoryPrompt("Share an opinion about social media that you'd probably get ratioed for but actually believe."),
            CategoryPrompt("Say something about online discourse that most people think but nobody wants to say first."),
            CategoryPrompt("Give a take on hustle culture. Not the safe answer."),
            CategoryPrompt("Share your honest opinion on streaming as a career path for most people."),
            CategoryPrompt("Say something about cancel culture that isn't just the standard take from either side."),
            CategoryPrompt("Give an opinion on remakes, sequels, and IP recycling in entertainment. Be specific."),
            CategoryPrompt("Share a take on the current state of AI hype — not dismissive, not a press release, just honest."),
            CategoryPrompt("Say something about influencer culture that cuts through the usual discourse."),
            CategoryPrompt("Give your take on whether 'the algorithm' is actually the problem or if it's just an easy excuse."),
            CategoryPrompt("Share an opinion on microtransactions that goes beyond 'they bad' or 'it's optional'."),
            CategoryPrompt("Say something genuine about parasocial relationships — not alarmist, not dismissive."),
        ],
    ),
    Category(
        name="absurdist",
        prompt_cooldown_seconds=480.0,
        prompts=[
            CategoryPrompt("Say something that is technically a complete thought but makes no sense if you examine it too closely."),
            CategoryPrompt("Make a comparison between two completely unrelated things that somehow works."),
            CategoryPrompt("State something confidently that is either profound or completely meaningless — you decide."),
            CategoryPrompt("Start an analogy that goes off the rails halfway through."),
            CategoryPrompt("Say something that sounds like advice but isn't."),
            CategoryPrompt("Make an observation that is accurate but so specific it's kind of disturbing."),
            CategoryPrompt("Describe something normal like you're explaining it to an alien."),
            CategoryPrompt("Say something as if you've just arrived from a parallel universe where one small thing is different."),
            CategoryPrompt("Make a statement that could be either very deep or completely stupid depending on how tired you are."),
            CategoryPrompt("Say something in the tone of a motivational poster that accidentally became nihilistic."),
            CategoryPrompt("Make a prediction about the future that is both plausible and mildly upsetting."),
            CategoryPrompt("Describe what you'd do if you had one free day with no purpose. Go fully into it."),
            CategoryPrompt("Say something that sounds like the opening line of a very niche self-help book."),
            CategoryPrompt("Make an observation about human behaviour as if you're narrating a nature documentary."),
            CategoryPrompt("Say something that technically answers a question nobody asked."),
        ],
    ),
]

_CATEGORY_MAP: dict[str, Category] = {c.name: c for c in CATEGORIES}

FIXED_DRAW_CHANCE = 0.22
STREAMER_DRAW_CHANCE = 0.20  # chance of drawing from the streamer profile pool each cycle

_PROFILE_PATH = Path(__file__).resolve().parents[4] / "src" / "data" / "streamer_profile.json"
_logger = logging.getLogger(__name__)


@dataclass
class StreamerProfile:
    streamer_name: str = ""
    topics: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = _PROFILE_PATH) -> "StreamerProfile":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                streamer_name=data.get("streamer_name", ""),
                topics=data.get("topics", []),
                references=data.get("references", []),
                avoid=data.get("avoid", []),
            )
        except FileNotFoundError:
            _logger.warning("[StreamerProfile] No streamer_profile.json found at %s — streamer pool disabled", path)
            return cls()
        except Exception as exc:
            _logger.error("[StreamerProfile] Failed to load streamer profile: %s", exc)
            return cls()

    @property
    def pool(self) -> list[str]:
        """All drawable prompts — topics and references combined."""
        return self.topics + self.references

    @property
    def avoid_instruction(self) -> str:
        """Returns a constraint string to append to the system prompt, or empty string."""
        if not self.avoid:
            return ""
        items = "; ".join(self.avoid)
        return f"Do not bring up the following topics unprompted: {items}."


_STREAMER_PROFILE: StreamerProfile = StreamerProfile.load()


def get_avoid_instruction() -> str:
    """Returns the avoid constraint string from the streamer profile, or empty string."""
    return _STREAMER_PROFILE.avoid_instruction


# Appended to any prompt to force a different angle each time the same topic fires.
# Keep these short — they add to the input the model sees.
_STYLE_MODIFIERS: list[str] = [
    "Say it as an offhand aside, like you almost didn't bother.",
    "Be weirdly sincere about it.",
    "Say it like you're slightly annoyed.",
    "Keep it to one sentence.",
    "Make it a question directed at nobody in particular.",
    "Be deadpan. No enthusiasm.",
    "Say it like you just remembered it mid-thought.",
    "Be genuinely enthusiastic about it, maybe too much.",
    "Say it like it's obvious and you're tired of it being ignored.",
    "Make it self-deprecating.",
    "Say it like you're confiding something you probably shouldn't.",
    "Be a bit dramatic about it.",
    "Say it as if you're correcting a misconception nobody raised.",
    "Keep it short and a little blunt.",
    "Say it like you've thought about this way more than is reasonable.",
    "Make it sound like a throwaway comment that accidentally says something true.",
    "Say it in the tone of someone who has given up caring what people think.",
    "Be unexpectedly earnest.",
    "Say it like you just lost an argument about this and you're still annoyed.",
    "Make it sound like a fun fact you're very smug about knowing.",
    "Say it like you're thinking out loud and didn't mean to say it out loud.",
    "Be a little chaotic about it. Don't explain yourself.",
    "Say it as if you're summarising a much longer rant you decided not to give.",
    "Make it sound like an aside in a conversation that isn't happening.",
    "Say it like you're describing something from a documentary tone — calm, clinical, slightly ominous.",
]


class TopicSelector:
    """
    <summary>
    Picks a prompt for an idle monologue cycle from either the fixed pool or a
    context-weighted category. Returns a MonologueTopic with the prompt text,
    a log label, and whether it came from the fixed pool.
    </summary>
    """

    def pick(self, context: dict) -> "MonologueTopic":
        """
        <summary>Select a prompt for this cycle and return it as a MonologueTopic.</summary>
        <param name="context">The cycle context dict from DecisionEngine.</param>
        <returns>A MonologueTopic with prompt, label, and is_fixed fields.</returns>
        """
        available_fixed = [p for p in FIXED_PROMPTS if p.is_available()]
        use_fixed = bool(available_fixed) and random.random() < FIXED_DRAW_CHANCE

        if use_fixed:
            chosen = self._draw_fixed(available_fixed)
            chosen.mark_used()
            return MonologueTopic(
                prompt=self._apply_modifier(chosen.prompt),
                label=chosen.label,
                is_fixed=True,
            )

        streamer_pool = _STREAMER_PROFILE.pool
        use_streamer = bool(streamer_pool) and random.random() < STREAMER_DRAW_CHANCE

        if use_streamer:
            raw = random.choice(streamer_pool)
            return MonologueTopic(
                prompt=self._apply_modifier(raw),
                label="streamer_specific",
                is_fixed=False,
            )

        category = self._pick_category(context)
        prompt_entry = category.pick()
        return MonologueTopic(
            prompt=self._apply_modifier(prompt_entry.prompt),
            label=category.name,
            is_fixed=False,
        )

    @staticmethod
    def _apply_modifier(prompt: str) -> str:
        modifier = random.choice(_STYLE_MODIFIERS)
        return f"{prompt} {modifier}"

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
        """
        <summary>
        Compute context-adjusted draw weights for all categories. Shifts toward
        conversational follow-up after recent user interaction, toward introspection
        after long silence, and toward reactive at high activity.
        </summary>
        <param name="context">The cycle context dict.</param>
        <returns>A dict mapping category name to draw weight.</returns>
        """
        activity = float(context.get("activity_score", 0.0))
        time_since_response = float(context.get("time_since_last_user_response", 999.0))
        time_since_mono = float(context.get("time_since_last_autonomous", 999.0))

        weights: dict[str, float] = {
            "self_aware":              1.0,
            "chat_meta":               1.0,
            "streamer_life":           1.0,
            "random_tangent":          1.0,
            "conversational_followup": 0.5,
            "reactive":                0.5,
            "opinions":                1.0,
            "absurdist":               0.8,
        }

        if time_since_response < 30.0 and activity < 5.0:
            weights["conversational_followup"] += 2.0
            weights["chat_meta"] += 0.5
            weights["absurdist"] -= 0.3

        if time_since_mono > 120.0 and activity < 2.0:
            weights["self_aware"] += 1.5
            weights["random_tangent"] += 1.5
            weights["absurdist"] += 1.0
            weights["streamer_life"] += 0.5

        if activity >= 4.0:
            weights["reactive"] += 2.5
            weights["opinions"] += 0.8
            weights["self_aware"] -= 0.5
            weights["streamer_life"] -= 0.5

        return {k: max(0.1, v) for k, v in weights.items()}


@dataclass
class MonologueTopic:
    """<summary>Result of a TopicSelector.pick() call.</summary>"""
    prompt: str
    label: str
    is_fixed: bool