from src.qubit.core.events import (
    Event,
    TwitchEvent,
    TwitchChatEvent,
    TwitchSubscriptionEvent,
    TwitchRaidEvent,
    TwitchFollowEvent,
    YoutubeEvent,
    KickEvent,
    ModeratedEvent,
    SpeechEvent,
    MonologueEvent,
    InputEvent,
    ResponsePromptEvent,
    ResponseGeneratedEvent,
    PromptAssemblyEvent,
    MiscInputEvent,
)


def test_base_event():
    e = Event(type="base", timestamp="2026-05-25T00:00:00Z", data={"a": 1})
    assert e.type == "base"
    assert e.data["a"] == 1


def test_twitch_chat_event():
    e = TwitchChatEvent(
        type="twitch_chat",
        timestamp="now",
        data={},
        user="kubi",
        text="hello world"
    )
    assert e.user == "kubi"
    assert e.text == "hello world"
    assert isinstance(e, TwitchEvent)


def test_twitch_subscription_event():
    e = TwitchSubscriptionEvent(
        type="twitch_sub",
        timestamp="now",
        data={},
        user="subber",
        tier="3",
        sub_type="resub"
    )
    assert e.tier == "3"


def test_response_generated_event():
    e = ResponseGeneratedEvent(
        type="response",
        timestamp="now",
        data={},
        prompt="tell a joke",
        source="llm",
        response="Why did the chicken..."
    )
    assert e.response.startswith("Why")


def test_input_event():
    e = InputEvent(
        type="input",
        timestamp="now",
        data={},
        source="twitch",
        text="hi"
    )
    assert e.source == "twitch"
    assert e.text == "hi"
