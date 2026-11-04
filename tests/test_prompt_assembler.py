"""
Tests for PromptAssembler and PromptInjection.

PromptAssembler is pure logic with no I/O or heavy imports. No stubs needed.

Coverage:
  - add() / build() ordering by priority
  - build_parts() split at USER_INPUT_PRIORITY boundary
  - Edge cases: empty assembler, single injection, duplicate priorities,
    empty content, negative priorities
  - Immutability: each assembler instance is independent
  - Module functions that feed real injections into it (personality, stream_type,
    input, length) are exercised for interface correctness
"""

import pytest

from src.qubit.prompting.injections import PromptInjection, USER_INPUT_PRIORITY
from src.qubit.prompting.prompt_assembler import PromptAssembler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def inj(content: str, priority: int = 0) -> PromptInjection:
    return PromptInjection(content=content, priority=priority)


def make_assembler(*injections: PromptInjection) -> PromptAssembler:
    a = PromptAssembler()
    for i in injections:
        a.add(i)
    return a


# ---------------------------------------------------------------------------
# PromptInjection dataclass
# ---------------------------------------------------------------------------

class TestPromptInjection:

    def test_default_priority_is_zero(self):
        i = PromptInjection(content="hello")
        assert i.priority == 0

    def test_stores_content_and_priority(self):
        i = PromptInjection(content="text", priority=50)
        assert i.content == "text"
        assert i.priority == 50

    def test_user_input_priority_constant_is_10(self):
        # Pin the boundary value so a change to injections.py fails loudly here
        # rather than silently shifting the system/user split.
        assert USER_INPUT_PRIORITY == 10

    def test_equality(self):
        assert PromptInjection("a", 5) == PromptInjection("a", 5)
        assert PromptInjection("a", 5) != PromptInjection("a", 6)
        assert PromptInjection("a", 5) != PromptInjection("b", 5)


# ---------------------------------------------------------------------------
# PromptAssembler.build()
# ---------------------------------------------------------------------------

class TestBuild:

    def test_empty_assembler_returns_empty_string(self):
        assert PromptAssembler().build() == ""

    def test_single_injection(self):
        a = make_assembler(inj("only", 10))
        assert a.build() == "only"

    def test_higher_priority_comes_first(self):
        a = make_assembler(inj("low", 10), inj("high", 90))
        assert a.build() == "high\n\nlow"

    def test_three_injections_ordered_by_priority(self):
        a = make_assembler(inj("C", 10), inj("A", 100), inj("B", 50))
        assert a.build() == "A\n\nB\n\nC"

    def test_add_order_does_not_affect_output_only_priority_does(self):
        a1 = make_assembler(inj("first", 20), inj("second", 80))
        a2 = make_assembler(inj("second", 80), inj("first", 20))
        assert a1.build() == a2.build() == "second\n\nfirst"

    def test_duplicate_priorities_stable_by_insertion_order(self):
        # Python's sort is stable — same-priority injections keep insertion order.
        a = make_assembler(inj("X", 50), inj("Y", 50), inj("Z", 50))
        result = a.build()
        assert result == "X\n\nY\n\nZ"

    def test_negative_priority_comes_last(self):
        a = make_assembler(inj("normal", 0), inj("below", -10))
        assert a.build() == "normal\n\nbelow"

    def test_empty_content_injection_still_appears(self):
        a = make_assembler(inj("before", 20), inj("", 10), inj("after", 5))
        assert a.build() == "before\n\n\n\nafter"

    def test_whitespace_content_preserved(self):
        a = make_assembler(inj("  spaces  ", 10))
        assert a.build() == "  spaces  "

    def test_separator_is_double_newline(self):
        a = make_assembler(inj("A", 2), inj("B", 1))
        assert "\n\n" in a.build()
        assert "\n\n\n" not in a.build()  # exactly two, not three


# ---------------------------------------------------------------------------
# PromptAssembler.build_parts()
# ---------------------------------------------------------------------------

class TestBuildParts:

    def test_empty_assembler_returns_two_empty_strings(self):
        system, user = PromptAssembler().build_parts()
        assert system == ""
        assert user == ""

    def test_above_boundary_goes_to_system(self):
        a = make_assembler(inj("sys", USER_INPUT_PRIORITY + 1))
        system, user = a.build_parts()
        assert system == "sys"
        assert user == ""

    def test_at_boundary_goes_to_user(self):
        # Priority == USER_INPUT_PRIORITY is the user turn (<=, not <)
        a = make_assembler(inj("usr", USER_INPUT_PRIORITY))
        system, user = a.build_parts()
        assert system == ""
        assert user == "usr"

    def test_below_boundary_goes_to_user(self):
        a = make_assembler(inj("usr", USER_INPUT_PRIORITY - 1))
        system, user = a.build_parts()
        assert system == ""
        assert user == "usr"

    def test_mixed_split_correctly(self):
        a = make_assembler(
            inj("system_high", 100),
            inj("system_low",  USER_INPUT_PRIORITY + 1),
            inj("user_at",     USER_INPUT_PRIORITY),
            inj("user_below",  0),
        )
        system, user = a.build_parts()
        assert "system_high" in system
        assert "system_low"  in system
        assert "user_at"     in user
        assert "user_below"  in user
        # Nothing crosses the boundary
        assert "user_at"    not in system
        assert "system_low" not in user

    def test_system_parts_ordered_highest_priority_first(self):
        a = make_assembler(inj("B", 50), inj("A", 90))
        system, _ = a.build_parts()
        assert system.index("A") < system.index("B")

    def test_user_parts_ordered_highest_priority_first(self):
        # Among user-turn injections, higher priority still comes first.
        a = make_assembler(
            inj("input",  USER_INPUT_PRIORITY),      # 10
            inj("length", USER_INPUT_PRIORITY - 5),  # 5
        )
        _, user = a.build_parts()
        assert user.index("input") < user.index("length")

    def test_build_and_build_parts_cover_same_content(self):
        a = make_assembler(
            inj("sys",  50),
            inj("usr",  10),
        )
        flat = a.build()
        system, user = a.build_parts()
        combined = (system + "\n\n" + user).strip()
        assert flat.strip() == combined

    def test_single_injection_at_boundary(self):
        a = make_assembler(inj("only", USER_INPUT_PRIORITY))
        system, user = a.build_parts()
        assert system == ""
        assert user == "only"


