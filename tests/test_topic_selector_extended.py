"""Extended TopicSelector tests for session additions: new categories, streamer profile, style modifiers."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
from src.qubit.cognitive.behaviours.topic_selector import (
    TopicSelector, CATEGORIES, FIXED_PROMPTS, _STYLE_MODIFIERS,
    StreamerProfile, _apply_modifier_fn,
)


def _context(activity=0.0, time_since_response=999.0, time_since_mono=999.0):
    return {
        "activity_score": activity,
        "time_since_last_user_response": time_since_response,
        "time_since_last_autonomous": time_since_mono,
    }


# -----------------------------------------------------------------------
# New categories exist
# -----------------------------------------------------------------------

def test_opinions_category_exists():
    names = [c.name for c in CATEGORIES]
    assert "opinions" in names


def test_absurdist_category_exists():
    names = [c.name for c in CATEGORIES]
    assert "absurdist" in names


def test_opinions_has_sufficient_prompts():
    cat = next(c for c in CATEGORIES if c.name == "opinions")
    assert len(cat.prompts) >= 10


def test_absurdist_has_sufficient_prompts():
    cat = next(c for c in CATEGORIES if c.name == "absurdist")
    assert len(cat.prompts) >= 10


def test_all_categories_have_at_least_ten_prompts():
    for cat in CATEGORIES:
        assert len(cat.prompts) >= 10, f"Category '{cat.name}' has only {len(cat.prompts)} prompts"


# -----------------------------------------------------------------------
# Style modifiers
# -----------------------------------------------------------------------

def test_style_modifiers_pool_non_empty():
    assert len(_STYLE_MODIFIERS) >= 10


def test_apply_modifier_appends_to_prompt():
    result = _apply_modifier_fn("Base prompt.")
    assert result.startswith("Base prompt.")
    assert len(result) > len("Base prompt.")


def test_apply_modifier_varies_output():
    results = {_apply_modifier_fn("Base prompt.") for _ in range(50)}
    assert len(results) > 1  # should produce different modifiers


def test_pick_prompt_includes_modifier():
    selector = TopicSelector()
    topic = selector.pick(_context())
    # The prompt should be longer than any raw prompt (modifier appended)
    assert len(topic.prompt) > 20


# -----------------------------------------------------------------------
# Streamer profile
# -----------------------------------------------------------------------

def test_streamer_profile_load_missing_file_returns_empty():
    profile = StreamerProfile.load(Path("/nonexistent/path/profile.json"))
    assert profile.pool == []
    assert profile.avoid_instruction == ""


def test_streamer_profile_load_from_file(tmp_path):
    data = {
        "streamer_name": "TestStreamer",
        "topics": ["topic A", "topic B"],
        "references": ["reference C"],
        "avoid": ["avoid this"],
    }
    f = tmp_path / "profile.json"
    f.write_text(json.dumps(data))
    profile = StreamerProfile.load(f)
    assert len(profile.pool) == 3
    assert "topic A" in profile.pool
    assert "reference C" in profile.pool


def test_streamer_profile_avoid_instruction_empty_when_no_avoids():
    profile = StreamerProfile(avoid=[])
    assert profile.avoid_instruction == ""


def test_streamer_profile_avoid_instruction_contains_items():
    profile = StreamerProfile(avoid=["politics", "personal drama"])
    instruction = profile.avoid_instruction
    assert "politics" in instruction
    assert "personal drama" in instruction


def test_streamer_pool_draws_occur(tmp_path):
    data = {"topics": ["streamer topic"], "references": [], "avoid": []}
    f = tmp_path / "profile.json"
    f.write_text(json.dumps(data))
    profile = StreamerProfile.load(f)

    selector = TopicSelector()
    # Patch the global profile and force draw chance to 1.0
    with patch("src.qubit.cognitive.behaviours.topic_selector._STREAMER_PROFILE", profile):
        with patch("src.qubit.cognitive.behaviours.topic_selector.STREAMER_DRAW_CHANCE", 1.0):
            with patch("src.qubit.cognitive.behaviours.topic_selector.FIXED_DRAW_CHANCE", 0.0):
                topic = selector.pick(_context())
    assert topic.label == "streamer_specific"
    assert "streamer topic" in topic.prompt


def test_streamer_draw_skipped_when_pool_empty():
    selector = TopicSelector()
    with patch("src.qubit.cognitive.behaviours.topic_selector._STREAMER_PROFILE", StreamerProfile()):
        with patch("src.qubit.cognitive.behaviours.topic_selector.STREAMER_DRAW_CHANCE", 1.0):
            # Empty pool — should fall through to category pick
            topic = selector.pick(_context())
    assert topic.label != "streamer_specific"


# -----------------------------------------------------------------------
# Category weight guards — new categories must never go negative
# -----------------------------------------------------------------------

def test_category_weights_opinions_positive_at_all_activity_levels():
    selector = TopicSelector()
    for activity in [0.0, 2.0, 4.0, 6.0, 10.0]:
        weights = selector._category_weights(_context(activity=activity))
        assert weights.get("opinions", 0) > 0, f"opinions weight negative at activity={activity}"


def test_category_weights_absurdist_positive_at_all_activity_levels():
    selector = TopicSelector()
    for activity in [0.0, 2.0, 4.0, 6.0, 10.0]:
        weights = selector._category_weights(_context(activity=activity))
        assert weights.get("absurdist", 0) > 0, f"absurdist weight negative at activity={activity}"


def test_all_category_weights_in_weight_map(selector=None):
    s = TopicSelector()
    ctx = _context()
    weights = s._category_weights(ctx)
    for cat in CATEGORIES:
        assert cat.name in weights, f"Category '{cat.name}' missing from weight map"