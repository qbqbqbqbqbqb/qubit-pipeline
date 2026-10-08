"""WebSocket server service for frontend communication and state broadcasting."""

import asyncio
import dataclasses
import json

import websockets

from src.qubit.core.service import Service


class WebSocketServerService(Service):
    """
    Manages WebSocket connections and routes frontend commands.

    WAIT_FOR_START = False because this service must be running before
    the frontend can send the start command — it cannot wait for the
    signal it is responsible for delivering.
    """

    WAIT_FOR_START = False

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        super().__init__("websocket_server")
        self.host = host
        self.port = port
        self.connected_clients: set = set()
        self.server = None

    async def _run(self) -> None:
        """Start the WebSocket server and serve until cancelled."""
        self.server = await websockets.serve(
            self.websocket_handler, self.host, self.port
        )
        self.logger.info("[_run] WebSocketServer listening on %s:%s", self.host, self.port)
        await self.server.wait_closed()

    async def stop(self) -> None:
        """Gracefully close the server then cancel the worker task."""
        self.logger.info("[stop] Stopping WebSocketServer")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await super().stop()

    async def websocket_handler(self, websocket) -> None:
        """Handle messages from a single connected client."""
        self.connected_clients.add(websocket)
        try:
            await self.send_states(websocket)
            async for message in websocket:
                await self._handle_message(websocket, json.loads(message))
        except Exception as e:
            self.logger.error("[websocket_handler] %s", e)
        finally:
            self.connected_clients.discard(websocket)

    async def _handle_message(self, websocket, data: dict) -> None:
        action = data.get("action")

        if action == "toggle":
            flag = data.get("input")
            state = data.get("state") == "on"
            features = self.app.state.features
            if hasattr(features, flag):
                setattr(features, flag, state)
                self.logger.info("[_handle_message] Toggled %s -> %s", flag, state)
                await self.broadcast_states()
            else:
                self.logger.warning("[_handle_message] Unknown feature flag: %s", flag)

        elif action == "start":
            self.logger.info("[_handle_message] Start command from frontend")
            for k, v in data.get("features", {}).items():
                features = self.app.state.features
                if hasattr(features, k):
                    setattr(features, k, bool(v))
                    self.logger.info("[_handle_message] Set feature %s = %s", k, v)
            self.app.state.start.set()
            await self.broadcast_states()

        elif action == "terminate":
            self.logger.info("[_handle_message] Terminate command from frontend")
            self.app.state.shutdown.set()

        elif action == "play_audio":
            file_path = data.get("file_path")
            if file_path and hasattr(self.app, "audio_player"):
                await self.app.audio_player.play_file(file_path)
                self.logger.info("[_handle_message] Playing audio: %s", file_path)
            else:
                self.logger.warning("[_handle_message] play_audio: no file_path or audio_player")

        elif action == "stop_audio":
            if hasattr(self.app, "audio_player"):
                await self.app.audio_player.stop_playback()
                self.logger.info("[_handle_message] Stop audio requested")

        elif action == "list_audio_files":
            if hasattr(self.app, "audio_player"):
                directory = self.app.audio_player.audio_directory
                files = []
                if directory.exists():
                    files = [
                        str(f.relative_to(directory))
                        for f in sorted(directory.glob("*.wav"))
                    ]
                await websocket.send(json.dumps({"type": "audio_files", "data": files}))

    def _features_as_dict(self) -> dict:
        """Serialize FeatureFlags dataclass to a plain dict for JSON broadcast."""
        return dataclasses.asdict(self.app.state.features)

    async def send_states(self, websocket) -> None:
        """Push current feature states to a newly connected client."""
        await websocket.send(json.dumps({
            "type": "states",
            "data": self._features_as_dict(),
        }))

    async def broadcast_states(self) -> None:
        """Push current feature states to all connected clients."""
        if self.connected_clients:
            message = json.dumps({
                "type": "states",
                "data": self._features_as_dict(),
            })
            await asyncio.gather(*(c.send(message) for c in self.connected_clients))

    async def forward_event(self, event_type: str, data: dict) -> None:
        """Forward an internal event to all connected clients."""
        if self.connected_clients:
            message = json.dumps({"type": event_type, "data": data})
            await asyncio.gather(*(c.send(message) for c in self.connected_clients))
