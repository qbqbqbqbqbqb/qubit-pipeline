import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.qubit.output.handlers.vtube as target_module
from src.qubit.output.handlers.vtube import VtubeStudioHandler

TARGET_MODULE = target_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_vts(request_return=None):
    """A stand-in for a connected pyvts.vts instance."""
    vts = MagicMock()
    vts.connect = AsyncMock()
    vts.request_authenticate_token = AsyncMock()
    vts.request_authenticate = AsyncMock()
    vts.close = AsyncMock()
    vts.request = AsyncMock(return_value=request_return if request_return is not None else {"messageType": "OK"})
    vts.vts_request = MagicMock()
    vts.vts_request.BaseRequest = MagicMock(side_effect=lambda name, data: {"messageType": name, "data": data})
    return vts


def make_mock_pyvts_module(vts_instance):
    module = MagicMock()
    module.vts = MagicMock(return_value=vts_instance)
    return module


async def immediate_task(*args, **kwargs):
    """A coroutine that returns right away, for stubbing background loops."""
    return None


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_defaults(self):
        h = VtubeStudioHandler()
        assert h.plugin_name == "Qubit Pipeline"
        assert h.developer == "Khubie"
        assert h.port == 8001
        assert h.token_path == "vtubeStudio_token.txt"
        assert h.vts is None
        assert h.connected is False
        assert h.speaking is False
        assert h._mouth_task is None
        assert h._idle_task is None

    def test_custom_values(self):
        h = VtubeStudioHandler(plugin_name="P", developer="D", port=1234, token_path="t.txt")
        assert h.plugin_name == "P"
        assert h.developer == "D"
        assert h.port == 1234
        assert h.token_path == "t.txt"

    def test_warns_when_pyvts_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(TARGET_MODULE, "pyvts", None)
        VtubeStudioHandler()
        out = capsys.readouterr().out
        assert "pyvts not installed" in out


# ---------------------------------------------------------------------------
# connect / ensure_connected
# ---------------------------------------------------------------------------

class TestConnect:
    @pytest.mark.asyncio
    async def test_returns_false_when_pyvts_missing(self, monkeypatch):
        monkeypatch.setattr(TARGET_MODULE, "pyvts", None)
        h = VtubeStudioHandler()

        result = await h.connect()

        assert result is False
        assert h.connected is False

    @pytest.mark.asyncio
    async def test_success_path_authenticates_and_sets_connected(self, monkeypatch):
        vts_instance = make_mock_vts()
        monkeypatch.setattr(TARGET_MODULE, "pyvts", make_mock_pyvts_module(vts_instance))
        h = VtubeStudioHandler()

        result = await h.connect()

        assert result is True
        assert h.connected is True
        assert h.vts is vts_instance
        vts_instance.connect.assert_awaited_once()
        vts_instance.request_authenticate_token.assert_awaited_once()
        vts_instance.request_authenticate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_closes_existing_client_before_reconnecting(self, monkeypatch):
        old_vts = make_mock_vts()
        new_vts = make_mock_vts()
        pyvts_module = make_mock_pyvts_module(new_vts)
        monkeypatch.setattr(TARGET_MODULE, "pyvts", pyvts_module)

        h = VtubeStudioHandler()
        h.vts = old_vts

        await h.connect()

        old_vts.close.assert_awaited_once()
        assert h.vts is new_vts

    @pytest.mark.asyncio
    async def test_ignores_exception_when_closing_existing_client(self, monkeypatch):
        old_vts = make_mock_vts()
        old_vts.close.side_effect = RuntimeError("already closed")
        new_vts = make_mock_vts()
        monkeypatch.setattr(TARGET_MODULE, "pyvts", make_mock_pyvts_module(new_vts))

        h = VtubeStudioHandler()
        h.vts = old_vts

        result = await h.connect()

        assert result is True

    @pytest.mark.asyncio
    async def test_failure_path_resets_state_and_returns_false(self, monkeypatch):
        vts_instance = make_mock_vts()
        vts_instance.connect.side_effect = RuntimeError("VTube Studio not running")
        monkeypatch.setattr(TARGET_MODULE, "pyvts", make_mock_pyvts_module(vts_instance))
        h = VtubeStudioHandler()

        result = await h.connect()

        assert result is False
        assert h.connected is False
        assert h.vts is None


