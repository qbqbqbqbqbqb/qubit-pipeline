"""
WebSocket server service for frontend communication and state broadcasting.
"""

import asyncio
import dataclasses
import json
from datetime import datetime, timezone

import websockets

from src.qubit.core.events import Event
from src.qubit.core.service import Service


class WebSocketServerService(Service):

    WAIT_FOR_START = False

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        super().__init__("websocket_server")
        self.host = host
        self.port = port
        self.connected_clients: set = set()
        self.server = None

    async def _run(self) -> None:
        self.server = await websockets.serve(
            self.websocket_handler, self.host, self.port
        )
        self.logger.info("[_run] WebSocketServer listening on %s:%s", self.host, self.port)
        await self.server.wait_closed()

    async def stop(self) -> None:
        self.logger.info("[stop] Stopping WebSocketServer")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await super().stop()

    async def websocket_handler(self, websocket) -> None:
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

        if action == "initialize":
            self.logger.info("[_handle_message] Initialize — loading models")
            llm_service = getattr(self.app.state, "llm_service", None)
            if llm_service is None:
                self.logger.error("[_handle_message] initialize: llm_service not on state")
                return
            try:
                for profile in llm_service.list_profiles():
                    self.logger.info("[_handle_message] Loading profile: %s", profile)
                    await llm_service.ensure_loaded(profile)
                self.logger.info("[_handle_message] All models loaded")
            except Exception as exc:
                self.logger.error("[_handle_message] Model load failed: %s", exc)
            await self.broadcast_states()

        elif action == "toggle":
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

        elif action == "end_stream":
            self.logger.info("[_handle_message] End stream — halting input processing")
            self.app.state.features.processing_active = False
            await self.app.event_bus.publish(Event(
                type="bot_end_stream",
                timestamp=datetime.now(timezone.utc).isoformat(),
                data={"command": "end_stream", "source": "frontend"},
            ))
            await self.broadcast_states()

        elif action == "terminate":
            self.logger.info("[_handle_message] Terminate command from frontend")
            self.app.state.shutdown.set()

        elif action == "reconnect":
            self.logger.info("[_handle_message] Reconnect requested")
            await self.broadcast_states()

        elif action == "set_stream_type":
            stream_type = data.get("stream_type", "").strip()
            if stream_type:
                self.app.state.stream_type = stream_type
                self.logger.info("[_handle_message] Stream type set to: %s", stream_type)
                await self.broadcast_states()

        elif action == "list_windows":
            try:
                from src.qubit.input.vision.capture import list_windows
                windows = list_windows()
            except Exception:
                windows = []
            await websocket.send(json.dumps({"type": "window_list", "data": windows}))

        elif action == "set_vision_window":
            window = data.get("window", "").strip()
            self.app.state.vision_window = window
            self.logger.info("[_handle_message] Vision window set to: %r", window)
            await self.broadcast_states()

        elif action == "play_audio":
            file_path = data.get("file_path")
            if file_path and self.app.audio_player:
                await self.app.audio_player.play_file(file_path)
                self.logger.info("[_handle_message] Playing audio: %s", file_path)
            else:
                self.logger.warning("[_handle_message] play_audio: no file_path or audio_player")

        elif action == "stop_audio":
            if self.app.audio_player:
                await self.app.audio_player.stop_playback()
                self.logger.info("[_handle_message] Stop audio requested")

        elif action == "list_audio_files":
            if self.app.audio_player:
                directory = self.app.audio_player.audio_directory
                files = []
                if directory.exists():
                    files = [
                        str(f.relative_to(directory))
                        for f in sorted(directory.glob("*.wav"))
                    ]
                await websocket.send(json.dumps({"type": "audio_files", "data": files}))

    def _features_as_dict(self) -> dict:
        return {
            **dataclasses.asdict(self.app.state.features),
            "stream_type": getattr(self.app.state, "stream_type", ""),
            "vision_window": getattr(self.app.state, "vision_window", ""),
            "current_obs_scene": getattr(self.app.state, "current_obs_scene", ""),
            "health": getattr(self.app.state, "health", {}),
        }

    async def send_states(self, websocket) -> None:
        await websocket.send(json.dumps({
            "type": "states",
            "data": self._features_as_dict(),
        }))

    async def broadcast_states(self) -> None:
        if self.connected_clients:
            message = json.dumps({
                "type": "states",
                "data": self._features_as_dict(),
            })
            await asyncio.gather(*(c.send(message) for c in self.connected_clients))

    async def forward_event(self, event_type: str, data: dict) -> None:
        if self.connected_clients:
            message = json.dumps({"type": event_type, "data": data})
            await asyncio.gather(*(c.send(message) for c in self.connected_clients))