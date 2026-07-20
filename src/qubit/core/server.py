import asyncio
import json
import websockets
from src.qubit.core.service import Service

class WebSocketServerService(Service):

    def __init__(self, host="0.0.0.0", port=8765):
        super().__init__("websocket_server")
        self.host = host
        self.port = port
        self.connected_clients = set()
        self.server = None
        self.app = None
        self.event_bus = None

    async def start(self, app) -> None:
        self.app = app
        self.event_bus = app.event_bus
        self.server = await websockets.serve(self.websocket_handler, self.host, self.port)
        self.logger.info("[start] WebSocketServer started on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        self.logger.info("[stop] Stopping WebSocketServer...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.logger.info("[stop] WebSocketServer stopped.")

    async def websocket_handler(self, websocket) -> None:
        self.connected_clients.add(websocket)
        try:
            await self.send_states(websocket)
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")
                if action == "toggle":
                    input_type = data.get("input")
                    state = data.get("state")
                    if input_type in self.app.state.features:
                        self.app.state.features[input_type] = (state == "on")
                        self.logger.info("[webSocketHandler] Toggled %s %s", input_type, state)
                        await self.broadcast_states()
                    else:
                        self.logger.warning("[webSocketHandler] Unknown input type: %s", input_type)
                elif action == "terminate":
                    self.logger.info("[webSocketHandler] terminate")
                    self.app.state.shutdown.set()
                elif action == 'start':
                    self.logger.info("[webSocketHandler] Start command from frontend")
                    if 'features' in data:
                        for k, v in data.get('features', {}).items():
                            if k in self.app.state.features:
                                self.app.state.features[k] = bool(v)
                                self.logger.info("[webSocketHandler] Set feature %s = %s from start config", k, v)
                    self.app.state.start.set()
                    await self.broadcast_states()

                elif action == 'play_audio':
                    file_path = data.get("file_path")
                    if file_path and hasattr(self.app, 'audio_player'):
                        await self.app.audio_player.play_file(file_path)
                        self.logger.info("[webSocketHandler] Playing audio: %s", file_path)
                    else:
                        self.logger.warning("[webSocketHandler] play_audio failed")

                elif action == 'stop_audio':
                    if hasattr(self.app, 'audio_player'):
                        await self.app.audio_player.stop_playback()
                        self.logger.info("[webSocketHandler] Stop audio requested")

                elif action == 'list_audio_files':
                    if hasattr(self.app, 'audio_player'):
                        directory = self.app.audio_player.audio_directory
                        files = []
                        if directory.exists():
                            for f in sorted(directory.glob("*.wav")):
                                files.append(str(f.relative_to(directory)))
                        await websocket.send(json.dumps({"type": "audio_files", "data": files}))
        except Exception as e:
            self.logger.error(e)
        finally:
            self.connected_clients.remove(websocket)

    async def send_states(self, websocket) -> None:
        states_message = json.dumps({"type": "states", "data": self.app.state.features})
        await websocket.send(states_message)

    async def broadcast_states(self) -> None:
        if self.connected_clients:
            message = json.dumps({"type": "states", "data": self.app.state.features})
            await asyncio.gather(*(client.send(message) for client in self.connected_clients))

    async def forward_event(self, event_type, data) -> None:
        if self.connected_clients:
            message = json.dumps({"type": event_type, "data": data})
            await asyncio.gather(*(client.send(message) for client in self.connected_clients))