class TestEnsureConnected:
    @pytest.mark.asyncio
    async def test_returns_true_immediately_if_already_connected(self):
        h = VtubeStudioHandler()
        h.connected = True
        h.connect = AsyncMock()

        result = await h.ensure_connected()

        assert result is True
        h.connect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_calls_connect_if_not_connected(self):
        h = VtubeStudioHandler()
        h.connected = False
        h.connect = AsyncMock(return_value=True)

        result = await h.ensure_connected()

        assert result is True
        h.connect.assert_awaited_once()


# ---------------------------------------------------------------------------
# start_speaking / stop_speaking / start_idle
# ---------------------------------------------------------------------------

class TestSpeakingIdleTaskManagement:
    @pytest.mark.asyncio
    async def test_start_speaking_noop_if_already_speaking(self):
        h = VtubeStudioHandler()
        h.speaking = True
        h._mouth_animation_loop = AsyncMock(side_effect=immediate_task)

        await h.start_speaking()

        h._mouth_animation_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_speaking_sets_flag_and_starts_mouth_task(self):
        h = VtubeStudioHandler()
        h._mouth_animation_loop = AsyncMock(side_effect=immediate_task)

        await h.start_speaking()

        assert h.speaking is True
        assert h._mouth_task is not None
        await h._mouth_task
        h._mouth_animation_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_speaking_cancels_running_idle_task(self):
        h = VtubeStudioHandler()

        async def never_ending_idle():
            await asyncio.sleep(1000)

        h._idle_task = asyncio.create_task(never_ending_idle())
        h._mouth_animation_loop = AsyncMock(side_effect=immediate_task)

        await h.start_speaking()

        assert h._idle_task is None

    @pytest.mark.asyncio
    async def test_stop_speaking_noop_if_not_speaking(self):
        h = VtubeStudioHandler()
        h.speaking = False
        h.idle_animation = AsyncMock(side_effect=immediate_task)

        await h.stop_speaking()

        h.idle_animation.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_speaking_cancels_mouth_task_and_starts_idle(self):
        h = VtubeStudioHandler()
        h.speaking = True

        async def never_ending_mouth():
            await asyncio.sleep(1000)

        h._mouth_task = asyncio.create_task(never_ending_mouth())
        h.idle_animation = AsyncMock(side_effect=immediate_task)

        await h.stop_speaking()

        assert h.speaking is False
        assert h._mouth_task is None
        assert h._idle_task is not None
        await h._idle_task
        h.idle_animation.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_idle_noop_if_speaking(self):
        h = VtubeStudioHandler()
        h.speaking = True
        h.idle_animation = AsyncMock(side_effect=immediate_task)

        await h.start_idle()

        h.idle_animation.assert_not_called()
        assert h._idle_task is None

    @pytest.mark.asyncio
    async def test_start_idle_starts_task_when_not_already_running(self):
        h = VtubeStudioHandler()
        h.speaking = False
        h.idle_animation = AsyncMock(side_effect=immediate_task)

        await h.start_idle()

        assert h._idle_task is not None
        await h._idle_task
        h.idle_animation.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_idle_does_not_replace_running_task(self):
        h = VtubeStudioHandler()
        h.speaking = False

        async def never_ending_idle():
            await asyncio.sleep(1000)

        existing_task = asyncio.create_task(never_ending_idle())
        h._idle_task = existing_task

        await h.start_idle()

        assert h._idle_task is existing_task
        existing_task.cancel()
        try:
            await existing_task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# _send_request
# ---------------------------------------------------------------------------

