"""Tests for CommunityEventQueue."""

import pytest
from src.qubit.cognitive.activity.community_event_queue import CommunityEventQueue


def test_add_stamps_id():
    q = CommunityEventQueue()
    detail = {"kind": "raid", "username": "streamer1", "viewer_count": 50}
    q.add(detail)
    assert "_id" in detail
    assert detail["_id"]


def test_peek_returns_all_events():
    q = CommunityEventQueue()
    q.add({"kind": "raid", "username": "a"})
    q.add({"kind": "follow", "username": "b"})
    peeked = q.peek()
    assert len(peeked) == 2


def test_peek_is_nondestructive():
    q = CommunityEventQueue()
    q.add({"kind": "raid", "username": "a"})
    q.peek()
    assert len(q.peek()) == 1


def test_remove_by_id():
    q = CommunityEventQueue()
    detail = {"kind": "raid", "username": "a"}
    q.add(detail)
    q.remove([detail])
    assert q.peek() == []


def test_remove_only_specified_events():
    q = CommunityEventQueue()
    d1 = {"kind": "raid", "username": "a"}
    d2 = {"kind": "follow", "username": "b"}
    q.add(d1)
    q.add(d2)
    q.remove([d1])
    remaining = q.peek()
    assert len(remaining) == 1
    assert remaining[0]["username"] == "b"


def test_remove_nonexistent_id_is_noop():
    q = CommunityEventQueue()
    q.add({"kind": "raid", "username": "a"})
    q.remove([{"_id": "fake-id-that-does-not-exist"}])
    assert len(q.peek()) == 1


def test_remove_without_id_is_noop():
    q = CommunityEventQueue()
    q.add({"kind": "raid", "username": "a"})
    q.remove([{"kind": "raid"}])
    assert len(q.peek()) == 1


def test_ids_are_unique():
    q = CommunityEventQueue()
    d1 = {"kind": "raid", "username": "a"}
    d2 = {"kind": "raid", "username": "b"}
    q.add(d1)
    q.add(d2)
    assert d1["_id"] != d2["_id"]


def test_insertion_order_preserved():
    q = CommunityEventQueue()
    for i in range(5):
        q.add({"kind": "follow", "username": f"user{i}"})
    names = [e["username"] for e in q.peek()]
    assert names == [f"user{i}" for i in range(5)]
