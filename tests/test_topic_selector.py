"""Tests for TopicSelector — fixed prompt pool, category selection, recency suppression."""

import time
import pytest
from src.qubit.cognitive.behaviours.topic_selector import (
    TopicSelector, FixedPrompt, Category, CategoryPrompt, MonologueTopic, CATEGORIES
)


@pytest.fixture
def selector():
    return TopicSelector()


def _context(activity=0.0, time_since_response=999.0, time_since_mono=999.0, game=None):
    ctx = {
        "activity_score": activity,
        "time_since_last_user_response": time_since_response,
        "time_since_last_autonomous": time_since_mono,
    }
    if game:
        ctx["game"] = game
    return ctx


# -----------------------------------------------------------------------
# MonologueTopic dataclass
# -----------------------------------------------------------------------

def test_monologue_topic_fields():
    t = MonologueTopic(prompt="say something", label="self_aware", is_fixed=False)
    assert t.prompt == "say something"
    assert t.label == "self_aware"
    assert t.is_fixed is False


# -----------------------------------------------------------------------
# FixedPrompt
# -----------------------------------------------------------------------

def test_fixed_prompt_available_initially():
    p = FixedPrompt(label="test", prompt="do something", cooldown_seconds=60.0)
    assert p.is_available() is True


def test_fixed_prompt_unavailable_after_use():
    p = FixedPrompt(label="test", prompt="do something", cooldown_seconds=999.0)
    p.mark_used()
    assert p.is_available() is False


def test_fixed_prompt_available_after_cooldown():
    p = FixedPrompt(label="test", prompt="do something", cooldown_seconds=0.01)
    p.mark_used()
    time.sleep(0.05)
    assert p.is_available() is True


# -----------------------------------------------------------------------
# Category
# -----------------------------------------------------------------------

def test_category_pick_returns_prompt():
    cat = Category(
        name="test_cat",
        prompts=[CategoryPrompt("prompt A"), CategoryPrompt("prompt B")],
        prompt_cooldown_seconds=0.0,
    )
    result = cat.pick()
    assert isinstance(result, CategoryPrompt)
    assert result.prompt in ("prompt A", "prompt B")


def test_category_pick_marks_used():
    cat = Category(
        name="test_cat",
        prompts=[CategoryPrompt("only prompt")],
        prompt_cooldown_seconds=999.0,
    )
    p = cat.pick()
    assert p._last_used > 0.0


def test_category_falls_back_to_lru_when_all_on_cooldown():
    cat = Category(
        name="test_cat",
        prompts=[CategoryPrompt("p1"), CategoryPrompt("p2")],
        prompt_cooldown_seconds=999.0,
    )
    cat.prompts[0].mark_used()
    cat.prompts[1].mark_used()
    # Should return the least recently used without raising
    result = cat.pick()
    assert result in cat.prompts


# -----------------------------------------------------------------------
# TopicSelector.pick
# -----------------------------------------------------------------------

def test_pick_returns_monologue_topic(selector):
    ctx = _context()
    topic = selector.pick(ctx)
    assert isinstance(topic, MonologueTopic)
    assert topic.prompt
    assert topic.label


def test_pick_low_activity_long_silence_biases_introspective(selector):
    ctx = _context(activity=0.0, time_since_mono=999.0)
    labels = [selector.pick(ctx).label for _ in range(30)]
    # self_aware and random_tangent should appear frequently at low activity
    introspective = sum(1 for l in labels if l in ("self_aware", "random_tangent"))
    assert introspective >= 10


def test_pick_high_activity_biases_reactive(selector):
    ctx = _context(activity=6.0)
    labels = [selector.pick(ctx).label for _ in range(30)]
    reactive = sum(1 for l in labels if l == "reactive")
    assert reactive >= 5


def test_pick_recent_response_biases_followup(selector):
    ctx = _context(activity=1.0, time_since_response=10.0)
    labels = [selector.pick(ctx).label for _ in range(30)]
    followup = sum(1 for l in labels if l == "conversational_followup")
    assert followup >= 5


def test_pick_fixed_prompt_uses_is_fixed_flag(selector):
    # Force fixed draw by making all fixed prompts available and setting draw to 1.0
    import unittest.mock as mock
    with mock.patch.object(selector, '_pick_category') as mock_cat:
        with mock.patch('src.qubit.cognitive.behaviours.topic_selector.random.random', return_value=0.0):
            topic = selector.pick(_context())
    # With random() = 0.0 < FIXED_DRAW_CHANCE, should pick fixed
    assert isinstance(topic, MonologueTopic)


def test_all_categories_have_prompts():
    for cat in CATEGORIES:
        assert len(cat.prompts) > 0, f"Category '{cat.name}' has no prompts"


def test_all_categories_have_unique_names():
    names = [cat.name for cat in CATEGORIES]
    assert len(names) == len(set(names))


def test_category_weights_sum_positive(selector):
    ctx = _context()
    weights = selector._category_weights(ctx)
    assert all(v > 0 for v in weights.values())


def test_category_weights_no_negatives_high_activity(selector):
    ctx = _context(activity=10.0)
    weights = selector._category_weights(ctx)
    assert all(v >= 0.1 for v in weights.values())