class TestSendRequest:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_vts_client(self):
        h = VtubeStudioHandler()
        h.vts = None

        result = await h._send_request({"some": "request"})

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_response_on_success(self):
        h = VtubeStudioHandler()
        h.vts = make_mock_vts(request_return={"messageType": "SomeResponse"})

        result = await h._send_request({"some": "request"})

        assert result == {"messageType": "SomeResponse"}
        h.vts.request.assert_awaited_once_with({"some": "request"})

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self):
        h = VtubeStudioHandler()
        h.vts = make_mock_vts(request_return={"messageType": "APIError", "data": {"message": "bad request"}})

        result = await h._send_request({"some": "request"})

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_request_raises(self):
        h = VtubeStudioHandler()
        h.vts = make_mock_vts()
        h.vts.request.side_effect = RuntimeError("boom")

        result = await h._send_request({"some": "request"})

        assert result is None


# ---------------------------------------------------------------------------
# _blink
# ---------------------------------------------------------------------------

class TestBlink:
    @pytest.mark.asyncio
    async def test_noop_when_not_connected(self):
        h = VtubeStudioHandler()
        h.connected = False
        h.vts = make_mock_vts()

        await h._blink()

        h.vts.request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_noop_when_no_vts_client(self):
        h = VtubeStudioHandler()
        h.connected = True
        h.vts = None

        await h._blink()

    @pytest.mark.asyncio
    async def test_closes_then_opens_eyes(self, monkeypatch):
        h = VtubeStudioHandler()
        h.connected = True
        h.vts = make_mock_vts()
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        await h._blink(duration=0.05)

        assert h.vts.request.await_count == 2
        first_call_request = h.vts.request.await_args_list[0].args[0]
        second_call_request = h.vts.request.await_args_list[1].args[0]

        first_values = {p["id"]: p["value"] for p in first_call_request["data"]["parameterValues"]}
        second_values = {p["id"]: p["value"] for p in second_call_request["data"]["parameterValues"]}

        assert first_values == {"EyeOpenLeft": 0.0, "EyeOpenRight": 0.0}
        assert second_values == {"EyeOpenLeft": 1.0, "EyeOpenRight": 1.0}

    @pytest.mark.asyncio
    async def test_swallows_exceptions(self, monkeypatch):
        h = VtubeStudioHandler()
        h.connected = True
        h.vts = make_mock_vts()
        h.vts.request.side_effect = RuntimeError("boom")
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        await h._blink()


# ---------------------------------------------------------------------------
# _mouth_animation_loop / idle_animation
# ---------------------------------------------------------------------------

class TestMouthAnimationLoop:
    @pytest.mark.asyncio
    async def test_returns_immediately_if_not_connected(self, monkeypatch):
        h = VtubeStudioHandler()
        h.ensure_connected = AsyncMock(return_value=False)
        h.connected = False
        h._reset_speaking_parameters = AsyncMock()

        await h._mouth_animation_loop()

        h._reset_speaking_parameters.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_runs_while_speaking_and_resets_on_exit(self, monkeypatch):
        h = VtubeStudioHandler()
        h.ensure_connected = AsyncMock(return_value=True)
        h.connected = True
        h.vts = make_mock_vts()
        h.speaking = True
        h._reset_speaking_parameters = AsyncMock()
        h._blink = AsyncMock()

        call_count = {"n": 0}

        async def fake_sleep(_):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                h.speaking = False

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr("random.uniform", lambda a, b: a)

        await h._mouth_animation_loop()

        assert h.vts.request.await_count >= 1
        h._reset_speaking_parameters.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_called_even_if_loop_raises(self, monkeypatch):
        h = VtubeStudioHandler()
        h.ensure_connected = AsyncMock(return_value=True)
        h.connected = True
        h.vts = make_mock_vts()
        h.vts.request.side_effect = RuntimeError("boom")
        h.speaking = True
        h._reset_speaking_parameters = AsyncMock()

        async def fake_sleep(_):
            h.speaking = False

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr("random.uniform", lambda a, b: a)

        await h._mouth_animation_loop()

        h._reset_speaking_parameters.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_cancellation_and_still_resets(self, monkeypatch):
        h = VtubeStudioHandler()
        h.ensure_connected = AsyncMock(return_value=True)
        h.connected = True
        h.vts = make_mock_vts()
        h.speaking = True
        h._reset_speaking_parameters = AsyncMock()

        async def cancel_sleep(_):
            raise asyncio.CancelledError()

        monkeypatch.setattr(asyncio, "sleep", cancel_sleep)
        monkeypatch.setattr("random.uniform", lambda a, b: a)

        await h._mouth_animation_loop()

        h._reset_speaking_parameters.assert_awaited_once()


