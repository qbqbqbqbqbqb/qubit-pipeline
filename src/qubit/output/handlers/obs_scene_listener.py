"""
OBSSceneListener — persistent OBS WebSocket connection for scene awareness.

Maintains a long-lived connection to OBS and listens for SceneChanged events.
On each scene change, updates RuntimeState.current_obs_scene so the prompt
assembly layer can inject scene context into generation.

This is separate from OBSHandler (which handles subtitle writes per-call).
OBSHandler stays stateless; this service owns the event subscription.

Requires: websocket-client (already installed for OBSHandler)
OBS WebSocket eventSubscriptions flag 4 = SceneChanged events only.
"""

import asyncio
import base64
import hashlib
import json

import websocket

from src.qubit.core.service import Service


class OBSSceneListener(Service):

    WAIT_FOR_START = True
    MAX_RESTARTS = 0  # supervisor handles restarts; we manage our own reconnect loop

    def __init__(self, settings) -> None:
        super().__init__("obs_scene_listener")
        self.settings = settings
        self.url = f"ws://{settings.obs_host}:{settings.obs_port}"
        self._ws: websocket.WebSocket | None = None

    async def _run(self) -> None:
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            try:
                await asyncio.to_thread(self._connect_and_listen)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.logger.warning("[_run] OBS connection lost: %s — retrying in 10s", exc)
                self._set_disconnected(str(exc))
                await asyncio.sleep(10)

    def _connect_and_listen(self) -> None:
        """Blocking — runs in executor thread. Connects and processes events until disconnect."""
        self._ws = websocket.WebSocket()
        self._ws.connect(self.url, timeout=10)

        # Hello handshake
        hello = json.loads(self._ws.recv())
        auth_str = ""
        if "authentication" in hello.get("d", {}):
            auth_str = self._build_auth(
                hello["d"]["authentication"]["salt"],
                hello["d"]["authentication"]["challenge"],
            )

        identify = {
            "op": 1,
            "d": {
                "rpcVersion": 1,
                "authentication": auth_str,
                "eventSubscriptions": 4,  # SceneChanged only
            },
        }
        self._ws.send(json.dumps(identify))
        identified = json.loads(self._ws.recv())
        if identified.get("op") != 2:
            raise ConnectionError(f"OBS identify failed: {identified}")

        # Fetch current scene immediately on connect
        self._ws.send(json.dumps({
            "op": 6,
            "d": {
                "requestType": "GetCurrentProgramScene",
                "requestId": "initial_scene",
            },
        }))

        self.logger.info("[_connect_and_listen] Connected to OBS at %s", self.url)
        self._set_connected()

        # Event loop
        while True:
            raw = self._ws.recv()
            if not raw:
                break
            msg = json.loads(raw)
            op = msg.get("op")

            # op 7 = RequestResponse (our GetCurrentProgramScene reply)
            if op == 7:
                scene = (
                    msg.get("d", {})
                    .get("responseData", {})
                    .get("currentProgramSceneName", "")
                )
                if scene:
                    self._update_scene(scene)

            # op 5 = Event
            elif op == 5:
                event_type = msg.get("d", {}).get("eventType", "")
                if event_type == "CurrentProgramSceneChanged":
                    scene = msg["d"]["eventData"].get("sceneName", "")
                    if scene:
                        self._update_scene(scene)

    def _update_scene(self, scene_name: str) -> None:
        self.logger.info("[_update_scene] OBS scene: %s", scene_name)
        try:
            self.app.state.current_obs_scene = scene_name
            self.app.state.health["obs_scene_listener"] = {
                "status": "connected",
                "detail": f"scene: {scene_name}",
            }
        except Exception:
            pass

    def _build_auth(self, salt: str, challenge: str) -> str:
        secret = base64.b64encode(
            hashlib.sha256((self.settings.obs_password + salt).encode()).digest()
        )
        return base64.b64encode(
            hashlib.sha256(secret + challenge.encode()).digest()
        ).decode()

    async def stop(self) -> None:
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        await super().stop()