"""Tests for ProposalArbiter — winner selection and scoring."""

import pytest
from src.qubit.cognitive.decision.proposal_arbiter import ProposalArbiter


@pytest.fixture
def arbiter():
    return ProposalArbiter()


def _proposal(type_="monologue", score=0.5, reason="idle_monologue", tier=0):
    return {"type": type_, "score": score, "reason": reason, "priority_tier": tier}


def test_empty_proposals_returns_none(arbiter):
    assert arbiter.select_winner([]) is None


def test_none_only_proposals_returns_none(arbiter):
    assert arbiter.select_winner([None, None]) is None


def test_none_proposals_filtered_valid_wins(arbiter):
    valid = _proposal(score=0.5)
    result = arbiter.select_winner([None, valid, None])
    assert result is valid


def test_single_proposal_wins(arbiter):
    p = _proposal(score=0.5)
    assert arbiter.select_winner([p]) is p


def test_higher_score_wins_same_tier(arbiter):
    low = _proposal(score=0.2, reason="idle_monologue")
    high = _proposal(score=0.9, reason="chat_response")
    winner = arbiter.select_winner([low, high])
    assert winner is high


def test_higher_tier_beats_lower_score(arbiter):
    low_tier = _proposal(score=1.0, tier=0, reason="idle_monologue")
    high_tier = _proposal(score=0.1, tier=1, reason="chat_response")
    winner = arbiter.select_winner([low_tier, high_tier])
    assert winner is high_tier


def test_community_tier_beats_all(arbiter):
    community = _proposal(score=0.1, tier=2, reason="community_event")
    stt = _proposal(score=1.0, tier=1, reason="stt_response")
    chat = _proposal(score=1.0, tier=0, reason="chat_response")
    winner = arbiter.select_winner([chat, stt, community])
    assert winner is community


def test_catchup_bonus_can_flip_winner(arbiter):
    monologue = _proposal(score=0.5, reason="idle_monologue", tier=0)
    chat = _proposal(score=0.6, reason="chat_response", tier=0)
    # Without bonus, chat wins
    assert arbiter.select_winner([monologue, chat]) is chat
    # With large catchup bonus, monologue wins
    winner = arbiter.select_winner(
        [monologue, chat],
        extra_bonus_by_reason={"idle_monologue": 10.0},
    )
    assert winner is monologue


def test_zero_score_proposal_wins_alone(arbiter):
    p = _proposal(score=0.0)
    assert arbiter.select_winner([p]) is p