# ---------------------------------------------------------------------------
# Instance independence: fresh assembler each call
# ---------------------------------------------------------------------------

class TestInstanceIndependence:

    def test_two_assemblers_do_not_share_injections(self):
        a1 = PromptAssembler()
        a2 = PromptAssembler()
        a1.add(inj("only_in_a1", 10))
        assert a2.build() == ""
        assert a1.build() == "only_in_a1"

    def test_adding_to_one_does_not_affect_the_other(self):
        a1 = make_assembler(inj("shared_content", 50))
        a2 = make_assembler(inj("shared_content", 50))
        a1.add(inj("extra", 99))
        assert "extra" not in a2.build()

    def test_sequential_assemblers_produce_independent_results(self):
        """Simulates two generation calls each creating a fresh assembler."""
        def build_prompt(user_text: str) -> str:
            a = PromptAssembler()
            a.add(inj("system context", 100))
            a.add(inj(user_text, USER_INPUT_PRIORITY))
            return a.build()

        r1 = build_prompt("first message")
        r2 = build_prompt("second message")
        assert "first message"  in r1
        assert "second message" not in r1
        assert "second message" in r2
        assert "first message"  not in r2


# ---------------------------------------------------------------------------
# Real module functions: interface contract
# ---------------------------------------------------------------------------

class TestRealModules:
    """
    Exercises the module functions that GenerationCoordinator feeds into the
    assembler. Verifies they return a PromptInjection with non-empty content
    and the expected priority tier, without testing exact prompt wording.
    """

    def test_personality_module_returns_injection(self):
        from src.qubit.prompting.modules.personality import personality_module
        inj_out = personality_module(mood="calm", tone="formal", interaction_level="low")
        assert isinstance(inj_out, PromptInjection)
        assert inj_out.content
        assert inj_out.priority > USER_INPUT_PRIORITY  # must be system-side

    def test_personality_module_all_interaction_levels(self):
        from src.qubit.prompting.modules.personality import personality_module
        for level in ("low", "medium", "high"):
            i = personality_module(interaction_level=level)
            assert isinstance(i, PromptInjection)
            assert i.content

    def test_stream_type_module_uses_override(self):
        from src.qubit.prompting.modules.stream_type import stream_type_module
        i = stream_type_module("Minecraft")
        assert isinstance(i, PromptInjection)
        assert "Minecraft" in i.content
        assert i.priority > USER_INPUT_PRIORITY

    def test_stream_type_module_falls_back_to_settings(self):
        from src.qubit.prompting.modules.stream_type import stream_type_module
        i = stream_type_module(None)
        assert isinstance(i, PromptInjection)
        assert i.content  # falls back to STREAM_TYPE from settings stub

    def test_input_module_embeds_text(self):
        from src.qubit.prompting.modules.input import input_module
        i = input_module("hello chat")
        assert isinstance(i, PromptInjection)
        assert "hello chat" in i.content
        # input_module is the user turn — must be at or below boundary
        assert i.priority <= USER_INPUT_PRIORITY

    def test_length_module_returns_injection(self):
        from src.qubit.prompting.modules.length import length_module
        for event_type, source in [
            ("twitch_chat_processed", "twitch"),
            ("autonomous_prompt",     None),
            (None,                    None),
        ]:
            i = length_module(event_type=event_type, source=source)
            assert isinstance(i, PromptInjection)
            assert i.content

    def test_full_assembly_matches_generation_coordinator_pattern(self):
        """
        Replays the exact assembler usage from GenerationCoordinator._generate_response
        (minus LLM call) and asserts the resulting messages list is well-formed.
        """
        from src.qubit.prompting.modules.personality import personality_module
        from src.qubit.prompting.modules.stream_type import stream_type_module
        from src.qubit.prompting.modules.input import input_module
        from src.qubit.prompting.modules.length import length_module
        from src.qubit.prompting.modules.core import core_system_module

        assembler = PromptAssembler()
        assembler.add(core_system_module())
        assembler.add(personality_module(mood="energetic", tone="casual", interaction_level="high"))
        assembler.add(stream_type_module("Just Chatting"))
        assembler.add(length_module(event_type="twitch_chat_processed", source="twitch"))
        assembler.add(input_module("what's your favourite game?"))

        system_text, user_text = assembler.build_parts()

        # System text must exist (core + personality + stream_type are all above boundary)
        assert system_text.strip()
        # User text must contain the input
        assert "favourite game" in user_text

        messages = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        if user_text:
            messages.append({"role": "user", "content": user_text})

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        # No injection appears in both turns
        assert messages[0]["content"] != messages[1]["content"]