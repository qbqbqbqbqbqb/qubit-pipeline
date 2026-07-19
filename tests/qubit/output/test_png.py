from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.qubit.output.handlers.png import PNGOutputHandler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def handler():
    """A handler with its real httpx client swapped for a mock."""
    h = PNGOutputHandler(frontend_url="http://testserver:8000")
    await h.client.aclose()
    h.client = AsyncMock()
    yield h


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_defaults(self):
        h = PNGOutputHandler()
        assert h.frontend_url == "http://127.0.0.1:8000"
        assert h.folder_path == Path("/data/png_models")
        assert h.processed_folders == {}
        assert h.current_idle is None
        assert h.current_speak is None
        assert h.current_model is None
        assert h.connected is False

    def test_custom_frontend_url(self):
        h = PNGOutputHandler(frontend_url="http://example.com")
        assert h.frontend_url == "http://example.com"


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------

class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_processes_folders_and_sets_connected(self, handler):
        handler.process_folders = AsyncMock()
        await handler.connect()
        handler.process_folders.assert_awaited_once()
        assert handler.connected is True


# ---------------------------------------------------------------------------
# load_model
# ---------------------------------------------------------------------------

class TestLoadModel:
    @pytest.mark.asyncio
    async def test_unknown_folder_returns_false(self, handler):
        handler.processed_folders = {}
        result = await handler.load_model("missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_known_folder_sets_state_and_sends_command(self, handler):
        idle_path = Path("/data/png_models/char1/char1_idle.png")
        speak_path = Path("/data/png_models/char1/char1_speak.png")
        handler.processed_folders = {
            "char1": {"idle": idle_path, "speak": speak_path, "all_images": [idle_path, speak_path]}
        }
        handler._send_command = AsyncMock()

        result = await handler.load_model("char1")

        assert result is True
        assert handler.current_idle == idle_path
        assert handler.current_speak == speak_path
        assert handler.current_model == idle_path
        handler._send_command.assert_awaited_once_with("load_model", {"folder": "char1"})

    @pytest.mark.asyncio
    async def test_folder_with_no_speak_image(self, handler):
        idle_path = Path("/data/png_models/char2/char2_idle.png")
        handler.processed_folders = {
            "char2": {"idle": idle_path, "speak": None, "all_images": [idle_path]}
        }
        handler._send_command = AsyncMock()

        result = await handler.load_model("char2")

        assert result is True
        assert handler.current_speak is None
        assert handler.current_model == idle_path


# ---------------------------------------------------------------------------
# speak / idle
# ---------------------------------------------------------------------------

class TestSpeak:
    @pytest.mark.asyncio
    async def test_switches_to_speak_model(self, handler):
        handler.current_idle = Path("idle.png")
        handler.current_speak = Path("speak.png")
        handler.current_model = Path("idle.png")
        handler._send_command = AsyncMock()

        await handler.speak()

        assert handler.current_model == Path("speak.png")
        handler._send_command.assert_awaited_once_with("speak")

    @pytest.mark.asyncio
    async def test_no_op_when_already_speaking(self, handler):
        handler.current_speak = Path("speak.png")
        handler.current_model = Path("speak.png")
        handler._send_command = AsyncMock()

        await handler.speak()

        handler._send_command.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_op_when_no_speak_image_loaded(self, handler):
        handler.current_speak = None
        handler.current_model = Path("idle.png")
        handler._send_command = AsyncMock()

        await handler.speak()

        handler._send_command.assert_not_awaited()


class TestIdle:
    @pytest.mark.asyncio
    async def test_switches_to_idle_model(self, handler):
        handler.current_idle = Path("idle.png")
        handler.current_speak = Path("speak.png")
        handler.current_model = Path("speak.png")
        handler._send_command = AsyncMock()

        await handler.idle()

        assert handler.current_model == Path("idle.png")
        handler._send_command.assert_awaited_once_with("idle")

    @pytest.mark.asyncio
    async def test_no_op_when_already_idle(self, handler):
        handler.current_idle = Path("idle.png")
        handler.current_model = Path("idle.png")
        handler._send_command = AsyncMock()

        await handler.idle()

        handler._send_command.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_op_when_no_idle_image_loaded(self, handler):
        handler.current_idle = None
        handler.current_model = Path("speak.png")
        handler._send_command = AsyncMock()

        await handler.idle()

        handler._send_command.assert_not_awaited()


# ---------------------------------------------------------------------------
# _send_command
# ---------------------------------------------------------------------------

class TestSendCommand:
    @pytest.mark.asyncio
    async def test_noop_when_not_connected(self, handler):
        handler.connected = False
        await handler._send_command("idle")
        handler.client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_posts_expected_payload(self, handler):
        handler.connected = True
        await handler._send_command("load_model", {"folder": "char1"})
        handler.client.post.assert_awaited_once_with(
            "http://testserver:8000/png/command",
            json={"action": "load_model", "folder": "char1"},
        )

    @pytest.mark.asyncio
    async def test_posts_with_no_payload(self, handler):
        handler.connected = True
        await handler._send_command("idle")
        handler.client.post.assert_awaited_once_with(
            "http://testserver:8000/png/command",
            json={"action": "idle"},
        )

    @pytest.mark.asyncio
    async def test_swallows_request_exceptions(self, handler):
        handler.connected = True
        handler.client.post.side_effect = RuntimeError("connection refused")
        # Should not raise.
        await handler._send_command("idle")


# ---------------------------------------------------------------------------
# retrieve_image_files
# ---------------------------------------------------------------------------

class TestRetrieveImageFiles:
    def test_returns_only_image_files(self, tmp_path):
        h = PNGOutputHandler()
        (tmp_path / "a_idle.png").touch()
        (tmp_path / "a_speak.jpg").touch()
        (tmp_path / "notes.txt").touch()

        result = h.retrieve_image_files(tmp_path)

        assert {f.name for f in result} == {"a_idle.png", "a_speak.jpg"}

    def test_raises_when_folder_has_no_images(self, tmp_path):
        h = PNGOutputHandler()
        (tmp_path / "notes.txt").touch()

        with pytest.raises(FileNotFoundError):
            h.retrieve_image_files(tmp_path)

    def test_ignores_subdirectories(self, tmp_path):
        h = PNGOutputHandler()
        (tmp_path / "sub").mkdir()
        (tmp_path / "a_idle.png").touch()

        result = h.retrieve_image_files(tmp_path)

        assert [f.name for f in result] == ["a_idle.png"]


# ---------------------------------------------------------------------------
# filter_and_validate_images
# ---------------------------------------------------------------------------

class TestFilterAndValidateImages:
    def test_splits_idle_and_speak_images(self, tmp_path):
        h = PNGOutputHandler()
        idle = tmp_path / "char_idle.png"
        speak = tmp_path / "char_speak.png"
        idle.touch()
        speak.touch()

        idle_images, speak_images = h.filter_and_validate_images(tmp_path, [idle, speak])

        assert idle_images == [idle]
        assert speak_images == [speak]

    def test_case_insensitive_suffix_match(self, tmp_path):
        h = PNGOutputHandler()
        idle = tmp_path / "char_IDLE.png"
        idle.touch()

        idle_images, speak_images = h.filter_and_validate_images(tmp_path, [idle])

        assert idle_images == [idle]
        assert speak_images == []

    def test_raises_on_multiple_idle_images(self, tmp_path):
        h = PNGOutputHandler()
        f1, f2 = tmp_path / "a_idle.png", tmp_path / "b_idle.png"
        f1.touch()
        f2.touch()

        with pytest.raises(ValueError):
            h.filter_and_validate_images(tmp_path, [f1, f2])

    def test_raises_on_multiple_speak_images(self, tmp_path):
        h = PNGOutputHandler()
        f1, f2 = tmp_path / "a_speak.png", tmp_path / "b_speak.png"
        f1.touch()
        f2.touch()

        with pytest.raises(ValueError):
            h.filter_and_validate_images(tmp_path, [f1, f2])

    def test_no_matching_images_returns_empty_lists(self, tmp_path):
        h = PNGOutputHandler()
        misc = tmp_path / "char_walk.png"
        misc.touch()

        idle_images, speak_images = h.filter_and_validate_images(tmp_path, [misc])

        assert idle_images == []
        assert speak_images == []


# ---------------------------------------------------------------------------
# save_processed_folder
# ---------------------------------------------------------------------------

class TestSaveProcessedFolder:
    def test_saves_expected_structure(self, tmp_path):
        h = PNGOutputHandler()
        idle = tmp_path / "char_idle.png"
        all_images = [idle]

        h.save_processed_folder(tmp_path, [idle], [], all_images)

        assert h.processed_folders[tmp_path.name] == {
            "idle": idle,
            "speak": None,
            "all_images": all_images,
        }

    def test_handles_no_idle_or_speak(self, tmp_path):
        h = PNGOutputHandler()
        other = tmp_path / "char_walk.png"

        h.save_processed_folder(tmp_path, [], [], [other])

        assert h.processed_folders[tmp_path.name] == {
            "idle": None,
            "speak": None,
            "all_images": [other],
        }


# ---------------------------------------------------------------------------
# process_folders
# ---------------------------------------------------------------------------

class TestProcessFolders:
    @pytest.mark.asyncio
    async def test_missing_base_path_leaves_processed_folders_empty(self, tmp_path):
        h = PNGOutputHandler()
        h.folder_path = tmp_path / "does_not_exist"

        await h.process_folders()

        assert h.processed_folders == {}

    @pytest.mark.asyncio
    async def test_processes_a_valid_model_folder(self, tmp_path):
        model_dir = tmp_path / "char1"
        model_dir.mkdir()
        (model_dir / "char1_idle.png").touch()
        (model_dir / "char1_speak.png").touch()

        h = PNGOutputHandler()
        h.folder_path = tmp_path
        await h.process_folders()

        assert "char1" in h.processed_folders
        assert h.processed_folders["char1"]["idle"].name == "char1_idle.png"
        assert h.processed_folders["char1"]["speak"].name == "char1_speak.png"

    @pytest.mark.asyncio
    async def test_invalid_folder_is_skipped_but_others_still_process(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "notes.txt").touch()  # no images -> FileNotFoundError

        good_dir = tmp_path / "good"
        good_dir.mkdir()
        (good_dir / "good_idle.png").touch()

        h = PNGOutputHandler()
        h.folder_path = tmp_path
        await h.process_folders()

        assert "empty" not in h.processed_folders
        assert "good" in h.processed_folders

    @pytest.mark.asyncio
    async def test_folder_with_duplicate_idle_images_is_skipped(self, tmp_path):
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "a_idle.png").touch()
        (bad_dir / "b_idle.png").touch()

        h = PNGOutputHandler()
        h.folder_path = tmp_path
        await h.process_folders()

        assert "bad" not in h.processed_folders

    @pytest.mark.asyncio
    async def test_resets_processed_folders_on_each_call(self, tmp_path):
        model_dir = tmp_path / "char1"
        model_dir.mkdir()
        (model_dir / "char1_idle.png").touch()

        h = PNGOutputHandler()
        h.folder_path = tmp_path
        h.processed_folders = {"stale": {"idle": None, "speak": None, "all_images": []}}

        await h.process_folders()

        assert "stale" not in h.processed_folders
        assert "char1" in h.processed_folders