class TestIdleAnimation:
    @pytest.mark.asyncio
    async def test_returns_immediately_if_not_connected(self):
        h = VtubeStudioHandler()
        h.ensure_connected = AsyncMock(return_value=False)
        h.connected = False
        h._reset_idle_parameters = AsyncMock()

        await h.idle_animation()

        h._reset_idle_parameters.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_runs_while_not_speaking_and_resets_on_exit(self, monkeypatch):
        h = VtubeStudioHandler()
        h.ensure_connected = AsyncMock(return_value=True)
        h.connected = True
        h.vts = make_mock_vts()
        h.speaking = False
        h._reset_idle_parameters = AsyncMock()
        h._blink = AsyncMock()

        call_count = {"n": 0}

        async def fake_sleep(_):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                h.speaking = True

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr("random.uniform", lambda a, b: a)

        await h.idle_animation()

        assert h.vts.request.await_count >= 1
        h._reset_idle_parameters.assert_awaited_once()


# ---------------------------------------------------------------------------
# _reset_speaking_parameters / _reset_idle_parameters
# ---------------------------------------------------------------------------

class TestResetParameters:
    @pytest.mark.asyncio
    async def test_reset_speaking_noop_when_not_connected(self):
        h = VtubeStudioHandler()
        h.connected = False
        h.vts = make_mock_vts()

        await h._reset_speaking_parameters()

        h.vts.request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reset_speaking_sends_neutral_values(self):
        h = VtubeStudioHandler()
        h.connected = True
        h.vts = make_mock_vts()

        await h._reset_speaking_parameters()

        h.vts.request.assert_awaited_once()
        sent = h.vts.request.await_args.args[0]
        values = {p["id"]: p["value"] for p in sent["data"]["parameterValues"]}
        assert values["JawOpen"] == 0.0
        assert values["MouthOpen"] == 0.0
        assert values["MouthSmile"] == 0.25

    @pytest.mark.asyncio
    async def test_reset_speaking_swallows_exceptions(self):
        h = VtubeStudioHandler()
        h.connected = True
        h.vts = make_mock_vts()
        h.vts.request.side_effect = RuntimeError("boom")

        await h._reset_speaking_parameters()

    @pytest.mark.asyncio
    async def test_reset_idle_noop_when_not_connected(self):
        h = VtubeStudioHandler()
        h.connected = False
        h.vts = make_mock_vts()

        await h._reset_idle_parameters()

        h.vts.request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reset_idle_sends_neutral_values(self):
        h = VtubeStudioHandler()
        h.connected = True
        h.vts = make_mock_vts()

        await h._reset_idle_parameters()

        h.vts.request.assert_awaited_once()
        sent = h.vts.request.await_args.args[0]
        values = {p["id"]: p["value"] for p in sent["data"]["parameterValues"]}
        assert values["MouthSmile"] == 0.45
        assert values["FaceAngleX"] == 0.0

    @pytest.mark.asyncio
    async def test_reset_idle_swallows_exceptions(self):
        h = VtubeStudioHandler()
        h.connected = True
        h.vts = make_mock_vts()
        h.vts.request.side_effect = RuntimeError("boom")

        await h._reset_idle_parameters() 