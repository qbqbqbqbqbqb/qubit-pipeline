"""
<summary>
PNGOutputHandler — drives a PNG avatar via HTTP commands to the frontend web server.
</summary>
<remarks>
Sends speak/idle/load_model commands as JSON POST requests to the frontend.
The frontend's PngStateManager owns all model/image state and resolves the
correct image URL itself. This handler is intentionally stateless with respect
to model folders: it does not scan a local directory, because the frontend is
the single source of truth for which model is loaded and which images exist.

speak() / idle() fire unconditionally — no local guard on current_model —
so the frontend's deduplication logic handles redundant commands rather than
the pipeline silently dropping them due to stale local state.
</remarks>
"""

import httpx

from src.qubit.utils.log_utils import get_logger

logger = get_logger("PNGOutputHandler")


class PNGOutputHandler:
    """
    <summary>
    Controls a PNG avatar by posting speak/idle/load_model commands to the
    frontend web server. Stateless with respect to model selection — the
    frontend owns that state.
    </summary>
    """

    def __init__(self, frontend_url: str = "http://127.0.0.1:8000"):
        """
        <summary>Initialise the handler with the frontend server URL.</summary>
        <param name="frontend_url">Base URL of the frontend server that accepts PNG avatar commands.</param>
        """
        self.frontend_url = frontend_url.rstrip("/")
        self.connected = False
        self.client = httpx.AsyncClient(timeout=5.0)
        self.logger = logger

    async def connect(self) -> None:
        """
        <summary>
        Mark the handler as connected. Does not verify that the frontend is
        reachable — the first command will surface any connectivity error via
        the warning log in _send_command.
        </summary>
        """
        self.connected = True
        self.logger.info("[connect] PNGOutputHandler ready — frontend: %s", self.frontend_url)

    async def disconnect(self) -> None:
        """<summary>Close the underlying HTTP client.</summary>"""
        self.connected = False
        await self.client.aclose()
        self.logger.info("[disconnect] PNGOutputHandler disconnected")

    async def load_model(self, folder_name: str) -> None:
        """
        <summary>
        Tell the frontend to load a specific model folder.
        Call this to programmatically switch models at runtime; the normal
        path is the operator clicking Load in the control panel.
        </summary>
        <param name="folder_name">The model folder name as uploaded via the control panel.</param>
        """
        await self._send_command("load_model", {"folder": folder_name})
        self.logger.info("[load_model] Requested model: %s", folder_name)

    async def speak(self) -> None:
        """<summary>Switch the avatar to its speaking image.</summary>"""
        await self._send_command("speak")

    async def idle(self) -> None:
        """<summary>Switch the avatar to its idle image.</summary>"""
        await self._send_command("idle")

    async def _send_command(self, action: str, payload: dict = None) -> None:
        """
        <summary>POST a command to the frontend. Logs failures without raising.</summary>
        <param name="action">The action string ('speak', 'idle', 'load_model').</param>
        <param name="payload">Optional extra fields merged into the request body.</param>
        """
        if not self.connected:
            self.logger.debug("[_send_command] Not connected — skipping action: %s", action)
            return

        try:
            body = {"action": action, **(payload or {})}
            await self.client.post(f"{self.frontend_url}/png/command", json=body)
        except Exception as e:
            self.logger.warning("[_send_command] Failed to reach PNG frontend (%s): %s", action, e)